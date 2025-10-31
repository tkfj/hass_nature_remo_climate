from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, DEFAULT_NAME


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([NatureRemoClimate(entry.entry_id)])


class NatureRemoClimate(ClimateEntity):
    """属性だけ見せるダミーNature Remoエアコン。
    - 動作は未実装（操作しても変化しない）
    - モード/温度範囲/風量/左右スイングのみ属性表示
    - 上下スイングは無視（auto固定扱いで属性には出さない）
    """

    _attr_has_entity_name = True
    _attr_name = DEFAULT_NAME
    _attr_unique_id: str

    # 単位
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    # 表示用フラグ（操作は無効）
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_HORIZONTAL_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    # モード：自動(heat_cool), 送風, 冷房, 除湿, 暖房
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT_COOL,
        HVACMode.FAN_ONLY,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.HEAT,
    ]

    # 風量（オート + 1〜5）
    _attr_fan_modes = ["auto", "1", "2", "3", "4", "5"]

    # 左右スイング：1(左) / 2(中央) / 3(右) / swing
    _attr_swing_horizontal_modes = ["left", "center", "right", "swing"]

    # 表示上の現在値
    _current_hvac_mode = HVACMode.HEAT_COOL
    _current_swing_horizontal_mode = "center"
    _current_fan_mode = "auto"
    _current_target_temperature = 18.5
    _current_temperature = 22.3

    def __init__(self, unique_suffix: str) -> None:
        self._attr_unique_id = f"{DOMAIN}-{unique_suffix}"

    # デバイス情報
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=DEFAULT_NAME,
            manufacturer="Demo",
            model="NatureRemo-AC",
        )

    @property
    def current_temperature(self) -> float:
        return self._current_temperature

    @property
    def target_temperature(self) -> float | None:
        return self._current_target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        return self._current_hvac_mode

    @property
    def swing_horizontal_mode(self) -> str:
        return self._current_swing_horizontal_mode

    @property
    def fan_mode(self) -> str:
        return self._current_fan_mode

    @property
    def min_temp(self) -> float:
        return 15.0

    @property
    def max_temp(self) -> float:
        return 32.0

    @property
    def available(self) -> bool:
        return True

    @property
    def should_poll(self) -> bool:
        return False

    # 追加属性（上下スイングは出さない）
    @property
    def extra_state_attributes(self) -> dict:
        return {
            "temperature_constraints": {
                "cool": {"min": 18, "max": 32},
                "heat": {"min": 15, "max": 32},
                "heat_cool": "target_base ±2 (display only)",
                "dry": {"min": 15, "max": 32},
                "fan_only": None,
            },
            "note": "Display-only stub. Vertical swing ignored; horizontal swing mapped to swing_mode.",
        }

    # ---- 操作（ダミー：表示だけ合わせる。実制御なし）----
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode in self._attr_hvac_modes:
            self._current_hvac_mode = hvac_mode
            self.async_write_ha_state()

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        if swing_mode in self._attr_swing_horizontal_modes:
            self._current_swing_horizontal_mode = swing_horizontal_mode
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        if (t := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        # モード別の簡易制約
        min_v, max_v = 15.0, 32.0
        if self._current_hvac_mode == HVACMode.COOL:
            min_v = 18.0

        try:
            v = float(t)
        except (TypeError, ValueError):
            return

        v = max(min_v, min(max_v, v))  # クランプ
        self._current_target_temperature = v
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        if fan_mode in self._attr_fan_modes:
            self._current_fan_mode = fan_mode
            self.async_write_ha_state()
