"""Native administrator selection and explicit persistent read-only approval."""

import probatio
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN, SCOPE
from .projection import Refused
from .selection import matches, select


class SelectionFlow:
    async def async_step_select(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                self.bindings = select(
                    self.hass, user_input.get("zones"), user_input.get("alerts")
                )
                return await self.async_step_approve()
            except Refused:
                errors["base"] = "invalid_selection"
        return self.async_show_form(
            step_id="select",
            data_schema=probatio.Schema(
                {
                    probatio.Required("zones"): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", integration="bow_lighting", multiple=True
                        )
                    ),
                    probatio.Required("alerts"): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", integration="bow_lighting"
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_approve(self, user_input=None):
        if not getattr(self, "bindings", None) or not matches(self.hass, self.bindings):
            return self.async_abort(reason="selection_changed")
        if user_input is not None:
            if user_input.get("approve") is not True:
                return self.async_abort(reason="approval_required")
            data = {"approved": True, "bindings": self.bindings, "scope": SCOPE}
            if isinstance(self, config_entries.OptionsFlow):
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=data
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})
            await self.async_set_unique_id("lighting_status")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="BowLabs Lighting Status", data=data)
        return self.async_show_form(
            step_id="approve",
            data_schema=probatio.Schema(
                {
                    probatio.Required("approve", default=False): bool,
                }
            ),
            description_placeholders={
                "entities": ", ".join(x["entity_id"] for x in self.bindings),
                "scope": SCOPE,
            },
        )


class LightingFlow(SelectionFlow, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return await self.async_step_select(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return LightingOptions()


class LightingOptions(SelectionFlow, config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            if user_input["action"] == "review":
                return await self.async_step_select()
            return await self.async_step_revoke()
        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required("action", default="revoke"): probatio.In(
                        ["revoke", "review"]
                    ),
                }
            ),
        )

    async def async_step_revoke(self, user_input=None):
        if user_input is not None:
            if user_input.get("confirm") is not True:
                return self.async_abort(reason="approval_required")
            # Persist first; a subsequent restart must remain revoked.
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, "approved": False}
            )
            self.config_entry.runtime_data.stop()
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="revoke",
            data_schema=probatio.Schema(
                {probatio.Required("confirm", default=False): bool}
            ),
        )
