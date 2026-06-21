import os
import json
import discord
import requests
from discord.ext import tasks
from keep_alive import keep_alive

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

VERSION_FILE = "version.json"
EXPLOIT_FILE = "exploit_status.json"

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# ---------------- Roblox Version ----------------

def get_current_version():
    try:
        response = requests.get(
            "https://weao.xyz/api/versions/current",
            headers={"User-Agent": "WEAO-3PService"},
            timeout=10
        )
        return response.json()["Windows"]
    except:
        return None


def load_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r") as f:
            return json.load(f).get("version")
    return None


def save_version(version):
    with open(VERSION_FILE, "w") as f:
        json.dump({"version": version}, f)


@tasks.loop(minutes=1)
async def check_roblox_version():

    current_version = get_current_version()

    if current_version is None:
        return

    saved_version = load_version()

    if saved_version is None:
        save_version(current_version)
        return

    if current_version != saved_version:

        embed = discord.Embed(
            title="🚨 Roblox 업데이트 감지",
            color=0x00ff00
        )

        embed.add_field(
            name="📦 이전 버전",
            value=f"`{saved_version}`",
            inline=False
        )

        embed.add_field(
            name="🆕 현재 버전",
            value=f"`{current_version}`",
            inline=False
        )

        embed.timestamp = discord.utils.utcnow()

        channel = client.get_channel(CHANNEL_ID)

        if channel:
            await channel.send(embed=embed)

        save_version(current_version)


# ---------------- WEAO ----------------

def get_exploit_status():
    try:
        response = requests.get(
            "https://weao.xyz/api/status/exploits",
            headers={"User-Agent": "WEAO-3PService"},
            timeout=10
        )
        return response.json()
    except:
        return []


def load_exploit_data():
    if os.path.exists(EXPLOIT_FILE):
        with open(EXPLOIT_FILE, "r") as f:
            return json.load(f)
    return {}


def save_exploit_data(data):
    with open(EXPLOIT_FILE, "w") as f:
        json.dump(data, f, indent=4)


def format_update_status(status):
    if status is True:
        return "🟡 Updating"
    elif status is False:
        return "🟢 Updated"
    return "⚪ Unknown"


def format_detected_status(status):
    if status is True:
        return "🔴 Detected"
    elif status is False:
        return "🟢 Undetected"
    return "⚪ Unknown"


@tasks.loop(minutes=1)
async def check_exploits():

    current_data = get_exploit_status()

    if not current_data:
        return

    saved_data = load_exploit_data()

    channel = client.get_channel(CHANNEL_ID)

    changes = []

    for exploit in current_data:

        name = exploit["title"]

        current = {
            "version": exploit.get("version"),
            "status": exploit.get("updateStatus"),
            "detected": exploit.get("detected")
        }

        if name not in saved_data:
            saved_data[name] = current
            continue

        old = saved_data[name]

        if (
            current["version"] != old["version"]
            or current["status"] != old["status"]
            or current["detected"] != old["detected"]
        ):

            changes.append({
                "name": name,
                "old_version": old["version"],
                "new_version": current["version"],
                "status": current["status"],
                "detected": current["detected"]
            })

        saved_data[name] = current

    save_exploit_data(saved_data)

    if changes and channel:

        embed = discord.Embed(
            title="🔔 Exploit 상태 변경",
            color=0x3498db
        )

        for change in changes:
            embed.add_field(
                name=change["name"],
                value=(
                    f"📦 Version\n"
                    f"`{change['old_version']}` → `{change['new_version']}`\n\n"
                    f"🛠 Status\n"
                    f"{format_update_status(change['status'])}\n\n"
                    f"🛡 Detection\n"
                    f"{format_detected_status(change['detected'])}"
                ),
                inline=False
            )

        embed.timestamp = discord.utils.utcnow()

        await channel.send(embed=embed)


@client.event
async def on_ready():
    print(f"{client.user} 로그인 완료")

    if not check_roblox_version.is_running():
        check_roblox_version.start()

    if not check_exploits.is_running():
        check_exploits.start()


keep_alive()
client.run(TOKEN)