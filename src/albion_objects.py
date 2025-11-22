from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from enum import Enum
import asyncio
import json
import os
import aiohttp
from config import (
    BASE_IP,
    BATTLES_LIMIT,
    BATTLES_MAX_AGE_MINUTES,
    CANVAS_WIDTH_2V2,
    LETHAL_2V2_IP_CAP,
    LETHAL_2V2_SOFTCAP_PERCENT,
    LETHAL_5V5_IP_CAP,
    LETHAL_5V5_SOFTCAP_PERCENT,
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
    HEALING_WEAPONS,
    IMAGE_SIZE,
    EQUIPMENT_CANVAS_SIZE,
)


class Slot(Enum):
    MainHand = "MainHand"
    OffHand = "OffHand"
    Armor = "Armor"
    Head = "Head"
    Shoes = "Shoes"
    Cape = "Cape"
    Bag = "Bag"
    Potion = "Potion"
    Food = "Food"

class Item:
    def __init__(self, item_dict: dict):
        self.type: str = ""
        self.tier: int = 0
        self.enchantment: int = 0
        self.quality = item_dict["Quality"]
        item_type = item_dict["Type"]
        self._parse_item_type(item_type)

    def _parse_item_type(self, item_type: str):
        if item_type[0].upper() == "T":
            self.tier = int(item_type[1])
            item_type = item_type[3:]
        else:
            self.tier = 0

        if item_type[-2] == "@":
            self.enchantment = int(item_type[-1])
            item_type = item_type[:-2]

        self.type = item_type

    def __str__(self):
        return f"{self.type.ljust(25)} \tTier: {self.tier} \tEnchantment:{self.enchantment} \tQuality: {self.quality}"

    def _get_quality_ip(self) -> float:
        quality_ip_map = {
            0: 0,  # No Quality Data
            1: 0,  # Normal
            2: 20,  # Good
            3: 40,  # Outstanding
            4: 60,  # Excellent
            5: 100,  # Masterpiece
        }
        return quality_ip_map.get(self.quality, 0)
    
    @staticmethod
    def apply_ip_cap(ip: float, ip_cap: float, soft_cap_percent: int) -> float:
        if ip <= ip_cap:
            return ip
        return ip_cap + (ip - ip_cap) * (soft_cap_percent / 100)

    def get_max_item_power(self, ip_cap: float, ip_softcap_percent: int) -> float:
        """Calculates base item power without mastery bonuses."""
        item_power = BASE_IP
        item_power += self.tier * 100
        item_power += self.enchantment * 100
        item_power += self._get_quality_ip()
        item_power = self.apply_ip_cap(item_power, ip_cap, ip_softcap_percent)
        return item_power

class ArmorPiece(Item):
    def __init__(self, item_dict: dict):
        super().__init__(item_dict)

    def get_max_item_power(self, ip_cap: float, ip_softcap_percent: int) -> float:
        item_power = super().get_max_item_power(ip_cap, ip_softcap_percent)

        MASTERY_BONUS_PERCENT = self.tier - 4 * 5
        MAX_ITEM_LEVEL = 120
        IP_PER_LEVEL = 2
        NB_NON_ARTEFACT_ITEMS = 3
        IP_PER_LEVEL_NON_ARTEFACT_ITEM = 0.2
        NB_ARTEFACT_ITEMS = 4
        IP_PER_LEVEL_ARTEFACT_BRANCH_ITEM = 0.1
        OVERCHARGE_BONUS = 100

        item_power += OVERCHARGE_BONUS
        item_power += MAX_ITEM_LEVEL * IP_PER_LEVEL
        item_power += NB_NON_ARTEFACT_ITEMS * IP_PER_LEVEL_NON_ARTEFACT_ITEM * MAX_ITEM_LEVEL
        item_power += NB_ARTEFACT_ITEMS * IP_PER_LEVEL_ARTEFACT_BRANCH_ITEM * MAX_ITEM_LEVEL
        item_power += item_power * MASTERY_BONUS_PERCENT / 100
        item_power = self.apply_ip_cap(item_power, ip_cap, ip_softcap_percent)

        return item_power

    @property
    def is_plate(self) -> bool:
        return "plate" in self.type.lower() 
    @property
    def is_leather(self) -> bool:
        return "leather" in self.type.lower() 
    @property
    def is_cloth(self) -> bool:
        return "cloth" in self.type.lower() 

class WeaponOrOffhand(Item):
    def __init__(self, item_dict: dict):
        super().__init__(item_dict)

    def get_max_item_power(self, ip_cap: float, ip_softcap_percent: int) -> float:
        item_power = super().get_max_item_power(ip_cap, ip_softcap_percent)

        MASTERY_BONUS_PERCENT = self.tier - 4 * 5
        MAX_ITEM_LEVEL = 120
        IP_PER_LEVEL = 2
        NB_NON_ARTEFACT_ITEMS = 3
        IP_PER_LEVEL_NON_ARTEFACT_ITEM = 0.2
        NB_ARTEFACT_ITEMS = 4
        IP_PER_LEVEL_ARTEFACT_BRANCH_ITEM = 0.1
        NB_CRYSTAL_ITEMS = 5
        IP_PER_LEVEL_CRYSTAL_ITEM = 0.025
        OVERCHARGE_BONUS = 100

        item_power += OVERCHARGE_BONUS
        item_power += MAX_ITEM_LEVEL * IP_PER_LEVEL
        item_power += NB_NON_ARTEFACT_ITEMS * IP_PER_LEVEL_NON_ARTEFACT_ITEM * MAX_ITEM_LEVEL
        item_power += NB_ARTEFACT_ITEMS * IP_PER_LEVEL_ARTEFACT_BRANCH_ITEM * MAX_ITEM_LEVEL
        item_power += NB_CRYSTAL_ITEMS * IP_PER_LEVEL_CRYSTAL_ITEM * MAX_ITEM_LEVEL
        item_power += item_power * MASTERY_BONUS_PERCENT / 100
        item_power = self.apply_ip_cap(item_power, ip_cap, ip_softcap_percent)

        return item_power

class ItemWithoutIPScaling(Item):
    def __init__(self, item_dict: dict):
        super().__init__(item_dict)

    def get_max_item_power(self, ip_cap: float, ip_softcap_percent: int) -> float:
        return super().get_max_item_power(ip_cap, ip_softcap_percent)

class MainHand(WeaponOrOffhand):
    def __init__(self, item_dict: dict):
        super().__init__(item_dict)
    
    @property
    def is_healing_weapon(self) -> bool:
        return self.type in HEALING_WEAPONS

class OffHand(WeaponOrOffhand):
    def __init__(self, item_dict: dict):
        super().__init__(item_dict)

class Armor(ArmorPiece):
    def __init__(self, item_dict: dict):
        super().__init__(item_dict)

class Head(ArmorPiece):
    def __init__(self, item_dict: dict):
        super().__init__(item_dict)

class Shoes(ArmorPiece):
    def __init__(self, item_dict: dict):
        super().__init__(item_dict)

class Cape(ItemWithoutIPScaling):
    def __init__(self, item_dict: dict):
        super().__init__(item_dict)

class Bag(ItemWithoutIPScaling):
    def __init__(self, item_dict: dict):
        super().__init__(item_dict)

class Potion(ItemWithoutIPScaling):
    def __init__(self, item_dict: dict):
        super().__init__(item_dict)

class Food(ItemWithoutIPScaling):
    def __init__(self, item_dict: dict):
        super().__init__(item_dict)

class Equipment:
    
    _item_class_map = {
        Slot.MainHand: MainHand,
        Slot.OffHand: OffHand,
        Slot.Armor: Armor,
        Slot.Head: Head,
        Slot.Shoes: Shoes,
        Slot.Cape: Cape,
        Slot.Bag: Bag,
        Slot.Potion: Potion,
        Slot.Food: Food,
    }


    def __init__(self, equipment_dict: dict):
        self.mainhand: Optional[MainHand] = None
        self.offhand: Optional[OffHand] = None
        self.armor: Optional[Armor] = None
        self.head: Optional[Head] = None
        self.shoes: Optional[Shoes] = None
        self.cape: Optional[Cape] = None
        self.bag: Optional[Bag] = None
        self.potion: Optional[Potion] = None
        self.food: Optional[Food] = None


        for slot, item_class in self._item_class_map.items():
            if equipment_dict.get(slot.value):
                setattr(self, slot.name.lower(), item_class(equipment_dict[slot.value]))

    @property
    def items(self) -> List[Item]:
        return [item for item in self.__dict__.values() if isinstance(item, Item)]

    def __str__(self):
        equipment = ""
        for item in self.items:
            if item is not None:
                slot_name = item.__class__.__name__
                equipment += f"\t{slot_name.ljust(10)}: \t{item}\n"
        return equipment

    def max_average_item_power(self, ip_cap: float, ip_softcap_percent: int) -> int:
        total_ip = 0

        ip_contributing_items = [self.head, self.armor, self.shoes, self.mainhand,self.offhand, self.cape]
        for item in ip_contributing_items:
            if item:
                total_ip += item.get_max_item_power(ip_cap, ip_softcap_percent)

        if self.offhand is None and self.mainhand is not None:  # 2-handed weapon, counts for two slots
            total_ip += self.mainhand.get_max_item_power(ip_cap, ip_softcap_percent)

        return int(total_ip / 6)
    
    def update(self, source_equipment: "Equipment"):
        """
        Updates the current equipment with items from a source equipment object
        if the current equipment has a slot empty.
        """
        for slot, item_class in self._item_class_map.items():
            slot_name = slot.name.lower()
            current_item = getattr(self, slot_name)
            source_item = getattr(source_equipment, slot_name)

            if current_item is None and source_item is not None:
                setattr(self, slot_name, source_item)

class Player:
    id: str
    name: str
    guild: str
    alliance: str
    equipment: Equipment
    average_item_power: float

    def __init__(self, player_dict: dict):
        self.id = player_dict["Id"]
        self.name = player_dict["Name"]
        self.guild = player_dict["GuildName"]
        self.alliance = player_dict["AllianceName"]
        self.equipment = Equipment(player_dict["Equipment"])
        self.average_item_power = player_dict["AverageItemPower"]


    def __str__(self):
        player = f"Player: {self.name}\n"
        player += f"Guild: {self.guild}\n"
        player += f"Alliance: {self.alliance}\n"
        player += f"Equipment:\n{self.equipment}"
        return player

    def max_average_item_power(self, ip_cap: float, ip_softcap_percent: int) -> float:
        return self.equipment.max_average_item_power(ip_cap, ip_softcap_percent)
    
    def update(self, other_player: "Player"):
        """
        Updates the player's equipment from another Player object if they are the same player.
        """
        if other_player.id == self.id:
            self.equipment.update(other_player.equipment)
            if self.average_item_power == 0 and other_player.average_item_power > 0:
                self.average_item_power = other_player.average_item_power

class Event:
    def __init__(self, event_dict: dict):
        self.id:int = event_dict["EventId"]
        self.killer = Player(event_dict["Killer"])
        self.victim = Player(event_dict["Victim"])
        self.participants = [Player(participant) for participant in event_dict["Participants"]]
        self.group_members = [Player(group_member) for group_member in event_dict["GroupMembers"]]

    def __str__(self):
        event =  f"Event: {self.id} \tKiller: {self.killer.name} \tVictim: {self.victim.name}\n"
        event += f"\tParticipants: {[participant.name for participant in self.participants]}\n"
        event += f"\tGroup Members: {[group_member.name for group_member in self.group_members]}\n"

class Battle:
    def __init__(self, battle_dict: dict, battle_events: List[dict]):
        assert battle_dict is not None, f"battle_dict cannot be None"
        assert battle_events is not None, f"battle_events cannot be None {battle_dict['id']}"


        self.id: int = battle_dict["id"]
        self.start_time: str = battle_dict["startTime"]
        self.end_time: str = battle_dict["endTime"]
        self.events: List[Event] = [Event(event_dict) for event_dict in battle_events]
        self.victim_ids: List[str] = [event.victim.id for event in self.events]

        self.players: List[Player] = []
        self._find_and_update_players()


        self.team_a_ids: List[str] = []
        self.team_b_ids: List[str] = []

        self._split_ids_by_team()
        self._sort_teams_by_class()



    def __str__(self):
        battle = f"Battle: {self.id} \tStart Time: {self.start_time} \tEnd Time: {self.end_time}\n"
        battle += f"\tPlayers: {[player.name for player in self.players]}\n"
        battle += f"\tVictims: {[self.get_player(player_id).name for player_id in self.victim_ids]}\n"
        battle += f"\tTeam A:  {[self.get_player(player_id).name for player_id in self.team_a_ids]}\n"
        battle += f"\tTeam A:  {[self.get_player(player_id).name for player_id in self.team_b_ids]}\n"
        return battle

    @property
    def is_hellgate_5v5(self) -> bool:

        ten_player_battle = len(self.players) == 10
        if not ten_player_battle:
            return False

        five_vs_five = self._is_x_vs_x_battle(5)
        if not five_vs_five:
            return False
        
        print(f"{self.id} is 5v5",flush=True)

        ip_capped = self._is_ip_capped(ip_cap=LETHAL_5V5_IP_CAP, ip_softcap_percent=LETHAL_5V5_SOFTCAP_PERCENT)
        if not ip_capped:
            return False
        
        print(f"{self.id} is IP capped",flush=True)

        return True
    
    
    @property
    def is_hellgate_2v2(self) -> bool:

        four_player_battle = len(self.players) == 4
        if not four_player_battle:
            return False
        
        print(f"{self.id} is a 4 man battle",flush=True)

        two_vs_two = self._is_x_vs_x_battle(2)
        if not two_vs_two:
            return False

        print(f"{self.id} is 2v2",flush=True)


        ip_capped = self._is_ip_capped(ip_cap=LETHAL_2V2_IP_CAP, ip_softcap_percent=LETHAL_2V2_SOFTCAP_PERCENT)
        if not ip_capped:
            return False
        print(f"{self.id} is IP capped",flush=True)

        return True
    
    def _is_x_vs_x_battle(self,x:int) -> bool:
        has_team_of_size_x = False
        for event in self.events:

            group_member_count = len(event.group_members)
            team_of_size_geater_than_x = group_member_count > x

            if team_of_size_geater_than_x:
                return False
            if group_member_count == 5:
                has_team_of_size_x = True

        return has_team_of_size_x
    
    
    
    def _is_ip_capped(self, ip_cap: float, ip_softcap_percent: int) -> bool:
        for player in self.players:
            ACCOUNT_FOR_ARTIFACT_IP = 100
            if player.average_item_power > player.max_average_item_power(ip_cap, ip_softcap_percent) + ACCOUNT_FOR_ARTIFACT_IP:
                print (f"Player {player.name} has an average item power of {player.average_item_power} and max average item power of {player.max_average_item_power(ip_cap, ip_softcap_percent)+ACCOUNT_FOR_ARTIFACT_IP}",flush=True)
                return False
        return True

    def _split_ids_by_team(self) -> None:
        team_a_ids = set()
        team_b_ids = set()

        all_player_ids = set([player.id for player in self.players])

        # Seed the teams with the first event's killer.
        if self.events:
            first_killer_id = self.events[0].killer.id
            team_a_ids.add(first_killer_id)

        # Iteratively assign players to teams until the assignments are stable.
        for _ in range(len(all_player_ids) + 1):
            for event in self.events:
                killer_id = event.killer.id
                victim_id = event.victim.id

                group_member_ids = {player.id for player in event.group_members}

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
  
        if len(team_a_ids) >= len(self.players) // 2:
            team_b_ids.update(all_player_ids - team_a_ids)
            team_a_ids = all_player_ids - team_b_ids
        elif len(team_b_ids) >= len(self.players) // 2:
            team_a_ids.update(all_player_ids - team_b_ids)
            team_b_ids = all_player_ids - team_a_ids
  
        self.team_a_ids = list(team_a_ids)
        self.team_b_ids = list(team_b_ids)

    def get_player(self, id: str) -> Player:
        for player in self.players:
            if player.id == id:
                return player
        return None


    def _sort_teams_by_class(self) -> None:
        self.team_a_ids = self._sort_team(self.team_a_ids)
        self.team_b_ids = self._sort_team(self.team_b_ids)

    def _sort_team(self, team: List[str]) -> List[str]:
        
        healers = []
        melees = []
        tanks = []
        leathers = []
        cloth = []
        unknown = []

        for player_id in team:

            player = self.get_player(player_id)

            if player.equipment.mainhand is not None and player.equipment.mainhand.is_healing_weapon:
                healers.append(player_id)
                continue
            
            if player.equipment.armor is not None:
                if player.equipment.armor.is_plate:
                    
                    if (
                        "ROYAL" in player.equipment.armor.type or 
                        "SET1" in player.equipment.armor.type
                    ):
                        melees.append(player_id)
                        continue
                    
                    melees.append(player_id)
                    continue

                if player.equipment.armor.is_leather:
                    leathers.append(player_id)
                    continue

                if player.equipment.armor.is_cloth:
                    cloth.append(player_id)
                    continue

            else:
                unknown.append(player_id)
                continue

        def key(player_id):
            if self.get_player(player_id).equipment.mainhand is None:
                return "Z"
            return self.get_player(player_id).equipment.mainhand.type

        cloth.sort(key=key)
        unknown.sort(key=key)
        tanks.sort(key=key)
        melees.sort(key=key)
        leathers.sort(key=key)
        cloth.sort(key=key)
        healers.sort(key=key)

        sorted_team = unknown + tanks + melees + leathers + cloth + healers
        return sorted_team
    
    def _find_and_update_players(self):

        for event in self.events:
            all_players = event.participants + event.group_members + [event.killer, event.victim]
            for player in all_players:
                if self.get_player(player.id) is None:
                    self.players.append(player)
                else:
                    self.get_player(player.id).update(player)

class BattleReportImageGenerator():
    def __init__(self):
        pass

    @staticmethod
    async def generate_5v5_battle_reports(battles: List[Battle]) -> List[str]:
        battle_reports = [await BattleReportImageGenerator.generate_5v5_battle_report(battle) for battle in battles]
        return battle_reports
    

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
                    f"\tAn error occurred while fetching {url}: {e}"
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
                    f"\tAn error occurred while fetching {url}: {e}"
                )
                return None

    @staticmethod
    async def generate_battle_report_2v2(battle: Battle) -> str:
        return await BattleReportImageGenerator._generate_battle_report(battle, CANVAS_WIDTH_2V2, BATTLE_REPORT_CANVAS_SIZE_2V2)
    
    @staticmethod
    async def generate_battle_report_5v5(battle: Battle) -> str:
        return await BattleReportImageGenerator._generate_battle_report(battle, CANVAS_WIDTH_5V5, BATTLE_REPORT_CANVAS_SIZE_5V5)

    @staticmethod
    async def _generate_battle_report(battle: Battle, canvas_width: int, battle_report_canvas_size: int) -> str:
        battle_report_image = Image.new("RGB", battle_report_canvas_size, BACKGROUND_COLOR)

        draw = ImageDraw.Draw(battle_report_image)

        player_name_font = ImageFont.truetype(PLAYER_NAME_FONT_PATH, PLAYER_NAME_FONT_SIZE)  
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
                equipment_image_path = await BattleReportImageGenerator.generate_equipment_image(player.equipment)
                equipment_image = Image.open(equipment_image_path).convert("RGBA")

                # Make dead players gray
                if player_id in battle.victim_ids:
                    enhancer = ImageEnhance.Color(equipment_image)
                    equipment_image = enhancer.enhance(DEAD_PLAYER_GRAYSCALE_ENHANCEMENT)

                R, G, B, A = equipment_image.split()
                battle_report_image.paste(
                    im=equipment_image, box=(x_pos, y_pos + PLAYER_NAME_AREA_HEIGHT), mask=A
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
                draw.text((ip_text_x, ip_text_y), ip_text, font=ip_font, fill=FONT_COLOR)

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
        duration = datetime.fromisoformat(battle.end_time) - datetime.fromisoformat(battle.start_time)
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
            f"\tgenerating {battle_report_image_path}"
        )

        battle_report_image.save(battle_report_image_path)

        return battle_report_image_path

class HellgateWatcher():


    def __init__(self):
        pass

    async def get_json(self, url: str) -> Dict | None:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT)
        ) as session:
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    return await response.json()

            except Exception as e:
                print(
                    f"An error occurred while fetching {url}: {e}"
                )
                return None

    async def _get_50_battles(self, server_url:str, limit=BATTLES_LIMIT, page=1):
        battles = []
        request = f"{server_url}/battles?limit={limit}&sort=recent&offset={page * limit}"
        response_json = await self.get_json(request)

        if response_json:
            battles.extend(list(response_json))
        return battles

    def _contains_battles_out_of_range(self, battles_dicts):
        if not battles_dicts:
            return False

        times = [
            datetime.fromisoformat(battle_dict["startTime"].replace("Z", "+00:00"))
            for battle_dict in battles_dicts
        ]
        return max(times) - min(times) > timedelta(minutes=BATTLES_MAX_AGE_MINUTES)

    async def get_recent_battles(self) -> List[Battle]:

        reported_battles_per_server = self.load_json(REPORTED_BATTLES_JSON_PATH)

        recent_battles= {
            "europe": {
                "5v5": [],
                "2v2": [],
                "total": 0
            },
            "americas": {
                "5v5": [],
                "2v2": [],
                "total": 0
            },
            "asia": {
                "5v5": [],
                "2v2": [],
                "total": 0
            }
        }

        for server in ["europe", "americas", "asia"]:
            
            page_number = 0
            battles_dicts = []
            reported_battles = reported_battles_per_server.get(server, [])
            server_url = SERVER_URLS[server]

            while not self._contains_battles_out_of_range(battles_dicts):
                battles_dicts.extend(await self._get_50_battles(server_url, page=page_number))
                page_number += 1
                print(f"{len(battles_dicts)} battles fetched for {server}",flush=True)

            recent_battles[server]["total"] = len(battles_dicts)

            for battle_dict in battles_dicts:
                player_count = len(battle_dict["players"])

                if player_count <= 10:
                    print(f"{battle_dict['id']} found a 10 man battle for {server}",flush=True)
                    battle_events = await self.get_battle_events(battle_dict["id"], server_url)
                    battle = Battle(battle_dict=battle_dict, battle_events=battle_events)
                    if battle.is_hellgate_5v5:
                        recent_battles[server]["5v5"].append(battle)
                        print(f"{battle.id} found a 5v5 battle for {server}",flush=True)
                    elif battle.is_hellgate_2v2:
                        recent_battles[server]["2v2"].append(battle)
                        print(f"{battle.id} found a 2v2 battle for {server}",flush=True)

        return recent_battles

    async def get_battle_events(self, battle_id: int, server_url: str) -> List[dict]:
        return await self.get_json(f"{server_url}/events/battle/{battle_id}")

    async def get_battle_from_id(self, battle_id: int, server_url: str) -> Battle:
        battle_dict = await self.get_json(f"{server_url}/battles/{battle_id}")
        battle_events = await self.get_battle_events(battle_id, server_url)
        return Battle(battle_dict, battle_events)

    def load_json(self, json_path: str) -> Dict:
        with open(json_path, "r") as f:
            return json.load(f)
        
    def save_json(self, json_path: str, data: Dict) -> None:
        with open(json_path, "w+") as f:
            json.dump(data, f, indent=4)