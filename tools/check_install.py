"""Real config/options flow, lifecycle and removal tests in the fixed fake HA lab."""

import asyncio
import json
import sys
from pathlib import Path

import aiohttp

LAB = Path(__file__).resolve().parents[2] / "work/lighting-install.nosync"
URL = "http://127.0.0.1:18168"
DOMAIN = "bowlabs_lighting_status"


async def main():
    assert not LAB.is_symlink()
    assert (LAB / "ready").read_text().strip() == URL + "/config/integrations"
    admin, viewer = [
        (LAB / (kind + "-token")).read_text() for kind in ("admin", "viewer")
    ]
    checks = []
    async with aiohttp.ClientSession(trust_env=False) as client:

        async def api(path, data=None, method="POST", token=admin, status=200):
            async with client.request(
                method,
                URL + path,
                json=data,
                headers={"Authorization": "Bearer " + token},
            ) as response:
                text = await response.text()
                assert response.status == status, (path, response.status, text[:180])
                return (
                    json.loads(text)
                    if text and response.content_type == "application/json"
                    else None
                )

        async def start():
            return await api("/api/config/config_entries/flow", {"handler": DOMAIN})

        async def submit(flow, data, options=False):
            prefix = (
                "/api/config/config_entries/"
                + ("options/" if options else "")
                + "flow/"
            )
            return await api(prefix + flow["flow_id"], data)

        async def options(entry, action):
            flow = await api(
                "/api/config/config_entries/options/flow", {"handler": entry}
            )
            return await submit(flow, {"action": action}, True)

        def check(name, condition):
            assert condition, name
            checks.append(name)

        async def summary():
            for _ in range(60):
                states = await api("/api/states", method="GET")
                rows = [
                    s
                    for s in states
                    if s["attributes"].get("evidence") == "application_reported"
                    and "physical_verified" in s["attributes"]
                ]
                if rows:
                    return rows[0]
                await asyncio.sleep(0.1)
            raise AssertionError("No summary sensor")

        if len(sys.argv) > 1 and sys.argv[1] == "after-restart":
            row = await summary()
            check(
                "revocation_survives_process_restart",
                row["state"] == "revoked" and row["attributes"]["details"] == {},
            )
            checkpoint = json.loads((LAB / "checkpoint.json").read_text())
            entry = checkpoint["entry_id"]
            # Reapprove only through another explicit selection and approval.
            flow = await options(entry, "review")
            flow = await submit(
                flow, json.loads((LAB / "selection.json").read_text()), True
            )
            check("reapproval_requires_confirmation", flow["step_id"] == "approve")
            result = await submit(flow, {"approve": True}, True)
            check("explicit_reapproval", result["type"] == "create_entry")
            await asyncio.sleep(0.2)
            row = await summary()
            check("reapproved_status_available", row["state"] == "active")
            result = await api(
                "/api/config/config_entries/entry/" + entry, method="DELETE"
            )
            check("remove_requires_no_restart", result.get("require_restart") is False)
            await asyncio.sleep(0.2)
            await api("/api/states/" + row["entity_id"], method="GET", status=404)
            check("removal_clears_sensor", True)
            raw = await api(
                "/api/states/"
                + json.loads((LAB / "selection.json").read_text())["zones"][0],
                method="GET",
            )
            check("source_untouched_after_removal", raw["state"] == "Adapting")
            (LAB / "restart-removal-checks.json").write_text(
                json.dumps(checks, indent=2)
            )
            print(f"Passed {len(checks)} restart/reapproval/removal checks.")
            return
        selection = json.loads((LAB / "selection.json").read_text())
        assert len(selection["zones"]) == 1 and selection["alerts"]
        before = await api("/api/states/" + selection["zones"][0], method="GET")
        await api(
            "/api/config/config_entries/flow",
            {"handler": DOMAIN},
            token=viewer,
            status=401,
        )
        check("viewer_cannot_configure", True)
        for value in [
            {"zones": ["sensor.foreign"], "alerts": selection["alerts"]},
            {"zones": [selection["alerts"]], "alerts": selection["zones"][0]},
            {"zones": selection["zones"] * 2, "alerts": selection["alerts"]},
        ]:
            flow = await start()
            result = await submit(flow, value)
            check(
                "invalid_selection_" + str(len(checks)),
                result["type"] == "form"
                and result["errors"].get("base") == "invalid_selection",
            )
            await api(
                "/api/config/config_entries/flow/" + flow["flow_id"], method="DELETE"
            )
        flow = await start()
        flow = await submit(flow, selection)
        check("native_approval_step", flow["step_id"] == "approve")
        result = await submit(flow, {"approve": False})
        check("unapproved_aborts", result["type"] == "abort")
        flow = await start()
        flow = await submit(flow, selection)
        result = await submit(flow, {"approve": True})
        check("installation_created", result["type"] == "create_entry")
        entry = result["result"]["entry_id"]
        row = await summary()
        check(
            "approved_summary",
            row["state"] == "active"
            and row["attributes"]["authorization"] == "approved",
        )
        check("private_fields_filtered", "PRIVATE_CANARY" not in json.dumps(row))
        check(
            "physical_success_not_claimed",
            row["attributes"]["physical_verified"] is False,
        )
        result = await start()
        check("duplicate_install_refused", result["type"] == "abort")
        held = {**before["attributes"], "holds": {"PRIVATE_CANARY": {}}}
        await api(
            "/api/states/" + selection["zones"][0],
            {"state": "Manual hold", "attributes": held},
        )
        await asyncio.sleep(0.2)
        row = await summary()
        check(
            "held_state_normal",
            row["state"] == "idle" and row["attributes"]["details"]["held_count"] == 1,
        )
        await api(
            "/api/states/" + selection["zones"][0],
            {"state": "Adapting", "attributes": before["attributes"]},
        )
        flow = await options(entry, "revoke")
        check("revocation_confirmation", flow["step_id"] == "revoke")
        result = await submit(flow, {"confirm": True}, True)
        check("revocation_saved", result["type"] == "create_entry")
        await asyncio.sleep(0.2)
        row = await summary()
        check(
            "revocation_clears_details",
            row["state"] == "revoked" and row["attributes"]["details"] == {},
        )
        after = await api("/api/states/" + selection["zones"][0], method="GET")
        check(
            "source_unchanged",
            after["state"] == before["state"]
            and after["attributes"] == before["attributes"],
        )
        (LAB / "checkpoint.json").write_text(json.dumps({"entry_id": entry}))
        (LAB / "install-checks.json").write_text(json.dumps(checks, indent=2))
        print(
            f"Passed {len(checks)} native installation/revocation checks. "
            "Ready for process restart."
        )


if __name__ == "__main__":
    asyncio.run(main())
