"""Only the lab harness creates fixture entries."""

from homeassistant import config_entries


class FixtureFlow(config_entries.ConfigFlow, domain="bow_lighting"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return self.async_abort(reason="fixture_only")
