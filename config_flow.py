from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from .const import (
    DOMAIN,
    DEFAULT_NAME,
    CONF_TOKEN,
    CONF_APPLIANCE_ID,
)
from .api import NatureRemoApi, RemoAuthError, RemoConnectionError

class NatureRemoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._token: str | None = None
        self._acs: list[dict] | None = None

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            # 1) トークン受領→APIでユーザーと家電一覧を取得
            token = user_input[CONF_TOKEN]
            api = NatureRemoApi(token)
            try:
                info = await api.async_get_user_and_appliances()
            except RemoAuthError:
                errors["base"] = "auth"
            except RemoConnectionError:
                errors["base"] = "cannot_connect"
            else:
                # ACのみ抽出
                acs = [a for a in info.get("appliances", []) if a.get("type") == "AC"]
                if not acs:
                    errors["base"] = "no_ac"
                else:
                    self._token = token
                    self._acs = acs
                    # 同一ユーザーに対して1エントリを想定
                    await self.async_set_unique_id(info.get("user_id", "remo-user"))
                    self._abort_if_unique_id_configured()
                    return await self.async_step_select()

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_TOKEN): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_select(self, user_input: dict | None = None):
        assert self._token is not None
        assert self._acs is not None

        if user_input is not None:
            # 2) 選択を受け取り→エントリ作成
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data={
                    CONF_TOKEN: self._token,
                    CONF_APPLIANCE_ID: user_input[CONF_APPLIANCE_ID],
                },
            )

        # ACの選択肢を作成
        choices = {
            a["id"]: f"{a.get('nickname') or a.get('model', {}).get('name','AC')}  ({a['id'][:6]}…)"
            for a in self._acs
        }
        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_APPLIANCE_ID): vol.In(choices),
            }
        )
        return self.async_show_form(step_id="select", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NatureRemoOptionsFlow(config_entry)

class NatureRemoOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        # オプションなし
        return self.async_create_entry(title="", data={})