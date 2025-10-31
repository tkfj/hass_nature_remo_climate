from __future__ import annotations
from typing import Any
import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import callback

from .const import DOMAIN, DEFAULT_NAME, CONF_APPLIANCE_ID, CONF_TOKEN
from .coordinator import RemoCoordinator
from .api import NatureRemoApi, RemoAuthError, RemoConnectionError

_LOGGER = logging.getLogger(__name__)

HVAC_TO_REMO = {
    HVACMode.OFF: "off",
    HVACMode.HEAT_COOL: "auto",
    HVACMode.HEAT: "warm",
    HVACMode.COOL: "cool",
    HVACMode.DRY: "dry",
    HVACMode.FAN_ONLY: "blow",
}
REMO_TO_HVAC = {
    "off": HVACMode.OFF,
    "auto": HVACMode.HEAT_COOL,
    "warm": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "dry": HVACMode.DRY,
    "blow": HVACMode.FAN_ONLY,
}
REMO_HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.HEAT_COOL,
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
]
REMO_FAN_OPTIONS = ["auto", "1", "2", "3", "4", "5"]
REMO_SWING_H_OPTIONS = ["1", "2", "3", "swing"]
REMO_SWING_OPTIONS = ["1", "2", "3", "4", "5", "auto", "swing"]
REMO_TEMPERATURE_CONSTRAINTS = {
    HVACMode.HEAT_COOL: (-2, 2),
    HVACMode.HEAT: (15, 32),
    HVACMode.COOL: (18, 32),
    HVACMode.DRY: (-2, 2),
    HVACMode.FAN_ONLY: (None, None),
}

async def async_setup_entry(hass, entry, async_add_entities):
    coord: RemoCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NatureRemoClimate(coord, entry.data)], True)

class NatureRemoClimate(ClimateEntity):

    _attr_has_entity_name = True
    _attr_name = DEFAULT_NAME
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_HORIZONTAL_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = REMO_HVAC_MODES
    _attr_fan_modes = REMO_FAN_OPTIONS
    _attr_swing_horizontal_modes = REMO_SWING_H_OPTIONS
    _attr_swing_modes = REMO_SWING_OPTIONS
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: RemoCoordinator, data: dict) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{DOMAIN}-{coordinator.appliance_id}"
        self._api = NatureRemoApi(data[CONF_TOKEN])
        self._appliance_id = data[CONF_APPLIANCE_ID]

        # 初期表示値
        self._current_hvac_mode = HVACMode.OFF
        self._current_fan_mode = "auto"
        self._current_swing_mode = "auto"
        self._current_swing_horizontal_mode = "2"
        self._current_target_temperature = None

        self._update_from_coordinator()

    # ========= 標準プロパティ =========
    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.data or {}
        model = (data.get("model") or {}).get("name", "AC")
        manufacturer = (data.get("device") or {}).get("manufacturer", "Nature")
        name = data.get("nickname", DEFAULT_NAME)
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=name,
            manufacturer=manufacturer,
            model=model,
        )

    @property
    def target_temperature(self) -> float | None: return self._current_target_temperature

    @property
    def hvac_mode(self) -> HVACMode: return self._current_hvac_mode

    @property
    def swing_horizontal_mode(self) -> str | None: return self._current_swing_horizontal_mode

    @property
    def swing_mode(self) -> str | None: return self._current_swing_mode

    @property
    def fan_mode(self) -> str | None: return self._current_fan_mode

    @property
    def min_temp(self) -> float: return REMO_TEMPERATURE_CONSTRAINTS.get(self._current_hvac_mode,(15,32,))[0]

    @property
    def max_temp(self) -> float: return REMO_TEMPERATURE_CONSTRAINTS.get(self._current_hvac_mode,(15,32,))[1]

    @property
    def available(self) -> bool: return self.coordinator.last_update_success

    @property
    def should_poll(self) -> bool: return False

    # ========= 操作（POST → 反映） =========

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in self._attr_hvac_modes:
            return
        target = HVAC_TO_REMO.get(hvac_mode, None)
        if target is None:
            return
        try:
            await self._api.async_set_mode(self._appliance_id, target)
        except (RemoAuthError, RemoConnectionError) as e:
            _LOGGER.warning("Failed to set hvac_mode: %s", e)
            return
        self._current_hvac_mode = hvac_mode
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()


    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        if swing_horizontal_mode not in self._attr_swing_horizontal_modes:
            return
        try:
            await self._api.async_set_swing_horizontal(self._appliance_id, swing_horizontal_mode)
        except (RemoAuthError, RemoConnectionError) as e:
            _LOGGER.warning("Failed to set swing_horizontal: %s", e)
            return
        self._current_swing_horizontal_mode = swing_horizontal_mode
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        if swing_mode not in self._attr_swing_modes:
            return
        try:
            await self._api.async_set_swing(self._appliance_id, swing_mode)
        except (RemoAuthError, RemoConnectionError) as e:
            _LOGGER.warning("Failed to set swing: %s", e)
            return
        self._current_swing_mode = swing_mode
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        if (t := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        try:
            v = float(t)
        except (TypeError, ValueError):
            return
        v = round(v * 2) / 2
        _l,_h = REMO_TEMPERATURE_CONSTRAINTS.get(self._current_hvac_mode,(15,32,))
        if _l is not None:
            v = max(_l, v)
        if _h is not None:
            v = min(_h, v)
        try:
            await self._api.async_set_temperature(self._appliance_id, v)
        except (RemoAuthError, RemoConnectionError) as e:
            _LOGGER.warning("Failed to set temperature: %s", e)
            return
        self._current_target_temperature = v
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        if fan_mode not in self._attr_fan_modes:
            return
        try:
            await self._api.async_set_fan(self._appliance_id, fan_mode)
        except (RemoAuthError, RemoConnectionError) as e:
            _LOGGER.warning("Failed to set fan: %s", e)
            return
        self._current_fan_mode = fan_mode
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        # ONは“何かしらの設定POST”で成立。ここでは現在モードを再送（OFF時はAUTOにして送る）
        hvac = self._current_hvac_mode if self._current_hvac_mode != HVACMode.OFF else HVACMode.HEAT_COOL
        await self.async_set_hvac_mode(hvac)

    async def async_turn_off(self) -> None:
        try:
            await self._api.async_set_power(self._appliance_id, False)
        except (RemoAuthError, RemoConnectionError) as e:
            _LOGGER.warning("Failed to power off: %s", e)
            return
        self._current_hvac_mode = HVACMode.OFF
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    # ========= Coordinator → Entity =========
    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _update_from_coordinator(self) -> None:
        data = self.coordinator.data or {}
        settings = data.get("settings") or {}

        temp = settings.get("temp")
        try:
            self._current_target_temperature = float(temp) if temp is not None else None
        except (TypeError, ValueError):
            self._current_target_temperature = None

        mode = (settings.get("mode") or "").lower()
        button = (settings.get("button") or "").lower()
        if button == "power-off":
            self._current_hvac_mode = HVACMode.OFF
        else:
            self._current_hvac_mode = REMO_TO_HVAC.get(mode, self._current_hvac_mode)

        vol = (settings.get("vol") or "").lower()
        self._current_fan_mode = vol if vol in REMO_FAN_OPTIONS else self._current_fan_mode

        dirh = (settings.get("dirh") or "").lower()
        self._current_swing_horizontal_mode = dirh if dirh in REMO_SWING_H_OPTIONS else self._current_swing_horizontal_mode

        dir = (settings.get("dir") or "").lower()
        self._current_swing_mode = dir if dir in REMO_SWING_OPTIONS else self._current_swing_mode
