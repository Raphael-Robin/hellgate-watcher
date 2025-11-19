import json
import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import datetime,timedelta
import aiohttp,asyncio
from config import *



async def get_recent_battles(server_url, limit=BATTLES_LIMIT,page=1):
    battles = []
    request = f"{server_url}/battles?limit={limit}&sort=recent&offset={page*limit}"

    battle_data = await fetch_response_from_request_url(request, return_json=True)
    if battle_data:
        battles = battle_data
    return battles

def find_10_man_battles (battles):
    ten_man_battles = []
    for battle in battles:
        nb_players = len(battle["players"])
        if nb_players == 10:
            ten_man_battles.append(battle)
    return ten_man_battles

def is_ip_capped(data):    
    team_a = data["TeamA"]
    team_b = data["TeamB"]

    for x in range(5):
        for player in team_a+team_b:
            max_ip = get_max_ip_player(player)
            if player["AverageItemPower"] > max_ip:
                print(f"Player {player["Name"]} has {int(player["AverageItemPower"])} IP, however the maximum possible IP is {int(max_ip)}")
                return False
    return True

def get_max_ip_player(player):
    equipment = player["Equipment"]
    
    overcharge_bonus = 100

    max_ip_player = 0
    max_ip_player += get_max_ip_item(equipment["MainHand"])
    max_ip_player += get_max_ip_item(equipment["OffHand"]) if equipment["OffHand"] else get_max_ip_item(equipment["MainHand"])
    max_ip_player += get_max_ip_item(equipment["Armor"])
    max_ip_player += get_max_ip_item(equipment["Head"])
    max_ip_player += get_max_ip_item(equipment["Shoes"])
    max_ip_player += get_max_ip_item(equipment["Cape"])
    max_average_ip_player = (max_ip_player + overcharge_bonus * 5) / 6
    return max_average_ip_player

def get_max_ip_item(item):
    if not item:
        return 0.
    
    item_type = item["Type"]
    item_quality = item["Quality"]
    tier = 4
    enchatment = 0
    if item_type[0].upper() == "T":
        tier = float(item_type[1])
    if item_type[-2] == "@":
        enchatment = float(item_type[-1])

    mastery_bonus_percent = tier - 4 * 5
    overcharge_bonus = 100


    base_ip = 300 + (tier+enchatment) * 100 + QUALITY_IP[str(item_quality)]
    max_ip = base_ip + (120 * 2 + 36 * 2 + 48 + 3 * 7) * (1 + mastery_bonus_percent / 100)
    max_ip = add_5v5_ip_softcap(max_ip)
    return max_ip + 1

def add_5v5_ip_softcap(ip):
    SOFTCAP_PERCENT = 35
    IP_CAP = 1100

    if ip > IP_CAP:
        return IP_CAP + (ip - IP_CAP) * (SOFTCAP_PERCENT / 100)
    else:
        return ip

def get_battle_data(battle_events):
    """
    Analyzes a list of battle events to determine the teams, deaths, and player equipment.

    This function makes the following assumptions for a 10-player battle:
    - A Killer and a Victim are never on the same Team.
    - A Killer's GroupMembers are always on their Team.
    - All players must be on a Team.
    - All Teams must have 5 players.
    - Player equipment is most accurately found in the 'Participants' list or 'Killer'/'Victim' objects.
    """
    if not battle_events:
        return {"TeamA": [], "TeamB": [], "killers": [], "victims": []}

    players = {}  # {player_id: {name, equipment, id, ...}}
    
    def add_or_update_player(player_data):
        player_id = player_data.get('Id')
        if not player_id:
            return
        # Prioritize data with equipment, as it can be missing in some parts of the event data
        if player_id not in players:
            players[player_id] = {
                "Id": player_id,
                "Name": player_data.get('Name'),
                "Equipment": player_data.get('Equipment'),
                "guild": player_data.get("GuildName"),
                "alliance": player_data.get("AllianceName"),
                "AverageItemPower": player_data.get("AverageItemPower")
            }
        else:
            existing_player = players[player_id]
            for item in existing_player["Equipment"].keys():
                if existing_player["Equipment"][item] is None:
                    existing_player["Equipment"][item] = player_data["Equipment"][item]

    

    # 1. Collect all players and their most recent data from all events.
    # Participants list and killer/victim objects are good sources for equipment.
    for event in battle_events:
        add_or_update_player(event['Killer'])
        add_or_update_player(event['Victim'])
        for participant in event['Participants']:
            add_or_update_player(participant)
        for group_member in event['GroupMembers']:
            add_or_update_player(group_member)

    all_player_ids = set(players.keys())
    
    team_a_ids = set()
    team_b_ids = set()

    # 2. Determine teams based on event interactions.
    if not all_player_ids:
        return {"TeamA": [], "TeamB": [], "killers": [], "victims": []}

    # Seed the teams with the first event's killer.
    if battle_events:
        first_killer_id = battle_events[0]['Killer']['Id']
        if first_killer_id in all_player_ids:
            team_a_ids.add(first_killer_id)

    # Iteratively assign players to teams until the assignments are stable.
    for _ in range(len(all_player_ids) + 1): 
        for event in battle_events:
            killer_id = event['Killer']['Id']
            victim_id = event['Victim']['Id']
            
            group_member_ids = {p['Id'] for p in event['GroupMembers']}

            if killer_id in team_a_ids:
                team_a_ids.update(group_member_ids)
                if victim_id not in team_a_ids:
                    team_b_ids.add(victim_id)
            elif killer_id in team_b_ids:
                team_b_ids.update(group_member_ids)
                if victim_id not in team_b_ids:
                    team_a_ids.add(victim_id)
            
            if victim_id in team_a_ids:
                if killer_id not in team_a_ids:
                    team_b_ids.add(killer_id)
                    team_b_ids.update(group_member_ids)
            elif victim_id in team_b_ids:
                if killer_id not in team_b_ids:
                    team_a_ids.add(killer_id)
                    team_a_ids.update(group_member_ids)
        


    # 3. Finalize teams, assuming a 10-player battle.
    if len(all_player_ids) == 10:
        if len(team_a_ids) >= 5:
            team_b_ids.update(all_player_ids - team_a_ids)
            team_a_ids = all_player_ids - team_b_ids # Recalculate to trim extras
        elif len(team_b_ids) >= 5:
            team_a_ids.update(all_player_ids - team_b_ids)
            team_b_ids = all_player_ids - team_a_ids # Recalculate to trim extras

    # Assign any remaining unassigned players
    unassigned_ids = all_player_ids - team_a_ids - team_b_ids
    for player_id in unassigned_ids:
        if len(team_a_ids) < 5:
            team_a_ids.add(player_id)
        else:
            team_b_ids.add(player_id)

    # 4. Collect killers and victims for the final output.
    killers = [event["Killer"]["Name"] for event in battle_events]
    victims = [event["Victim"]["Name"] for event in battle_events]

    # 5. Format team lists from IDs and sort them by role.
    team_a = [players[pid] for pid in team_a_ids if pid in players]
    team_b = [players[pid] for pid in team_b_ids if pid in players]

    team_a = sort_teams_by_class(team_a)
    team_b = sort_teams_by_class(team_b)

    return {
        "TeamA": team_a,
        "TeamB": team_b,
        "killers": killers,
        "victims": victims
    }

async def generate_item_image_from_json(item:dict):
    
    item_image_path = f"{IMAGE_FOLDER}/items/{item["Type"]}&{item["Quality"]}.png"
    
    if VERBOSE_LOGGING:
        print(f"fetching {item_image_path}")

    if os.path.exists(item_image_path):
        return item_image_path

    request = f"{RENDER_API_URL}{item['Type']}.png?count=1&quality={item['Quality']}"
    image = await fetch_response_from_request_url(request, return_json=False)
    if not image: return None # Or a path to a placeholder image

    with open(item_image_path,'wb') as f:
        f.write(image)
    return item_image_path

async def generate_equipment_image_from_json(equipment_json:dict):
    images = {}

    for item_slot,item in equipment_json.items():
        if item is None:
            continue

        image = await generate_item_image_from_json(item)
        if image is None:
            continue
        images[item_slot] = image

    equipment_image = Image.new('RGB',CANVAS_SIZE, BACKGROUND_COLOR)

    for item_slot,image in images.items():
        if item_slot in LAYOUT:
            item_image = Image.open(image).convert('RGBA')
            coords = (LAYOUT[item_slot][0]*IMAGE_SIZE, LAYOUT[item_slot][1]*IMAGE_SIZE)
            R, G, B, A = item_image.split()
            equipment_image.paste(item_image,coords,A)

    image_name = ""
    for item_slot,item in equipment_json.items():
        if item is None:
            continue
        image_name += item["Type"]

    equipment_image_path = f"{IMAGE_FOLDER}/equipments/equipment_{image_name}.png"

    if VERBOSE_LOGGING:
        print(f"generating {equipment_image_path}")
    equipment_image.save(equipment_image_path)
    return equipment_image_path
            
async def generate_battle_report_image(battle_events,id):
    
    data = get_battle_data(battle_events)

    if not is_ip_capped(data):
        print("IP is not capped, skipping report")
        return None

    if not data:
        return None
    
    battle_report_image = Image.new('RGB', BATTLE_REPORT_CANVAS_SIZE, BACKGROUND_COLOR)
    draw = ImageDraw.Draw(battle_report_image)
    
    try:
        # Using a common font, you might need to provide a path to a .ttf file
        # For bold, use a specific bold font file like 'arialbd.ttf'
        player_name_font = ImageFont.truetype(PLAYER_NAME_FONT_PATH, PLAYER_NAME_FONT_SIZE) # Keep player name font size
        timestamp_font = ImageFont.truetype(TIMESTAMP_FONT_PATH, TIMESTAMP_FONT_SIZE) # Increased font size for timestamp
    except IOError:
        print("Arial font not found. Using default font.")
        player_name_font = ImageFont.load_default()
        timestamp_font = ImageFont.load_default()

    dead_players = set(data["victims"])

    # --- Draw Team A ---
    y_pos = TOP_BOTTOM_PADDING
    for i, player in enumerate(data["TeamA"]):
        x_pos = SIDE_PADDING + i * (EQUIPMENT_IMAGE_SIZE + SPACING)
        
        # Draw player name
        try:
            # Center the name above the equipment image
            bbox = draw.textbbox((0, 0), player["Name"], font=player_name_font)
            text_width = bbox[2] - bbox[0]
            draw.text((x_pos + (EQUIPMENT_IMAGE_SIZE - text_width) / 2, y_pos), player["Name"], font=player_name_font, fill=FONT_COLOR)
        except AttributeError: # Fallback for older Pillow versions
            draw.text((x_pos, y_pos), player["Name"], font=player_name_font, fill=FONT_COLOR)

        # Paste equipment image
        equipment_image_path = await generate_equipment_image_from_json(player["Equipment"])
        equipment_image = Image.open(equipment_image_path).convert('RGBA')

        # Make dead players gray
        if player["Name"] in dead_players:
            enhancer = ImageEnhance.Color(equipment_image)
            equipment_image = enhancer.enhance(DEAD_PLAYER_GRAYSCALE_ENHANCEMENT) 

        R, G, B, A = equipment_image.split()
        battle_report_image.paste(equipment_image, (x_pos, y_pos + PLAYER_NAME_AREA_HEIGHT), A)

    # --- Draw Team B ---
    y_pos = TOP_BOTTOM_PADDING + PLAYER_NAME_AREA_HEIGHT + EQUIPMENT_IMAGE_SIZE + MIDDLE_GAP
    for i, player in enumerate(data["TeamB"]):
        x_pos = SIDE_PADDING + i * (EQUIPMENT_IMAGE_SIZE + SPACING)

        # Draw player name
        try:
            # Center the name above the equipment image
            bbox = draw.textbbox((0, 0), player["Name"], font=player_name_font)
            text_width = bbox[2] - bbox[0]
            draw.text((x_pos + (EQUIPMENT_IMAGE_SIZE - text_width) / 2, y_pos), player["Name"], font=player_name_font, fill=(255, 255, 255))
        except AttributeError: # Fallback for older Pillow versions
            draw.text((x_pos, y_pos), player["Name"], font=player_name_font, fill=(255, 255, 255))

        # Paste equipment image
        equipment_image_path = await generate_equipment_image_from_json(player["Equipment"])
        equipment_image = Image.open(equipment_image_path).convert('RGBA')

        # Make dead players gray
        if player["Name"] in dead_players:
            enhancer = ImageEnhance.Color(equipment_image)
            equipment_image = enhancer.enhance(0.3)


        R, G, B, A = equipment_image.split()
        battle_report_image.paste(equipment_image, (x_pos, y_pos + PLAYER_NAME_AREA_HEIGHT), A)

    # --- Draw Timestamp ---
    if battle_events:
        # Parse timestamps from the event data
        start_time = datetime.fromisoformat(battle_events[0]['TimeStamp'].replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(battle_events[-1]['TimeStamp'].replace('Z', '+00:00'))
        
        # Calculate duration
        duration = end_time - start_time
        duration_minutes = int(duration.total_seconds() // 60)
        duration_seconds = int(duration.total_seconds() % 60)

        # Format the text strings
        start_time_text = f"Start Time: {start_time.strftime('%H:%M:%S')} UTC"
        duration_text = f"Duration: {duration_minutes:02d}m {duration_seconds:02d}s"

        # Calculate text position for centering
        timestamp_y = TOP_BOTTOM_PADDING + PLAYER_NAME_AREA_HEIGHT + EQUIPMENT_IMAGE_SIZE + (MIDDLE_GAP // 2)
        
        # Using textbbox for better centering if available (Pillow >= 8.0.0)
        try:
            start_bbox = draw.textbbox((0, 0), start_time_text, font=timestamp_font)
            start_text_width = start_bbox[2] - start_bbox[0]
            text_height = start_bbox[3] - start_bbox[1] # Height of a single line of text

            # Calculate vertical positions for centered text with spacing
            start_text_y = timestamp_y - (text_height + LINE_SPACING) / 2
            duration_text_y = start_text_y + text_height + LINE_SPACING

            draw.text(((CANVAS_WIDTH - start_text_width) / 2, start_text_y), start_time_text, font=timestamp_font, fill=(255, 255, 255))

            duration_bbox = draw.textbbox((0, 0), duration_text, font=timestamp_font)
            duration_text_width = duration_bbox[2] - duration_bbox[0]
            draw.text(((CANVAS_WIDTH - duration_text_width) / 2, duration_text_y), duration_text, font=timestamp_font, fill=(255, 255, 255))
        except AttributeError: # Fallback for older Pillow versions
            draw.text((CANVAS_WIDTH / 2 - 400, timestamp_y - 50), start_time_text, font=timestamp_font, fill=(255, 255, 255))
            draw.text((CANVAS_WIDTH / 2 - 400, timestamp_y), duration_text, font=timestamp_font, fill=(255, 255, 255))
            
    battle_report_image_path = f"{IMAGE_FOLDER}/battle_reports/battle_report_{id}.png"
    
    print(f"generating {battle_report_image_path}")
    battle_report_image.save(battle_report_image_path)
    return battle_report_image_path

def sort_teams_by_class(team):
    unknown = []
    tanks = []
    melees = []
    leathers = []
    others = []
    healers = []

    for player in team:
        if player["Equipment"]["Armor"] is None:
            unknown.append(player)
            continue


        armor = player["Equipment"].get("Armor", {}).get("Type", "")
        is_player_healer = is_healer(player)

        if is_player_healer:
            healers.append(player)
        elif "PLATE_ROYAL" in armor:
            melees.append(player)
        elif "PLATE" in armor:
            tanks.append(player)
        elif "LEATHER" in armor:
            leathers.append(player)
        else:
            others.append(player)

    return unknown + tanks + melees + leathers + others + healers

def is_healer(player):
    weapon = player["Equipment"]["MainHand"]["Type"][3:].split('@')[0]
    return weapon in HEALING_WEAPONS

async def get_recent_battle_reports():
    battles = []
    battle_report_paths = []
    contains_battles_out_of_range = False
    page_number = 0

    while not contains_battles_out_of_range:
        battles.extend(await get_recent_battles(SERVER_URL,limit=BATTLES_LIMIT,page=page_number))
        # print(f"Fetching page {page_number}, {len(battles)} battles so far")
        page_number += 1
        await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
        contains_battles_out_of_range = battles_contains_battle_older_than(battles)
    
    print(f"Parsed {len(battles)} Battles")
    
    battles = find_10_man_battles(battles)
    print(f"Found {len(battles)} battles with 10 players")

    covered_battle_reports = load_covered_battles()

    for battle in battles:
        id = battle["id"]
        if id not in covered_battle_reports:
            battle_events = await fetch_response_from_request_url(f"{SERVER_URL}/events/battle/{id}", return_json=True)
            
            if not battle_events:
                continue

            is_5v5 = True
            for kill in battle_events:
                if kill.get("groupMemberCount") != 5:
                    is_5v5 = False
                    break
            
            if is_5v5:
                print(f"Found 5v5 battle: {id}")
                covered_battle_reports.append(id)
                battle_report_image_path = await generate_battle_report_image(battle_events, id)
                if battle_report_image_path:
                    battle_report_paths.append(battle_report_image_path)

    battle_report_paths.sort()
    save_covered_battles(covered_battle_reports)
    print(f"Generated {len(battle_report_paths)} battle reports")
    return battle_report_paths

def battles_contains_battle_older_than(battles,max_age= timedelta(minutes=BATTLES_MAX_AGE_MINUTES)):
    if not battles:
        return False
    startTime1 = datetime.fromisoformat(battles[0]["startTime"])
    startTime2 = datetime.fromisoformat(battles[-1]["startTime"])
    duration = abs(startTime1 - startTime2)    
    return duration >= max_age
    
def load_covered_battles():
    try:
        with open(COVERED_BATTLES_JSON_PATH, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return [] 

def save_covered_battles(covered_battles):
    with open(COVERED_BATTLES_JSON_PATH, 'w') as f:
        json.dump(covered_battles, f, indent=4)

async def fetch_response_from_request_url(url, return_json=True):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
        try:
            # Initiate the request and manage the response object
            async with session.get(url) as response:
                
                # Check for bad HTTP status codes (e.g., 404, 500)
                # This raises a ClientResponseError if the status is >= 400
                response.raise_for_status()
                
                if return_json:
                    return await response.json()
                else:
                    return await response.read()
                
        except aiohttp.ClientResponseError as e:
            # Handles 4xx and 5xx responses
            print(f"HTTP Error {e.status} for URL {url}: {e.message}")
            return None
        except aiohttp.ClientConnectorError:
            # Handles issues like DNS failures or connection refused
            print(f"Connection Error: Could not connect to {url}")
            return None
        except asyncio.TimeoutError:
            # Handles timeout errors
            print(f"Request timed out after {TIMEOUT} seconds for URL {url}")
            return None
        except aiohttp.ContentTypeError:
            # Handles cases where the response is not valid JSON
            print(f"Failed to parse JSON response from {url}")
            return None
        except Exception as e:
            # Catch all other unexpected errors
            print(f"An unexpected error occurred while fetching {url}: {e}")
            return None

def print_team_names(team):
        print([player["Name"]for player in team])

async def generate_report_image_from_id(id):
    battle_events = await fetch_response_from_request_url(f"{SERVER_URL}/events/battle/{id}", return_json=True)
    await generate_battle_report_image(battle_events,id)

async def get_battle_data_from_id(id):
    battle_events = await fetch_response_from_request_url(f"{SERVER_URL}/events/battle/{id}", return_json=True)
    return get_battle_data(battle_events)


def clear_covered_battles():
    with open(COVERED_BATTLES_JSON_PATH, 'w') as f:
        json.dump([], f, indent=4)

