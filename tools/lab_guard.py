"""Accidental-contact guard for the owned HA lab, never a production policy."""

import ipaddress
import sys

BLOCKED = []


def install():
    def audit(event, args):
        denied = False
        if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.exec"}:
            denied = True
        elif event == "socket.getaddrinfo":
            try:
                denied = not ipaddress.ip_address(args[0]).is_loopback
            except (TypeError, ValueError):
                denied = args[0] != "localhost"
        elif event in {"socket.connect", "socket.bind", "socket.sendto"}:
            sock, address = args[0], args[-1]
            if sock.family in (2, 10) and isinstance(address, tuple):
                try:
                    denied = not ipaddress.ip_address(address[0]).is_loopback
                except (TypeError, ValueError):
                    denied = True
        if denied:
            BLOCKED.append(event)
            raise PermissionError(
                "Suite lab permits only loopback and no child processes"
            )

    sys.addaudithook(audit)
