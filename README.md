# Albion Online Hellgate Watcher

A Discord bot that monitors and reports recent 2v2 and 5v5 Hellgate battles from Albion Online servers.

## Features

- **Automatic Battle Reporting:** Periodically checks for new Hellgate battles on the specified Albion Online servers (Europe, Americas, and Asia).
- **Image Generation:** Generates images of battle reports, showing the teams, their gear, and the outcome.
- **Server and Mode specific:** Allows setting up different channels for different servers and Hellgate modes (2v2 or 5v5).
- **Configurable:** Most settings, such as the battle check interval and image generation settings, can be configured.

## Commands

The bot uses a slash command to set the channel for battle reports:

- `/setchannel <server> <mode> <channel>`: Sets the channel for Hellgate battle reports.
  - **server:** The Albion Online server to get reports from (`Europe`, `Americas`, or `Asia`).
  - **mode:** The Hellgate mode (`2v2` or `5v5`).
  - **channel:** The Discord channel where the reports will be sent.

This command requires administrator permissions.

## Setup and Installation

### Prerequisites

- Python 3.13 or higher.

### 1. Clone the repository

```bash
git clone https://github.com/your-username/hellgate-watcher.git
cd hellgate-watcher
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```
*Note: The dependencies are listed in `pyproject.toml`. You may need to generate a `requirements.txt` file or install them manually.*

### 3. Configure the bot

Create a `.env` file in the root directory and add your Discord bot token:

```
DISCORDTOKEN=your_discord_bot_token
```

### 4. Run the bot

```bash
python main.py
```

## Configuration

The bot can be configured by editing the `config.py` file. Here are some of the most important settings:

- `BATTLE_CHECK_INTERVAL_MINUTES`: The interval in minutes at which the bot checks for new battles.
- `BATTLES_MAX_AGE_MINUTES`: The maximum age of battles to report.
- `VERBOSE_LOGGING`: Set to `True` for more detailed logging.

The image generation settings can also be tweaked in the `config.py` file.

## Project Structure

```
.
├── .gitignore
├── .python-version
├── config.py             # Bot and image generation settings
├── main.py               # Main entry point of the bot
├── pyproject.toml        # Project metadata and dependencies
├── README.md             # This file
├── uv.lock
├── data/
│   └── channels.json     # Stores the channel mappings
├── images/               # Folder for generated images
└── src/
    ├── albion_objects.py # Albion Online data objects
    ├── bot.py            # Discord bot logic and commands
    ├── hellgate_watcher.py # Fetches and processes battle reports
    └── utils.py          # Utility functions
```