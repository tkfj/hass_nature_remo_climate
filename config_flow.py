from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from .const import DOMAIN, DEFAULT_NAME

class EmptyAcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        if user_input is not None:
            # 同一インスタンス1件を想定。複数作りたい場合はunique_idを可変に。
            await self.async_set_unique_id("singleton-hass-nature-remo-climate")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input.get(CONF_NAME, DEFAULT_NAME), data={})
        schema = vol.Schema({vol.Optional(CONF_NAME, default=DEFAULT_NAME): str})
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EmptyAcOptionsFlow(config_entry)

class EmptyAcOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        # オプションなし
        return self.async_create_entry(title="", data={})