from __future__ import annotations

import socket


def local_ipv4_addresses() -> list[str]:
    """Return non-loopback IPv4 addresses for this machine (best-effort)."""
    seen: set[str] = set()
    result: list[str] = []

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                seen.add(ip)
                result.append(ip)
    except OSError:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127.") or ip in seen:
                continue
            seen.add(ip)
            result.append(ip)
    except OSError:
        pass

    return result
