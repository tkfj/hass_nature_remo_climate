from __future__ import annotations
from typing import Any, List
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
async def async_setup_entry(hass, entry, async_add_entities):
    coord: RemoCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NatureRemoClimate(coord, entry.data, entry.options)], True)

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

    def __init__(self, coordinator: RemoCoordinator, data: dict, options: dict) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{DOMAIN}-{coordinator.appliance_id}"
        self._api = NatureRemoApi(data[CONF_TOKEN])
        self._appliance_id = data[CONF_APPLIANCE_ID]

        self._current_hvac_mode = HVACMode.OFF
        self._current_fan_mode = "auto"
        self._current_swing_mode = "auto"
        self._current_swing_horizontal_mode = "swing"
        self._current_temperature = None
        self._current_target_temperature = None

        self._update_from_coordinator()

    def _caps(self) -> dict:
        return self.coordinator.entry.options.get("capabilities", {"modes": {}, "order": []})

    def _mode_caps(self, mode: HVACMode) -> dict:
        return self._caps().get("modes", {}).get(mode.value, {})

    def _temp_bounds_for(self, mode: HVACMode) -> tuple[float, float]:
        temps = self._mode_caps(mode).get("temp_list") or []
        if temps:
            if temps != [""]: # FAN_ONLYは空だがHASSの仕様上値を返さないとUIでモード操作時にエラーが出るのでフォールバックさせる
                return (min(temps), max(temps))
        # フォールバック（機種が空を返すケース）
        if mode in (HVACMode.HEAT_COOL, HVACMode.DRY):
            return (-2.0, 2.0)
        return (18, 32)

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
    def target_temperature(self) -> float | None: return self._current_target_temperature if self._current_hvac_mode != HVACMode.OFF else None

    @property
    def hvac_mode(self) -> HVACMode: return self._current_hvac_mode

    @property
    def swing_horizontal_mode(self) -> str | None: return self._current_swing_horizontal_mode if self._current_hvac_mode != HVACMode.OFF else ""

    @property
    def swing_mode(self) -> str | None: return self._current_swing_mode if self._current_hvac_mode != HVACMode.OFF else ""

    @property
    def fan_mode(self) -> str | None: return self._current_fan_mode if self._current_hvac_mode != HVACMode.OFF else ""

    @property
    def min_temp(self) -> float: return self._temp_bounds_for(self._current_hvac_mode)[0]

    @property
    def max_temp(self) -> float: return self._temp_bounds_for(self._current_hvac_mode)[1]

    @property
    def current_temperature(self) -> float | None: return None  # 観測温度は使わない

    @property
    def hvac_modes(self) -> List[HVACMode]:
        result: list[HVACMode] = [HVACMode(k) for k in self._caps().get("order") or [] if k in HVAC_TO_REMO]
        # 空になった場合のフォールバック
        if not result:
            result = [
                HVACMode.OFF,
                HVACMode.HEAT,
                HVACMode.COOL,
            ]
        return result

    @property
    def fan_modes(self) -> List[str]:
        caps = self._mode_caps(self._current_hvac_mode)
        lst = caps.get("vol_list")
        return lst or [""]

    @property
    def swing_horizontal_modes(self) -> List[str]:
        caps = self._mode_caps(self._current_hvac_mode)
        lst = caps.get("dirh_list")
        return lst or [""]

    @property
    def swing_modes(self) -> List[str]:
        caps = self._mode_caps(self._current_hvac_mode)
        lst = caps.get("dir_list")
        return lst or [""]

    @property
    def target_temperature_step(self) -> float: return 0.5

    @property
    def available(self) -> bool: return self.coordinator.last_update_success

    @property
    def should_poll(self) -> bool: return False

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in self.hvac_modes:
            return
        target = HVAC_TO_REMO.get(hvac_mode)
        if target is None:
            return
        try:
            await self._api.async_set_mode(self._appliance_id, target)
        except (RemoAuthError, RemoConnectionError) as e:
            _LOGGER.warning("Failed to set hvac_mode: %s", e)
            return
        self._current_hvac_mode = hvac_mode

        # 既存ターゲット温度が新レンジ外なら丸め・クランプ
        if self._current_target_temperature is not None:
            lo, hi = self._temp_bounds_for(self._current_hvac_mode)
            v = round(float(self._current_target_temperature) * 2) / 2
            self._current_target_temperature = max(lo, min(hi, v))

        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        if swing_horizontal_mode not in self.swing_horizontal_modes:
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
        if swing_mode not in self.swing_modes:
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
        # 能力表のレンジで丸め・クランプ
        lo, hi = self._temp_bounds_for(self._current_hvac_mode)
        v = round(v * 2) / 2
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
        if fan_mode not in self.fan_modes:
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
            self._current_target_temperature = float(temp) if temp not in (None, "") else None
        except (TypeError, ValueError):
            self._current_target_temperature = None

        mode = (settings.get("mode") or "").lower()
        button = (settings.get("button") or "").lower()
        if button == "power-off":
            self._current_hvac_mode = HVACMode.OFF
        else:
            self._current_hvac_mode = REMO_TO_HVAC.get(mode, self._current_hvac_mode)

        vol = (settings.get("vol") or "").lower()
        if vol in self.fan_modes:
            self._current_fan_mode = vol

        dirh = (settings.get("dirh") or "").lower()
        if dirh in self.swing_horizontal_mode:
            self._current_swing_horizontal_mode = dirh

        dir = (settings.get("dir") or "").lower()
        if dir in self.swing_mode:
            self._current_swing_mode = dir
