from hellgate_watcher import generate_battle_report_image, get_recent_battles, find_10_man_battles, find_5v5_battles
import requests

SERVER_URL = "https://gameinfo-ams.albiononline.com/api/gameinfo"


def main():
    battles = get_recent_battles(SERVER_URL,limit=50,pages=1)
    print(f"Parsed {len(battles)} Battles")
    battles = find_10_man_battles(battles)
    print(f"Found {len(battles)} battles with 10 players")
    battles = find_5v5_battles(battles)
    print(f"Found {len(battles)} 5v5 battles")

    print("Battles =====================================")
    for battle in battles:
        id = battle["id"]
        b = requests.get(f"{SERVER_URL}/events/battle/{id}").json()
        generate_battle_report_image(b,id)

    
    id = 286454201
    b = requests.get(f"{SERVER_URL}/events/battle/{id}").json()
    generate_battle_report_image(b,id)


if __name__ == "__main__":
    main()
