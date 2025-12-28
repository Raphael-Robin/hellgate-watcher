import discord
from discord.ext import commands, tasks
from discord import app_commands
from src.hellgate_watcher import (
    BattleReportImageGenerator,
    HellgateWatcher,
    clear_battle_reports_images,
    clear_equipments_images,
    clear_reported_battles,
)
import os
import json
from config import (
    CHANNELS_JSON_PATH,
    BOT_COMMAND_PREFIX,
    BATTLE_CHECK_INTERVAL_MINUTES,
    VERBOSE_LOGGING,
)
from src.utils import get_current_time_formatted


def load_channels():
    try:
        with open(CHANNELS_JSON_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_channels(channel_map):
    directory = os.path.dirname(CHANNELS_JSON_PATH)
    os.makedirs(directory, exist_ok=True)
    with open(CHANNELS_JSON_PATH, "w") as f:
        json.dump(channel_map, f, indent=4)


# DISCORD BOT

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=BOT_COMMAND_PREFIX, intents=intents)


@bot.event
async def on_ready():
    print(
        f"[{get_current_time_formatted()}]\tLogged in as {bot.user} (ID: {bot.user.id})" # type: ignore
    )
    await bot.tree.sync()
    if not clear_storage.is_running():
        clear_storage.start()
    if not send_battle_reports.is_running():
        send_battle_reports.start()
    print(f"[{get_current_time_formatted()}]\tBattle report watcher started.")


# COMMANDS


@commands.has_permissions(administrator=True)
@bot.tree.command(
    name="setchannel", description="Sets the channel for hellgate battle reports."
)
@app_commands.describe(
    server="The server to get reports from.",
    mode="The hellgate mode (2v2 or 5v5).",
    channel="The channel where reports will be sent.",
)
@app_commands.choices(
    server=[
        app_commands.Choice(name="Europe", value="europe"),
        app_commands.Choice(name="Americas", value="americas"),
        app_commands.Choice(name="Asia", value="asia"),
    ],
    mode=[
        app_commands.Choice(name="5v5", value="5v5"),
        app_commands.Choice(name="2v2", value="2v2"),
    ],
)
async def setchannel(
    interaction: discord.Interaction,
    server: str,
    mode: str,
    channel: discord.TextChannel,
):
    if not interaction.guild:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return

    if not channel.permissions_for(interaction.guild.me).send_messages:
        await interaction.response.send_message(
            "I don't have permissions to send messages in that channel.", ephemeral=True
        )
        return

    channels_map = load_channels()
    channels_map.setdefault(server, {}).setdefault(mode, {})[
        str(interaction.guild.id)
    ] = channel.id
    save_channels(channels_map)
    await interaction.response.send_message(
        f"Hellgate {mode} reports for **{server.capitalize()}** will now be sent to {channel.mention}."
    )

@tasks.loop(minutes=BATTLE_CHECK_INTERVAL_MINUTES)
async def send_battle_reports():
    print(f"[{get_current_time_formatted()}]\tStarted looking for new battle reports...")
    battles = await HellgateWatcher.get_recent_battles()
    battle_reports = await get_battle_reports(battles)
    channels = await get_verified_channels()

    for server in ["europe", "americas", "asia"]:
        for mode in ["5v5", "2v2"]:
            for battle in battle_reports[server][mode]:
                for channel in channels[server][mode]:
                    try:
                        await channel.send(file=discord.File(battle))
                        print(
                            f"[{get_current_time_formatted()}]\tSent battle report to {channel.name}"
                        )
                    except Exception as e:
                        print(
                            f"[{get_current_time_formatted()}]\tAn error occurred while sending battle report: {e}"
                        )
                        continue
    print(f"[{get_current_time_formatted()}]\tfinished sending out battle reports")

@tasks.loop(hours=2)
async def clear_storage():
    print(f"[{get_current_time_formatted()}]\tClearing storage...")
    clear_battle_reports_images()
    print(f"[{get_current_time_formatted()}]\tCleared battle reports...")
    clear_equipments_images()
    print(f"[{get_current_time_formatted()}]\tCleared equipment images...")
    clear_reported_battles()
    print(f"[{get_current_time_formatted()}]\tClearing reported battles json...")

async def get_battle_reports(battles):
    battle_reports = {}
    for server in ["europe", "americas", "asia"]:
        battle_reports[server] = {}
        if "5v5" in battles[server]:
            battle_reports[server]["5v5"] = [await BattleReportImageGenerator.generate_battle_report_5v5(battle) for battle in battles[server]["5v5"]] 
        if "2v2" in battles[server]:
            battle_reports[server]["2v2"] = [await BattleReportImageGenerator.generate_battle_report_2v2(battle) for battle in battles[server]["2v2"]] 
    return battle_reports

async def get_verified_channels():
    channels_map = load_channels()
    verified_channels = {}
    for server in ["europe", "americas", "asia"]:
        if server not in channels_map:
            continue
        verified_channels[server] = {}
        for mode in ["5v5", "2v2"]:
            if mode not in channels_map[server]:
                continue
            verified_channels[server][mode] = []

            for channel_id in channels_map[server][mode].values():
                channel = await verify_channel(channel_id)
                if channel:
                    verified_channels[server][mode].append(channel)
    return verified_channels

async def verify_channel(channel_id) -> discord.TextChannel | None:
    try:
        channel = await bot.fetch_channel(channel_id)
        if VERBOSE_LOGGING:
            print(
                f"[{get_current_time_formatted()}]\tFound channel '{channel.name}' ({channel_id})" # type: ignore
            )
    except discord.NotFound:
        if VERBOSE_LOGGING:
            print(
                f"[{get_current_time_formatted()}]\tChannel {channel_id} not found. Skipping."
            )
        return None
    except discord.Forbidden:
        if VERBOSE_LOGGING:
            print(
                f"[{get_current_time_formatted()}]\tNo permission to fetch channel {channel_id}. Skipping."
            )
        return None
    except Exception as e:
        if VERBOSE_LOGGING:
            print(
                f"[{get_current_time_formatted()}]\tAn error occurred while fetching channel {channel_id}: {e}"
            )
        return None

    if not channel.permissions_for(channel.guild.me).send_messages:
        print(
            f"[{get_current_time_formatted()}]\tNo permission to send messages in channel {channel.name} ({channel_id}). Skipping."
        )
        return None
    
    return channel

