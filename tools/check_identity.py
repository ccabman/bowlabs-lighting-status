"""Verify registry-identity changes fail closed, using the synthetic source only."""

import asyncio
import json
from pathlib import Path

import aiohttp

LAB = Path(__file__).resolve().parents[2] / "work/lighting-install.nosync"
URL = "http://127.0.0.1:18168"
DOMAIN = "bowlabs_lighting_status"


async def main():
    assert (LAB / "ready").read_text().strip() == URL + "/config/integrations"
    selection = json.loads((LAB / "selection.json").read_text())
    zone = selection["zones"][0]
    assert zone == "sensor.bowlabs_fixture_zone"
    token = (LAB / "admin-token").read_text()
    checks = []
    async with aiohttp.ClientSession(
        headers={"Authorization": "Bearer " + token}, trust_env=False
    ) as client:

        async def api(path, data=None, method="POST"):
            async with client.request(method, URL + path, json=data) as response:
                assert response.status == 200
                return await response.json()

        async def ws(kind, **fields):
            async with client.ws_connect(URL + "/api/websocket") as socket:
                await socket.receive_json()
                await socket.send_json({"type": "auth", "access_token": token})
                await socket.receive_json()
                await socket.send_json({"id": 1, "type": kind, **fields})
                result = await socket.receive_json()
                assert result["success"]
                return result["result"]

        async def summary():
            rows = await api("/api/states", method="GET")
            return next(row for row in rows if "physical_verified" in row["attributes"])

        entries = await ws("config_entries/get")
        entry = next(e["entry_id"] for e in entries if e["domain"] == DOMAIN)
        base = "/api/config/config_entries/options/flow"
        flow = await api(base, {"handler": entry})
        flow = await api(base + "/" + flow["flow_id"], {"action": "review"})
        flow = await api(base + "/" + flow["flow_id"], selection)
        await api(base + "/" + flow["flow_id"], {"approve": True})
        await asyncio.sleep(0.2)
        assert (await summary())["state"] == "active"
        checks.append("explicit_reapproval_before_identity_test")
        moved = "sensor.bowlabs_fixture_moved"
        renamed = False
        try:
            await ws(
                "config/entity_registry/update", entity_id=zone, new_entity_id=moved
            )
            renamed = True
            await asyncio.sleep(0.2)
            row = await summary()
            assert row["state"] == "invalid"
            checks.append("rename_invalidates_selected_identity")
            assert row["attributes"]["authorization"] == "selection_changed"
            checks.append("approval_not_transferred_to_new_selector")
            assert row["attributes"]["details"] == {}
            checks.append("identity_change_clears_current_details")
        finally:
            if renamed:
                await ws(
                    "config/entity_registry/update", entity_id=moved, new_entity_id=zone
                )
            flow = await api(base, {"handler": entry})
            flow = await api(base + "/" + flow["flow_id"], {"action": "revoke"})
            await api(base + "/" + flow["flow_id"], {"confirm": True})
        await asyncio.sleep(0.2)
        assert (await summary())["state"] == "revoked"
        checks.append("final_permission_revoked")
        raw = await api("/api/states/" + zone, method="GET")
        assert raw["state"] == "Adapting"
        checks.append("synthetic_source_restored_and_unchanged")
    (LAB / "identity-checks.json").write_text(json.dumps(checks, indent=2))
    print(
        f"Passed {len(checks)} native identity-binding checks; "
        "source restored and status revoked."
    )


if __name__ == "__main__":
    asyncio.run(main())
