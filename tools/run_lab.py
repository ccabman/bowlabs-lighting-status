"""Real HA, owned loopback-only suite dashboard. Synthetic observations only."""

import asyncio
import json
import logging
import os
import shutil
import signal
import socket
import sys
from pathlib import Path

import aiohttp
from homeassistant import bootstrap, loader
from homeassistant.auth.providers.homeassistant import InvalidUsername
from homeassistant.components.http.config import (
    HTTP_STORAGE_SCHEMA,
    async_get_and_load_store,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

sys.path.insert(0, str(Path(__file__).resolve().parent))
from homeassistant import config_entries
from homeassistant.helpers import entity_registry as er
from lab_guard import BLOCKED, install

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "work/lighting-install.nosync"
PORT = 18168
URL = f"http://127.0.0.1:{PORT}"


async def main():
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", PORT))
    if LAB.is_symlink() or (LAB / "config").is_symlink():
        raise RuntimeError("Refused symlink lab")
    LAB.mkdir(mode=0o700, parents=True, exist_ok=True)
    LAB.chmod(0o700)
    config_dir = LAB / "config"
    config_dir.mkdir(mode=0o700, exist_ok=True)
    (LAB / "ready").unlink(missing_ok=True)
    os.environ["UV_CACHE_DIR"] = str(LAB / "cache")
    for domain, source in [
        (
            "bowlabs_lighting_status",
            ROOT / "LightingStatus/custom_components/bowlabs_lighting_status",
        ),
        ("bow_lighting", ROOT / "LightingStatus/tests/fixtures/bow_lighting"),
    ]:
        if domain == "bowlabs_lighting_status" and "--without-candidate" in sys.argv:
            continue
        shutil.copytree(
            source,
            config_dir / "custom_components" / domain,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (config_dir / "custom_components/__init__.py").touch()
    hass = HomeAssistant(str(config_dir))
    loader.async_setup(hass)
    stopped = asyncio.Event()
    try:
        from homeassistant.components import http

        make = http.make_server

        def confined(instance, conf, supervisor_unix_socket_path=None):
            if (
                conf.get("server_host") != ["127.0.0.1"]
                or conf.get("server_port") != PORT
            ):
                raise RuntimeError("Unexpected lab listener rejected before binding")
            return make(instance, conf, supervisor_unix_socket_path)

        http.make_server = confined
        store = await async_get_and_load_store(hass)
        await store.async_set_pending(
            HTTP_STORAGE_SCHEMA({"server_host": ["127.0.0.1"], "server_port": PORT})
        )
        if store.pending is not None:
            await store.async_promote_pending()
        await store.async_mark_yaml_migration_done()
        config = {
            "homeassistant": {
                "name": "BowLabs synthetic suite preview",
                "latitude": 0,
                "longitude": 0,
                "elevation": 0,
                "time_zone": "America/Chicago",
                "unit_system": "metric",
            },
            "http": {},
            "api": {},
            "websocket_api": {},
        }
        assert await bootstrap.async_from_config_dict(config, hass)
        users = await hass.auth.async_get_users()
        owner = next((x for x in users if x.is_owner), None)
        if owner is None:
            owner = await hass.auth.async_create_user(
                "Suite lab administrator", group_ids=["system-admin"], local_only=True
            )
        viewer = next((x for x in users if x.name == "Suite preview viewer"), None)
        if viewer is None:
            viewer = await hass.auth.async_create_user(
                "Suite preview viewer", group_ids=["system-read-only"], local_only=True
            )
        provider = hass.auth.get_auth_provider("homeassistant", None)
        try:
            await provider.async_add_auth("suite-viewer", "bowlabs-synthetic-viewer")
        except InvalidUsername:
            await provider.async_validate_login(
                "suite-viewer", "bowlabs-synthetic-viewer"
            )
        credentials = await provider.async_get_or_create_credentials(
            {"username": "suite-viewer"}
        )
        if not any(c.id == credentials.id for c in viewer.credentials):
            await hass.auth.async_link_user(viewer, credentials)
        try:
            await provider.async_add_auth("lighting-admin", "bowlabs-synthetic-admin")
        except InvalidUsername:
            await provider.async_validate_login(
                "lighting-admin", "bowlabs-synthetic-admin"
            )
        admin_credentials = await provider.async_get_or_create_credentials(
            {"username": "lighting-admin"}
        )
        if not any(c.id == admin_credentials.id for c in owner.credentials):
            await hass.auth.async_link_user(owner, admin_credentials)
        assert await async_setup_component(hass, "frontend", {**config, "frontend": {}})
        if onboarding := hass.data.get("onboarding"):
            onboarding.onboarded = True
        await hass.async_start()
        assert all(s.getsockname()[0] == "127.0.0.1" for s in hass.http._server.sockets)
        for kind in ("zone", "global"):
            if not any(
                e.data.get("kind") == kind
                for e in hass.config_entries.async_entries("bow_lighting")
            ):
                source = config_entries.ConfigEntry(
                    version=1,
                    minor_version=1,
                    domain="bow_lighting",
                    title="Synthetic " + kind,
                    data={"kind": kind},
                    options={},
                    source="user",
                    unique_id=kind,
                    discovery_keys={},
                    subentries_data=[],
                )
                await hass.config_entries.async_add(source)
        registry = er.async_get(hass)
        selection = {"zones": [], "alerts": None}
        for record in registry.entities.values():
            if record.platform == "bow_lighting":
                if record.unique_id.endswith("_alerts_active"):
                    selection["alerts"] = record.entity_id
                elif record.unique_id.endswith("_status"):
                    selection["zones"].append(record.entity_id)
        (LAB / "selection.json").write_text(json.dumps(selection))
        lab_dashboard = {
            "title": "Lighting install lab",
            "views": [
                {
                    "title": "Status",
                    "path": "status",
                    "cards": [
                        {
                            "type": "markdown",
                            "content": "# BowLabs Lighting Status\n"
                            "**SYNTHETIC SOURCES · DISPOSABLE HOME ASSISTANT**\n\n"
                            "Use Settings → Devices & services → Add integration → "
                            "BowLabs Lighting Status. "
                            "Household systems remain untouched. "
                            "This lab uses a fake registry/state producer, "
                            "never the real lighting controller.",
                        }
                    ],
                }
            ],
        }
        tokens = {}
        for kind, user in [("owner", owner), ("viewer", viewer)]:
            refresh = await hass.auth.async_create_refresh_token(user, client_id=URL)
            tokens[kind] = hass.auth.async_create_access_token(refresh)
        async with aiohttp.ClientSession(trust_env=False) as session:

            async def ws_command(token, number, kind, **fields):
                async with session.ws_connect(URL + "/api/websocket") as ws:
                    await ws.receive_json()
                    await ws.send_json({"type": "auth", "access_token": token})
                    assert (await ws.receive_json())["type"] == "auth_ok"
                    await ws.send_json({"id": number, "type": kind, **fields})
                    return await ws.receive_json()

            listed = await ws_command(tokens["owner"], 1, "lovelace/dashboards/list")
            assert listed.get("success")
            if not any(x["url_path"] == "bowlabs-suite" for x in listed["result"]):
                created = await ws_command(
                    tokens["owner"],
                    2,
                    "lovelace/dashboards/create",
                    url_path="bowlabs-suite",
                    title="BowLabs preview",
                    icon="mdi:flask-outline",
                    show_in_sidebar=True,
                    require_admin=False,
                )
                assert created.get("success"), created
            saved = await ws_command(
                tokens["owner"],
                3,
                "lovelace/config/save",
                url_path="bowlabs-suite",
                config=lab_dashboard,
            )
            assert saved.get("success"), saved
            readback = await ws_command(
                tokens["viewer"], 4, "lovelace/config", url_path="bowlabs-suite"
            )
            assert readback.get("success") and readback["result"] == lab_dashboard
            denied = await ws_command(
                tokens["viewer"],
                5,
                "lovelace/config/save",
                url_path="bowlabs-suite",
                config=lab_dashboard,
            )
            assert (
                not denied.get("success") and denied["error"]["code"] == "unauthorized"
            )
            # Keep a private test-only token for read-only runtime verification.
            token_file = LAB / "viewer-token"
            token_file.touch(mode=0o600, exist_ok=True)
            token_file.chmod(0o600)
            token_file.write_text(tokens["viewer"])
            admin_file = LAB / "admin-token"
            admin_file.touch(mode=0o600, exist_ok=True)
            admin_file.chmod(0o600)
            admin_file.write_text(tokens["owner"])
        (LAB / "runtime-checks.json").write_text(
            json.dumps(
                {
                    "real_home_assistant": True,
                    "loopback_only": True,
                    "dashboard_readback": True,
                    "viewer_can_read": True,
                    "viewer_cannot_save": True,
                    "synthetic_entities_only": True,
                },
                indent=2,
            )
        )
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_running_loop().add_signal_handler(sig, stopped.set)
        (LAB / "ready").write_text(URL + "/config/integrations\n")
        while not stopped.is_set():
            (LAB / "guard-status.json").write_text(
                json.dumps({"blocked_attempts": len(BLOCKED)})
            )
            try:
                await asyncio.wait_for(stopped.wait(), 1)
            except TimeoutError:
                pass
    finally:
        (LAB / "ready").unlink(missing_ok=True)
        (LAB / "viewer-token").unlink(missing_ok=True)
        (LAB / "admin-token").unlink(missing_ok=True)
        await hass.async_stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    install()
    asyncio.run(main())
