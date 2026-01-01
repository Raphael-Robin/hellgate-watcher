from typing import Dict, List

from src.albion_objects import *
from src.utils import logger

from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import datetime
import os
import aiohttp
from config import *
from src.hellgate_watcher import clear_equipments_images




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

        url = f"{RENDER_API_URL}T{item.tier}_{item.type}@{item.enchantment}.png?count=1&quality={item.quality}"

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
                logger.error(f"An error occurred while fetching {url}: {e}")
                return None

    @staticmethod
    async def get_json(url: str) -> Dict | None:
        attempt = 0
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT)
        ) as session:
            while attempt < MAX_RETRIES:
                try:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        return await response.json()

                except Exception as e:
                    logger.error(f"An error occurred while fetching {url}: {e}")
                attempt += 1
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
        battle: Battle, canvas_width: int, battle_report_canvas_size: tuple[int, int]
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

        logger.info(f"saving battle report image to {battle_report_image_path}")

        battle_report_image.save(battle_report_image_path)

        clear_equipments_images()

        return battle_report_image_path
