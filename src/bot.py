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
        f"[{get_current_time_formatted()}]\tLogged in as {bot.user} (ID: {bot.user.id})"
    )
    await bot.tree.sync()
    if not check_for_new_battles.is_running():
        check_for_new_battles.start()
    print(f"[{get_current_time_formatted()}]\tBattle report watcher started.")


# COMMANDS


@commands.has_permissions(administrator=True)
@bot.tree.command(name="setchannel", description="Sets the channel for hellgate battle reports.")
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
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    if not channel.permissions_for(interaction.guild.me).send_messages:
        await interaction.response.send_message("I don't have permissions to send messages in that channel.", ephemeral=True)
        return

    channels_map = load_channels()
    channels_map.setdefault(server, {}).setdefault(mode, {})[str(interaction.guild.id)] = channel.id
    save_channels(channels_map)
    await interaction.response.send_message(f"Hellgate {mode} reports for **{server.capitalize()}** will now be sent to {channel.mention}.")


@tasks.loop(minutes=BATTLE_CHECK_INTERVAL_MINUTES)
async def check_for_new_battles():
    print(f"[{get_current_time_formatted()}]\tChecking for new battle reports...")
    recent_hellgates = await HellgateWatcher.get_recent_battles()

    channels_per_server = load_channels()

    for server in ["europe", "americas", "asia"]:
        if server not in channels_per_server:
            continue
        server_channels = channels_per_server.get(server, {})
        for mode in ["5v5", "2v2"]:
            if mode not in server_channels:
                continue
            channels_map = server_channels.get(mode, {})
            if not recent_hellgates[server][mode]:
                continue

            for channel_id in channels_map.values():
                try:
                    channel = await bot.fetch_channel(channel_id)
                    if VERBOSE_LOGGING:
                        print(
                            f"[{get_current_time_formatted()}]\tFound channel '{channel.name}' ({channel_id})"
                        )
                except discord.NotFound:
                    if VERBOSE_LOGGING:
                        print(
                            f"[{get_current_time_formatted()}]\tChannel {channel_id} not found. Skipping."
                        )
                    continue
                except discord.Forbidden:
                    if VERBOSE_LOGGING:
                        print(
                            f"[{get_current_time_formatted()}]\tNo permission to fetch channel {channel_id}. Skipping."
                        )
                    continue

                if channel.permissions_for(channel.guild.me).send_messages:
                    battle_reports = []

                    if mode == "5v5":
                        battle_reports = await BattleReportImageGenerator.generate_battle_reports_5v5(
                            recent_hellgates[server][mode]
                        )
                    elif mode == "2v2":
                        battle_reports = await BattleReportImageGenerator.generate_battle_reports_2v2(
                            recent_hellgates[server][mode]
                        )

                    for battle_report_path in battle_reports:
                        try:
                            with open(battle_report_path, "rb") as f:
                                file_name = os.path.basename(battle_report_path)
                                battle_report = discord.File(f, filename=file_name)
                                await channel.send(file=battle_report)
                                print(
                                    f"[{get_current_time_formatted()}]\tSent battle report ({file_name}) to channel {channel.name} ({channel_id})"
                                )
                        except FileNotFoundError:
                            print(
                                f"[{get_current_time_formatted()}]\tError: Battle report file not found at {battle_report_path}"
                            )
                        except discord.HTTPException as e:
                            print(
                                f"[{get_current_time_formatted()}]\tError sending message to channel {channel.name} ({channel_id}): {e}"
                            )
                else:
                    print(
                        f"[{get_current_time_formatted()}]\tNo permission to send messages in channel {channel.name} ({channel_id}). Skipping."
                    )
    print(
        f"[{get_current_time_formatted()}]\tFinished checking for new battle reports."
    )


@tasks.loop(hours=24)
async def clear_storage():
    print(f"[{get_current_time_formatted()}]\tClearing storage...")
    clear_battle_reports_images()
    clear_equipments_images()
    clear_reported_battles()
