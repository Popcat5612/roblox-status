"""
config.py — 환경변수로 설정 관리
Render 대시보드 > Environment에 아래 변수들을 등록하세요.
"""

import os

# ── Discord ───────────────────────────────────────────────────
DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]

# 익스플로잇 상태를 보낼 채널 ID (int)
EXPLOIT_CHANNEL_ID: int = int(os.environ["EXPLOIT_CHANNEL_ID"])

# Roblox 버전을 보낼 채널 ID (int)
# EXPLOIT_CHANNEL_ID와 같은 채널이어도 됩니다
VERSION_CHANNEL_ID: int = int(os.environ.get("VERSION_CHANNEL_ID", os.environ["EXPLOIT_CHANNEL_ID"]))

# ── 폴링 간격 ─────────────────────────────────────────────────
# 기본 60초 — WEAO rate limit 주의 (너무 짧게 설정하지 마세요)
POLL_INTERVAL_SECONDS: int = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))
