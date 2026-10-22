"""Disposable Linux HA install/restart/uninstall, using only synthetic sources."""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]


def main():
    assert sys.platform == "linux", "This runner requires Linux"
    with tempfile.TemporaryDirectory(prefix="bowlabs-lighting-ci-") as directory:
        root = Path(directory)
        staged = root / "LightingStatus"
        shutil.copytree(
            REPO,
            staged,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".ruff_cache"),
        )
        lab = root / "work/lighting-install.nosync"
        process = None
        log = root / "ha.log"

        def stop():
            if process and process.poll() is None:
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=30)

        def start(*args):
            nonlocal process
            ready = lab / "ready"
            ready.unlink(missing_ok=True)
            with log.open("a") as output:
                process = subprocess.Popen(
                    [sys.executable, str(staged / "tools/run_lab.py"), *args],
                    stdout=output,
                    stderr=output,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )
            for _ in range(180):
                if ready.is_file():
                    return
                if process.poll() is not None:
                    raise AssertionError(log.read_text()[-8000:])
                time.sleep(0.5)
            raise AssertionError("Lab startup timed out: " + log.read_text()[-8000:])

        try:
            start()
            subprocess.run(
                [sys.executable, str(staged / "tools/check_install.py")], check=True
            )
            subprocess.run(
                [sys.executable, str(staged / "tools/check_identity.py")], check=True
            )
            stop()
            start()
            subprocess.run(
                [
                    sys.executable,
                    str(staged / "tools/check_install.py"),
                    "after-restart",
                ],
                check=True,
            )
            stop()
            # Remove only the candidate code after native entry removal, then boot.
            shutil.rmtree(lab / "config/custom_components/bowlabs_lighting_status")
            start("--without-candidate")
            request = Request(
                "http://127.0.0.1:18168/api/states",
                headers={
                    "Authorization": "Bearer " + (lab / "admin-token").read_text()
                },
            )
            with urlopen(request, timeout=10) as response:
                states = json.load(response)
            assert not any("physical_verified" in row["attributes"] for row in states)
            assert any(
                row["entity_id"] == "sensor.bowlabs_fixture_zone"
                and row["state"] == "Adapting"
                for row in states
            )
            assert not (
                lab / "config/custom_components/bowlabs_lighting_status"
            ).exists()
            print(
                "PASS Linux: 16 install/revoke + 6 identity + 7 restart/remove checks; "
                "code removal and clean boot; synthetic source unchanged."
            )
        finally:
            stop()


if __name__ == "__main__":
    main()
