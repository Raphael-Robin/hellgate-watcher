from src.bot import bot
import dotenv
import os

dotenv.load_dotenv()
DISCORDTOKEN = os.getenv("DISCORDTOKEN")


def main():
    if DISCORDTOKEN:
        bot.run(DISCORDTOKEN)
    else:
        raise Exception("Missing DISCORDTOKEN environment variable")


if __name__ == "__main__":
    main()
