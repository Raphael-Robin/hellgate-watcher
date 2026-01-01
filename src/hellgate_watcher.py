import asyncio
from src.database import is_battle_new, save_data_from_battle5v5
from src.albion_objects import Battle
from src.utils import logger
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import json
import os
import aiohttp
from config import *




class HellgateWatcher:
    @staticmethod
    async def get_json(url: str) -> Dict | None:
        json = None
        tries = 0
        while tries < MAX_RETRIES:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=TIMEOUT)
            ) as session:
                try:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        json = await response.json()

                except Exception as e:
                    logger.error(f"An error occurred while fetching {url}: {e}")
            tries += 1
            return json

    @staticmethod
    async def _get_50_battles(server_url: str, limit=BATTLES_LIMIT, page=0):
        request = (
            f"{server_url}/battles?limit={limit}&sort=recent&offset={page * limit}"
        )
        json = await HellgateWatcher.get_json(request)

        if json:
            return list(json)
        return []

    @staticmethod
    def _contains_battles_out_of_range(
        battles_dicts, range_minutes=BATTLES_MAX_AGE_MINUTES
    ):
        if not battles_dicts:
            return False

        for battle_dict in battles_dicts:
            if HellgateWatcher.is_out_of_range(
                battle_dict, range_minutes=range_minutes
            ):
                return True
        return

    @staticmethod
    def is_out_of_range(battle_dict, range_minutes=BATTLES_MAX_AGE_MINUTES):
        start_time = datetime.fromisoformat(battle_dict["startTime"])
        return datetime.now(timezone.utc) - start_time > timedelta(
            minutes=range_minutes
        )

    @staticmethod
    async def get_recent_battles() -> Dict[str, Dict[str, List[Battle]]]:
        recent_battles = {
            "europe": {"5v5": [], "2v2": [], "total": 0},
            "americas": {"5v5": [], "2v2": [], "total": 0},
            "asia": {"5v5": [], "2v2": [], "total": 0},
        }

        for server in ["europe", "americas", "asia"]:
            logger.debug(f"Started looking for battles in {server} server")
            server_url = SERVER_URLS[server]
            page_number = 0

            while True:
                logger.debug(f"Fetching 50 Battles from {server_url}")
                batch = await HellgateWatcher._get_50_battles(server_url, page=page_number)
                batch.reverse()
            
                if not batch:
                    break

                batch_tasks = [HellgateWatcher.process_single_battle(battle, server) for battle in batch]
                results = await asyncio.gather(*batch_tasks)

                for battle in results:
                    if battle:
                        recent_battles[server]["total"] += 1
                        if battle.is_hellgate_5v5:
                            recent_battles[server]["5v5"].append(battle)
                        elif battle.is_hellgate_2v2:
                            recent_battles[server]["2v2"].append(battle)

                if  HellgateWatcher._contains_battles_out_of_range(batch):
                    logger.debug("finished looking for battles in this server")
                    break

                page_number += 1

            logger.info(
                f"SERVER: {server.ljust(8)} \tFound {len(recent_battles[server]['5v5'])} 5v5 Hellgate Battles"
            )
            logger.info(
                f"SERVER: {server.ljust(8)} \tFound {len(recent_battles[server]['2v2'])} 2v2 Hellgate Battles"
            )

        return recent_battles

    @staticmethod
    async def process_single_battle(battle_dict: dict, server: str) -> Battle | None:
        server_url = SERVER_URLS[server]
        battle_id = battle_dict["id"]
                
        player_count = len(battle_dict["players"])
        if not (player_count == 4 or player_count == 10):
            return

        logger.debug(f"Checking if battle {battle_id} has already been processed")
        if not await is_battle_new(battle_id):
            logger.debug(f"Battle {battle_id} has already been processed, skipping battle")
            return
        
        logger.debug(f"Fetching battle events for battle: {battle_id}")
        battle_events = await HellgateWatcher.get_battle_events(
            battle_id, server_url
        )
        try:
            battle_dict["battle_events"] = battle_events
            battle = Battle(battle_dict)
        except Exception as e:
            logger.error(
                f"An error occurred while parsing battle {battle_dict['id']}: {e}"
            )
            return
        
        if battle.is_hellgate_5v5:
            logger.debug(f"Battle {battle.id} is a 5v5 Hellgate Battle")
            await save_data_from_battle5v5(battle=battle, server=server)
            return battle
        elif battle.is_hellgate_2v2:
            return battle

    @staticmethod
    async def save_battles_5v5(
        max_lookback_minutes: int, 
        servers: List[str] = ["europe", "americas", "asia"]
    ) -> None:
        """
        Crawls servers for recent 5v5 battles within a specific lookback window
        and saves them to the database using concurrent batch processing.
        """
        for server in servers:
            logger.info(f"Started scanning {server} for 5v5 battles (Lookback: {max_lookback_minutes}m)")
            server_url = SERVER_URLS[server]
            page_number = 0
            total_saved = 0

            while True:
                logger.debug(f"Fetching page {page_number} from {server}")
                batch = await HellgateWatcher._get_50_battles(server_url, page=page_number)
                
                if not batch:
                    logger.info(f"No more battles found on {server} at page {page_number}")
                    break

                # 1. Process the batch concurrently (Process 50 battles at once)
                # This uses your process_single_battle which handles is_battle_new and save_data_from_battle5v5
                batch_tasks = [
                    HellgateWatcher.process_single_battle(battle_dict, server) 
                    for battle_dict in batch
                ]
                results = await asyncio.gather(*batch_tasks)

                # Count how many were actually 5v5 and saved
                saved_in_batch = len([b for b in results if b and b.is_hellgate_5v5])
                total_saved += saved_in_batch
                
                logger.info(f"Page {page_number} processed. 5v5 battles saved this batch: {saved_in_batch}")

                # 2. Check if we have reached the time limit
                # Note: contains_battles_out_of_range needs the max_lookback_minutes passed in
                if HellgateWatcher._contains_battles_out_of_range(batch, range_minutes=max_lookback_minutes):
                    logger.info(f"Reached lookback limit ({max_lookback_minutes}m) on {server}. Stopping.")
                    break

                # 3. Safety break for API limits
                if page_number >= 199:
                    logger.warning(f"Reached hard page limit (200) on {server}")
                    break

                page_number += 1
                # Optional: Small sleep to be kind to the API
                await asyncio.sleep(1)

            logger.info(f"Finished {server}. Total 5v5 battles saved: {total_saved}")

    @staticmethod
    async def get_battle_events(battle_id: int, server_url: str) -> List[dict]:
        return await HellgateWatcher.get_json(f"{server_url}/events/battle/{battle_id}")  # type: ignore

    @staticmethod
    async def get_battle_from_id(battle_id: int, server_url: str) -> Battle | None:
        battle_dict = await HellgateWatcher.get_json(
            f"{server_url}/battles/{battle_id}"
        )
        if not battle_dict:
            return None
        battle_events = await HellgateWatcher.get_battle_events(battle_id, server_url)
        try:
            battle_dict["battle_events"] = battle_events
            battle = Battle(battle_dict)
        except Exception as e:
            logger.error(f"An error occurred while parsing battle {battle_id}: {e}")
            return None
        return battle

    @staticmethod
    def load_json(json_path: str) -> Dict:
        with open(json_path, "r") as f:
            return json.load(f)

    @staticmethod
    def save_json(json_path: str, data: Dict) -> None:
        with open(json_path, "w+") as f:
            json.dump(data, f, indent=4)


def clear_battle_reports_images():
    for file in os.listdir(BATTLE_REPORT_IMAGE_FOLDER):
        if file.endswith(".png"):
            os.remove(os.path.join(BATTLE_REPORT_IMAGE_FOLDER, file))


def clear_equipments_images():
    for file in os.listdir(EQUIPMENT_IMAGE_FOLDER):
        if file.endswith(".png"):
            os.remove(os.path.join(EQUIPMENT_IMAGE_FOLDER, file))
