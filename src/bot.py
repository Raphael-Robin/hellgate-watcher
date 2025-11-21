import discord
from discord.ext import commands, tasks
from src.hellgate_watcher import (
    get_battle_reports,
    clear_battle_reports_images,
    clear_equipments_images,
    clear_reported_battles,
    get_current_time_formatted,
)
import os
import json
from config import (
    CHANNELS_JSON_PATH,
    BOT_COMMAND_PREFIX,
    BATTLE_CHECK_INTERVAL_MINUTES,
    VERBOSE_LOGGING,
)


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
        f"[{get_current_time_formatted().ljust(20)}]\tLogged in as {bot.user} (ID: {bot.user.id})"
    )
    if not check_for_new_battles.is_running():
        check_for_new_battles.start()
    print(f"[{get_current_time_formatted().ljust(20)}]\tBattle report watcher started.")


# COMMANDS


@commands.has_permissions(administrator=True)
@bot.command()
async def setchannel(ctx, channel: discord.TextChannel):
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    if not ctx.guild == channel.guild:
        await ctx.send("This channel is not in this server.")
        return

    if not channel.permissions_for(ctx.guild.me).send_messages:
        await ctx.send("I do not have permission to send messages in this channel.")
        return

    channels_map = load_channels()
    guild_id_str = str(ctx.guild.id)
    channels_map[guild_id_str] = channel.id

    save_channels(channels_map)
    await ctx.send(f"Battle reports will now be sent to {channel.mention}.")


@tasks.loop(minutes=BATTLE_CHECK_INTERVAL_MINUTES)
async def check_for_new_battles():
    print(
        f"[{get_current_time_formatted().ljust(20)}]\tChecking for new battle reports..."
    )
    battle_reports = await get_battle_reports()
    if not battle_reports:
        print(
            f"[{get_current_time_formatted().ljust(20)}]\tNo new battle reports found."
        )
        return

    channels_map = load_channels()
    if not channels_map:
        if VERBOSE_LOGGING:
            print("No channels configured for battle reports.")
        return

    print(
        f"[{get_current_time_formatted().ljust(20)}] \tFound \t{len(battle_reports)} new battle reports. Checking {len(channels_map)} \tchannels."
    )

    for channel_id in channels_map.values():
        try:
            channel = await bot.fetch_channel(channel_id)
            print(
                f"[{get_current_time_formatted().ljust(20)}]\tFound channel '{channel.name}' ({channel_id})"
            )
        except discord.NotFound:
            print(
                f"[{get_current_time_formatted().ljust(20)}]\tChannel {channel_id} not found. Skipping."
            )
            continue
        except discord.Forbidden:
            print(
                f"[{get_current_time_formatted().ljust(20)}]\tNo permission to fetch channel {channel_id}. Skipping."
            )
            continue

        if channel.permissions_for(channel.guild.me).send_messages:
            for battle_report_path in battle_reports:
                try:
                    with open(battle_report_path, "rb") as f:
                        file_name = os.path.basename(battle_report_path)
                        battle_report = discord.File(f, filename=file_name)
                        await channel.send(file=battle_report)
                        print(
                            f"[{get_current_time_formatted().ljust(20)}]\tSent battle report ({file_name}) to channel {channel.name} ({channel_id})"
                        )
                except FileNotFoundError:
                    print(
                        f"[{get_current_time_formatted().ljust(20)}]\tError: Battle report file not found at {battle_report_path}"
                    )
                except discord.HTTPException as e:
                    print(
                        f"[{get_current_time_formatted().ljust(20)}]\tError sending message to channel {channel.name} ({channel_id}): {e}"
                    )
        else:
            print(
                f"[{get_current_time_formatted().ljust(20)}]\tNo permission to send messages in channel {channel.name} ({channel_id}). Skipping."
            )
    print(
        f"[{get_current_time_formatted().ljust(20)}]\tFinished checking for new battle reports."
    )


@tasks.loop(hours=24)
async def clear_storage():
    clear_battle_reports_images()
    clear_equipments_images()
    clear_reported_battles()
