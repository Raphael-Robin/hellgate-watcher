import os
from datetime import datetime
from typing import List, Dict, Any
from pymongo import MongoClient, UpdateOne, ASCENDING, DESCENDING
from pymongo.errors import BulkWriteError
from src.albion_objects import Battle, Player, Equipment, Item, Slot


# Load environment variables (ensure you have python-dotenv installed if using .env)
# from dotenv import load_dotenv
# load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "AlbionBattles")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
battles_col = db["battles"]
players_col = db["players"]
equipments_col = db["equipments"]

# Ensure Indexes (Run this once or on startup)
def init_indexes():
    # Battles: Query by ID and Time
    battles_col.create_index([("id", ASCENDING)], unique=True)
    battles_col.create_index([("start_time", DESCENDING)])
                             
    # This 'multikey index' allows you to instantly find all battles a player was in.
    battles_col.create_index([("all_player_ids", ASCENDING)])
    
    # Players: Query by Name (for search)
    players_col.create_index([("name", ASCENDING)])
    
    # Equipments: Query by Item Type for Meta Analysis (e.g., "MainHand.type")
    equipments_col.create_index([("main_hand.type", ASCENDING)])
    equipments_col.create_index([("timestamp", DESCENDING)])
    print("Database indexes initialized.")

def format_equipment(equipment_obj) -> Dict[str, Any]:
    """Converts an Equipment object to a flat dictionary of items."""
    if not equipment_obj:
        return {}

    # Define the slots we care about matching your Equipment class attributes
    slots = ["main_hand", "off_hand", "head", "armor", "shoes", "cape", "mount", "potion", "food"]
    
    formatted_equip = {}
    for slot in slots:
        item: Item | None = getattr(equipment_obj, slot, None)
        if item is None:
            continue
        else:
            formatted_equip[slot] = item.type
        
    return formatted_equip

def save_battle_to_mongo(battle_obj: Battle):
    """
    Main entry point. Transforms the Battle object and saves to 3 collections:
    1. Players (Registry of who exists)
    2. Battles (The match history with snapshots)
    3. Equipments (Flattened list for meta analysis)
    """
    
    if not battle_obj:
        return

    # --- 1. PREPARE DATA ---
    
    all_ids = []
    if hasattr(battle_obj, "team_a_ids"):
        all_ids.extend(battle_obj.team_a_ids)
    if hasattr(battle_obj, "team_b_ids"):
        all_ids.extend(battle_obj.team_b_ids)
    
    # Basic Battle Metadata
    battle_doc = {
        "_id": battle_obj.id,  # Use Albion ID as MongoDB _id
        "id": battle_obj.id,
        "start_time": datetime.fromisoformat(battle_obj.start_time.replace("Z", "+00:00")),
        "end_time": datetime.fromisoformat(battle_obj.end_time.replace("Z", "+00:00")),
        "is_5v5": getattr(battle_obj, "is_hellgate_5v5", False),
        "is_2v2": getattr(battle_obj, "is_hellgate_2v2", False),
        "team_a": battle_obj.team_a_ids,
        "team_b": battle_obj.team_b_ids,
        "all_player_ids": all_ids,
        "players_snapshot": {} # Map: PlayerID -> {Info + Gear}
    }

    player_ops = []
    equipment_docs = []

    for player_id in all_ids:
        player = battle_obj.get_player(player_id)

        # A. Format Equipment
        formatted_gear = format_equipment(player.equipment)
        
        # B. Prepare Player Registry Update (Upsert)
        # We update the name/guild in case they changed, but keep the ID constant.
        player_update = UpdateOne(
            {"_id": player_id},
            {
                "$set": {
                    "name": player.name,
                    "last_seen": battle_doc["start_time"],
                },
                "$setOnInsert": {
                    "first_seen": battle_doc["start_time"]
                }
            },
            upsert=True
        )
        player_ops.append(player_update)

        # C. Prepare Battle Snapshot Data
        # This goes INSIDE the battle document. It freezes their stats for this specific match.
        snapshot = {
            "name": player.name,
            "average_ip": getattr(player, "average_item_power", 0),
            "team": "A" if player_id in battle_obj.team_a_ids else "B",
            "is_victim": player_id in battle_obj.victim_ids,
            "equipment": formatted_gear
        }
        battle_doc["players_snapshot"][player_id] = snapshot

        # D. Prepare Equipment/Meta Document
        # This goes into the 'equipments' collection for easy analytics 
        # (e.g. "Find all battles where MainHand was Type X")
        equip_doc = {
            "battle_id": battle_obj.id,
            "player_id": player_id,
            "timestamp": battle_doc["start_time"],
            "average_ip": getattr(player, "average_item_power", 0),
            **formatted_gear # Unpack gear to top level or keep nested
        }
        equipment_docs.append(equip_doc)

    # --- 2. EXECUTE WRITES ---

    try:
        # Save Players (Bulk Upsert)
        if player_ops:
            players_col.bulk_write(player_ops, ordered=False)

        # Save Battle (Upsert to prevent duplicates)
        battles_col.replace_one({"_id": battle_doc["_id"]}, battle_doc, upsert=True)

        # Save Equipments (Insert Only - usually we don't update these unless re-parsing)
        # We check if they exist first to avoid duplicates on re-runs
        if equipment_docs:
            # Optional: Delete existing entries for this battle before inserting to ensure cleanliness
            equipments_col.delete_many({"battle_id": battle_doc["id"]})
            equipments_col.insert_many(equipment_docs)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] DB: Saved Battle {battle_obj.id} | {len(player_ops)} Players updated.")

    except BulkWriteError as bwe:
        print(f"DB Error: {bwe.details}")
    except Exception as e:
        print(f"DB Error processing battle {battle_obj.id}: {e}")