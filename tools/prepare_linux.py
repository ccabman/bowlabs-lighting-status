"""Preinstall pinned HA test dependencies before the isolated runtime guard."""

import json
import subprocess
import sys
from pathlib import Path

import homeassistant
from homeassistant.auth.mfa_modules import totp
from homeassistant.bootstrap import CORE_INTEGRATIONS, DEFAULT_INTEGRATIONS

if sys.platform != "linux":
    raise SystemExit("Use only in the disposable Linux CI environment")
root = Path(homeassistant.__file__).parent / "components"
pending = (
    set(CORE_INTEGRATIONS)
    | set(DEFAULT_INTEGRATIONS)
    | {
        "frontend",
        "http",
        "api",
        "websocket_api",
        "sensor",
    }
)
seen, requirements = set(), set(totp.REQUIREMENTS)
while pending:
    domain = pending.pop()
    if domain in seen:
        continue
    seen.add(domain)
    manifest = root / domain / "manifest.json"
    if not manifest.is_file():
        continue
    data = json.loads(manifest.read_text())
    requirements.update(data.get("requirements", []))
    pending.update(set(data.get("dependencies", [])) - seen)
print(
    "Preinstalling pinned test-only HA requirements:", sorted(requirements), flush=True
)
subprocess.run(
    [sys.executable, "-m", "pip", "install", *sorted(requirements)], check=True
)
