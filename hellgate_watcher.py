from ast import mod
import os
from webbrowser import get
import requests,datetime
from PIL import Image, ImageDraw, ImageFont

BASE_URL_EUROPE = "https://gameinfo-ams.albiononline.com/api/gameinfo"

SERVER_URL = BASE_URL_EUROPE
RATE_LIMIT_DELAY_SECONDS = 0.5

IMAGE_FOLDER = "./images"

LAYOUT = {
    "Bag": (0, 0),
    "Head": (1, 0),
    "Cape": (2, 0),
    
    "MainHand": (0, 1),
    "Armor": (1, 1),
    "OffHand": (2, 1),
    
    "Potion": (0, 2),
    "Shoes": (1, 2),
    "Food": (2, 2)
}
IMAGE_SIZE = 217
CANVAS_SIZE = (3*IMAGE_SIZE, 3*IMAGE_SIZE)



def get_recent_battles(server_url, limit=50,pages=1):
    battles = []
    for x in range(pages):
        request = f"{server_url}/battles?limit={limit}&sort=recent&offset={x*limit}"
        response = requests.get(request,timeout=10).json()
        battles.extend(response)

    return battles

def find_10_man_battles (battles):
    sorted_battles = []
    for battle in battles:
        nb_players = len(battle["players"])
        if nb_players == 10:
            sorted_battles.append(battle)
    return sorted_battles



def find_5v5_battles(battles):
    hellgate_battles = []
    for battle in battles:
        if is_five_vs_five_battle(battle['id']):
            hellgate_battles.append(battle)
    return hellgate_battles


def is_five_vs_five_battle(id):
    request = f"{SERVER_URL}/events/battle/{id}"
    response = requests.get(request,timeout=10).json()
    for kill in response:
        if kill["groupMemberCount"] != 5:
            return False
    return True


def print_battle(battle_events):
    """
    Analyzes a list of Albion Online kill events, groups players into two teams
    (based on the Killer and Victim of the first event), and prints aggregated
    kills, deaths, and main weapon for each player.

    Args:
        battle_events (list): A list of kill event dictionaries from the Albion API.
    """
    
    if not battle_events:
        print("Error: No battle events found in the data.")
        return

    player_stats = {}

    def register_player(player, team_id, team_name):
        """Initializes a player in the stats dictionary if they don't exist."""
        player_id = player['Id']
        if player_id not in player_stats:
            
            # Extract Main Hand Weapon, prioritizing the Killer's/Victim's equipment
            main_hand = player.get('Equipment', {}).get('MainHand')
            weapon_name = main_hand.get('Type') if main_hand else "N/A"
            
            player_stats[player_id] = {
                'name': player['Name'],
                'weapon': weapon_name,
                'kills': 0,
                'deaths': 0,
                'team_id': team_id,
                'team_name': team_name
            }

    # --- 1. Define Team A (Killer's Side) and Team B (Victim's Side) ---
    
    first_event = battle_events[0]
    
    # Team A (Killer's primary identity)
    team_a_killer = first_event['Killer']
    # Use AllianceId > GuildId > PlayerId to define the group identity
    team_a_id = team_a_killer.get('AllianceId') or team_a_killer.get('GuildId') or team_a_killer['Id']
    team_a_tag = team_a_killer.get('AllianceTag') or team_a_killer.get('GuildName') or "SOLO"
    
    # Team B (Victim's primary identity)
    team_b_victim = first_event['Victim']
    team_b_id = team_b_victim.get('AllianceId') or team_b_victim.get('GuildId') or team_b_victim['Id']
    team_b_tag = team_b_victim.get('AllianceTag') or team_b_victim.get('GuildName') or "OPPONENTS"
    
    # If the main defining IDs are the same, use a different ID for Team B for the purpose of separation
    if team_a_id == team_b_id:
        print("Note: Killer and Victim belong to the same primary group/alliance.")
        print("For printing, players will be split based on the Killer's group vs the rest of the Participants.")
        team_b_id = 'N/A_OPPONENT_SIDE'
        team_b_tag = "OPPONENTS (Mixed/Other)"

    # --- 2. Aggregate statistics and register players ---
    
    for event in battle_events:
        killer = event['Killer']
        victim = event['Victim']
        
        # Identify the Killer's group ID for this *specific* kill event
        current_killer_group_id = killer.get('AllianceId') or killer.get('GuildId') or killer['Id']
        
        # --- Kills ---
        
        # If the Killer belongs to the dominant Team A group
        if current_killer_group_id == team_a_id:
            # Register the Killer and all GroupMembers as part of Team A
            for group_member in event['GroupMembers']:
                register_player(group_member, team_a_id, team_a_tag)
            
            register_player(killer, team_a_id, team_a_tag)
            player_stats[killer['Id']]['kills'] += 1

        # If the Killer belongs to the dominant Team B group
        elif current_killer_group_id == team_b_id:
            # Register the Killer and all GroupMembers as part of Team B
            for group_member in event['GroupMembers']:
                register_player(group_member, team_b_id, team_b_tag)
                
            register_player(killer, team_b_id, team_b_tag)
            player_stats[killer['Id']]['kills'] += 1
        
        # --- Deaths ---

        # Identify the Victim's group ID
        current_victim_group_id = victim.get('AllianceId') or victim.get('GuildId') or victim['Id']

        # If the Victim belongs to the dominant Team A group
        if current_victim_group_id == team_a_id:
             register_player(victim, team_a_id, team_a_tag)
             player_stats[victim['Id']]['deaths'] += 1

        # If the Victim belongs to the dominant Team B group (or is an unaffiliated opponent)
        else: # Treat any non-Team A victim as Team B (The Opposing Side)
             register_player(victim, team_b_id, team_b_tag)
             player_stats[victim['Id']]['deaths'] += 1


    # --- 3. Group and Sort Players for Printing ---
    
    team1_players = []
    team2_players = []
    
    for stats in player_stats.values():
        if stats['team_id'] == team_a_id:
            team1_players.append(stats)
        elif stats['team_id'] == team_b_id:
            team2_players.append(stats)

    # Sort players by Kills (descending)
    team1_players.sort(key=lambda x: x['kills'], reverse=True)
    team2_players.sort(key=lambda x: x['kills'], reverse=True)

    # --- 4. Print Output ---
    
    def print_team(header, players):
        print("\n" + "="*70)
        print(f"** {header.upper()} **")
        print("="*70)
        print(f"{'PLAYER NAME':<20} {'MAIN WEAPON':<35} {'KILLS':>5} {'DEATHS':>5}")
        print("-" * 70)
        
        if not players:
            print("No recorded players in this group from the events provided.")
            return

        for p in players:
            print(f"{p['name']:<20} {p['weapon']:<35} {p['kills']:>5} {p['deaths']:>5}")

    print(datetime.datetime.fromisoformat(battle_events[0]['TimeStamp']))
    print_team(f"TEAM 1 ({team_a_tag})", team1_players)
    print()
    print_team(f"TEAM 2 ({team_b_tag})", team2_players)
    print()
    print()
    print()

def printfile(list_of_battles):
    with open("output.json",'w+') as f:
        f.write(str(list_of_battles))

def get_battle_data(battle):
    TeamA = []
    TeamB = []
    
    kill_event = battle[0]

    killer = {
        "id": kill_event["Killer"]['Id'], 
        "name": kill_event["Killer"]['Name'], 
        "equipment": kill_event["Killer"]['Equipment']
    }

    killer_group_members = [{
        "id":player['Id'], 
        "name": player['Name'], 
        "equipment": player['Equipment']
    }for player in kill_event["Participants"]]
    
    victim = {
        "id": kill_event["Victim"]['Id'], 
        "name": kill_event["Victim"]['Name'], 
        "equipment": kill_event["Victim"]['Equipment']
    }

    TeamA.append(killer)
    TeamA.extend(killer_group_members)
    TeamB.append(victim)


    for kill_event in battle[1:]:
        victim = {
            "id": kill_event["Victim"]['Id'], 
            "name": kill_event["Victim"]['Name'], 
            "equipment": kill_event["Victim"]['Equipment']
        }

        if victim not in TeamA:
            TeamB.append(victim)

        else:
            TeamB=[]
            killer_group_members = [{
                "id":player['Id'], 
                "name": player['Name'], 
                "equipment": player['Equipment']
            }for player in kill_event["Participants"]]
            TeamB.append(killer)
            TeamB.extend(killer_group_members)
            break
    

    killers=[]
    victims=[]
    for event in battle:
        killers.append(event["Killer"]["Name"])
        victims.append(event["Victim"]["Name"])

    return {
        "TeamA": TeamA,
        "TeamB": TeamB,
        "killers": killers,
        "victims": victims
    }

EQUIPMENT =  {
    "MainHand": {
    "Type": "T4_MAIN_HOLYSTAFF@2",
    "Count": 1,
    "Quality": 4,
    "ActiveSpells": [],
    "PassiveSpells": [],
    "LegendarySoul": None
    },
    "OffHand": {
    "Type": "T4_OFF_HORN_KEEPER@2",
    "Count": 1,
    "Quality": 4,
    "ActiveSpells": [],
    "PassiveSpells": [],
    "LegendarySoul": None
    },
    "Head": {
    "Type": "T4_HEAD_PLATE_SET3@2",
    "Count": 1,
    "Quality": 4,
    "ActiveSpells": [],
    "PassiveSpells": [],
    "LegendarySoul": None
    },
    "Armor": {
    "Type": "T4_ARMOR_CLOTH_SET2@2",
    "Count": 1,
    "Quality": 4,
    "ActiveSpells": [],
    "PassiveSpells": [],
    "LegendarySoul": None
    },
    "Shoes": {
    "Type": "T4_SHOES_CLOTH_SET1@2",
    "Count": 1,
    "Quality": 2,
    "ActiveSpells": [],
    "PassiveSpells": [],
    "LegendarySoul": None
    },
    "Bag": {
    "Type": "T5_BAG",
    "Count": 1,
    "Quality": 2,
    "ActiveSpells": [],
    "PassiveSpells": [],
    "LegendarySoul": None
    },
    "Cape": {
    "Type": "T4_CAPEITEM_FW_LYMHURST",
    "Count": 1,
    "Quality": 2,
    "ActiveSpells": [],
    "PassiveSpells": [],
    "LegendarySoul": None
    },
    "Mount": None,
    "Potion": {
    "Type": "T7_POTION_STONESKIN@1",
    "Count": 1,
    "Quality": 0,
    "ActiveSpells": [],
    "PassiveSpells": [],
    "LegendarySoul": None
    },
    "Food": None
}

RENDER_API_URL = "https://render.albiononline.com/v1/item/"

def generate_item_image_from_json(item:dict):
    
    item_image_path = f"{IMAGE_FOLDER}/items/{item["Type"]}&{item["Quality"]}.png"
    print(f"fetching {item_image_path}")
    if os.path.exists(item_image_path):
        return item_image_path

    request = f"{RENDER_API_URL}{item['Type']}.png?quality={item['Quality']}"
    image = requests.get(request,timeout=15).content
    with open(item_image_path,'wb') as f:
        f.write(image)
    return item_image_path

def generate_equipment_image_from_json(equipment_json:dict):
    images = {}

    for item_slot,item in equipment_json.items():
        if item is None:
            continue

        image = generate_item_image_from_json(item)
        images[item_slot] = image

    equipment_image = Image.new('RGB',CANVAS_SIZE, (40,40,40,255))

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

    equipment_image_path = f"{IMAGE_FOLDER}/equipment/{image_name}.png"

    equipment_image.save(equipment_image_path)
    return equipment_image_path
            

def generate_battle_report_image(battle_events,id):
    
    data = get_battle_data(battle_events)
    
    teamA_equipment_images = []
    teamB_equipment_images = []

    for player in data["TeamA"]:
        teamA_equipment_images.append(generate_equipment_image_from_json(player["equipment"]))
    for player in data["TeamB"]:
        teamB_equipment_images.append(generate_equipment_image_from_json(player["equipment"]))


    IMAGE_SIZE = 651
    CANVAS_SIZE = (3255, 1953)
    
    battle_report_image = Image.new('RGB',CANVAS_SIZE, (40,40,40,255))

    coords = (0,0)
    for image in teamA_equipment_images:
        item_image = Image.open(image).convert('RGBA')
        R, G, B, A = item_image.split()
        battle_report_image.paste(item_image,coords,A)
        coords = (coords[0]+IMAGE_SIZE,coords[1])

    coords = (0,1302)
    for image in teamB_equipment_images:
        item_image = Image.open(image).convert('RGBA')
        R, G, B, A = item_image.split()
        battle_report_image.paste(item_image,coords,A)
        coords = (coords[0]+IMAGE_SIZE,coords[1])

    battle_report_image_path = f"{IMAGE_FOLDER}/battle_reports/battle_report_{id}.png"
    battle_report_image.save(battle_report_image_path)
    return battle_report_image_path


    


    




if __name__ == "__main__":
    battles = get_recent_battles(SERVER_URL,limit=50,pages=1)
    print(f"Parsed {len(battles)} Battles")
    battles = find_10_man_battles(battles)
    print(f"Found {len(battles)} battles with 10 players")
    battles = find_5v5_battles(battles)
    print(f"Found {len(battles)} 5v5 battles")

    print("Battles =====================================")
    for battle in battles:
        id = battle["id"]
        b = requests.get(f"{SERVER_URL}/events/battle/{id}").json()
        generate_battle_report_image(b,id)
