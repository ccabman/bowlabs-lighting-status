"""Pure production projection tests: deny every socket and child process."""

import sys
import unittest
from pathlib import Path

violations = []


def audit(event, args):
    if event.startswith("socket.") or event in {
        "subprocess.Popen",
        "os.system",
        "os.posix_spawn",
        "os.exec",
    }:
        violations.append(event)
        raise PermissionError("Pure lighting tests cannot contact services")


if __name__ == "__main__":
    sys.addaudithook(audit)
    suite = unittest.defaultTestLoader.discover(
        str(Path(__file__).resolve().parents[1] / "tests")
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() and not violations else 1)
