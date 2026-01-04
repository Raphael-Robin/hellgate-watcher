from src.database import get_most_active_players, pretty_print_stats,get_player_statistics
import asyncio


async def main():
    players = await get_most_active_players("europe")
    if not players :
        return
    for player in players:
        pretty_print_stats(await get_player_statistics(player))
        print('\n')

if __name__ == "__main__":
    asyncio.run(main())