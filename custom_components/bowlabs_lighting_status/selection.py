"""Validate registry identity without importing or activating BowLighting."""

from homeassistant.helpers import entity_registry as er

from .projection import Refused


def select(hass, zones, alert):
    if (
        type(zones) is not list
        or not 1 <= len(zones) <= 32
        or any(type(e) is not str for e in zones)
        or type(alert) is not str
        or len(set(zones)) != len(zones)
        or alert in zones
    ):
        raise Refused()
    registry = er.async_get(hass)
    result = []
    for entity_id, role in [(e, "zone") for e in zones] + [(alert, "alerts")]:
        record = registry.async_get(entity_id)
        source = (
            hass.config_entries.async_get_entry(record.config_entry_id)
            if record
            else None
        )
        suffix = "_status" if role == "zone" else "_alerts_active"
        kind = "global" if role == "alerts" else "zone"
        if (
            record is None
            or source is None
            or record.platform != "bow_lighting"
            or not entity_id.startswith("sensor.")
            or record.disabled
            or source.domain != "bow_lighting"
            or (source.data.get("kind") == "global") != (kind == "global")
            or record.unique_id != source.entry_id + suffix
        ):
            raise Refused()
        result.append(
            {
                "entity_id": entity_id,
                "unique_id": record.unique_id,
                "config_entry_id": source.entry_id,
                "role": role,
            }
        )
    return result


def matches(hass, bindings):
    try:
        zones = [x["entity_id"] for x in bindings if x["role"] == "zone"]
        alerts = [x["entity_id"] for x in bindings if x["role"] == "alerts"]
        return len(alerts) == 1 and select(hass, zones, alerts[0]) == bindings
    except (KeyError, TypeError, Refused):
        return False
