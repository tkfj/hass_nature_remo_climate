from __future__ import annotations
from datetime import timedelta
from typing import Any, Dict, List
import logging

from homeassistant.core import HomeAssistant
from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_TOKEN, CONF_APPLIANCE_ID
from .api import NatureRemoApi, RemoAuthError, RemoConnectionError

_LOGGER = logging.getLogger("custom_components.hass_nature_remo_climate")
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
    """/appliances の 1 AC データから機能レンジを抽出し、HA 用に正規化して保存可能にする。"""
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
    """Fetch one AC appliance snapshot via Nature Remo Cloud API (read-only)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.api = NatureRemoApi(entry.data[CONF_TOKEN])
        self.appliance_id = entry.data[CONF_APPLIANCE_ID]
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-coordinator",
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self) -> dict | None:
        try:
            apps = await self.api._req("GET", "/appliances")
        except RemoAuthError as e:
            raise UpdateFailed("Unauthorized token") from e
        except RemoConnectionError as e:
            raise UpdateFailed(f"Connection error: {e}") from e

        ac = next((a for a in apps if a.get("id") == self.appliance_id), None)
        if not ac:
            raise UpdateFailed("Appliance not found")

        # 初回のみ能力表を options に保存（以降は不変）
        if "capabilities" not in self.entry.options:
            caps = _build_capabilities(ac)
            new_opts = dict(self.entry.options)
            new_opts["capabilities"] = caps
            # 非同期で options を更新（リロード不要）
            self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
            _LOGGER.debug("Saved capabilities to options: %s", caps)

        return ac
