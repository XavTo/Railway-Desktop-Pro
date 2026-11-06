"""Non-invasive readiness checks for the Linux desktop container."""
from pathlib import Path


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
