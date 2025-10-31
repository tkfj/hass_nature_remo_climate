from __future__ import annotations
from homeassistant.components.climate import ClimateEntity, HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, DEFAULT_NAME

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([EmptyClimateEntity(entry.entry_id)])

class EmptyClimateEntity(ClimateEntity):
    """何もしないが表示だけされるclimateエンティティ。
    - 温度や現在動作はすべて未設定(None)
    - HVACモードは OFF のみ
    - 操作メソッドは受け取るが実際には何もしない
    """

    _attr_has_entity_name = True
    _attr_name = DEFAULT_NAME
    _attr_unique_id: str
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF]

    def __init__(self, unique_suffix: str) -> None:
        self._attr_unique_id = f"{DOMAIN}-{unique_suffix}"

    # 最低限：デバイス登録
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=DEFAULT_NAME,
            manufacturer="Demo",
            model="Empty-AC",
        )

    # 「完全に空」= 値を返さない/操作しても状態は変わらない
    @property
    def current_temperature(self):
        return None

    @property
    def target_temperature(self):
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        # 何もしない
        return

    async def async_turn_on(self) -> None:
        # 何もしない
        return

    async def async_turn_off(self) -> None:
        # 何もしない
        return

    @property
    def available(self) -> bool:
        return True

    @property
    def should_poll(self) -> bool:
        return False
