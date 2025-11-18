import os
import requests
from PIL import Image

BASE_URL_EUROPE = "https://gameinfo-ams.albiononline.com/api/gameinfo"
RENDER_API_URL = "https://render.albiononline.com/v1/item/"


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

HEALING_WEAPONS = [
    "MAIN_HOLYSTAFF",
    "2H_HOLYSTAFF",
    "2H_DIVINESTAFF",
    "MAIN_HOLYSTAFF_MORGANA",
    "2H_HOLYSTAFF_HELL",
    "2H_HOLYSTAFF_UNDEAD",
    "MAIN_HOLYSTAFF_AVALON",
    "2H_HOLYSTAFF_CRYSTAL",
    "MAIN_NATURESTAFF",
    "2H_NATURESTAFF",
    "2H_WILDSTAFF",
    "MAIN_NATURESTAFF_KEEPER",
    "2H_NATURESTAFF_HELL",
    "2H_NATURESTAFF_KEEPER",
    "MAIN_NATURESTAFF_AVALON",
    "MAIN_NATURESTAFF_CRYSTAL",
]

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

def printfile(list_of_battles):
    with open("output.json",'w+') as f:
        f.write(str(list_of_battles))

def get_battle_data(battle):
    
    print("getting data from battle")
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
        
    TeamA = remove_duplicates(TeamA)
    TeamB = remove_duplicates(TeamB)
      
    killers=[]
    victims=[]
    for event in battle:
        killers.append(event["Killer"]["Name"])
        victims.append(event["Victim"]["Name"])

    TeamA = sort_teams_by_class(TeamA)
    TeamB = sort_teams_by_class(TeamB)

    return {
        "TeamA": TeamA,
        "TeamB": TeamB,
        "killers": killers,
        "victims": victims
    }

def remove_duplicates(team):
    unique_team = []
    
    for player in team:
        if not player in unique_team:
            unique_team.append(player)
        
    return unique_team    

def generate_item_image_from_json(item:dict):
    
    item_image_path = f"{IMAGE_FOLDER}/items/{item["Type"]}&{item["Quality"]}.png"
    print(f"fetching {item_image_path}")
    if os.path.exists(item_image_path):
        return item_image_path

    request = f"{RENDER_API_URL}{item['Type']}.png?quality={item['Quality']}"
    image = requests.get(request,timeout=30).content
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

    equipment_image_path = f"{IMAGE_FOLDER}/equipments/{image_name}.png"

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

def sort_teams_by_class(team):
    print('sorting team')

    sorted_team = []

    for player in team:
        if player not in sorted_team and "PLATE" in player["equipment"]["Armor"]["Type"] and not "PLATE_ROYAL" in player["equipment"]["Armor"]["Type"] :
            sorted_team.append(player)

    for player in team:
        if player not in sorted_team and "PLATE_ROYAL" in player["equipment"]["Armor"]["Type"]:
            sorted_team.append(player)

    for player in team:
        if player not in sorted_team and "LEATHER" in player["equipment"]["Armor"]["Type"]  and not is_healer(player):
            sorted_team.append(player)

    for player in team:
        if player not in sorted_team and not is_healer(player):
            sorted_team.append(player)

    for player in team:
        if player not in sorted_team and is_healer(player):
            sorted_team.append(player)

    for player in team:
        if player not in sorted_team:
            sorted_team.append(player)
            
    return sorted_team
    
def is_healer(player):
    weapon = player["equipment"]["MainHand"]["Type"][3:].split('@')[0]
    if weapon in HEALING_WEAPONS:
        return True
    return False
