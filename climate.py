from __future__ import annotations
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import callback

from .const import DOMAIN, DEFAULT_NAME
from .coordinator import RemoCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    coord: RemoCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NatureRemoClimate(coord)])


class NatureRemoClimate(ClimateEntity):

    _attr_has_entity_name = True
    _attr_name = DEFAULT_NAME
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_HORIZONTAL_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT_COOL,
        HVACMode.FAN_ONLY,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.HEAT,
    ]

    _attr_fan_modes = ["auto", "1", "2", "3", "4", "5"]

    _attr_swing_horizontal_modes = ["1", "2", "3", "swing"]

    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: RemoCoordinator) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{DOMAIN}-{coordinator.appliance_id}"

        # UIに何か出すための初期値（API到着前）
        self._current_hvac_mode = HVACMode.OFF
        self._current_fan_mode = "auto"
        self._current_swing_horizontal_mode = "2"
        self._current_temperature = None
        self._current_target_temperature = None

        # 初回データを反映
        self._update_from_coordinator()

    # ========== HA 標準プロパティ ==========
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
    def current_temperature(self) -> float | None:
        return self._current_temperature

    @property
    def target_temperature(self) -> float | None:
        return self._current_target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        return self._current_hvac_mode

    @property
    def swing_horizontal_mode(self) -> str | None:
        return self._current_swing_horizontal_mode

    @property
    def fan_mode(self) -> str | None:
        return self._current_fan_mode

    @property
    def min_temp(self) -> float:
        return 15.0

    @property
    def max_temp(self) -> float:
        return 32.0

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "temperature_constraints": {
                "cool": {"min": 18, "max": 32},
                "heat": {"min": 15, "max": 32},
                "heat_cool": "target_base ±2 (display only)",
                "dry": {"min": 15, "max": 32},
                "fan_only": None,
            },
            "note": "Display-only. Values are fetched from Nature Remo API; no control yet.",
        }

    # ========== 表示だけ更新（制御はしない） ==========
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode in self._attr_hvac_modes:
            self._current_hvac_mode = hvac_mode
            self.async_write_ha_state()

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        if swing_horizontal_mode in self._attr_swing_horizontal_modes:
            self._current_swing_horizontal_mode = swing_horizontal_mode
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        if (t := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        try:
            v = float(t)
        except (TypeError, ValueError):
            return
        # 表示のためだけにクランプ
        min_v = 18.0 if self._current_hvac_mode == HVACMode.COOL else 15.0
        v = max(min_v, min(32.0, v))
        self._current_target_temperature = v
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        if fan_mode in self._attr_fan_modes:
            self._current_fan_mode = fan_mode
            self.async_write_ha_state()

    # ========== Coordinator → Entity 反映 ==========
    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _update_from_coordinator(self) -> None:
        """Coordinatorの /appliances 1件データから現在値を抽出"""
        data = self.coordinator.data or {}
        settings = data.get("settings") or {}
        newest = data.get("newest_events") or {}

        # 現在温度（te.val）
        te = (newest.get("te") or {}).get("val")
        try:
            self._current_temperature = float(te) if te is not None else None
        except (TypeError, ValueError):
            self._current_temperature = None

        # 目標温度（settings.temp）
        temp = settings.get("temp")
        try:
            self._current_target_temperature = float(temp) if temp is not None else None
        except (TypeError, ValueError):
            self._current_target_temperature = None

        # モード
        mode = (settings.get("mode") or "").lower()
        button = (settings.get("button") or "").lower()
        if button == "power-off":
            self._current_hvac_mode = HVACMode.OFF
        else:
            self._current_hvac_mode = {
                "cool": HVACMode.COOL,
                "warm": HVACMode.HEAT,
                "dry": HVACMode.DRY,
                "auto": HVACMode.HEAT_COOL,
                "blow": HVACMode.FAN_ONLY,
                "off": HVACMode.OFF,
            }.get(mode, HVACMode.OFF)

        vol = (settings.get("vol") or "").lower()
        self._current_fan_mode = vol if vol in self._attr_fan_modes else "auto"

        dirh = (settings.get("dirh") or "").lower()
        self._current_swing_horizontal_mode = dirh if dirh in self._attr_swing_horizontal_modes else "2"
