from src.bot import bot
import dotenv
import os

dotenv.load_dotenv()
DISCORDTOKEN = os.getenv("DISCORDTOKEN")


def main():
    bot.run(DISCORDTOKEN)


if __name__ == "__main__":
    main()
