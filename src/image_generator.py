from typing import Any, Dict, List
from src.albion_objects import *
from src.utils import logger
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import datetime
import os
import aiohttp
from config import *
from src.hellgate_watcher import clear_equipments_images

# Shared Constants for a cohesive look


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

    @staticmethod
    async def generate_equipment_with_stats_image(equipment: Equipment, stats: Dict[str, Any]) -> str:
        equipment_image_path = await BattleReportImageGenerator.generate_equipment_image(equipment)
        equipment_image = Image.open(equipment_image_path)
        eq_w, eq_h = equipment_image.size

        # --- Metrics ---
        header_h = 80
        row_h = 50
        table_h = header_h + (len(stats) * row_h) + 20
        
        final_image = Image.new("RGB", (eq_w, eq_h + table_h), BACKGROUND_COLOR)
        final_image.paste(equipment_image, (0, 0))
        draw = ImageDraw.Draw(final_image)
        
        # 1. Big Left-Aligned Header
        font_large = ImageFont.truetype(PLAYER_NAME_FONT_PATH, LARGE_FONT_SIZE)
        draw.text((GLOBAL_PADDING, eq_h + 15), "EQUIPMENT STATS", font=font_large, fill=FONT_COLOR)
        
        # 2. Accent Line under Header
        draw.rectangle([GLOBAL_PADDING, eq_h + 70, eq_w - GLOBAL_PADDING, eq_h + 73], fill=PRIMARY_ACCENT)

        # 3. Stats Rows
        font_stats = ImageFont.truetype(TIMESTAMP_FONT_PATH, MEDIUM_FONT_SIZE)
        curr_y = eq_h + header_h + 10
        for key, value in stats.items():
            draw.text((GLOBAL_PADDING, curr_y), f"{key}:", font=font_stats, fill=(180, 180, 180))
            draw.text((eq_w // 2, curr_y), str(value), font=font_stats, fill=FONT_COLOR)
            curr_y += row_h

        path = f"{EQUIPMENT_IMAGE_FOLDER}/eq_{datetime.now().strftime('%f')}.png"
        final_image.save(path)
        return path

    @staticmethod
    async def generate_team_mates_image(team_mates_stats: List[Dict[str, Any]]) -> str:
        # Set standard column widths for a wide dashboard feel
        col_widths = {"name": 450, "battles": 200, "winrate": 200}
        total_w = sum(col_widths.values()) + (GLOBAL_PADDING * 2)
        row_h = 60
        header_h = 80
        
        img_h = header_h + (len(team_mates_stats) * row_h) + GLOBAL_PADDING
        image = Image.new("RGB", (total_w, img_h), BACKGROUND_COLOR)
        draw = ImageDraw.Draw(image)
        
        f_header = ImageFont.truetype(PLAYER_NAME_FONT_PATH, LARGE_FONT_SIZE)
        f_row = ImageFont.truetype(TIMESTAMP_FONT_PATH, MEDIUM_FONT_SIZE)

        # Headers
        cols = [("Player", "name"), ("Battles", "battles"), ("Winrate", "winrate")]
        curr_x = GLOBAL_PADDING
        for label, key in cols:
            draw.text((curr_x, 20), label, font=f_header, fill=PRIMARY_ACCENT)
            curr_x += col_widths[key]

        # Content
        curr_y = header_h
        for player in team_mates_stats:
            curr_x = GLOBAL_PADDING
            draw.text((curr_x, curr_y), str(player.get("player_name", "")), font=f_row, fill=FONT_COLOR)
            curr_x += col_widths["name"]
            draw.text((curr_x, curr_y), str(player.get("nb_battles", "")), font=f_row, fill=FONT_COLOR)
            curr_x += col_widths["battles"]
            draw.text((curr_x, curr_y), str(player.get("winrate", "")), font=f_row, fill=FONT_COLOR)
            curr_y += row_h

        path = f"{EQUIPMENT_IMAGE_FOLDER}/tm_{datetime.now().strftime('%f')}.png"
        image.save(path)
        return path

    @staticmethod
    async def generate_equipment_with_stats_list_image(equipment_stats_list: List[Dict[str, Any]]) -> str:
        """
        Generates a combined image of multiple equipment with their stats.
        Each item in the list is a dict with 'equipment' (Equipment object)
        and 'stats' (Dict[str, any]).
        """
        if not equipment_stats_list:
            return ""

        individual_images = []
        for item_data in equipment_stats_list:
            equipment = item_data["equipment"]
            stats = item_data["stats"]
            image_path = await BattleReportImageGenerator.generate_equipment_with_stats_image(
                equipment, stats
            )
            individual_images.append(Image.open(image_path))

        # Calculate total width and max height
        total_width = sum(img.width for img in individual_images) + (len(individual_images) - 1) * SPACING
        max_height = max(img.height for img in individual_images)

        # Create a new blank image with the calculated dimensions
        combined_image = Image.new("RGB", (total_width, max_height), BACKGROUND_COLOR)

        # Paste individual images horizontally
        current_x = 0
        for img in individual_images:
            combined_image.paste(img, (current_x, 0))
            current_x += img.width + SPACING

        # Save the combined image
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        combined_image_path = (
            f"{EQUIPMENT_IMAGE_FOLDER}/combined_equipment_stats_{timestamp}.png"
        )
        combined_image.save(combined_image_path)
        logger.debug(f"Saved combined equipment with stats image to {combined_image_path}")

        return combined_image_path
       
    @staticmethod
    async def generate_player_stats_image(player_stats: Dict[str, Any]) -> str:
        """
        Generates an image displaying a summary of player stats.
        """
        if not player_stats:
            logger.warning("Received empty dict for player_stats. No image generated.")
            return ""

        # --- Layout settings ---
        title_font = ImageFont.truetype(PLAYER_NAME_FONT_PATH, 40)
        stat_font = ImageFont.truetype(TIMESTAMP_FONT_PATH, 30)
        padding = 20
        line_height = 45
        left_col_width = 200

        # --- Prepare data ---
        stats_to_display = {
            "Battles": player_stats.get("nb_battles", "N/A"),
            "Winrate": player_stats.get("winrate", "N/A"),
            "First Seen": player_stats.get("first_seen"),
            "Last Seen": player_stats.get("last_seen"),
        }

        # Format dates
        for key in ["First Seen", "Last Seen"]:
            if isinstance(stats_to_display[key], datetime):
                stats_to_display[key] = stats_to_display[key].strftime("%d %B %Y")
            elif isinstance(stats_to_display[key], str):
                try:
                    stats_to_display[key] = datetime.fromisoformat(stats_to_display[key].replace("Z", "+00:00")).strftime("%d %B %Y")
                except ValueError:
                    pass # Keep original string if parsing fails


        # --- Canvas setup ---
        img_width = 600
        img_height = padding * 2 + line_height * (len(stats_to_display) + 1) # +1 for title
        
        image = Image.new("RGB", (img_width, img_height), BACKGROUND_COLOR)
        draw = ImageDraw.Draw(image)

        # --- Draw Content ---
        player_name = player_stats.get('name', 'Player Stats')
        title_bbox = draw.textbbox((0,0), player_name, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(((img_width - title_width) / 2, padding), player_name, font=title_font, fill=FONT_COLOR)

        current_y = padding + line_height
        for key, value in stats_to_display.items():
            # Draw Key
            draw.text((padding, current_y), f"{key}:", font=stat_font, fill=FONT_COLOR)
            # Draw Value
            draw.text((padding + left_col_width, current_y), str(value), font=stat_font, fill=FONT_COLOR)
            current_y += line_height

        # --- Save Image ---
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        image_path = f"{BATTLE_REPORT_IMAGE_FOLDER}/player_summary_{timestamp}.png"
        image.save(image_path)
        
        logger.debug(f"Saved player summary image to {image_path}")

        return image_path

    @staticmethod
    async def generate_player_stats_summary_image(stats: dict) -> str:
        # 1. Generate sections
        paths = {
            "PLAYER OVERVIEW": await BattleReportImageGenerator.generate_player_stats_image(stats["player_stats"]),
            "FREQUENT TEAMMATES": await BattleReportImageGenerator.generate_team_mates_image(stats["most_common_relationships"]),
            "MOST USED BUILDS": await BattleReportImageGenerator.generate_equipment_with_stats_list_image(stats["most_played_builds"])
        }
        
        raw_images = {k: Image.open(v) for k, v in paths.items()}
        
        # 2. Resizing - Normalize all to the widest component
        content_width = max(img.width for img in raw_images.values())
        MARGIN = 50
        final_width = content_width + (MARGIN * 2)
        
        processed_sections = []
        for title, img in raw_images.items():
            ratio = content_width / img.width
            new_h = int(img.height * ratio)
            processed_sections.append((title, img.resize((content_width, new_h), Image.Resampling.LANCZOS)))

        # 3. Height Calculation
        BAR_H = 90
        GAP = 60
        total_height = sum(img.height for t, img in processed_sections) + (len(processed_sections) * (BAR_H + GAP)) + MARGIN
        
        final_image = Image.new("RGB", (final_width, total_height), BACKGROUND_COLOR)
        draw = ImageDraw.Draw(final_image)
        f_title = ImageFont.truetype(PLAYER_NAME_FONT_PATH, 50) # Very large section titles

        # 4. Paste Loop
        curr_y = MARGIN
        for title, img in processed_sections:
            # Draw Left-Aligned Section Header
            # Draw a small vertical accent bar next to title
            draw.rectangle([MARGIN, curr_y, MARGIN + 8, curr_y + 50], fill=PRIMARY_ACCENT)
            draw.text((MARGIN + 25, curr_y - 5), title, font=f_title, fill=FONT_COLOR)
            
            curr_y += BAR_H
            
            # Paste Content
            final_image.paste(img, (MARGIN, curr_y))
            curr_y += img.height + GAP

        # 5. Final Save
        save_path = f"{BATTLE_REPORT_IMAGE_FOLDER}/summary_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        final_image.save(save_path)
        
        # Cleanup
        for p in paths.values():
            if os.path.exists(p): os.remove(p)
        return save_path