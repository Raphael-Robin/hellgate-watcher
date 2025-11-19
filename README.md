# Hellgate Watcher Discord Bot

Hellgate Watcher is a Discord bot that monitors 5v5 Hellgate battles in Albion Online, generates detailed battle reports as images, and posts them to a designated Discord channel.

## Features

- **Automatic Battle Monitoring**: Regularly checks for new 5v5 Hellgate battles.
- **Image-based Reports**: Creates easy-to-read image summaries for each battle.
- **Detailed Information**: Reports include the players on each team, their equipment, and a list of who died.
- **Team Composition**: Automatically determines and sorts teams based on in-game roles (Tank, Healer, DPS).
- **Configurable**: Settings like refresh rate and battle age limits can be easily adjusted.

## Prerequisites

- Python 3.13
- A Discord Bot Token
- Git

## Setup Guide

Follow these steps to set up and run the Hellgate Watcher bot.

### 1. Clone the Repository

First, clone this repository to your local machine:

```bash
git clone https://github.com/your-username/hellgate-watcher.git
cd hellgate-watcher
```

### 2. Set Up a Virtual Environment

It is highly recommended to use a virtual environment to manage project dependencies.

```bash
# Create the virtual environment
python -m venv .venv

# Activate it
# On Windows
.venv\Scripts\activate
# On macOS/Linux
source .venv/bin/activate
```

### 3. Install Dependencies

This project uses `uv` for fast package management, but you can also use `pip`.

```bash
# Install dependencies with uv or pip
pip install -r requirements.txt
```
*(Note: You may need to generate a `requirements.txt` file from `pyproject.toml` if it's not included, or install dependencies manually.)*

### 4. Configure the Bot

You need to configure the bot with your Discord token and channel information.

**A. Discord Bot Token**

1. Create a `.env` file in the root of the project directory.
2. Add your Discord bot token to this file:

    ```
    DISCORD_TOKEN=YourDiscordBotTokenGoesHere
    ```

**B. Channel ID**

1. Open the `channels.json` file.
2. You need to provide the **Server (Guild) ID** and the **Channel ID** where the bot will post messages.
3. To get these IDs, you must enable **Developer Mode** in Discord:
   - Go to `User Settings > Advanced` and turn on `Developer Mode`.
   - Right-click on your server icon and select `Copy Server ID`.
   - Right-click on the desired text channel and select `Copy Channel ID`.
4. Update `channels.json` with your IDs. The format is `"guild_id": "channel_id"`:

    ```json
    {
        "YOUR_SERVER_ID_HERE": "YOUR_CHANNEL_ID_HERE"
    }
    ```

### 5. Running the Bot

Once everything is configured, you can run the bot:

```bash
python main.py
```

The bot will start, and you should see a confirmation message in your console. It will begin checking for new battles and posting reports in the channel you configured.

## Configuration Details

For more advanced settings, you can modify the `config.py` file. Here are some of the key options:

-   `BATTLES_MAX_AGE_MINUTES`: The maximum age of battles to fetch (e.g., only show battles from the last 60 minutes).
-   `REFRESH_RATE_SECONDS`: How often the bot checks for new battles.
-   `SERVER_URL`: The URL of the Albion Online data server to use (e.g., for West or East).
-   `IMAGE_FOLDER`: The directory where generated images are stored.

Make sure to review the settings in `config.py` to tailor the bot to your needs.
