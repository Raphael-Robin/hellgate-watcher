import discord
from discord.ext import commands,tasks
from hellgate_watcher import get_recent_battle_reports
import dotenv,os,json
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
    
    channels_map = load_channels()
    
    for channel_id in channels_map.values():
        channel = bot.get_channel(channel_id)
        
        if channel and channel.permissions_for(channel.guild.me).send_messages:
            for battle_report_path in battle_reports:
                try:
                    with open(battle_report_path, 'rb') as f:
                        file_name = battle_report_path.split('/')[-1]
                        battle_report = discord.File(f, filename=file_name)
                        await channel.send(file=battle_report)
                        print(f"Sent battle report ({file_name}) to channel {channel.name} ({channel_id})")
                except FileNotFoundError:
                    print(f"Error: Battle report file not found at {battle_report_path}")
                except discord.HTTPException as e:
                    print(f"Error sending message to channel {channel.name} ({channel_id}): {e}")

@tasks.loop(hours=24)
async def clear_storage():
    config.clear_battle_reports_images()
    config.clear_equipments_images()
    config.clear_covered_battles()

