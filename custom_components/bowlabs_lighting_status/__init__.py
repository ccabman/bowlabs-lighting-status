"""Read-only, explicitly selected local BowLighting diagnostics."""

import logging
from datetime import timedelta

from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import (
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, PLATFORMS, SCOPE
from .projection import Refused, lighting
from .selection import matches

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
_LOGGER = logging.getLogger(__name__)


class LightingCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(
            hass, _LOGGER, name="BowLabs Lighting Status", config_entry=entry
        )
        self.entry = entry
        self.stopped = False
        self.unsubs = []

    @callback
    def refresh(self, event=None):
        row = {
            "authorization": "revoked",
            "availability": "revoked",
            "operating_state": "unknown",
            "readiness": "not_checked",
            "details": {},
            "evidence": "application_reported",
            "physical_verified": False,
        }
        if (
            not self.stopped
            and self.entry.data.get("approved") is True
            and self.entry.data.get("scope") == SCOPE
        ):
            bindings = self.entry.data.get("bindings")
            if not matches(self.hass, bindings):
                row.update(authorization="selection_changed", availability="invalid")
            else:
                try:
                    zones, alert = [], None
                    for binding in bindings:
                        state = self.hass.states.get(binding["entity_id"])
                        if binding["role"] == "alerts":
                            alert = {"state": None if state is None else state.state}
                        else:
                            zones.append(
                                {"state": "unavailable"}
                                if state is None
                                else {
                                    "state": state.state,
                                    "attributes": dict(state.attributes),
                                }
                            )
                    availability, operating, readiness, code, details = lighting(
                        {"zones": zones, "alerts": alert}
                    )
                    row.update(
                        authorization="approved",
                        availability=availability,
                        operating_state=operating,
                        readiness=readiness,
                        error_code=code,
                        details=details,
                    )
                except (Refused, TypeError, KeyError):
                    row.update(authorization="approved", availability="invalid")
        self.async_set_updated_data(row)

    def stop(self):
        self.stopped = True
        for unsub in self.unsubs:
            unsub()
        self.unsubs.clear()
        self.refresh()


async def async_setup_entry(hass, entry):
    coordinator = LightingCoordinator(hass, entry)
    entry.runtime_data = coordinator
    coordinator.refresh()
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        if entry.data.get("approved") is True and entry.data.get("scope") == SCOPE:
            ids = [b["entity_id"] for b in entry.data.get("bindings", [])]
            coordinator.unsubs.append(
                async_track_entity_registry_updated_event(
                    hass, ids, coordinator.refresh
                )
            )
            coordinator.unsubs.append(
                async_track_state_change_event(hass, ids, coordinator.refresh)
            )
            coordinator.unsubs.append(
                async_track_time_interval(
                    hass, coordinator.refresh, timedelta(seconds=30)
                )
            )
    except BaseException:
        coordinator.stop()
        raise
    return True


async def async_unload_entry(hass, entry):
    entry.runtime_data.stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass, entry):
    if getattr(entry, "runtime_data", None) is not None:
        entry.runtime_data.stop()
