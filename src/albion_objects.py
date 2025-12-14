from typing import List, Optional
from enum import Enum
from config import (
    BASE_IP,
    LETHAL_2V2_IP_CAP,
    LETHAL_2V2_SOFTCAP_PERCENT,
    LETHAL_5V5_IP_CAP,
    LETHAL_5V5_SOFTCAP_PERCENT,
    HEALING_WEAPONS,
    VERBOSE_LOGGING,
)
from src.utils import get_current_time_formatted


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
        item_power += (
            NB_NON_ARTEFACT_ITEMS * IP_PER_LEVEL_NON_ARTEFACT_ITEM * MAX_ITEM_LEVEL
        )
        item_power += (
            NB_ARTEFACT_ITEMS * IP_PER_LEVEL_ARTEFACT_BRANCH_ITEM * MAX_ITEM_LEVEL
        )
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
        item_power += (
            NB_NON_ARTEFACT_ITEMS * IP_PER_LEVEL_NON_ARTEFACT_ITEM * MAX_ITEM_LEVEL
        )
        item_power += (
            NB_ARTEFACT_ITEMS * IP_PER_LEVEL_ARTEFACT_BRANCH_ITEM * MAX_ITEM_LEVEL
        )
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

        ip_contributing_items = [
            self.head,
            self.armor,
            self.shoes,
            self.mainhand,
            self.offhand,
            self.cape,
        ]
        for item in ip_contributing_items:
            if item:
                total_ip += item.get_max_item_power(ip_cap, ip_softcap_percent)

        if (
            self.offhand is None and self.mainhand is not None
        ):  # 2-handed weapon, counts for two slots
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
        self.id: int = event_dict["EventId"]
        self.killer = Player(event_dict["Killer"])
        self.victim = Player(event_dict["Victim"])
        self.kill_fame = event_dict["TotalVictimKillFame"]
        self.participants = [
            Player(participant) for participant in event_dict["Participants"]
        ]
        self.group_members = [
            Player(group_member) for group_member in event_dict["GroupMembers"]
        ]

    def __str__(self):
        event = f"Event: {self.id} \tKiller: {self.killer.name} \tVictim: {self.victim.name}\n"
        event += f"\tParticipants: {[participant.name for participant in self.participants]}\n"
        event += f"\tGroup Members: {[group_member.name for group_member in self.group_members]}\n"
        return event


class Battle:
    def __init__(self, battle_dict: dict, battle_events: List[dict]):
        if battle_events is None:
            raise ValueError(
                f"[{get_current_time_formatted}]\t Error: \t{battle_dict['id']} battle_events cannot be None"
            )

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

        if VERBOSE_LOGGING:
            print(f"[{get_current_time_formatted()}]{self.id} is 5v5", flush=True)

        ip_capped = self._is_ip_capped(
            ip_cap=LETHAL_5V5_IP_CAP, ip_softcap_percent=LETHAL_5V5_SOFTCAP_PERCENT
        )
        if not ip_capped:
            return False

        if VERBOSE_LOGGING:
            print(f"[{get_current_time_formatted()}]{self.id} is IP capped", flush=True)

        return True

    @property
    def is_hellgate_2v2(self) -> bool:
        four_player_battle = len(self.players) == 4
        if not four_player_battle:
            return False

        if VERBOSE_LOGGING:
            print(f"{self.id} is a 4 man battle", flush=True)

        two_vs_two = self._is_x_vs_x_battle(2)
        if not two_vs_two:
            return False

        if VERBOSE_LOGGING:
            print(f"{self.id} is 2v2", flush=True)

        ip_capped = self._is_ip_capped(
            ip_cap=LETHAL_2V2_IP_CAP, ip_softcap_percent=LETHAL_2V2_SOFTCAP_PERCENT
        )
        if not ip_capped:
            return False

        if VERBOSE_LOGGING:
            print(f"{self.id} is IP capped", flush=True)

        is_depths = self.is_depths()
        if is_depths:
            return False

        if VERBOSE_LOGGING:
            print(f"{self.id} is not in depths", flush=True)

        return True

    def _is_x_vs_x_battle(self, x: int) -> bool:
        has_team_of_size_x = False
        for event in self.events:
            group_member_count = len(event.group_members)
            team_of_size_geater_than_x = group_member_count > x

            if team_of_size_geater_than_x:
                return False
            if group_member_count == x:
                has_team_of_size_x = True

        return has_team_of_size_x

    def _is_ip_capped(self, ip_cap: float, ip_softcap_percent: int) -> bool:
        for player in self.players:
            ACCOUNT_FOR_ARTIFACT_IP = 100
            if (
                player.average_item_power
                > player.max_average_item_power(ip_cap, ip_softcap_percent)
                + ACCOUNT_FOR_ARTIFACT_IP
            ):
                if VERBOSE_LOGGING:
                    print(
                        f"[{get_current_time_formatted()}]\tBattle: {self.id} \tPlayer {player.name} has an average item power of {player.average_item_power} and max average item power of {player.max_average_item_power(ip_cap, ip_softcap_percent) + ACCOUNT_FOR_ARTIFACT_IP}",
                        flush=True,
                    )
                return False
        return True

    def is_depths(self) -> bool:
        for event in self.events:
            if event.kill_fame == 0:
                return True
        return False

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

            if (
                player.equipment.mainhand is not None
                and player.equipment.mainhand.is_healing_weapon
            ):
                healers.append(player_id)
                continue

            if player.equipment.armor is not None:
                if player.equipment.armor.is_plate:
                    if (
                        "ROYAL" in player.equipment.armor.type
                        or "SET1" in player.equipment.armor.type
                    ):
                        melees.append(player_id)
                        continue

                    tanks.append(player_id)
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
            all_players = (
                event.participants + event.group_members + [event.killer, event.victim]
            )
            for player in all_players:
                if self.get_player(player.id) is None:
                    self.players.append(player)
                else:
                    self.get_player(player.id).update(player)
