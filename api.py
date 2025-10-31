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

    async def _req(self, method: str, path: str) -> Any:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        async with aiohttp.ClientSession(headers=headers) as sess:
            async with sess.request(method, f"{self.BASE}{path}") as r:
                if r.status == 401:
                    raise RemoAuthError("Unauthorized")
                try:
                    r.raise_for_status()
                except aiohttp.ClientResponseError as e:
                    raise RemoConnectionError(str(e)) from e
                return await r.json()

    async def async_get_user_and_appliances(self) -> dict:
        me = await self._req("GET", "/users/me")
        apps = await self._req("GET", "/appliances")
        return {"user_id": me.get("id"), "appliances": apps}
