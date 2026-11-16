"""Non-invasive readiness checks for the Linux desktop container."""
from pathlib import Path
import os
import signal
import time


def has_loopback_listener(port, table_path='/proc/net/tcp'):
    """Require an IPv4 LISTEN socket on 127.0.0.1, without connecting to it.

    Both private relays bind to this explicit address. Linux exposes its IPv4
    socket table in network-namespace-local procfs, with little-endian addresses.
    An unavailable table fails readiness rather than reporting an unknown state
    as healthy. Child-process and real X-display checks run separately.
    """
    expected = f'0100007F:{port:04X}'
    try:
        with Path(table_path).open() as table:
            return any(len(fields) > 3 and fields[1] == expected
                       and fields[3] == '0A'
                       for fields in (line.split() for line in table))
    except OSError:
        return False


def signal_process_group(process, signum):
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        pass


def monitor_desktop(children, stopping, start_desktop):
    """Recover the XFCE session in place while the display and proxy stay up."""
    session_started = time.monotonic()
    quick_exits = 0
    while not stopping.wait(1):
        for name, process in tuple(children.items()):
            if name != 'desktop' and (exit_code := process.poll()) is not None:
                print(f'[railway] Required process {name} exited with status {exit_code}.', flush=True)
                return False

        process = children['desktop']
        exit_code = process.poll()
        if exit_code is None:
            continue
        if time.monotonic() - session_started >= 60:
            quick_exits = 0
        quick_exits += 1
        if quick_exits > 3:
            print(f'[railway] XFCE repeatedly exited during startup (status {exit_code}).', flush=True)
            return False
        print(f'[railway] XFCE session exited (status {exit_code}); restarting session.', flush=True)
        signal_process_group(process, signal.SIGTERM)
        if stopping.wait(quick_exits):
            break
        start_desktop()
        session_started = time.monotonic()
    return True
