#!/usr/bin/env python3
"""Railway-compatible supervision for a private, persistent noVNC workstation."""
import http.server
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import subprocess
from tempfile import TemporaryDirectory, mkdtemp
import threading
import time

from runtime_checks import has_loopback_listener, monitor_desktop, signal_process_group
from startup_resources import wait_for_resources

password = os.environ.get('PASSWORD', '')
username = os.environ.get('CUSTOM_USER') or 'admin'
if len(password) < 16 or '\n' in password or '\r' in password:
    raise SystemExit('PASSWORD must contain at least 16 characters and no line breaks.')
if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', username):
    raise SystemExit('CUSTOM_USER must be a simple nonempty username.')
try:
    port = int(os.environ.get('PORT') or '3000')
except ValueError:
    raise SystemExit('PORT must be a number between 1024 and 65535.') from None
resolution = os.environ.get('VNC_RESOLUTION') or '1440x900'
if not 1024 <= port <= 65535 or not re.fullmatch(r'\d{3,4}x\d{3,4}', resolution):
    raise SystemExit('Invalid PORT or VNC_RESOLUTION')
width, height = map(int, resolution.split('x'))
if not (800 <= width <= 2560 and 600 <= height <= 1440):
    raise SystemExit('VNC_RESOLUTION must be between 800x600 and 2560x1440')

account = pwd.getpwnam('headless')
home = Path('/config')


def prepare_home():
    home.mkdir(exist_ok=True)
    # Seed missing paths atomically so a failed copy can be retried.
    for source in Path('/opt/desktop-seed').iterdir():
        target = home / source.name
        if target.exists() or target.is_symlink():
            continue
        with TemporaryDirectory(dir=home, prefix='.desktop-seed-') as staging:
            candidate = Path(staging) / source.name
            if source.is_dir():
                shutil.copytree(source, candidate, symlinks=True)
            else:
                shutil.copy2(source, candidate, follow_symlinks=False)
            if not target.exists() and not target.is_symlink():
                candidate.rename(target)
    for name in ['Downloads', 'Desktop', '.config', '.cache', '.local/share']:
        (home / name).mkdir(parents=True, exist_ok=True)
    subprocess.run(['chown', '-R', 'headless:headless', str(home)], check=True)


if not wait_for_resources(home, port, prepare_home):
    raise SystemExit(0)
session_runtime = Path(mkdtemp(prefix='desktop-xdg-', dir='/run'))
os.chown(session_runtime, account.pw_uid, account.pw_gid)
subprocess.run(['chpasswd'], input='headless:' + password + '\n', text=True, check=True)

hashed = subprocess.run(['openssl', 'passwd', '-6', '-stdin'], input=password,
    text=True, check=True, capture_output=True).stdout.strip()
credentials = Path('/run/desktop.htpasswd')
credentials.write_text(username + ':' + hashed + '\n')
credentials.chmod(0o640)
shutil.chown(credentials, group='www-data')
nginx = '''user www-data;
worker_processes 1;
pid /run/desktop-nginx.pid;
events { worker_connections 512; }
http {
  include /etc/nginx/mime.types;
  access_log off;
  error_log /dev/stderr warn;
  server_tokens off;
  map $http_upgrade $connection_upgrade { default upgrade; '' close; }
  server {
    listen 0.0.0.0:PORT;
    auth_basic "Private Railway desktop";
    auth_basic_user_file /run/desktop.htpasswd;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header Referrer-Policy no-referrer always;
    location = /healthz {
      auth_basic off;
      proxy_pass http://127.0.0.1:8099;
      proxy_connect_timeout 2s;
      proxy_read_timeout 8s;
    }
    location /files/ {
      alias /config/Downloads/;
      autoindex on;
      disable_symlinks on;
      add_header Cache-Control "no-store";
    }
    location / {
      proxy_pass http://127.0.0.1:6901;
      proxy_http_version 1.1;
      proxy_set_header Host $host;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection $connection_upgrade;
      proxy_buffering off;
      proxy_read_timeout 3600s;
      add_header Cache-Control "no-store";
    }
  }
}
'''.replace('0.0.0.0:PORT', '0.0.0.0:' + str(port))
Path('/run/desktop-nginx.conf').write_text(nginx)
novnc_home = Path(os.environ.get('NOVNC_HOME', '/usr/libexec/noVNCdim'))
(novnc_home / 'index.html').write_text(
    '<!doctype html><html><head><meta charset="utf-8">'
    '<meta http-equiv="refresh" content="0;url=/vnc.html?autoconnect=true&amp;resize=remote&amp;reconnect=true">'
    '<title>Private Railway desktop</title></head><body>Connecting to your private desktop…</body></html>')

environment = os.environ.copy()
environment.update(HOME='/config', USER='headless', LOGNAME='headless', DISPLAY=':1',
                   XDG_RUNTIME_DIR=str(session_runtime))
# Do not pass the web login password or unrelated Railway secrets to desktop apps.
for name in list(environment):
    if name in {'PASSWORD', 'VNC_PW'} or 'TOKEN' in name or 'API_KEY' in name:
        environment.pop(name)
children = {}
stopping = threading.Event()

def launch(name, command, user=True):
    children[name] = subprocess.Popen(command, env=environment, cwd=home,
        user=account.pw_uid if user else None, group=account.pw_gid if user else None,
        extra_groups=[] if user else None, start_new_session=True)

def listening(port):
    # Inspect the listening socket without creating a VNC client on every poll.
    return has_loopback_listener(port)

def display_ready():
    try:
        return subprocess.run(['xdpyinfo', '-display', ':1'], env=environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3,
            user=account.pw_uid, group=account.pw_gid, extra_groups=[]).returncode == 0
    except subprocess.TimeoutExpired:
        return False

def process_exists(name):
    return subprocess.run(['pgrep', '-u', str(account.pw_uid), '-x', name],
        stdout=subprocess.DEVNULL).returncode == 0

class Health(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            healthy = (not stopping.is_set() and bool(children)
                and all(p.poll() is None for p in tuple(children.values()))
                and listening(5901) and listening(6901) and display_ready()
                and process_exists('xfce4-session'))
        except (OSError, subprocess.TimeoutExpired):
            healthy = False
        self.send_response(200 if healthy else 503)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b'ready\n' if healthy else b'starting\n')
    def log_message(self, *args):
        pass

server = http.server.ThreadingHTTPServer(('127.0.0.1', 8099), Health)
threading.Thread(target=server.serve_forever, daemon=True).start()
for folder in ['/tmp/.X11-unix', '/tmp/.ICE-unix']:
    Path(folder).mkdir(exist_ok=True)
    os.chown(folder, 0, 0)
    os.chmod(folder, 0o1777)
for stale in [Path('/tmp/.X1-lock'), Path('/tmp/.X11-unix/X1')]:
    stale.unlink(missing_ok=True)
launch('display', [shutil.which('Xvnc') or 'Xtigervnc', ':1', '-geometry', resolution, '-depth', '24', '-rfbport', '5901',
    '-localhost', '-ac', '-SecurityTypes', 'None', '-AlwaysShared', '-nolisten', 'tcp',
    '-rendernode', ''])
deadline = time.monotonic() + 45
while not display_ready():
    if children['display'].poll() is not None or time.monotonic() > deadline:
        raise SystemExit('The graphical display did not start')
    time.sleep(0.5)


def start_desktop():
    launch('desktop', ['dbus-run-session', '--', 'startxfce4'])


start_desktop()
launch('websocket', [shutil.which('websockify') or str(novnc_home / 'utils/websockify/run'),
    '--web', str(novnc_home), '127.0.0.1:6901', '127.0.0.1:5901'])
launch('proxy', ['nginx', '-c', '/run/desktop-nginx.conf', '-g', 'daemon off;'], user=False)
if os.environ.get('DESKTOP_APP') == 'chromium':
    browser = shutil.which('chromium') or shutil.which('chromium-browser')
    if not browser:
        raise SystemExit('The pinned image does not contain Chromium')
    # Single-replica volume: Chromium's old container hostname no longer exists.
    # Remove only its three transient singleton links, never profile databases.
    profile = home / '.config/chromium'
    profile.mkdir(exist_ok=True)
    for name in ['SingletonLock', 'SingletonSocket', 'SingletonCookie']:
        (profile / name).unlink(missing_ok=True)
    os.chown(profile, account.pw_uid, account.pw_gid)
    browser_args = [browser, '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu',
        '--no-first-run', '--no-default-browser-check', '--password-store=basic',
        '--user-data-dir=/config/.config/chromium', '--start-maximized']
    # Optional on-demand test workstations: suppress Chromium's own housekeeping
    # traffic so it does not keep an otherwise idle Railway service awake.
    # Page requests and normal interactive browsing remain enabled.
    if os.environ.get('SERVERLESS_FRIENDLY', '').lower() in {'1', 'true', 'yes'}:
        browser_args += ['--disable-background-networking', '--disable-component-update',
            '--disable-sync', '--disable-domain-reliability', '--no-pings',
            '--disable-background-mode', '--disable-notifications',
            '--disable-features=MediaRouter,OptimizationGuideModelDownloading,'
            'OptimizationHintsFetching,OptimizationTargetPrediction,OptimizationHints',
            # GCM ignores the background-networking switch. Its supported
            # endpoint overrides affect push messaging, never page requests.
            '--gcm-checkin-url=https://127.0.0.1:9',
            '--gcm-registration-url=https://127.0.0.1:9',
            '--gcm-mcs-endpoint=https://127.0.0.1:9']
    launch('browser', browser_args + ['https://example.com'])

def stop(*args):
    stopping.set()
for sig in [signal.SIGTERM, signal.SIGINT]:
    signal.signal(sig, stop)
print('[railway] Private desktop started; only the authenticated HTTP proxy is public.', flush=True)
try:
    clean_exit = monitor_desktop(children, stopping, start_desktop)
finally:
    stopping.set()
    for process in reversed(list(children.values())):
        signal_process_group(process, signal.SIGTERM)
    for process in children.values():
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            signal_process_group(process, signal.SIGKILL)
            process.wait()
    server.shutdown()
    shutil.rmtree(session_runtime, ignore_errors=True)
raise SystemExit(0 if clean_exit else 1)
