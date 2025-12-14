from src.albion_objects import Battle, Item, Equipment
from src.utils import get_current_time_formatted

from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import json
import os
import aiohttp
from config import (
    BATTLES_LIMIT,
    BATTLES_MAX_AGE_MINUTES,
    CANVAS_WIDTH_2V2,
    MAX_RETRIES,
    RENDER_API_URL,
    EQUIPMENT_IMAGE_FOLDER,
    ITEM_IMAGE_FOLDER,
    BATTLE_REPORT_IMAGE_FOLDER,
    REPORTED_BATTLES_JSON_PATH,
    SERVER_URLS,
    TIMEOUT,
    PLAYER_NAME_FONT_PATH,
    TIMESTAMP_FONT_PATH,
    PLAYER_NAME_FONT_SIZE,
    TIMESTAMP_FONT_SIZE,
    FONT_COLOR,
    TOP_BOTTOM_PADDING,
    PLAYER_NAME_AREA_HEIGHT,
    EQUIPMENT_IMAGE_SIZE,
    MIDDLE_GAP,
    IP_AREA_HEIGHT,
    LINE_SPACING,
    SPACING,
    CANVAS_WIDTH_5V5,
    SIDE_PADDING,
    BACKGROUND_COLOR,
    DEAD_PLAYER_GRAYSCALE_ENHANCEMENT,
    LAYOUT,
    BATTLE_REPORT_CANVAS_SIZE_2V2,
    BATTLE_REPORT_CANVAS_SIZE_5V5,
    IMAGE_SIZE,
    EQUIPMENT_CANVAS_SIZE,
)


class BattleReportImageGenerator:
    @staticmethod
    async def generate_battle_reports_5v5(battles: List[Battle]) -> List[str]:
        battle_reports = [
            await BattleReportImageGenerator.generate_battle_report_5v5(battle)
            for battle in battles
        ]
        return battle_reports

    @staticmethod
    async def generate_battle_reports_2v2(battles: List[Battle]) -> List[str]:
        battle_reports = [
            await BattleReportImageGenerator.generate_battle_report_2v2(battle)
            for battle in battles
        ]
        return battle_reports

    @staticmethod
    async def generate_equipment_image(equipment: Equipment) -> str:
        item_images = {}

        for item in equipment.items:
            image_path = await BattleReportImageGenerator.get_item_image(item)
            item_images[item.__class__.__name__.lower()] = image_path

        equipment_image = Image.new("RGB", EQUIPMENT_CANVAS_SIZE, BACKGROUND_COLOR)

        for item_slot, image_path in item_images.items():
            if not image_path:
                continue
            if item_slot in LAYOUT:
                item_image = Image.open(image_path).convert("RGBA")
                coords = (
                    LAYOUT[item_slot][0] * IMAGE_SIZE,
                    LAYOUT[item_slot][1] * IMAGE_SIZE,
                )
                R, G, B, A = item_image.split()
                equipment_image.paste(item_image, coords, A)

        image_name = "equipment_"
        for item in equipment.items:
            image_name += f"T{item.tier}_{item.type}@{item.enchantment}&{item.quality}"

        equipment_image_path = f"{EQUIPMENT_IMAGE_FOLDER}/{image_name}.png"
        equipment_image.save(equipment_image_path)

        return equipment_image_path

    @staticmethod
    async def get_item_image(item: Item) -> str | None:
        if not item:
            return None

        item_image_path = f"{ITEM_IMAGE_FOLDER}/T{item.tier}_{item.type}@{item.enchantment}&{item.quality}.png"
        if os.path.exists(item_image_path):
            return item_image_path

        url = f"{RENDER_API_URL}T{item.tier}_{item.type}@{item.enchantment}.png?count=1&quality={item.enchantment}"

        image = await BattleReportImageGenerator.get_image(url)
        if not image:
            return None

        with open(item_image_path, "wb") as f:
            f.write(image)
        return item_image_path

    @staticmethod
    async def get_image(url: str) -> bytes | None:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT)
        ) as session:
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    return await response.read()

            except Exception as e:
                print(
                    f"[{get_current_time_formatted()}]\tAn error occurred while fetching {url}: {e}"
                )
                return None

    @staticmethod
    async def get_json(url: str) -> Dict | None:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT)
        ) as session:
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    return await response.json()

            except Exception as e:
                print(
                    f"[{get_current_time_formatted()}]\tAn error occurred while fetching {url}: {e}"
                )
                return None

    @staticmethod
    async def generate_battle_report_2v2(battle: Battle) -> str:
        return await BattleReportImageGenerator._generate_battle_report(
            battle, CANVAS_WIDTH_2V2, BATTLE_REPORT_CANVAS_SIZE_2V2
        )

    @staticmethod
    async def generate_battle_report_5v5(battle: Battle) -> str:
        return await BattleReportImageGenerator._generate_battle_report(
            battle, CANVAS_WIDTH_5V5, BATTLE_REPORT_CANVAS_SIZE_5V5
        )

    @staticmethod
    async def _generate_battle_report(
        battle: Battle, canvas_width: int, battle_report_canvas_size: int
    ) -> str:
        battle_report_image = Image.new(
            "RGB", battle_report_canvas_size, BACKGROUND_COLOR
        )

        draw = ImageDraw.Draw(battle_report_image)

        player_name_font = ImageFont.truetype(
            PLAYER_NAME_FONT_PATH, PLAYER_NAME_FONT_SIZE
        )
        timestamp_font = ImageFont.truetype(TIMESTAMP_FONT_PATH, TIMESTAMP_FONT_SIZE)
        ip_font = ImageFont.truetype(TIMESTAMP_FONT_PATH, 35)

        async def draw_team(y_pos, team_ids):
            for i, player_id in enumerate(team_ids):
                x_pos = SIDE_PADDING + i * (EQUIPMENT_IMAGE_SIZE + SPACING)
                player = battle.get_player(player_id)

                # Draw player name
                # Center the name above the equipment image
                bbox = draw.textbbox((0, 0), player.name, font=player_name_font)
                text_width = bbox[2] - bbox[0]
                draw.text(
                    text=player.name,
                    xy=(x_pos + (EQUIPMENT_IMAGE_SIZE - text_width) / 2, y_pos),
                    font=player_name_font,
                    fill=FONT_COLOR,
                )

                # Paste equipment image
                equipment_image_path = (
                    await BattleReportImageGenerator.generate_equipment_image(
                        player.equipment
                    )
                )
                equipment_image = Image.open(equipment_image_path).convert("RGBA")

                # Make dead players gray
                if player_id in battle.victim_ids:
                    enhancer = ImageEnhance.Color(equipment_image)
                    equipment_image = enhancer.enhance(
                        DEAD_PLAYER_GRAYSCALE_ENHANCEMENT
                    )

                R, G, B, A = equipment_image.split()
                battle_report_image.paste(
                    im=equipment_image,
                    box=(x_pos, y_pos + PLAYER_NAME_AREA_HEIGHT),
                    mask=A,
                )

                # Draw Average Item Power
                ip_text = str(round(player.average_item_power))
                bbox = draw.textbbox((0, 0), ip_text, font=ip_font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                ip_text_x = x_pos + (EQUIPMENT_IMAGE_SIZE - text_width) / 2
                ip_text_y = (
                    y_pos
                    + PLAYER_NAME_AREA_HEIGHT
                    + EQUIPMENT_IMAGE_SIZE
                    + (IP_AREA_HEIGHT - text_height) / 2
                )
                draw.text(
                    (ip_text_x, ip_text_y), ip_text, font=ip_font, fill=FONT_COLOR
                )

        # --- Draw Team A ---
        y_pos = TOP_BOTTOM_PADDING
        await draw_team(y_pos, battle.team_a_ids)

        # --- Draw Team B ---
        y_pos = (
            TOP_BOTTOM_PADDING
            + PLAYER_NAME_AREA_HEIGHT
            + EQUIPMENT_IMAGE_SIZE
            + IP_AREA_HEIGHT
            + MIDDLE_GAP
        )
        await draw_team(y_pos, battle.team_b_ids)

        # --- Draw Timestamp ---
        duration = datetime.fromisoformat(battle.end_time) - datetime.fromisoformat(
            battle.start_time
        )
        duration = duration.total_seconds()
        duration_minutes = int(duration // 60)
        duration_seconds = int(duration % 60)
        start_time = datetime.fromisoformat(battle.start_time.replace("Z", "+00:00"))

        # Format the text strings
        start_time_text = f"Start Time: {start_time.strftime('%H:%M:%S')} UTC"
        duration_text = f"Duration: {duration_minutes:02d}m {duration_seconds:02d}s"

        # Calculate text position for centering
        timestamp_y = (
            TOP_BOTTOM_PADDING
            + PLAYER_NAME_AREA_HEIGHT
            + EQUIPMENT_IMAGE_SIZE
            + IP_AREA_HEIGHT
            + (MIDDLE_GAP // 2)
        )

        # Using textbbox for better centering if available (Pillow >= 8.0.0)
        start_bbox = draw.textbbox((0, 0), start_time_text, font=timestamp_font)
        start_text_width = start_bbox[2] - start_bbox[0]
        text_height = start_bbox[3] - start_bbox[1]  # Height of a single line of text

        # Calculate vertical positions for centered text with spacing
        start_text_y = timestamp_y - (text_height + LINE_SPACING) / 2
        duration_text_y = start_text_y + text_height + LINE_SPACING

        draw.text(
            ((canvas_width - start_text_width) / 2, start_text_y),
            start_time_text,
            font=timestamp_font,
            fill=(255, 255, 255),
        )

        duration_bbox = draw.textbbox((0, 0), duration_text, font=timestamp_font)
        duration_text_width = duration_bbox[2] - duration_bbox[0]
        draw.text(
            ((canvas_width - duration_text_width) / 2, duration_text_y),
            duration_text,
            font=timestamp_font,
            fill=(255, 255, 255),
        )

        battle_report_image_path = (
            f"{BATTLE_REPORT_IMAGE_FOLDER}/battle_report_{battle.id}.png"
        )

        print(
            f"[{get_current_time_formatted()}]\tgenerating {battle_report_image_path}"
        )

        battle_report_image.save(battle_report_image_path)

        clear_equipments_images()

        return battle_report_image_path


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
                    print(
                        f"[{get_current_time_formatted()}]An error occurred while fetching {url}: {e}"
                    )
            tries += 1
            return json

    @staticmethod
    async def _get_50_battles(server_url: str, limit=BATTLES_LIMIT, page=0):
        request = (
            f"{server_url}/battles?limit={limit}&sort=recent&offset={page * limit}"
        )
        json = await HellgateWatcher.get_json(request)

        if json:
            return (list(json))
        return []

    @staticmethod
    def _contains_battles_out_of_range(battles_dicts):
        if not battles_dicts:
            return False

        for battle_dict in battles_dicts:
            if HellgateWatcher.is_out_of_range(battle_dict):
                return True
        return 
    
    @staticmethod
    def is_out_of_range(battle_dict):
        start_time = datetime.fromisoformat(battle_dict["startTime"])
        return datetime.now(timezone.utc) - start_time > timedelta(
            minutes=BATTLES_MAX_AGE_MINUTES
        )

    @staticmethod
    async def get_recent_battles() -> List[Battle]:
        reported_battles_per_server = HellgateWatcher.load_json(
            REPORTED_BATTLES_JSON_PATH
        )

        recent_battles = {
            "europe": {"5v5": [], "2v2": [], "total": 0},
            "americas": {"5v5": [], "2v2": [], "total": 0},
            "asia": {"5v5": [], "2v2": [], "total": 0},
        }

        for server in ["europe", "americas", "asia"]:
            server_url = SERVER_URLS[server]
            nb_battles_parsed = 0
            nb_battles_skipped = 0

            battles_dicts = await HellgateWatcher._get_50_battles(server_url, page=0)
            page_number = 1
            while not HellgateWatcher._contains_battles_out_of_range(battles_dicts):
                battles_dicts.extend(
                    await HellgateWatcher._get_50_battles(server_url, page=page_number)
                )
                page_number += 1

            for battle_dict in battles_dicts:
                if battle_dict["id"] in reported_battles_per_server[server]:
                    nb_battles_skipped += 1
                    continue
                else:
                    reported_battles_per_server[server].append(battle_dict["id"])
                    nb_battles_parsed += 1

                player_count = len(battle_dict["players"])

                if player_count <= 10:
                    battle_events = await HellgateWatcher.get_battle_events(
                        battle_dict["id"], server_url
                    )
                    try:
                        battle = Battle(
                            battle_dict=battle_dict, battle_events=battle_events
                        )
                    except Exception as e:
                        print(
                            f"[{get_current_time_formatted()}]\tAn error occurred while parsing battle {battle_dict['id']}: {e}"
                        )
                        continue

                    if battle.is_hellgate_5v5:
                        recent_battles[server]["5v5"].append(battle)
                    elif battle.is_hellgate_2v2:
                        recent_battles[server]["2v2"].append(battle)

            print(
                f"[{get_current_time_formatted()}]\tSERVER: {server.ljust(8)} \tParsed {nb_battles_parsed} battles \tSkipped {nb_battles_skipped} battles",
                flush=True,
            )
            print(
                f"[{get_current_time_formatted()}]\tSERVER: {server.ljust(8)} \tFound {len(recent_battles[server]['5v5'])} 5v5 Hellgate Battles",
                flush=True,
            )
            print(
                f"[{get_current_time_formatted()}]\tSERVER: {server.ljust(8)} \tFound {len(recent_battles[server]['2v2'])} 2v2 Hellgate Battles",
                flush=True,
            )

        HellgateWatcher.save_json(
            REPORTED_BATTLES_JSON_PATH, reported_battles_per_server
        )

        return recent_battles

    @staticmethod
    async def get_battle_events(battle_id: int, server_url: str) -> List[dict]:
        return await HellgateWatcher.get_json(f"{server_url}/events/battle/{battle_id}")

    @staticmethod
    async def get_battle_from_id(battle_id: int, server_url: str) -> Battle:
        battle_dict = await HellgateWatcher.get_json(
            f"{server_url}/battles/{battle_id}"
        )
        battle_events = await HellgateWatcher.get_battle_events(battle_id, server_url)
        try:
            battle = Battle(battle_dict=battle_dict, battle_events=battle_events)
        except Exception as e:
            print(f"[{get_current_time_formatted}]\tAn error occurred while parsing battle {battle_id}: {e}")
            return None    
        return Battle(battle_dict, battle_events)

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


def clear_reported_battles():
    reported_battles = HellgateWatcher.load_json(REPORTED_BATTLES_JSON_PATH)
    for server in reported_battles:
        reported_battles[server] = []
    HellgateWatcher.save_json(REPORTED_BATTLES_JSON_PATH, reported_battles)

