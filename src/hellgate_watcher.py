import asyncio
from datetime import datetime, timedelta
import json
from typing import TypedDict, List, Dict, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import os
import aiohttp
from config import (
    BATTLES_LIMIT,
    BATTLES_MAX_AGE_MINUTES,
    OVERCHARGE_BONUS_IP,
    LETHAL_5v5_IP_CAP,
    LETHAL_5v5_SOFTCAP_PERCENT,
    QUALITY_IP,
    SERVER_URL,
    RENDER_API_URL,
    IMAGE_FOLDER,
    EQUIPMENT_IMAGE_FOLDER,
    ITEM_IMAGE_FOLDER,
    BATTLE_REPORT_IMAGE_FOLDER,
    REPORTED_BATTLES_JSON_PATH,
    RATE_LIMIT_DELAY_SECONDS,
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
    CANVAS_WIDTH,
    SIDE_PADDING,
    BACKGROUND_COLOR,
    DEAD_PLAYER_GRAYSCALE_ENHANCEMENT,
    LAYOUT,
    BATTLE_REPORT_CANVAS_SIZE,
    HEALING_WEAPONS,
    VERBOSE_LOGGING,
    IMAGE_SIZE,
    EQUIPMENT_CANVAS_SIZE,
)


class Item(TypedDict):
    type: str
    quality: int


class Equipment(TypedDict):
    bag: Item
    head: Item
    cape: Item
    mainHand: Item
    armor: Item
    offHand: Item
    potion: Item
    shoes: Item
    food: Item


class Player(TypedDict):
    id: str
    name: str
    guild: str
    alliance: str
    equipment: Equipment
    averageItemPower: float


class Battle(TypedDict):
    id: str
    startTime: str
    team_a_ids: list[int]
    team_b_ids: list[int]
    players: dict[str, Player]
    victims: list[str]
    events: list[dict]


async def get_battle_reports():
    hellgate_battles = await get_hellgate_battles()
    hellgate_battle_reports = await generate_battle_reports(hellgate_battles)
    hellgate_battle_reports.reverse()
    return hellgate_battle_reports


async def get_hellgate_battles() -> List[Battle]:
    recent_battles = await get_recent_battles()
    hellgate_battles = []
    for battle in recent_battles:
        if is_hellgate_battle(battle):
            hellgate_battles.append(battle)
    return hellgate_battles


def is_hellgate_battle(battle: Battle) -> bool:
    ten_player_battle = is_ten_player_battle(battle)
    if not ten_player_battle:
        return False

    five_vs_five = is_five_vs_five_battle(battle)
    if not five_vs_five:
        return False

    ip_capped = is_ip_capped(battle)
    if not ip_capped:
        return False

    return True


def is_ten_player_battle(battle: Battle) -> bool:
    return len(battle["players"]) == 10


def is_five_vs_five_battle(battle: Battle) -> bool:
    for event in battle["events"]:
        if event["groupMemberCount"] > 5:
            return False
    return True


def is_ip_capped(battle: Battle) -> bool:
    for player in battle["players"].values():
        max_ip = get_max_ip_player(player)
        if player["averageItemPower"] > max_ip + 75:
            print(
                f"[{get_current_time_formatted().ljust(20)}]\tPlayer {player['name']} has {int(player['averageItemPower'])} IP, however the maximum possible IP is {max_ip}. Battle id {battle['id']}"
            )
            return False
    return True


def get_max_ip_player(player: Player) -> int:
    max_ip_player = 0
    for key in player["equipment"].keys():
        if key in ["bag", "potion", "food"]:
            continue
        elif key == "cape":
            max_ip_player += get_max_ip_item(player["equipment"][key], is_cape=True)
            continue

        max_ip_player += get_max_ip_item(player["equipment"][key])
    if not player["equipment"]["offHand"]:
        max_ip_player += get_max_ip_item(player["equipment"]["mainHand"])
    max_average_ip_player = max_ip_player / 6
    return int(max_average_ip_player)


def get_max_ip_item(item: Item, is_cape=False) -> float:
    if not item:
        return 0.0

    tier = 4
    if item["type"][0].upper() == "T":
        tier = float(item["type"][1])

    enchatment = 0
    if item["type"][-2] == "@":
        enchatment = float(item["type"][-1])

    mastery_bonus_percent = tier - 4 * 5
    base_ip = 300 + (tier + enchatment) * 100 + QUALITY_IP[str(item["quality"])]
    max_spec_bonus_ip = (120 * 2 + 36 * 2 + 48 + 3 * 7) * (not is_cape)
    overcharge_bonus = OVERCHARGE_BONUS_IP * (not is_cape)
    max_ip = (
        base_ip
        + max_spec_bonus_ip * (1 + mastery_bonus_percent / 100)
        + overcharge_bonus
    )
    max_ip_soft_capped = apply_5v5_ip_soft_cap(max_ip)

    return max_ip_soft_capped


def apply_5v5_ip_soft_cap(ip: float) -> float:
    if ip <= LETHAL_5v5_IP_CAP:
        return ip
    return LETHAL_5v5_IP_CAP + (ip - LETHAL_5v5_IP_CAP) * (
        LETHAL_5v5_SOFTCAP_PERCENT / 100
    )


async def generate_battle_reports(battles: List[Battle]) -> List[str]:
    battle_reports = [await generate_battle_report(battle) for battle in battles]
    return battle_reports


async def generate_equipment_image(equipment: Equipment) -> str:
    item_images = {}

    for item_slot in equipment:
        if not equipment[item_slot]:
            continue
        image_path = await generate_item_image(equipment[item_slot])
        item_images[item_slot] = image_path

    equipment_image = Image.new("RGB", EQUIPMENT_CANVAS_SIZE, BACKGROUND_COLOR)

    for item_slot in item_images:
        image = item_images[item_slot]
        if not image:
            continue
        if item_slot in LAYOUT:
            item_image = Image.open(image).convert("RGBA")
            coords = (
                LAYOUT[item_slot][0] * IMAGE_SIZE,
                LAYOUT[item_slot][1] * IMAGE_SIZE,
            )
            R, G, B, A = item_image.split()
            equipment_image.paste(item_image, coords, A)

    for item_slot, item_image in item_images.items():
        item_image = Image.open(item_image).convert("RGBA")
        coords = (LAYOUT[item_slot][0] * IMAGE_SIZE, LAYOUT[item_slot][1] * IMAGE_SIZE)
        R, G, B, A = item_image.split()
        equipment_image.paste(item_image, coords, A)

    image_name = "equipment_"
    for item_slot, item in equipment.items():
        if item is None:
            continue
        image_name += item["type"]

    equipment_image_path = f"{EQUIPMENT_IMAGE_FOLDER}/{image_name}.png"

    if VERBOSE_LOGGING:
        print(
            f"[{get_current_time_formatted().ljust(20)}]\tgenerating {equipment_image_path}"
        )

    equipment_image.save(equipment_image_path)

    return equipment_image_path


async def generate_item_image(item: Item) -> str | None:
    if not item:
        return None

    item_image_path = f"{ITEM_IMAGE_FOLDER}/{item['type']}&{item['quality']}.png"
    if os.path.exists(item_image_path):
        return item_image_path

    url = f"{RENDER_API_URL}{item['type']}.png?count=1&quality={item['quality']}"

    image = await get_image(url)
    if not image:
        return None

    with open(item_image_path, "wb") as f:
        f.write(image)
    return item_image_path


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
                f"[{get_current_time_formatted().ljust(20)}]\tAn error occurred while fetching {url}: {e}"
            )
            return None


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
                f"[{get_current_time_formatted().ljust(20)}]\tAn error occurred while fetching {url}: {e}"
            )
            return None


async def generate_battle_report(battle: Battle) -> str:
    battle_report_image = Image.new("RGB", BATTLE_REPORT_CANVAS_SIZE, BACKGROUND_COLOR)

    draw = ImageDraw.Draw(battle_report_image)

    try:
        player_name_font = ImageFont.truetype(
            PLAYER_NAME_FONT_PATH, PLAYER_NAME_FONT_SIZE
        )  # Keep player name font size
        timestamp_font = ImageFont.truetype(
            TIMESTAMP_FONT_PATH, TIMESTAMP_FONT_SIZE
        )  # Increased font size for timestamp
        ip_font = ImageFont.truetype(TIMESTAMP_FONT_PATH, 35)
    except IOError:
        print(
            f"[{get_current_time_formatted().ljust(20)}]\tFont not found. Using default font."
        )
        player_name_font = ImageFont.load_default()
        timestamp_font = ImageFont.load_default()
        ip_font = ImageFont.load_default()

    async def draw_team(y_pos, team_ids):
        for i, player_id in enumerate(team_ids):
            x_pos = SIDE_PADDING + i * (EQUIPMENT_IMAGE_SIZE + SPACING)
            player = battle["players"][player_id]

            # Draw player name
            # Center the name above the equipment image
            bbox = draw.textbbox((0, 0), player["name"], font=player_name_font)
            text_width = bbox[2] - bbox[0]
            draw.text(
                text=player["name"],
                xy=(x_pos + (EQUIPMENT_IMAGE_SIZE - text_width) / 2, y_pos),
                font=player_name_font,
                fill=FONT_COLOR,
            )

            # Paste equipment image
            equipment_image_path = await generate_equipment_image(player["equipment"])
            equipment_image = Image.open(equipment_image_path).convert("RGBA")

            # Make dead players gray
            if player["id"] in battle["victims"]:
                enhancer = ImageEnhance.Color(equipment_image)
                equipment_image = enhancer.enhance(DEAD_PLAYER_GRAYSCALE_ENHANCEMENT)

            R, G, B, A = equipment_image.split()
            battle_report_image.paste(
                im=equipment_image, box=(x_pos, y_pos + PLAYER_NAME_AREA_HEIGHT), mask=A
            )

            # Draw Average Item Power
            ip_text = str(round(player["averageItemPower"]))
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
            draw.text((ip_text_x, ip_text_y), ip_text, font=ip_font, fill=FONT_COLOR)

    # --- Draw Team A ---
    y_pos = TOP_BOTTOM_PADDING
    await draw_team(y_pos, battle["team_a_ids"])

    # --- Draw Team B ---
    y_pos = (
        TOP_BOTTOM_PADDING
        + PLAYER_NAME_AREA_HEIGHT
        + EQUIPMENT_IMAGE_SIZE
        + IP_AREA_HEIGHT
        + MIDDLE_GAP
    )
    await draw_team(y_pos, battle["team_b_ids"])

    # --- Draw Timestamp ---
    times = [datetime.fromisoformat(event["TimeStamp"]) for event in battle["events"]]
    duration = (max(times) - min(times)).total_seconds()
    duration_minutes = int(duration // 60)
    duration_seconds = int(duration % 60)
    start_time = battle["startTime"]
    start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

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
        ((CANVAS_WIDTH - start_text_width) / 2, start_text_y),
        start_time_text,
        font=timestamp_font,
        fill=(255, 255, 255),
    )

    duration_bbox = draw.textbbox((0, 0), duration_text, font=timestamp_font)
    duration_text_width = duration_bbox[2] - duration_bbox[0]
    draw.text(
        ((CANVAS_WIDTH - duration_text_width) / 2, duration_text_y),
        duration_text,
        font=timestamp_font,
        fill=(255, 255, 255),
    )

    battle_report_image_path = (
        f"{BATTLE_REPORT_IMAGE_FOLDER}/battle_report_{battle['id']}.png"
    )

    print(
        f"[{get_current_time_formatted().ljust(20)}]\tgenerating {battle_report_image_path}"
    )
    battle_report_image.save(battle_report_image_path)
    return battle_report_image_path


def get_battle_object(battle_dict: dict, battle_events: list[dict]) -> Battle:
    battle = Battle(
        id=battle_dict["id"],
        startTime=battle_dict["startTime"],
        events=battle_events,
        victims=[event["Victim"]["Id"] for event in battle_events],
        players=get_players(battle_dict, battle_events),
    )
    split_ids_by_team(battle=battle)

    return battle


def get_players(battle_dict, battle_events) -> Dict[str, Player]:
    players = {}
    for player_id, player_dict in battle_dict["players"].items():
        player = Player(
            id=player_id,
            name=player_dict["name"],
            guild=player_dict["guildName"],
            alliance=player_dict["allianceName"],
            equipment=get_equipment(player_id, battle_events),
            averageItemPower=get_average_item_power(player_id, battle_events),
        )
        players[player["id"]] = player
    return players


def get_equipment(id, battle_events) -> Equipment:
    equipment = Equipment(
        mainHand=None,
        offHand=None,
        armor=None,
        head=None,
        shoes=None,
        cape=None,
        bag=None,
        potion=None,
        food=None,
    )
    for event in battle_events:
        player_data = []
        player_data.append(event["Killer"])
        player_data.append(event["Victim"])
        for participant in event["Participants"]:
            player_data.append(participant)
        for group_member in event["GroupMembers"]:
            player_data.append(group_member)
        for player in player_data:
            if player["Id"] == id:
                if equipment["mainHand"] is None:
                    equipment["mainHand"] = get_item(player["Equipment"]["MainHand"])
                if equipment["offHand"] is None:
                    equipment["offHand"] = get_item(player["Equipment"]["OffHand"])
                if equipment["armor"] is None:
                    equipment["armor"] = get_item(player["Equipment"]["Armor"])
                if equipment["head"] is None:
                    equipment["head"] = get_item(player["Equipment"]["Head"])
                if equipment["shoes"] is None:
                    equipment["shoes"] = get_item(player["Equipment"]["Shoes"])
                if equipment["cape"] is None:
                    equipment["cape"] = get_item(player["Equipment"]["Cape"])
                if equipment["bag"] is None:
                    equipment["bag"] = get_item(player["Equipment"]["Bag"])
                if equipment["potion"] is None:
                    equipment["potion"] = get_item(player["Equipment"]["Potion"])
                if equipment["food"] is None:
                    equipment["food"] = get_item(player["Equipment"]["Food"])
    return equipment


def get_item(item_dict) -> Item | None:
    if not item_dict:
        return None
    item = Item(type=item_dict["Type"], quality=item_dict["Quality"])
    return item


def get_average_item_power(id, battle_events) -> float:
    average_item_power = 0.0
    for event in battle_events:
        player_data = []
        player_data.append(event["Killer"])
        player_data.append(event["Victim"])
        player_data.extend(event["Participants"])

        for player in player_data:
            if (
                player["Id"] == id
                and "AverageItemPower" in player.keys()
                and player["AverageItemPower"] > 0.0
            ):
                average_item_power = player["AverageItemPower"]
    return average_item_power


def split_ids_by_team(battle: Battle) -> Tuple[list[str], list[str]]:
    team_a_ids = set()
    team_b_ids = set()

    all_player_ids = set(battle["players"].keys())

    # Seed the teams with the first event's killer.
    if battle["events"]:
        first_killer_id = battle["events"][0]["Killer"]["Id"]
        team_a_ids.add(first_killer_id)

    # Iteratively assign players to teams until the assignments are stable.
    for _ in range(len(all_player_ids) + 1):
        for event in battle["events"]:
            killer_id = event["Killer"]["Id"]
            victim_id = event["Victim"]["Id"]

            group_member_ids = {p["Id"] for p in event["GroupMembers"]}

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

    # Assigning any remaining unassigned players
    # if either team is full, add any remaining players to the other team
    if len(all_player_ids) == 10:
        if len(team_a_ids) >= 5:
            team_b_ids.update(all_player_ids - team_a_ids)
            team_a_ids = all_player_ids - team_b_ids  # Recalculate to trim extras
        elif len(team_b_ids) >= 5:
            team_a_ids.update(all_player_ids - team_b_ids)
            team_b_ids = all_player_ids - team_a_ids  # Recalculate to trim extras
    battle["team_a_ids"] = list(team_a_ids)
    battle["team_b_ids"] = list(team_b_ids)

    sort_teams_ids_by_class(battle)


def load_reported_battles():
    try:
        with open(REPORTED_BATTLES_JSON_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_reported_battles(reported_battles):
    directory = os.path.dirname(REPORTED_BATTLES_JSON_PATH)
    os.makedirs(directory, exist_ok=True)
    with open(REPORTED_BATTLES_JSON_PATH, "w") as f:
        json.dump(reported_battles, f, indent=4)


async def get_50_battles(server_url, limit=BATTLES_LIMIT, page=1):
    battles = []
    request = f"{server_url}/battles?limit={limit}&sort=recent&offset={page * limit}"
    response_json = await get_json(request)

    if response_json:
        battles.extend(list(response_json))
    return battles


def contains_battles_out_of_range(battles):
    if not battles:
        return False

    times = [
        datetime.fromisoformat(battle["startTime"].replace("Z", "+00:00"))
        for battle in battles
    ]
    return max(times) - min(times) > timedelta(minutes=BATTLES_MAX_AGE_MINUTES)


async def get_recent_battles() -> List[Battle]:
    battles_dicts = []
    battles = []
    page_number = 0

    while not contains_battles_out_of_range(battles_dicts):
        battles_dicts.extend(
            await get_50_battles(SERVER_URL, limit=BATTLES_LIMIT, page=page_number)
        )
        page_number += 1
        await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)

    print(
        f"[{get_current_time_formatted().ljust(20)}]\tParsed {len(battles_dicts)} Battles"
    )

    battles_dicts = [battle for battle in battles_dicts if len(battle["players"]) == 10]
    print(
        f"[{get_current_time_formatted().ljust(20)}]\tFound {len(battles_dicts)} battles with 10 players"
    )

    reported_battles = load_reported_battles()

    for battle_dict in battles_dicts:
        id = battle_dict["id"]
        if id not in reported_battles:
            reported_battles.append(id)

            url = f"{SERVER_URL}/events/battle/{id}"
            battle_events = await get_json(url)

            if not battle_events:
                continue

            battle = get_battle_object(battle_dict, battle_events)

            if not is_hellgate_battle(battle):
                continue

            battles.append(battle)

    save_reported_battles(reported_battles)
    print(
        f"[{get_current_time_formatted().ljust(20)}]\tFound {len(battles)} hellgate battles"
    )
    return battles


def sort_teams_ids_by_class(battle: Battle) -> None:
    battle["team_a_ids"] = sort_team_ids_by_class(
        battle["team_a_ids"], battle["players"]
    )
    battle["team_b_ids"] = sort_team_ids_by_class(
        battle["team_b_ids"], battle["players"]
    )


def sort_team_ids_by_class(team, players) -> List[str]:
    healers = []
    melees = []
    tanks = []
    leathers = []
    cloth = []
    unknown = []

    for player_id in team:
        player = players[player_id]

        if is_healer(player):
            healers.append(player_id)
            continue

        if player["equipment"]["armor"] is None:
            unknown.append(player_id)
            continue

        if (
            "PLATE_ROYAL" in player["equipment"]["armor"]["type"]
            or "PLATE_SET1" in player["equipment"]["armor"]["type"]
        ):
            melees.append(player_id)
            continue

        elif "PLATE" in player["equipment"]["armor"]["type"]:
            tanks.append(player_id)
            continue

        elif "LEATHER" in player["equipment"]["armor"]["type"]:
            leathers.append(player_id)
            continue

        else:
            cloth.append(player_id)
            continue

    try:

        def key(player_id):
            if not players[player_id]["equipment"]["mainHand"]:
                return "zzzzzzzzzzz"
            return players[player_id]["equipment"]["mainHand"]["type"][2:]

        cloth.sort(key=key)
        unknown.sort(key=key)
        tanks.sort(key=key)
        melees.sort(key=key)
        leathers.sort(key=key)
        cloth.sort(key=key)
        healers.sort(key=key)
    except Exception as e:
        print(f"[{get_current_time_formatted().ljust(20)}]\tError sorting players: {e}")
    sorted_team = unknown + tanks + melees + leathers + cloth + healers
    return sorted_team


def is_healer(player: Player) -> bool:
    if not player["equipment"]["mainHand"]:
        return False
    weapon = player["equipment"]["mainHand"]["type"][3:].split("@")[0]
    return weapon in HEALING_WEAPONS


def clear_reported_battles() -> None:
    with open(REPORTED_BATTLES_JSON_PATH, "w") as f:
        json.dump([], f, indent=4)


def clear_equipments_images() -> None:
    for filename in os.listdir(os.path.join(IMAGE_FOLDER, "equipments")):
        file_path = os.path.join(os.path.join(IMAGE_FOLDER, "equipments"), filename)
        try:
            if (
                ".png" in filename
                and os.path.isfile(file_path)
                or os.path.islink(file_path)
            ):
                os.unlink(file_path)
        except Exception as e:
            print(
                "f[{get_current_time_formatted().ljust(20)}]\tFailed to delete %s. Reason: %s"
                % (file_path, e)
            )


def clear_battle_reports_images() -> None:
    for filename in os.listdir(os.path.join(IMAGE_FOLDER, "battle_reports")):
        file_path = os.path.join(os.path.join(IMAGE_FOLDER, "battle_reports"), filename)
        try:
            if (
                ".png" in filename
                and os.path.isfile(file_path)
                or os.path.islink(file_path)
            ):
                os.unlink(file_path)
        except Exception as e:
            print(
                f"[{get_current_time_formatted().ljust(20)}]\tFailed to delete %s. Reason: %s"
                % (file_path, e)
            )


async def gen_battle_report_by_id(battle_id):
    battle_dict = await get_json(f"{SERVER_URL}/battles/{battle_id}")
    battle_events = await get_json(f"{SERVER_URL}/events/battle/{battle_id}")
    await generate_battle_report(
        battle=get_battle_object(battle_dict=battle_dict, battle_events=battle_events)
    )


async def get_battle(battle_id):
    battle_dict = await get_json(f"{SERVER_URL}/battles/{battle_id}")
    battle_events = await get_json(f"{SERVER_URL}/events/battle/{battle_id}")
    return get_battle_object(battle_dict=battle_dict, battle_events=battle_events)


def get_current_time_formatted() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def get_battle_events(battle_id):
    return await get_json(f"{SERVER_URL}/events/battle/{battle_id}")


async def get_battle_dict(battle_id):
    return await get_json(f"{SERVER_URL}/battles/{battle_id}")


async def get_battle_obj_from_id(battle_id):
    battle_events = await get_battle_events(battle_id)
    battle_dict = await get_battle_dict(battle_id)
    battle = get_battle_object(battle_dict=battle_dict, battle_events=battle_events)
    return battle
