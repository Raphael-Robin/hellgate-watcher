import discord
from discord.ext import commands, tasks
from discord import app_commands
from src.hellgate_watcher import (
    HellgateWatcher,
    clear_battle_reports_images,
    clear_equipments_images,
)
from src.image_generator import BattleReportImageGenerator
from config import (
    BOT_COMMAND_PREFIX,
    BATTLE_CHECK_INTERVAL_MINUTES,
)
from src.database import get_channels, add_channel, remove_channel, DBChannel
from src.utils import logger





# DISCORD BOT

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=BOT_COMMAND_PREFIX, intents=intents)


@bot.event
async def on_ready():
    logger.info(
        f"Logged in as {bot.user} (ID: {bot.user.id})"  # type: ignore
    )
    await bot.tree.sync()
    if not clear_storage.is_running():
        clear_storage.start()
    if not send_battle_reports.is_running():
        send_battle_reports.start()
    logger.info("Battle report watcher started.")


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

    await add_channel(channel_id=channel.id, server_id=interaction.guild.id, server=server, hg_type=mode)
    await interaction.response.send_message(
        f"Hellgate {mode} reports for **{server.capitalize()}** will now be sent to {channel.mention}."
    )


@tasks.loop(minutes=BATTLE_CHECK_INTERVAL_MINUTES)
async def send_battle_reports():
    logger.info("Started looking for new battle reports...")
    battles = await HellgateWatcher.get_recent_battles()
    battle_reports: dict[str, dict[str, list[str]]]= await get_battle_reports(battles)
    await verify_channels()

    for server in ["europe", "americas", "asia"]:
        for mode in ["5v5", "2v2"]:

            channels = [await get_discord_channel(dbchannel) for dbchannel in await get_channels(server=server, hg_type=mode)]

            for battle in battle_reports[server][mode]:
                for channel in channels:
                    if not channel:
                        continue
                    try:
                        await channel.send(file=discord.File(battle))   
                        logger.info(f"Sent battle {battle.removeprefix('battle_report_').removesuffix('.png')} report to {channel.name}")
                    except Exception as e:
                        logger.error(
                            f"An error occurred while sending battle report: {e}"
                        )
                        continue
    logger.info("finished sending out battle reports")


@tasks.loop(hours=2)
async def clear_storage():
    logger.info("Clearing storage...")
    clear_battle_reports_images()
    logger.info("Cleared battle reports...")
    clear_equipments_images()
    logger.info("Cleared equipment images...")


async def get_battle_reports(battles):
    battle_reports = {}
    for server in ["europe", "americas", "asia"]:
        battle_reports[server] = {}
        if "5v5" in battles[server]:
            battle_reports[server]["5v5"] = [
                await BattleReportImageGenerator.generate_battle_report_5v5(battle)
                for battle in battles[server]["5v5"]
            ]
        if "2v2" in battles[server]:
            battle_reports[server]["2v2"] = [
                await BattleReportImageGenerator.generate_battle_report_2v2(battle)
                for battle in battles[server]["2v2"]
            ]
    return battle_reports


async def verify_channels():
    for server in ["europe", "americas", "asia"]:
        for mode in ["5v5", "2v2"]:
            channels = await get_channels(server=server, hg_type=mode)
            for channel in channels:
                if not await channel_exists(channel.channel_id):
                    await remove_channel(channel)

async def channel_exists(channel_id) -> bool:
    try:
        channel = await bot.fetch_channel(channel_id)
        logger.debug(f"Found channel '{channel.name}' ({channel_id})")  # type: ignore
        return True
    except Exception as e:
        logger.error(f"Something went wrong fetching channel {channel_id}: {e}")
        return False

async def get_discord_channel(channel: DBChannel) -> discord.TextChannel | None:
    if await channel_exists(channel.channel_id):
        discord_channel = await bot.fetch_channel(channel.channel_id)
        logger.debug(f"Found channel '{discord_channel.name}' ({discord_channel.id})")  # type: ignore
        return discord_channel # type: ignore