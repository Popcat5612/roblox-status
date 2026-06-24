"""
WEAO Discord Bot
- 주기적으로 WEAO API 폴링
- 변경 감지 시 기존 메세지 수정 (도배 방지)
- 채널당 메세지 1개 유지
"""

import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord.ext import tasks

from weao_api import WeaoClient, WeaoAPIError, ExploitStatus, RobloxVersions
from config import (
    DISCORD_TOKEN,
    EXPLOIT_CHANNEL_ID,
    VERSION_CHANNEL_ID,
    POLL_INTERVAL_SECONDS,
)

log = logging.getLogger("weao_bot")

# ── 상태 저장소 ───────────────────────────────────────────────
# { exploit_id: (state_key, discord.Message) }
exploit_messages: dict[str, tuple] = {}
# (state_key, discord.Message) | None
version_message: tuple | None = None

# 직전 상태 (변경 감지용)
prev_exploit_states: dict[str, tuple] = {}
prev_version_state: tuple | None = None


# ── Embed 생성 ────────────────────────────────────────────────

def make_exploit_embed(ex: ExploitStatus) -> discord.Embed:
    color_map = {
        "🟢": discord.Color.green(),
        "🟡": discord.Color.yellow(),
        "🔴": discord.Color.red(),
    }
    color = color_map[ex.status_emoji]

    embed = discord.Embed(
        title=f"{ex.status_emoji}  {ex.title}",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="상태", value=ex.status_text, inline=True)
    embed.add_field(name="버전", value=f"`{ex.version}`", inline=True)
    embed.add_field(name="플랫폼", value=ex.platform, inline=True)
    embed.add_field(name="가격", value="무료" if ex.free else (ex.cost or "유료"), inline=True)
    embed.add_field(name="UNC", value="✅" if ex.unc_status else "❌", inline=True)

    scores = []
    if ex.unc_percentage is not None:
        scores.append(f"UNC {ex.unc_percentage}%")
    if ex.sunc_percentage is not None:
        scores.append(f"sUNC {ex.sunc_percentage}%")
    if scores:
        embed.add_field(name="점수", value=" / ".join(scores), inline=True)

    features = []
    if ex.decompiler:
        features.append("디컴파일러")
    if ex.multi_inject:
        features.append("멀티 인젝트")
    if ex.key_system:
        features.append("키 시스템")
    if features:
        embed.add_field(name="기능", value="  •  ".join(features), inline=False)

    links = []
    if ex.website_link:
        links.append(f"[웹사이트]({ex.website_link})")
    if ex.discord_link:
        links.append(f"[디스코드]({ex.discord_link})")
    if ex.purchase_link and not ex.free:
        links.append(f"[구매]({ex.purchase_link})")
    if links:
        embed.add_field(name="링크", value="  •  ".join(links), inline=False)

    if ex.rbxversion:
        embed.set_footer(text=f"Roblox {ex.rbxversion}")

    return embed


def make_version_embed(cur: RobloxVersions, fut: RobloxVersions, past: RobloxVersions) -> discord.Embed:
    embed = discord.Embed(
        title="🎮  Roblox 버전 현황",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(
        name="🟢 현재 (Current)",
        value=f"**Windows** `{cur.windows}`\n{cur.windows_date}\n"
              f"**Mac** `{cur.mac}`\n{cur.mac_date}"
              + (f"\n**Android** `{cur.android}`\n{cur.android_date}" if cur.android else "")
              + (f"\n**iOS** `{cur.ios}`\n{cur.ios_date}" if cur.ios else ""),
        inline=False,
    )
    embed.add_field(
        name="🔵 예정 (Future)",
        value=f"**Windows** `{fut.windows}`\n{fut.windows_date}\n"
              f"**Mac** `{fut.mac}`\n{fut.mac_date}",
        inline=False,
    )
    embed.add_field(
        name="⚪ 이전 (Past)",
        value=f"**Windows** `{past.windows}`\n{past.windows_date}\n"
              f"**Mac** `{past.mac}`\n{past.mac_date}",
        inline=False,
    )
    embed.set_footer(text="WEAO API · 자동 업데이트")
    return embed


def make_summary_embed(exploits: list[ExploitStatus]) -> discord.Embed:
    """
    전체 요약 Embed — 플랫폼별 섹션으로 정렬
    순서: Windows External → iOS Executor → Android Executor → Mac Executor → Windows Executor
    """

    # extype 기준 정렬 순서
    SECTION_ORDER = [
        ("wexternal",  "🖥️  Windows External"),
        ("iexecutor",  "🍎  iOS Script Executor"),
        ("aexecutor",  "🤖  Android Script Executor"),
        ("mexecutor",  "💻  Mac Script Executor"),
        ("wexecutor",  "🪟  Windows Script Executor"),
    ]

    # 플랫폼별 버킷으로 분류
    buckets: dict[str, list[ExploitStatus]] = {k: [] for k, _ in SECTION_ORDER}
    other: list[ExploitStatus] = []
    for ex in exploits:
        t = ex.extype.lower()
        if t in buckets:
            buckets[t].append(ex)
        else:
            other.append(ex)

    total = len(exploits)
    updated_n = sum(1 for e in exploits if e.update_status and not e.detected)
    detected_n = sum(1 for e in exploits if e.update_status and e.detected)
    outdated_n = sum(1 for e in exploits if not e.update_status)

    embed = discord.Embed(
        title="📊  익스플로잇 전체 현황",
        description=(
            f"총 **{total}개** 추적 중  •  "
            f"🟢 정상 **{updated_n}**  •  "
            f"🟡 감지됨 **{detected_n}**  •  "
            f"🔴 미업데이트 **{outdated_n}**"
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )

    def fmt_section(lst: list[ExploitStatus]) -> str:
        if not lst:
            return "*없음*"
        lines = []
        for e in lst:
            # 버전 + UNC 뱃지
            badges = ""
            if e.unc_status:
                pct = f" {e.unc_percentage}%" if e.unc_percentage is not None else ""
                badges += f" `UNC{pct}`"
            if e.sunc_percentage is not None:
                badges += f" `sUNC {e.sunc_percentage}%`"
            price = "무료" if e.free else (e.cost or "유료")
            lines.append(
                f"{e.status_emoji} **{e.title}**  `{e.version}`  •  {price}{badges}"
            )
        return "\n".join(lines)

    for extype_key, section_name in SECTION_ORDER:
        bucket = buckets[extype_key]
        u = sum(1 for e in bucket if e.update_status and not e.detected)
        d = sum(1 for e in bucket if e.update_status and e.detected)
        o = sum(1 for e in bucket if not e.update_status)
        counter = f"🟢{u} 🟡{d} 🔴{o}"
        embed.add_field(
            name=f"{section_name}  ({len(bucket)})  {counter}",
            value=fmt_section(bucket),
            inline=False,
        )

    if other:
        embed.add_field(
            name=f"❓  기타  ({len(other)})",
            value=fmt_section(other),
            inline=False,
        )

    embed.set_footer(text="WEAO API · 자동 업데이트")
    return embed


# ── 봇 클래스 ─────────────────────────────────────────────────

class WeaoBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.weao = WeaoClient()

        # 채널당 단일 메세지 ID 캐시
        # { channel_id: { key: message_id } }
        self._msg_cache: dict[int, dict[str, int]] = {}

    async def setup_hook(self):
        await self.weao.start()
        self.poll_loop.start()

    async def close(self):
        self.poll_loop.cancel()
        await self.weao.close()
        await super().close()

    async def on_ready(self):
        log.info(f"✅ 로그인: {self.user}  |  폴링 간격: {POLL_INTERVAL_SECONDS}초")

    # ── 메세지 관리 헬퍼 ──────────────────────────────────────

    async def _upsert_message(
        self,
        channel: discord.TextChannel,
        cache_key: str,
        embed: discord.Embed,
    ) -> discord.Message:
        """
        cache_key에 해당하는 메세지가 있으면 수정, 없으면 새로 전송.
        메세지 ID를 _msg_cache에 저장해 재시작 후에도 채널에서 복구 시도.
        """
        ch_cache = self._msg_cache.setdefault(channel.id, {})
        msg_id = ch_cache.get(cache_key)

        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed)
                return msg
            except (discord.NotFound, discord.HTTPException):
                # 메세지가 삭제됐거나 못 찾으면 새로 전송
                ch_cache.pop(cache_key, None)

        msg = await channel.send(embed=embed)
        ch_cache[cache_key] = msg.id
        return msg

    # ── 폴링 루프 ─────────────────────────────────────────────

    @tasks.loop(seconds=POLL_INTERVAL_SECONDS)
    async def poll_loop(self):
        await self._poll_exploits()
        await self._poll_versions()

    @poll_loop.before_loop
    async def before_poll(self):
        await self.wait_until_ready()
        log.info("폴링 시작")

    @poll_loop.error
    async def poll_error(self, error: Exception):
        log.error(f"폴링 루프 오류: {error}")

    # ── 익스플로잇 폴링 ───────────────────────────────────────

    async def _poll_exploits(self):
        global prev_exploit_states

        channel = self.get_channel(EXPLOIT_CHANNEL_ID)
        if not channel:
            log.warning(f"EXPLOIT_CHANNEL_ID({EXPLOIT_CHANNEL_ID}) 채널을 찾을 수 없음")
            return

        try:
            exploits = await self.weao.get_all_exploits()
        except WeaoAPIError as e:
            log.warning(f"익스플로잇 API 오류: {e}")
            return

        # 1) 요약 메세지 항상 업데이트
        summary_embed = make_summary_embed(exploits)
        await self._upsert_message(channel, "__summary__", summary_embed)

        # 2) 변경된 익스플로잇만 개별 메세지 수정
        changed = False
        for ex in exploits:
            new_key = ex.state_key()
            old_key = prev_exploit_states.get(ex.id)

            if old_key is None:
                # 첫 실행 — 상태만 저장, 메세지 전송 안 함 (도배 방지)
                prev_exploit_states[ex.id] = new_key
                continue

            if new_key != old_key:
                log.info(f"변경 감지: {ex.title}  {old_key} → {new_key}")
                embed = make_exploit_embed(ex)
                embed.title = f"🔔  {embed.title}  *(업데이트)*"
                await self._upsert_message(channel, f"exploit_{ex.id}", embed)
                prev_exploit_states[ex.id] = new_key
                changed = True

        if changed:
            # 요약도 한 번 더 갱신
            await self._upsert_message(channel, "__summary__", make_summary_embed(exploits))

    # ── Roblox 버전 폴링 ──────────────────────────────────────

    async def _poll_versions(self):
        global prev_version_state

        channel = self.get_channel(VERSION_CHANNEL_ID)
        if not channel:
            log.warning(f"VERSION_CHANNEL_ID({VERSION_CHANNEL_ID}) 채널을 찾을 수 없음")
            return

        try:
            cur = await self.weao.get_current_versions()
            fut = await self.weao.get_future_versions()
            past = await self.weao.get_past_versions()
        except WeaoAPIError as e:
            log.warning(f"버전 API 오류: {e}")
            return

        new_key = cur.state_key()

        if prev_version_state is None:
            # 첫 실행 — 메세지 전송만
            embed = make_version_embed(cur, fut, past)
            await self._upsert_message(channel, "__version__", embed)
            prev_version_state = new_key
            return

        if new_key != prev_version_state:
            log.info(f"Roblox 버전 변경: {prev_version_state} → {new_key}")
            embed = make_version_embed(cur, fut, past)
            embed.title = "🔔  " + embed.title + "  *(업데이트)*"
            await self._upsert_message(channel, "__version__", embed)
            prev_version_state = new_key
        else:
            # 변경 없어도 timestamp 갱신
            embed = make_version_embed(cur, fut, past)
            await self._upsert_message(channel, "__version__", embed)


# ── 진입점 ────────────────────────────────────────────────────

def run_bot():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    bot = WeaoBot()
    bot.run(DISCORD_TOKEN)