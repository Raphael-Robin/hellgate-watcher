import hashlib
import os
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timezone
from itertools import combinations
from pydantic import BaseModel, Field
from pymongo import AsyncMongoClient, collation
from pymongo.errors import DuplicateKeyError

# Assuming your directory structure allows this import
from src.albion_objects import Battle, Equipment, Player, Slot
from src.utils import logger


# --- Configuration ---


MONGO_URI = os.getenv("MONGO_URI")
client = AsyncMongoClient(MONGO_URI)
db = client["hellgate_watcher"]
processed_batches = db["processed_battle_ids"]



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
            Slot.MainHand.value: {"Type": f"T7_{self.main_hand}", "Quality": 4}
            if self.main_hand
            else None,
            Slot.OffHand.value: {"Type": f"T7_{self.off_hand}", "Quality": 4}
            if self.off_hand
            else None,
            Slot.Head.value: {"Type": f"T7_{self.head}", "Quality": 4}
            if self.head
            else None,
            Slot.Armor.value: {"Type": f"T7_{self.armor}", "Quality": 4}
            if self.armor
            else None,
            Slot.Shoes.value: {"Type": f"T7_{self.shoes}", "Quality": 4}
            if self.shoes
            else None,
            Slot.Cape.value: {"Type": f"T7_{self.cape}", "Quality": 4}
            if self.cape
            else None,
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
    server: str
    last_seen: datetime


class UsageMetadata(BaseModel):
    player_id: str
    equipment_hash_id: str
    won: bool


class DBPlayer_Equipment_Usage_Logs(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    metadata: UsageMetadata

    @property
    def player_id(self) -> str:
        return self.metadata.player_id

    @property
    def equipment_hash_id(self) -> str:
        return self.metadata.equipment_hash_id

    async def get_equipment(self) -> DBEquipment:
        equipment = await get_db_equipment_by_hash(self.equipment_hash_id)
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

    async def get_players(self) -> Tuple[DBPlayer, DBPlayer]:
        player_a = await get_player_by_id(self.players[0])
        player_b = await get_player_by_id(self.players[1])
        if player_a and player_b:
            return player_a, player_b
        else:
            raise Exception(f"Player(s) with ID(s) {self.players} not found")

    async def get_other_player(self, player_name: str) -> DBPlayer:
        try:
            player_a, player_b = await self.get_players()
            player_a, player_b = await self.get_players()
            if player_a.name == player_name:
                return player_b
            elif player_b.name == player_name:
                return player_a
            else:
                raise Exception(f"Player {player_name} not found in relationship")
        except Exception as e:
            raise (e)


class DBBattle5v5(BaseModel):
    """The source of truth for every match"""

    id: int = Field(alias="_id")
    winning_team_id: str  # Hash reference to DBTeam
    losing_team_id: str  # Hash reference to DBTeam
    all_player_ids: List[str]
    winner_ids: List[str]
    loser_ids: List[str]
    # Maps player_id -> equipment_hash_id
    players_builds: Dict[str, str]
    timestamp: datetime
    server: str


class DBChannel(BaseModel):
    id: str = Field(alias="_id")
    server: str
    hg_type: str
    channel_id: int

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


def get_channel_hash(server_id: int,server: str,hg_type: str):
    return hashlib.md5(f"{server_id}_{server}_{hg_type}".encode()).hexdigest()

# --- Main Save Function ---


async def save_data_from_battle5v5(battle: Battle, server: str):
    """
    Parses a Battle object and updates all 7 collections (including item_trends).
    """
    logger.debug(f"Saving battle {battle.id} to database")
    
    db = client["hellgate_watcher"]

    # 1. Determine Winners vs Losers based on victims (Wipe Logic)
    winner_ids = battle.team_a_ids
    winner_hash = get_team_hash(winner_ids)

    loser_ids = battle.team_b_ids
    loser_hash = get_team_hash(loser_ids)

    battle_time = datetime.fromisoformat(battle.start_time.replace("Z", "+00:00"))

    # To track which player used which build for the Battle record
    players_builds_map = {}

    # 2. Update Teams Collection
    for team_hash, ids, won in [
        (winner_hash, winner_ids, True),
        (loser_hash, loser_ids, False),
    ]:
        await db.teams.update_one(
            {"_id": team_hash},
            {
                "$setOnInsert": {"player_ids": ids, "server": server},
                "$inc": {
                    "nb_battles": 1,
                    "nb_wins": 1 if won else 0,
                    "nb_losses": 0 if won else 1,
                },
                "$set": {"last_seen": battle_time},
            },
            upsert=True,
        )

    # 3. Update Player, Equipment, Equipment_Uses
    all_players = [(player_id, True) for player_id in winner_ids] + [
        (player_id, False) for player_id in loser_ids
    ]

    for player_id, won in all_players:
        player_obj = battle.get_player(player_id)
        if not player_obj:
            raise Exception(f"Player with ID {player_id} not found")

        equipment_hash = generate_equipment_hash(player_obj)
        players_builds_map[player_id] = equipment_hash

        # Player Registry
        await db.players.update_one(
            {"_id": player_id},
            {
                "$set": {"name": player_obj.name, "last_seen": battle_time},
                "$setOnInsert": {"first_seen": battle_time, "server": server},
                "$inc": {
                    "nb_wins": 1 if won else 0,
                    "nb_losses": 0 if won else 1,
                    "nb_battles": 1,
                },
            },
            upsert=True,
        )

        await db.equipments.update_one(
            {"_id": equipment_hash},
            {
                "$inc": {"nb_uses": 1, "nb_wins": 1 if won else 0},
                "$setOnInsert": {
                    "main_hand": player_obj.equipment.mainhand.type
                    if player_obj.equipment.mainhand
                    else None,
                    "off_hand": player_obj.equipment.offhand.type
                    if player_obj.equipment.offhand
                    else None,
                    "head": player_obj.equipment.head.type
                    if player_obj.equipment.head
                    else None,
                    "armor": player_obj.equipment.armor.type
                    if player_obj.equipment.armor
                    else None,
                    "shoes": player_obj.equipment.shoes.type
                    if player_obj.equipment.shoes
                    else None,
                    "cape": player_obj.equipment.cape.type
                    if player_obj.equipment.cape
                    else None,
                },
            },
            upsert=True,
        )

        # Player-Specific Equipment Usage
        log = {
            "timestamp": datetime.now(tz=timezone.utc),
            "metadata": {
                "player_id": player_id,
                "equipment_hash_id": equipment_hash,
                "won": won,
            },
        }
        await db.player_equipment_usage_logs.insert_one(log)

    # 4. Update Player Relationships (The Social Graph)
    for team_ids, won in [(winner_ids, True), (loser_ids, False)]:
        for p1, p2 in combinations(sorted(team_ids), 2):
            rel_hash = f"{p1}_{p2}"
            await db.player_relationships.update_one(
                {"_id": rel_hash},
                {
                    "$set": {"players": [p1, p2], "last_seen": battle_time},
                    "$inc": {"nb_shared_battles": 1, "shared_wins": 1 if won else 0},
                },
                upsert=True,
            )

    # 5. Save the Battle Instance with build mapping
    final_battle = DBBattle5v5(
        _id=battle.id,
        winning_team_id=winner_hash,
        losing_team_id=loser_hash,
        all_player_ids=winner_ids + loser_ids,
        winner_ids=winner_ids,
        loser_ids=loser_ids,
        players_builds=players_builds_map,
        timestamp=battle_time,
        server=server,
    )
    await db.battles.replace_one(
        {"_id": final_battle.id}, final_battle.model_dump(by_alias=True), upsert=True
    )


async def clear_database():
    
    db_name = "hellgate_watcher"
    if db_name in await client.list_database_names():
        await client.drop_database(db)
        logger.info(f"Database '{db_name}' dropped successfully.")
    else:
        logger.info(f"Database '{db_name}' does not exist.")




async def setup_database():
    """Initializes collections and indexes."""
    
    db = client["hellgate_watcher"]
    existing_collections = await db.list_collection_names()

    if "player_equipment_usage_logs" not in existing_collections:
        await db.create_collection(
            "player_equipment_usage_logs",
            timeseries={
                "timeField": "timestamp",
                "metaField": "metadata",
                "granularity": "minutes",
            },
        )
        logger.info("Created Time-Series collection: player_equipment_usage_logs")

    processed_batches = db["processed_battle_ids"]
    await processed_batches.create_index("created_at", expireAfterSeconds=24*60*60)
    await processed_batches.create_index("battle_id", unique=True)
    

    logger.info("Applying indexes")
    await db.battles.create_index([("all_player_ids", 1), ("datetime", -1)])
    await db.battles.create_index([("server", 1)])
    await db.players.create_index([("nb_battles", -1)])
    await db.players.create_index([("name", 1)])
    await db.players.create_index([("server", 1)])
    await db.teams.create_index([("player_ids", 1), ("wins", -1)])
    await db.player_relationships.create_index([("players", 1), ("nb_shared_battles", -1)])
    await db.player_equipment_usage_logs.create_index(
        [("metadata.equipment_hash_id", 1), ("timestamp", -1)]
    )
    await db.player_equipment_usage_logs.create_index(
        [("metadata.player_id", 1), ("timestamp", -1)]
    )
    logger.info("Database setup complete")


async def is_battle_new(battle_id: str) -> bool:
    """Checks if battle exists; if not, logs it and returns True."""
    try:
        await processed_batches.insert_one(
            {"battle_id": battle_id, "created_at": datetime.now(tz=timezone.utc)}
        )
        return True
    except DuplicateKeyError:
        return False
    except Exception as e:
        logger.error(f"Database error: {e}")
        return False


async def get_player_by_name_and_server(player_name: str, server: str) -> DBPlayer | None:
    
    player = await db.players.find_one(
        {"name": player_name, "server": server},
        collation=collation.Collation(locale="en", strength=2),
    )
    if not player:
        return None
    return DBPlayer(**player)


async def get_player_by_id(player_id: str) -> DBPlayer | None:
    
    player = await db.players.find_one({"_id": player_id})
    if not player:
        return None
    return DBPlayer(**player)


async def get_most_played_builds(player_id: str, limit_number: int = 5) -> List[dict]:
    

    pipeline = [
        # 1. Match only logs for this player
        {"$match": {"metadata.player_id": player_id}},
        # 2. Group by the equipment hash and calculate stats
        {
            "$group": {
                "_id": "$metadata.equipment_hash_id",
                "nb_uses": {"$sum": 1},
                # Sum 1 if metadata.won is True, else 0
                "nb_wins": {
                    "$sum": {"$cond": [{"$eq": ["$metadata.won", True]}, 1, 0]}
                },
            }
        },
        # 3. Sort by most used
        {"$sort": {"nb_uses": -1}},
        # 4. Limit results
        {"$limit": limit_number},
    ]

    logs = await db.player_equipment_usage_logs.aggregate(pipeline)

    aggregated_results = await logs.to_list()

    results = []
    for item in aggregated_results:
        # Extract the hash from the group _id
        equipment_hash = item["_id"]

        # Use your existing helper to get the full Equipment object
        equipment_obj = await get_equipment_by_hash(equipment_hash)

        results.append(
            {
                "equipment": equipment_obj,
                "stats":{
                    "nb_uses": item["nb_uses"],
                    "winrate": str(round(item["nb_wins"]/item["nb_uses"]*100,2))+'%',
                }
            }
        )
    return results


async def get_most_common_relationships(
    player_id: str, limit_number=4
) -> List[DBPlayer_Relationship] | None:
    
    relationships: List[DBPlayer_Relationship] = []
    for doc in (
        await db.player_relationships.find({"players": player_id})
        .sort("nb_shared_battles", -1)
        .limit(limit_number)
        .to_list()
    ):
        relationships.append(DBPlayer_Relationship(**doc))
    return relationships


async def get_db_equipment_by_hash(equipment_hash: str) -> DBEquipment | None:
    
    equipment = await db.equipments.find_one({"_id": equipment_hash})
    if not equipment:
        return None
    return DBEquipment(**equipment)


async def get_equipment_by_hash(equipment_hash: str) -> Equipment | None:
    dbequipment = await get_db_equipment_by_hash(equipment_hash)
    if not dbequipment:
        return None
    return dbequipment.to_equipment()


async def get_team_by_hash(team_hash: str) -> DBTeam | None:
    
    team = await db.teams.find_one({"_id": team_hash})
    if not team:
        return None
    return DBTeam(**team)


async def get_player_statistics(player: DBPlayer) -> Dict | None:
    player_stats = {
        "name": player.name,
        "nb_wins": player.nb_wins,
        "nb_losses": player.nb_losses,
        "nb_battles": player.nb_battles,
        "first_seen": player.first_seen,
        "last_seen": player.last_seen,
        "winrate": f"{round(player.nb_wins/player.nb_battles*100,2)}%"
    }

    most_played_builds_list = []
    most_common_relationships_list = []

    most_played_builds_list = await get_most_played_builds(player.id)
    most_common_relationships = await get_most_common_relationships(player.id)
    if most_common_relationships:
        most_common_relationships_list = [
            {
                "player_name": (await rel.get_other_player(player.name)).name,
                "nb_battles": rel.nb_shared_battles,
                "winrate": f"{round(rel.shared_wins/rel.nb_shared_battles*100,2)}%"
            }
            for rel in most_common_relationships
        ]

    result = {
        "player_stats": player_stats,
        "most_played_builds": most_played_builds_list,
        "most_common_relationships": most_common_relationships_list,
    }

    return result


async def get_most_active_players(server: str, limit_number: int=10) -> List[DBPlayer] | None:
    players: List[DBPlayer] = []
    
    for doc in (
        await db.players.find({"server": server}).sort("nb_battles", -1).limit(limit_number).to_list()):
        players.append(DBPlayer(**doc))
    return players


async def get_most_active_teams(server: str, limit_number: int=10) -> List[DBTeam] | None:
    teams: List[DBTeam] = []
    
    for doc in (
        await db.teams.find({"server": server}).sort("nb_battles", -1).limit(limit_number).to_list()
    ):
        teams.append(DBTeam(**doc))
    return teams

def pretty_print_stats(stats):
    player = stats["player_stats"]
    relationships = stats["most_common_relationships"]
    builds = stats["most_played_builds"]

    print(f"Player Stats")
    print(f"\t{"name".ljust(15)} \t{"nb_matches".ljust(15)} \t{"winrate".ljust(15)} \t{"last seen on".ljust(15)}")
    print(f"\t{player["name"].ljust(15)} \t{str(player["nb_battles"]).ljust(15)} \t{player["winrate"].ljust(15)} \t{str(player["last_seen"]).ljust(15)}")

    
    print(f"Team Members")
    print(f"\t{"name".ljust(15)} \t{"nb_matches".ljust(15)} \t{"winrate".ljust(15)}")
    for relationship in relationships:
        print(f"\t{str(relationship["player_name"]).ljust(15)} \t{str(relationship["nb_battles"]).ljust(15)} \t{relationship["winrate"].ljust(15)}")

    print(f"Builds")
    print(f"\t{"Weapon".ljust(15)} \t{"Offhand".ljust(15)} \t{"Helmet".ljust(15)} \t{"Armor".ljust(15)} \t{"Boots".ljust(15)} \t{"Cape".ljust(15)} \t{"nb_matches".ljust(15)} \t{"winrate".ljust(15)}")
    for build in builds:
        equipment:Equipment = build["equipment"]
        equipment_stats = build["stats"]
        print(f"""\t{str(equipment.mainhand.type if equipment.mainhand else "").ljust(15)} \t{str(equipment.offhand.type if equipment.offhand else "").ljust(15)} \t{str(equipment.head.type if equipment.head else "").ljust(15)} \t{str(equipment.armor.type if equipment.armor else "").ljust(15)} \t{str(equipment.shoes.type if equipment.shoes else "").ljust(15)} \t{str(equipment.cape.type if equipment.cape else "").ljust(15)} \t{str(equipment_stats["nb_uses"]).ljust(15)} \t{equipment_stats["winrate"].ljust(15)} """)


async def get_channels(server: str, hg_type: str):
    channels = await db.channels.find({"server": server, "hg_type": hg_type}).to_list()
    return [DBChannel(**doc) for doc in channels]

async def add_channel(server_id: int,channel_id: int, server: str, hg_type: str):
    await db.channels.update_one(
        {"_id": get_channel_hash(server_id,server,hg_type)},
        {
            "$set": {"channel_id":channel_id, "server": server, "hg_type": hg_type}
        },
        upsert=True,
    )

async def remove_channel(channel: DBChannel):
    await db.channels.delete_one({"_id": channel.id})