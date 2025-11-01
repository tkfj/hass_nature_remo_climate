from __future__ import annotations
from datetime import timedelta
from typing import Any, Dict, List
import logging
from copy import deepcopy

from homeassistant.core import HomeAssistant
from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_TOKEN, CONF_APPLIANCE_ID
from .api import NatureRemoApi, RemoAuthError, RemoConnectionError

_LOGGER = logging.getLogger(__name__)
_mode_sort = [
    HVACMode.OFF,
    HVACMode.HEAT_COOL,
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
]
def _mode_sort_key(_x):
    _m = HVACMode(_x)
    return _mode_sort.index(_m) if _m in _mode_sort else 99999999

def _build_capabilities(ac: dict) -> Dict[str, Any]:
    """ /appliances の1ACから能力表を抽出し、HA用に正規化 """
    modes = (((ac.get("aircon") or {}).get("range") or {}).get("modes") or {})
    # Remo表記 → HA表記
    map_mode = {
        "auto":HVACMode.HEAT_COOL.value,
        "warm":HVACMode.HEAT.value,
        "heat":HVACMode.HEAT.value,
        "cool":HVACMode.COOL.value,
        "dry":HVACMode.DRY.value,
        "blow":HVACMode.FAN_ONLY.value
    }
    caps: Dict[str, Any] = {"modes": {}, "order": []}

    caps["order"].append(HVACMode.OFF.value)
    caps["modes"]["off"] = {
        "temp_list": [""],
        "vol_list": [""],
        "dirh_list": [""],
        "dir_list": [""],
    }
    for k_remo, body in modes.items():
        ha_mode = map_mode.get(k_remo)
        if not ha_mode:
            continue
        caps["order"].append(ha_mode)
        # 温度: 文字列配列（""含む）→ float配列（または""）
        temps_str: List[str] = body.get("temp") or []
        temps: List[float|str] = []
        for s in temps_str:
            try:
                if s is None: 
                    continue
                if s == "":
                    temps.append(s)
                else:
                    temps.append(float(s))
            except Exception:
                pass
        temps.sort()
        vol = body.get("vol") or []
        dirh_v = body.get("dirh") or []
        dir_v = body.get("dir") or []

        caps["modes"][ha_mode] = {
            "temp_list": temps,          # 例：[-2,-1.5,...,2] / [18,18.5,...,32] / [""]
            "vol_list": vol,             # 例：["1","2","3","4","5","auto"] / [""] etc.
            "dirh_list": dirh_v,      # 例：["1","2","3","swing"]
            "dir_list": dir_v,      # 例：["1","2","3","4","5","auto","swing"]
        }
    caps['order'].sort(key=_mode_sort_key)
    return caps


class RemoCoordinator(DataUpdateCoordinator[dict | None]):
    """/appliances を叩いて指定ACの最新スナップショット＋能力表（メモリ保持のみ）"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.api = NatureRemoApi(entry.data[CONF_TOKEN])
        self.appliance_id = entry.data[CONF_APPLIANCE_ID]
        self._capabilities: Dict[str, Any] | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-coordinator",
            update_interval=timedelta(seconds=60),
        )

    @property
    def capabilities(self) -> Dict[str, Any] | None:
        return self._capabilities

    async def _async_update_data(self) -> dict | None:
        try:
            apps = await self.api._req("GET", "/appliances")
        except RemoAuthError as e:
            raise UpdateFailed("Unauthorized token") from e
        except RemoConnectionError as e:
            raise UpdateFailed(f"Connection error: {e}") from e

        apps_ac = next((a for a in apps if a.get("id") == self.appliance_id), None)
        if not apps_ac:
            raise UpdateFailed("Appliance not found")

        # 毎回、能力表を構築して差分があれば更新（=再起動時は当然取り直す）
        new_caps = _build_capabilities(apps_ac)
        if self._capabilities != new_caps:
            self._capabilities = deepcopy(new_caps)
            _LOGGER.debug("Capabilities updated (in-memory): %s", self._capabilities)

        dev_id = apps_ac["device"]["id"]
        try:
            devs = await self.api._req("GET", "/devices")
        except RemoAuthError as e:
            raise UpdateFailed("Unauthorized token") from e
        except RemoConnectionError as e:
            raise UpdateFailed(f"Connection error: {e}") from e

        devs_brdg = next((d for d in devs if d.get("id") == dev_id), None)
        if not devs_brdg:
            raise UpdateFailed("Bridge Device not found")

        return {"ac": apps_ac, "bridge":devs_brdg}
