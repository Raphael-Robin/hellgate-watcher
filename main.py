import os
from dotenv import load_dotenv
from src.bot import bot

load_dotenv()
DISCORDTOKEN = os.getenv("DISCORDTOKEN")


def main():
    if not DISCORDTOKEN:
        raise Exception("Missing Discord BotToken")
    bot.run(DISCORDTOKEN)


if __name__ == "__main__":
    main()
