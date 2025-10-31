# custom_components/hass_nature_remo_climate/api.py
from __future__ import annotations
from typing import Any

import aiohttp

class RemoAuthError(Exception):
    pass

class RemoConnectionError(Exception):
    pass

class NatureRemoApi:
    BASE = "https://api.nature.global/1"

    def __init__(self, token: str) -> None:
        self._token = token

    async def _req(self, method: str, path: str, data: dict[str, Any] | None = None) -> Any:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        async with aiohttp.ClientSession(headers=headers) as sess:
            async with sess.request(method, f"{self.BASE}{path}", data=data) as r:
                if r.status == 401:
                    raise RemoAuthError("Unauthorized")
                try:
                    r.raise_for_status()
                except aiohttp.ClientResponseError as e:
                    raise RemoConnectionError(str(e)) from e
                # /aircon_settings は本文が空のこともあるのでJSONでなくてOK
                if r.content_type == "application/json":
                    return await r.json()
                return await r.text()

    async def async_get_user_and_appliances(self) -> dict:
        me = await self._req("GET", "/users/me")
        apps = await self._req("GET", "/appliances")
        return {"user_id": me.get("id"), "appliances": apps}

    # ===== 制御系 =====

    async def async_set_power(self, appliance_id: str, on: bool) -> None:
        # Remoは電源OFFのみ明示的: button=power-off
        data = {"button": "power-off"} if not on else {}
        await self._req("POST", f"/appliances/{appliance_id}/aircon_settings", data=data)

    async def async_set_mode(self, appliance_id: str, mode: str) -> None:
        # mode: "cool" | "warm" | "heat" | "dry" | "auto" | "off"
        if mode == "off":
            await self.async_set_power(appliance_id, False)
            return
        await self._req(
            "POST",
            f"/appliances/{appliance_id}/aircon_settings",
            data={"operation_mode": mode},
        )

    async def async_set_temperature(self, appliance_id: str, temp_c: float) -> None:
        """温度を0.5℃単位で設定（整数は小数点なし）"""
        # 0.5単位に丸め
        rounded = round(temp_c * 2) / 2
        # .0 は付けない
        temp_str = str(int(rounded)) if rounded.is_integer() else str(rounded)
        await self._req(
            "POST",
            f"/appliances/{appliance_id}/aircon_settings",
            data={"temperature": temp_str},
        )

    async def async_set_fan(self, appliance_id: str, fan: str) -> None:
        await self._req(
            "POST",
            f"/appliances/{appliance_id}/aircon_settings",
            data={"air_volume": fan},
        )

    async def async_set_swing_horizontal(self, appliance_id: str, swing_horizontal: str) -> None:
        await self._req(
            "POST",
            f"/appliances/{appliance_id}/aircon_settings",
            data={"air_direction_h": swing_horizontal},
        )

    async def async_set_swing(self, appliance_id: str, swing: str) -> None:
        await self._req(
            "POST",
            f"/appliances/{appliance_id}/aircon_settings",
            data={"air_direction": swing},
        )
