import discord
from discord.ext import commands,tasks
from hellgate_watcher import get_recent_battle_reports,clear_battle_reports_images,clear_equipments_images,clear_covered_battles
import os
import json
import config

def load_channels():
    try:
        with open(config.CHANNELS_JSON_PATH, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {} 

def save_channels(channel_map):
    with open(config.CHANNELS_JSON_PATH, 'w') as f:
        json.dump(channel_map, f, indent=4)

# DISCORD BOT

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=config.BOT_COMMAND_PREFIX, intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    if not check_for_new_battles.is_running():
        check_for_new_battles.start()
    print('Battle report watcher started.')

# COMMANDS
 
@commands.has_permissions(administrator=True)
@bot.command()
async def setchannel(ctx, channel: discord.TextChannel):
    if not ctx.guild:
        await ctx.send('This command can only be used in a server.')
        return
    
    if not ctx.guild == channel.guild:
        await ctx.send('This channel is not in this server.')
        return

    if not channel.permissions_for(ctx.guild.me).send_messages:
        await ctx.send('I do not have permission to send messages in this channel.')
        return

    channels_map = load_channels()
    guild_id_str = str(ctx.guild.id)
    channels_map[guild_id_str] = channel.id
    
    save_channels(channels_map)
    await ctx.send(f'Battle reports will now be sent to {channel.mention}.')

@tasks.loop(minutes=config.BATTLE_CHECK_INTERVAL_MINUTES)
async def check_for_new_battles():
    battle_reports = await get_recent_battle_reports()
    if not battle_reports:
        if config.VERBOSE_LOGGING:
            print("No new battle reports found.")
        return

    channels_map = load_channels()
    if not channels_map:
        if config.VERBOSE_LOGGING:
            print("No channels configured for battle reports.")
        return

    print(f"Found {len(battle_reports)} new battle reports. Checking {len(channels_map)} channels.")

    for channel_id in channels_map.values():
        try:
            channel = await bot.fetch_channel(channel_id)
            print(f"Found channel '{channel.name}' ({channel_id})")
        except discord.NotFound:
            print(f"Channel {channel_id} not found. Skipping.")
            continue
        except discord.Forbidden:
            print(f"No permission to fetch channel {channel_id}. Skipping.")
            continue

        if channel.permissions_for(channel.guild.me).send_messages:
            for battle_report_path in battle_reports:
                try:
                    with open(battle_report_path, 'rb') as f:
                        file_name = os.path.basename(battle_report_path)
                        battle_report = discord.File(f, filename=file_name)
                        await channel.send(file=battle_report)
                        print(f"Sent battle report ({file_name}) to channel {channel.name} ({channel_id})")
                except FileNotFoundError:
                    print(f"Error: Battle report file not found at {battle_report_path}")
                except discord.HTTPException as e:
                    print(f"Error sending message to channel {channel.name} ({channel_id}): {e}")
        else:
            print(f"No permission to send messages in channel {channel.name} ({channel_id}). Skipping.")

@tasks.loop(hours=24)
async def clear_storage():
    clear_battle_reports_images()
    clear_equipments_images()
    clear_covered_battles()

