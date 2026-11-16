"""Serve an actionable page when a Linux desktop cannot start on its resources."""

import errno
from html import escape
import http.server
import os
from pathlib import Path
import signal
import socket
import subprocess
import threading
import time

MIB = 1024 ** 2
MIN_MEMORY = 500_000_000
MIN_FREE = 32 * MIB
CHECK_INTERVAL = 15
RESOURCE_WAIT_SECONDS = 10 * 60
STORAGE_ERRORS = {
    errno.ENOSPC: 'The /config volume is full. Free some space or expand the volume in Railway.',
    errno.EDQUOT: 'The /config volume has reached its storage quota. Free some space or expand the volume.',
    errno.EROFS: 'The /config volume is read-only. Attach a writable volume in Railway.',
    errno.EACCES: 'The /config volume is not writable. Check its mount and permissions in Railway.',
}


def memory_limit(root=Path('/sys/fs/cgroup')):
    for name in ('memory.max', 'memory/memory.limit_in_bytes'):
        try:
            value = int((root / name).read_text().strip())
        except (OSError, ValueError):
            continue
        if 0 < value < (1 << 60):
            return value
    return None


def resource_problems(home, environment):
    problems = []
    limit = memory_limit()
    page_size = os.sysconf('SC_PAGE_SIZE')
    effective_minimum = MIN_MEMORY // page_size * page_size
    if limit is not None and limit < effective_minimum:
        problems.append(f'The service is limited to {limit / 1_000_000:.1f} MB of RAM. '
                        'Raise the service memory limit to at least 500 MB in Railway.')
    if environment.get('RAILWAY_ENVIRONMENT_ID'):
        mounts = Path('/proc/self/mountinfo').read_text().splitlines()
        if not any(line.split()[4] == str(home) for line in mounts):
            return problems + ['Attach a persistent Railway volume at /config.']
    # A local Docker run can let the launcher create /config on first start.
    existing = home if home.exists() else home.parent
    try:
        stats = os.statvfs(existing)
        if stats.f_flag & os.ST_RDONLY or not os.access(existing, os.W_OK):
            problems.append(STORAGE_ERRORS[errno.EROFS])
        elif stats.f_bavail * stats.f_frsize < MIN_FREE or (stats.f_files > 0 and stats.f_favail == 0):
            problems.append(f'The /config filesystem has {stats.f_bavail * stats.f_frsize // MIB} MiB free. '
                            'Free or allocate at least 32 MiB and ensure there are free file entries.')
    except OSError as error:
        if error.errno not in STORAGE_ERRORS:
            raise
        problems.append(STORAGE_ERRORS[error.errno])
    return problems


class StartupHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/healthz':
            body, kind = b'waiting-for-resources\n', 'text/plain'
            status = 503
        elif self.path == '/':
            problems = ''.join(f'<li>{escape(problem)}</li>' for problem in self.server.problems)
            body = ('<!doctype html><html lang="en"><meta charset="utf-8">'
                    f'<meta http-equiv="refresh" content="{CHECK_INTERVAL}">'
                    '<meta name="viewport" content="width=device-width, initial-scale=1">'
                    '<style>body{font:1rem system-ui;max-width:42rem;margin:8vh auto;padding:0 1rem;'
                    'line-height:1.6}</style><title>Desktop waiting for resources</title>'
                    '<h1>Desktop waiting for resources</h1>'
                    f'<ul>{problems}</ul><p>The desktop starts once the resources are available. '
                    'If the issue persists for 10 minutes, the service stops. Adjust the resources '
                    'and restart the deployment in Railway.</p>'
                    '</html>').encode()
            kind = 'text/html; charset=utf-8'
            status = 200
        else:
            self.send_error(404)
            return
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class StartupServer(http.server.ThreadingHTTPServer):
    def __init__(self, port):
        dual = socket.has_dualstack_ipv6()
        self.address_family = socket.AF_INET6 if dual else socket.AF_INET
        super().__init__(('::' if dual else '0.0.0.0', port), StartupHandler)

    def server_bind(self):
        if self.address_family == socket.AF_INET6:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def wait_for_resources(home, port, prepare_home):
    def attempt():
        problems = resource_problems(home, os.environ)
        if problems:
            return problems
        try:
            prepare_home()
        except (OSError, subprocess.CalledProcessError) as error:
            message = STORAGE_ERRORS.get(getattr(error, 'errno', None))
            if message:
                return [message]
            problems = resource_problems(home, os.environ)
            if problems:
                return problems
            raise
        return []

    problems = attempt()
    if not problems:
        return True
    deadline = time.monotonic() + RESOURCE_WAIT_SECONDS
    stop = threading.Event()
    handlers = {sig: signal.signal(sig, lambda *_: stop.set())
                for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        with StartupServer(port) as server:
            server.problems = problems
            print('[railway] Desktop waiting for resources: ' + ' '.join(problems), flush=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                while not stop.wait(max(0, min(CHECK_INTERVAL, deadline - time.monotonic()))):
                    problems = attempt()
                    if not problems:
                        print('[railway] Startup resources available. Starting the desktop.', flush=True)
                        return True
                    if time.monotonic() >= deadline:
                        print('[railway] Resources still insufficient after 10 minutes. Stopping the service.', flush=True)
                        return False
                    server.problems = problems
                return False
            finally:
                server.shutdown()
                thread.join()
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
