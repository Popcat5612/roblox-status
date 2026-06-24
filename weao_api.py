"""
WEAO API 비동기 래퍼
https://docs.weao.xyz
"""

import urllib.parse
import aiohttp
from dataclasses import dataclass, field
from typing import Optional

BASE_URL = "https://weao.xyz/api"
HEADERS = {"User-Agent": "WEAO-3PService"}


@dataclass
class ExploitStatus:
    id: str
    title: str
    version: str
    updated_date: str
    platform: str
    free: bool
    detected: bool
    update_status: bool
    unc_status: bool
    unc_percentage: Optional[int] = None
    sunc_percentage: Optional[int] = None
    cost: Optional[str] = None
    website_link: Optional[str] = None
    discord_link: Optional[str] = None
    purchase_link: Optional[str] = None
    decompiler: Optional[bool] = None
    multi_inject: Optional[bool] = None
    key_system: Optional[bool] = None
    rbxversion: Optional[str] = None
    hidden: bool = False
    extype: str = ""          # wexternal / wexecutor / mexecutor / iexecutor / aexecutor

    @classmethod
    def from_dict(cls, d: dict) -> "ExploitStatus":
        return cls(
            id=d.get("_id", ""),
            title=d.get("title", "Unknown"),
            version=d.get("version", "Unknown"),
            updated_date=d.get("updatedDate", "Unknown"),
            platform=d.get("platform", "Unknown"),
            free=d.get("free", False),
            detected=d.get("detected", False),
            update_status=d.get("updateStatus", False),
            unc_status=d.get("uncStatus", False),
            unc_percentage=d.get("uncPercentage"),
            sunc_percentage=d.get("suncPercentage"),
            cost=d.get("cost"),
            website_link=d.get("websitelink"),
            discord_link=d.get("discordlink"),
            purchase_link=d.get("purchaselink"),
            decompiler=d.get("decompiler"),
            multi_inject=d.get("multiInject"),
            key_system=d.get("keysystem"),
            rbxversion=d.get("rbxversion"),
            hidden=d.get("hidden", False),
            extype=d.get("extype", ""),
        )

    @property
    def status_emoji(self) -> str:
        if not self.update_status:
            return "🔴"
        if self.detected:
            return "🟡"
        return "🟢"

    @property
    def status_text(self) -> str:
        if not self.update_status:
            return "미업데이트"
        if self.detected:
            return "감지됨 (Detected)"
        return "정상"

    def state_key(self) -> tuple:
        """변경 감지용 — 이 값이 바뀌면 Embed를 수정함"""
        return (self.version, self.update_status, self.detected, self.rbxversion)


@dataclass
class RobloxVersions:
    windows: str
    windows_date: str
    mac: str
    mac_date: str
    android: Optional[str] = None
    android_date: Optional[str] = None
    ios: Optional[str] = None
    ios_date: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "RobloxVersions":
        return cls(
            windows=d.get("Windows", "Unknown"),
            windows_date=d.get("WindowsDate", "Unknown"),
            mac=d.get("Mac", "Unknown"),
            mac_date=d.get("MacDate", "Unknown"),
            android=d.get("Android"),
            android_date=d.get("AndroidDate"),
            ios=d.get("iOS"),
            ios_date=d.get("iOSDate"),
        )

    def state_key(self) -> tuple:
        return (self.windows, self.mac, self.android, self.ios)


class WeaoAPIError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"[{status}] {message}")


class WeaoClient:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        self._session = aiohttp.ClientSession(headers=HEADERS)

    async def close(self):
        if self._session:
            await self._session.close()

    async def _get(self, endpoint: str) -> dict | list:
        if not self._session:
            raise RuntimeError("WeaoClient.start()를 먼저 호출하세요.")
        url = f"{BASE_URL}/{endpoint}"
        async with self._session.get(url) as resp:
            data = await resp.json(content_type=None)
            if resp.status == 429:
                remaining = data.get("rateLimitInfo", {}).get("remainingTime", "?")
                raise WeaoAPIError(429, f"Rate limit — {remaining}초 후 재시도")
            if resp.status != 200:
                raise WeaoAPIError(resp.status, str(data))
            return data

    async def get_all_exploits(self) -> list[ExploitStatus]:
        data = await self._get("status/exploits")
        items = data if isinstance(data, list) else data.get("exploits", data.get("data", []))
        return [ExploitStatus.from_dict(e) for e in items if not e.get("hidden", False)]

    async def get_exploit(self, name: str) -> ExploitStatus:
        encoded = urllib.parse.quote(name)
        data = await self._get(f"status/exploits/{encoded}")
        return ExploitStatus.from_dict(data)

    async def get_current_versions(self) -> RobloxVersions:
        data = await self._get("versions/current")
        return RobloxVersions.from_dict(data)

    async def get_future_versions(self) -> RobloxVersions:
        data = await self._get("versions/future")
        return RobloxVersions.from_dict(data)

    async def get_past_versions(self) -> RobloxVersions:
        data = await self._get("versions/past")
        return RobloxVersions.from_dict(data)