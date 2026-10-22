"""Production projection privacy/boundary tests without HA or application imports."""

import importlib.util
import unittest
from pathlib import Path

path = (
    Path(__file__).resolve().parents[1]
    / "custom_components/bowlabs_lighting_status/projection.py"
)
spec = importlib.util.spec_from_file_location("lighting_projection", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProjectionTests(unittest.TestCase):
    def payload(self, state="Adapting", holds=None):
        return {
            "zones": [
                {
                    "state": state,
                    "attributes": {
                        "holds": {} if holds is None else holds,
                        "brightness_override": False,
                        "error": None,
                        "resolved_lights": ["PRIVATE_CANARY"],
                    },
                }
            ],
            "alerts": {"state": "0"},
        }

    def test_only_safe_counts_leave_projection(self):
        result = module.lighting(
            self.payload("Manual hold", {"PRIVATE_CANARY": {"private": "SECRET"}})
        )
        self.assertEqual(result[1], "idle")
        self.assertEqual(result[-1]["held_count"], 1)
        self.assertNotIn("PRIVATE_CANARY", repr(result))
        self.assertNotIn("SECRET", repr(result))

    def test_bad_types_do_not_become_ready(self):
        for state in [True, "Surprise", None, 1]:
            with self.assertRaises(module.Refused):
                module.lighting(self.payload(state))
        bad = self.payload()
        bad["alerts"]["state"] = True
        with self.assertRaises(module.Refused):
            module.lighting(bad)

    def test_zone_and_hold_bounds(self):
        bad = self.payload()
        bad["zones"] *= 33
        with self.assertRaises(module.Refused):
            module.lighting(bad)
        with self.assertRaises(module.Refused):
            module.lighting(self.payload(holds={str(n): {} for n in range(129)}))

    def test_unavailable_source_does_not_claim_physical_success(self):
        result = module.lighting(
            {"zones": [{"state": "unavailable"}], "alerts": {"state": "0"}}
        )
        self.assertEqual(result[0], "unavailable")
        self.assertEqual(result[-1], {})

    def test_errors_are_normalized(self):
        bad = self.payload()
        bad["zones"][0]["attributes"]["error"] = "PRIVATE_CANARY credential"
        result = module.lighting(bad)
        self.assertEqual(result[1], "degraded")
        self.assertNotIn("PRIVATE_CANARY", repr(result))
