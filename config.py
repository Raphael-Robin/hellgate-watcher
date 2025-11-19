import dotenv,os

# --------------------------------------------------------------------------------------------------
# API and URLs
# --------------------------------------------------------------------------------------------------
BASE_URL_EUROPE = "https://gameinfo-ams.albiononline.com/api/gameinfo"
RENDER_API_URL = "https://render.albiononline.com/v1/item/"
SERVER_URL = BASE_URL_EUROPE

# --------------------------------------------------------------------------------------------------
# TIMING AND RATE LIMITS
# --------------------------------------------------------------------------------------------------
RATE_LIMIT_DELAY_SECONDS = 0.5
TIMEOUT = 30
BATTLE_CHECK_INTERVAL_MINUTES = 1
BATTLES_MAX_AGE_MINUTES = 5

# --------------------------------------------------------------------------------------------------
# FILE PATHS
# --------------------------------------------------------------------------------------------------
IMAGE_FOLDER = "./images"
COVERED_BATTLES_JSON_PATH = "./covered_battle_reports.json"
CHANNELS_JSON_PATH = 'channels.json'
PLAYER_NAME_FONT_PATH = "arialbd.ttf"
TIMESTAMP_FONT_PATH = "arial.ttf"

# --------------------------------------------------------------------------------------------------
# BOT SETTINGS
# --------------------------------------------------------------------------------------------------
BOT_COMMAND_PREFIX = '!'
VERBOSE_LOGGING = False

# --------------------------------------------------------------------------------------------------
# API REQUEST PARAMETERS
# --------------------------------------------------------------------------------------------------
BATTLES_LIMIT = 50

# --------------------------------------------------------------------------------------------------
# IMAGE GENERATION SETTINGS
# --------------------------------------------------------------------------------------------------
EQUIPMENT_IMAGE_SIZE = 651
SIDE_PADDING = 100
TOP_BOTTOM_PADDING = 50
SPACING = 30
MIDDLE_GAP = 200
PLAYER_NAME_AREA_HEIGHT = 60
CANVAS_WIDTH = (2 * SIDE_PADDING) + (5 * EQUIPMENT_IMAGE_SIZE) + ((5 - 1) * SPACING)
CANVAS_HEIGHT = (2 * TOP_BOTTOM_PADDING) + (2 * (EQUIPMENT_IMAGE_SIZE + PLAYER_NAME_AREA_HEIGHT)) + MIDDLE_GAP
BATTLE_REPORT_CANVAS_SIZE = (CANVAS_WIDTH, CANVAS_HEIGHT)
BACKGROUND_COLOR = (40, 40, 40, 255)
PLAYER_NAME_FONT_SIZE = 40
TIMESTAMP_FONT_SIZE = 60
FONT_COLOR = (255, 255, 255)
LINE_SPACING = 20
DEAD_PLAYER_GRAYSCALE_ENHANCEMENT = 0.8

# --------------------------------------------------------------------------------------------------
# EQUIPMENT AND LAYOUT
# --------------------------------------------------------------------------------------------------
LAYOUT = {
    "Bag": (0, 0), "Head": (1, 0), "Cape": (2, 0),
    "MainHand": (0, 1), "Armor": (1, 1), "OffHand": (2, 1),
    "Potion": (0, 2), "Shoes": (1, 2), "Food": (2, 2)
}
IMAGE_SIZE = 217
CANVAS_SIZE = (3 * IMAGE_SIZE, 3 * IMAGE_SIZE)

# --------------------------------------------------------------------------------------------------
# WEAPON LISTS
# --------------------------------------------------------------------------------------------------
HEALING_WEAPONS = [
    "MAIN_HOLYSTAFF", "2H_HOLYSTAFF", "2H_DIVINESTAFF", "MAIN_HOLYSTAFF_MORGANA",
    "2H_HOLYSTAFF_HELL", "2H_HOLYSTAFF_UNDEAD", "MAIN_HOLYSTAFF_AVALON", "2H_HOLYSTAFF_CRYSTAL",
    "MAIN_NATURESTAFF", "2H_NATURESTAFF", "2H_WILDSTAFF", "MAIN_NATURESTAFF_KEEPER",
    "2H_NATURESTAFF_HELL", "2H_NATURESTAFF_KEEPER", "MAIN_NATURESTAFF_AVALON",
    "MAIN_NATURESTAFF_CRYSTAL",
]

# --------------------------------------------------------------------------------------------------
# ALBION STATS
# --------------------------------------------------------------------------------------------------
QUALITY_IP = {
        "1": 0,
        "2": 20,
        "3": 40,
        "4": 60,
        "5": 100,
    }