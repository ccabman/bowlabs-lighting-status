"""A single sanitized diagnostic summary; no application controls."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([LightingSummary(entry)])


class LightingSummary(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Lighting status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:lightbulb-auto-outline"

    def __init__(self, entry):
        super().__init__(entry.runtime_data)
        self._attr_unique_id = entry.entry_id + "_summary"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "BowLabs",
            "manufacturer": "BowLabs",
            "model": "Read-only lighting status",
        }

    @property
    def native_value(self):
        row = self.coordinator.data
        return (
            row["operating_state"]
            if row["availability"] == "available"
            else row["availability"]
        )

    @property
    def extra_state_attributes(self):
        return self.coordinator.data
