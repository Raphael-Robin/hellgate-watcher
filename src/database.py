import hashlib
import os
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from itertools import combinations
from pydantic import BaseModel, Field
from pymongo import MongoClient, collation

# Assuming your directory structure allows this import
from src.albion_objects import Battle, Equipment, Item, Player, Slot

# --- Configuration ---

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["hellgate_watcher"]

# --- Pydantic Models for Database ---

class DBEquipment(BaseModel):
    """Stores the unique combination of items as a 'Build'"""
    id: str = Field(alias="_id")  # equipment_hash_id
    main_hand: Optional[str] = None
    off_hand: Optional[str] = None
    head: Optional[str] = None
    armor: Optional[str] = None
    shoes: Optional[str] = None
    cape: Optional[str] = None
    nb_uses: int = 0
    nb_wins: int = 0
    
    def to_equipment(self) -> Equipment:
        # 1. Map the DB field names back to the Slot enum values
        # This assumes Slot.MainHand.value is the key the Equipment class expects
        equipment_dict = {
            Slot.MainHand.value: {"Type": f"T7_{self.main_hand}", "Quality": 4} if self.main_hand else None,
            Slot.OffHand.value: {"Type": f"T7_{self.off_hand}", "Quality": 4} if self.off_hand else None,
            Slot.Head.value: {"Type": f"T7_{self.head}", "Quality": 4} if self.head else None,
            Slot.Armor.value: {"Type": f"T7_{self.armor}", "Quality": 4} if self.armor else None,
            Slot.Shoes.value: {"Type": f"T7_{self.shoes}", "Quality": 4} if self.shoes else None,
            Slot.Cape.value: {"Type": f"T7_{self.cape}", "Quality": 4} if self.cape else None,
        }
        return Equipment(equipment_dict)

class DBPlayer(BaseModel):
    """Unique registry of players"""
    id: str = Field(alias="_id")  # player_id
    name: str
    first_seen: datetime
    last_seen: datetime
    nb_battles: int = 0
    nb_wins: int = 0
    nb_losses: int = 0
    server: str

class DBTeam(BaseModel):
    """Tracks consistency of specific 5-man or 2-man rosters"""
    id: str = Field(alias="_id")  # player_ids_hash
    player_ids: List[str]
    nb_battles: int = 0
    nb_wins: int = 0
    nb_losses: int = 0

class DBPlayer_Equipment_Use(BaseModel):
    """Tracks how many times a specific player used a specific build"""
    id: str = Field(alias="_id")  # player_id_equipment_hash_id
    player_id: str
    equipment_hash_id: str
    nb_uses: int = 0
    nb_wins: int = 0
    last_used: datetime

    def get_player(self) -> DBPlayer:
        player = get_player_by_id(self.player_id)
        if player:
            return player
        else:
            raise Exception(f"Player with ID {self.player_id} not found")
        
    def get_equipment(self) -> DBEquipment:
        equipment = get_equipment_by_hash(self.equipment_hash_id)
        if equipment:
            return equipment
        else:
            raise Exception(f"Equipment with ID {self.equipment_hash_id} not found")
        
    
class DBPlayer_Relationship(BaseModel):
    """Social graph to find 'who plays with who' (Rotating 5th logic)"""
    id: str = Field(alias="_id")  # sorted_pair_hash
    players: List[str]  # [PlayerA_ID, PlayerB_ID]
    nb_shared_battles: int = 0
    shared_wins: int = 0
    last_seen: datetime

    def get_players(self) -> Tuple[DBPlayer, DBPlayer]:
        player_a = get_player_by_id(self.players[0])
        player_b = get_player_by_id(self.players[1])
        if player_a and player_b:
            return player_a, player_b
        else:
            raise Exception(f"Player(s) with ID(s) {self.players} not found")
        
    def get_other_player(self,player_name:str) -> DBPlayer:
        try:
            player_a, player_b = self.get_players()
            player_a, player_b = self.get_players()
            if player_a.name == player_name:
                return player_b
            elif player_b.name == player_name:
                return player_a
            else:
                raise Exception(f"Player {player_name} not found in relationship")
        except Exception as e:
            raise(e)

class DBBattle5v5(BaseModel):
    """The source of truth for every match"""
    id: int = Field(alias="_id")
    winning_team_id: str  # Hash reference to DBTeam
    losing_team_id: str   # Hash reference to DBTeam
    all_player_ids: List[str]
    winner_ids: List[str]
    loser_ids: List[str]
    # Maps player_id -> equipment_hash_id
    players_builds: Dict[str, str] 
    datetime: datetime
    server: str

# --- Helper Functions ---

def generate_equipment_hash(player_obj: Player) -> str:
    """Creates a hash based on item types (ignores tier/quality for meta tracking)"""
    items = []
    for slot in ["main_hand", "off_hand", "head", "armor", "shoes", "cape"]:
        item = getattr(player_obj.equipment, slot, None)
        items.append(item.type if item else "empty")
    return hashlib.md5("|".join(items).encode()).hexdigest()

def get_team_hash(player_ids: List[str]) -> str:
    """Generates a consistent hash for a group of players"""
    return hashlib.md5(",".join(sorted(player_ids)).encode()).hexdigest()

# --- Main Save Function ---

def save_data_from_battle(battle: Battle, server: str):
    """
    Parses a Battle object and updates all 7 collections (including item_trends).
    """
    # 1. Determine Winners vs Losers based on victims (Wipe Logic)
    team_a_ids = battle.team_a_ids
    team_b_ids = battle.team_b_ids
    victims = set(battle.victim_ids)
    
    if set(team_a_ids).issubset(victims):
        winner_ids, loser_ids = team_b_ids, team_a_ids
    else:
        winner_ids, loser_ids = team_a_ids, team_b_ids

    win_hash = get_team_hash(winner_ids)
    loss_hash = get_team_hash(loser_ids)
    battle_time = datetime.fromisoformat(battle.start_time.replace("Z", "+00:00"))

    # To track which player used which build for the Battle record
    players_builds_map = {}

    # 2. Update Teams Collection
    for team_hash, ids, won in [(win_hash, winner_ids, True), (loss_hash, loser_ids, False)]:
        db.teams.update_one(
            {"_id": team_hash},
            {
                "$setOnInsert": {"player_ids": ids},
                "$inc": {"nb_battles": 1, "nb_wins": 1 if won else 0, "nb_losses": 0 if won else 1},
                "$set": {"last_seen": battle_time}
            },
            upsert=True
        )

    # 3. Update Player, Equipment, Equipment_Uses, and Item_Trends
    all_players = [(player_id, True) for player_id in winner_ids] + [(player_id, False) for player_id in loser_ids]
    
    for player_id, won in all_players:
        player_obj = battle.get_player(player_id)
        if not player_obj: continue
        
        equipment_hash = generate_equipment_hash(player_obj)
        players_builds_map[player_id] = equipment_hash
        
        # Player Registry
        db.players.update_one(
            {"_id": player_id},
            {
                "$set": {"name": player_obj.name, "last_seen": battle_time},
                "$setOnInsert": {"first_seen": battle_time, "server": server},
                "$inc": {"nb_wins": 1 if won else 0, "nb_losses": 0 if won else 1, "nb_battles": 1}
            },
            upsert=True
        )

        # Global Equipment Meta
        db.equipments.update_one(
            {"_id": equipment_hash},
            {   
                "$inc": {
                    "nb_uses": 1, 
                    "nb_wins": 1 if won else 0
                },
                "$setOnInsert": {
                    "main_hand": player_obj.equipment.mainhand.type if player_obj.equipment.mainhand else None,
                    "off_hand": player_obj.equipment.offhand.type if player_obj.equipment.offhand else None,
                    "head": player_obj.equipment.head.type if player_obj.equipment.head else None,
                    "armor": player_obj.equipment.armor.type if player_obj.equipment.armor else None,
                    "shoes": player_obj.equipment.shoes.type if player_obj.equipment.shoes else None,
                    "cape": player_obj.equipment.cape.type if player_obj.equipment.cape else None,
                }
            },
            upsert=True
        )

        # Player-Specific Equipment Usage
        db.player_equipment_uses.update_one(
            {"_id": f"{player_id}_{equipment_hash}"},
            {
                "$set": {"player_id": player_id, "equipment_hash_id": equipment_hash, "last_used": battle_time},
                "$inc": {"nb_uses": 1, "nb_wins": 1 if won else 0}
            },
            upsert=True
        )

        # Item Trends (Time-Series Log)
        # Record every individual item used in this battle
        trend_entries = []
        for slot in ["main_hand", "off_hand", "head", "armor", "shoes", "cape"]:
            item = getattr(player_obj.equipment, slot, None)
            
            if not item:
                continue
            
            trend_entries.append({
                "timestamp": battle_time,
                "metadata": {
                    "item_type": item.type,
                    "slot": slot,
                    "server": server
                },
                "won": 1 if won else 0,
                "nb_uses": 1
            })
        
        if trend_entries:
            db.item_trends.insert_many(trend_entries)

    # 4. Update Player Relationships (The Social Graph)
    for team_ids, won in [(winner_ids, True), (loser_ids, False)]:
        for p1, p2 in combinations(sorted(team_ids), 2):
            rel_hash = f"{p1}_{p2}"
            db.player_relationships.update_one(
                {"_id": rel_hash},
                {
                    "$set": {"players": [p1, p2], "last_seen": battle_time},
                    "$inc": {"nb_shared_battles": 1, "shared_wins": 1 if won else 0}
                },
                upsert=True
            )

    # 5. Save the Battle Instance with build mapping
    final_battle = DBBattle5v5(
        _id=battle.id,
        winning_team_id=win_hash,
        losing_team_id=loss_hash,
        all_player_ids=winner_ids + loser_ids,
        winner_ids=winner_ids,
        loser_ids=loser_ids,
        players_builds=players_builds_map,
        datetime=battle_time,
        server=server
    )
    db.battles.replace_one({"_id": final_battle.id}, final_battle.model_dump(by_alias=True), upsert=True)

def clear_database():
    db_name = "hellgate_watcher"
    client.drop_database(db_name)
    print(f"Database '{db_name}' dropped successfully.", flush=True)

def setup_database():
    """Initializes collections and indexes."""
    existing_collections = db.list_collection_names()
    
    # Setup Time-Series for Item Trends
    if "item_trends" not in existing_collections:
        db.create_collection(
            "item_trends",
            timeseries={
                "timeField": "timestamp",
                "metaField": "metadata",
                "granularity": "seconds"
            }
        )
        print("Created Time-Series collection: item_trends", flush=True)

    # 2. Define Indexes (Crucial for performance)
    print("Applying indexes...", flush=True)
    db.battles.create_index([("all_player_ids", 1), ("datetime", -1)])
    db.players.create_index([("nb_battles",-1)])
    db.players.create_index([("name",1)])
    db.teams.create_index([("player_ids", 1), ("wins", -1)])
    db.player_relationships.create_index([("players", 1), ("nb_shared_battles", -1)])
    db.player_equipment_uses.create_index([("player_id", 1), ("nb_uses", -1)])
    db.item_trends.create_index([("metadata.item_type", 1), ("timestamp", -1)])

    print("Database setup complete!", flush=True)

def get_player_by_name_and_server(player_name: str, server: str) -> DBPlayer | None:
    player = db.players.find_one(
        {"name": player_name, "server": server},
        collation=collation.Collation(locale="en", strength=2)
    )
    if not player:
        return None
    return DBPlayer(**player)
    
def get_player_by_id(player_id: str) -> DBPlayer | None:
    player = db.players.find_one({"_id": player_id})
    if not player:
        return None
    return DBPlayer(**player)

def get_most_played_builds(player_id: str, limit_number = 5) -> List[DBPlayer_Equipment_Use] | None:
    result: List[DBPlayer_Equipment_Use] = []
    for doc in db.player_equipment_uses.find({"player_id": player_id}).sort("nb_uses", -1).limit(limit_number):
        result.append(DBPlayer_Equipment_Use(**doc))
    return result

def get_most_common_relationships(player_id: str, limit_number = 4) -> List[DBPlayer_Relationship] | None:
    relationships: List[DBPlayer_Relationship] = []
    for doc in db.player_relationships.find({"players": player_id}).sort("nb_shared_battles", -1).limit(limit_number):
        relationships.append(DBPlayer_Relationship(**doc))
    return relationships

def get_equipment_by_hash(equipment_hash: str) -> DBEquipment | None:
    equipment = db.equipments.find_one({"_id": equipment_hash})
    if not equipment:
        return None
    return DBEquipment(**equipment)

def get_team_by_hash(team_hash: str) -> DBTeam | None:
    team = db.teams.find_one({"_id": team_hash})
    if not team:
        return None
    return DBTeam(**team)

def get_player_statistics(player: DBPlayer) -> Dict | None:
    
    player_stats = {
        "nb_wins": player.nb_wins,
        "nb_losses": player.nb_losses,
        "nb_battles": player.nb_battles,
        "first_seen": player.first_seen,
        "last_seen": player.last_seen,
    }
    
    most_played_builds_list = []
    most_common_relationships_list = []


    most_played_builds = get_most_played_builds(player.id)
    if most_played_builds:
        most_played_builds_list = [{"equipment":build_use.get_equipment().to_equipment(), "nb_uses": build_use.nb_uses,"nb_wins":build_use.nb_wins} for build_use in most_played_builds]
    most_common_relationships = get_most_common_relationships(player.id)
    if most_common_relationships:
        most_common_relationships_list = [{"player_name":rel.get_other_player(player.name), "nb_battles": rel.nb_shared_battles, "nb_wins": rel.shared_wins} for rel in most_common_relationships]


    result = {
        "player": player_stats,
        "most_played_builds": most_played_builds_list,
        "most_common_relationships": most_common_relationships_list,
    }

    return result

def get_most_active_players(limit_number = 10) -> List[DBPlayer] | None:
    players: List[DBPlayer] = []
    for doc in db.players.find().sort("nb_battles", -1).limit(limit_number):
        players.append(DBPlayer(**doc))
    return players

def get_most_active_teams(limit_number = 10) -> List[DBTeam] | None:
    teams: List[DBTeam] = []
    for doc in db.teams.find().sort("wins", -1).limit(limit_number):
        teams.append(DBTeam(**doc))
    return teams