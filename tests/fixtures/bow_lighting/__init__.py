"""Synthetic SensorEntity platform; no real controller imports or controls."""


async def async_setup_entry(hass, entry):
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, ["sensor"])
