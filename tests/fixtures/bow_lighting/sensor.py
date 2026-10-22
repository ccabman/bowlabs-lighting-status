"""Two static synthetic diagnostic entities, with no polling or device access."""

from homeassistant.components.sensor import SensorEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Fixture(entry)])


class Fixture(SensorEntity):
    _attr_should_poll = False

    def __init__(self, entry):
        global_entry = entry.data.get("kind") == "global"
        self.entity_id = (
            "sensor.bowlabs_fixture_alerts"
            if global_entry
            else "sensor.bowlabs_fixture_zone"
        )
        self._attr_unique_id = entry.entry_id + (
            "_alerts_active" if global_entry else "_status"
        )
        self._attr_name = "Fixture alerts" if global_entry else "Fixture zone"
        self._attr_native_value = "0" if global_entry else "Adapting"
        self._attr_extra_state_attributes = (
            {}
            if global_entry
            else {
                "holds": {},
                "brightness_override": False,
                "error": None,
                "resolved_lights": ["PRIVATE_CANARY_LIGHT"],
                "profile": "PRIVATE_CANARY_ROOM",
            }
        )
