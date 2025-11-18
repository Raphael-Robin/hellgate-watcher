from hellgate_watcher import generate_battle_report_image, get_recent_battles, find_10_man_battles, find_5v5_battles
import requests

SERVER_URL = "https://gameinfo-ams.albiononline.com/api/gameinfo"


def main():
    battles = get_recent_battles(SERVER_URL,limit=50,pages=5)
    print(f"Parsed {len(battles)} Battles")
    battles = find_10_man_battles(battles)
    print(f"Found {len(battles)} battles with 10 players")
    battles = find_5v5_battles(battles)
    print(f"Found {len(battles)} 5v5 battles")

    print("Battles =====================================")
    for battle in battles:
        id = battle["id"]
        battle_events = requests.get(f"{SERVER_URL}/events/battle/{id}").json()
        generate_battle_report_image(battle_events,id)

    
    # id = 286561876
    # battle_events = requests.get(f"{SERVER_URL}/events/battle/{id}").json()
    # generate_battle_report_image(battle_events,id)


if __name__ == "__main__":
    main()
