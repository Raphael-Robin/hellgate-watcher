# --------------------------------------------------------------------------------------------------
# API and URLs
# --------------------------------------------------------------------------------------------------
BASE_URL_EUROPE = "https://gameinfo-ams.albiononline.com/api/gameinfo"
BASE_URL_AMERICAS = "https://gameinfo.albiononline.com/api/gameinfo"
BASE_URL_ASIA = "https://gameinfo-sgp.albiononline.com/api/gameinfo"
RENDER_API_URL = "https://render.albiononline.com/v1/item/"
SERVER_URLS = {
    "europe": BASE_URL_EUROPE,
    "americas": BASE_URL_AMERICAS,
    "asia": BASE_URL_ASIA,
}

# --------------------------------------------------------------------------------------------------
# TIMING AND RATE LIMITS
# --------------------------------------------------------------------------------------------------
RATE_LIMIT_DELAY_SECONDS = 0.5
TIMEOUT = 30
BATTLE_CHECK_INTERVAL_MINUTES = 1
BATTLES_MAX_AGE_MINUTES = 15

# --------------------------------------------------------------------------------------------------
# FILE PATHS
# --------------------------------------------------------------------------------------------------
IMAGE_FOLDER = "./images"
ITEM_IMAGE_FOLDER = "./images/items"
EQUIPMENT_IMAGE_FOLDER = "./images/equipments"
BATTLE_REPORT_IMAGE_FOLDER = "./images/battle_reports"

CHANNELS_JSON_PATH = "./data/channels.json"

PLAYER_NAME_FONT_PATH = "arialbd.ttf"
TIMESTAMP_FONT_PATH = "arial.ttf"

# --------------------------------------------------------------------------------------------------
# BOT SETTINGS
# --------------------------------------------------------------------------------------------------
BOT_COMMAND_PREFIX = "!"
VERBOSE_LOGGING = False

# --------------------------------------------------------------------------------------------------
# API REQUEST PARAMETERS
# --------------------------------------------------------------------------------------------------
BATTLES_LIMIT = 50
MAX_RETRIES = 3
# --------------------------------------------------------------------------------------------------
# IMAGE GENERATION SETTINGS
# --------------------------------------------------------------------------------------------------
EQUIPMENT_IMAGE_SIZE = 651
SIDE_PADDING = 100
TOP_BOTTOM_PADDING = 50
SPACING = 30
MIDDLE_GAP = 200
PLAYER_NAME_AREA_HEIGHT = 60
IP_AREA_HEIGHT = 50
CANVAS_WIDTH_5V5 = (2 * SIDE_PADDING) + (5 * EQUIPMENT_IMAGE_SIZE) + ((5 - 1) * SPACING)
CANVAS_WIDTH_2V2 = (2 * SIDE_PADDING) + (2 * EQUIPMENT_IMAGE_SIZE) + ((2 - 1) * SPACING)
CANVAS_HEIGHT = (
    (2 * TOP_BOTTOM_PADDING)
    + (2 * (EQUIPMENT_IMAGE_SIZE + PLAYER_NAME_AREA_HEIGHT + IP_AREA_HEIGHT))
    + MIDDLE_GAP
)
BATTLE_REPORT_CANVAS_SIZE_5V5 = (CANVAS_WIDTH_5V5, CANVAS_HEIGHT)
BATTLE_REPORT_CANVAS_SIZE_2V2 = (CANVAS_WIDTH_2V2, CANVAS_HEIGHT)
BACKGROUND_COLOR = (40, 40, 40, 255)
PLAYER_NAME_FONT_SIZE = 40
TIMESTAMP_FONT_SIZE = 60
FONT_COLOR = (255, 255, 255)
LINE_SPACING = 20
DEAD_PLAYER_GRAYSCALE_ENHANCEMENT = 0.2

# --------------------------------------------------------------------------------------------------
# EQUIPMENT AND LAYOUT
# --------------------------------------------------------------------------------------------------
LAYOUT = {
    "bag": (0, 0),
    "head": (1, 0),
    "cape": (2, 0),
    "mainhand": (0, 1),
    "armor": (1, 1),
    "offhand": (2, 1),
    "potion": (0, 2),
    "shoes": (1, 2),
    "food": (2, 2),
}
IMAGE_SIZE = 217
EQUIPMENT_CANVAS_SIZE = (3 * IMAGE_SIZE, 3 * IMAGE_SIZE)

# --------------------------------------------------------------------------------------------------
# WEAPON LISTS
# --------------------------------------------------------------------------------------------------
HEALING_WEAPONS = [
    "MAIN_HOLYSTAFF",
    "2H_HOLYSTAFF",
    "2H_DIVINESTAFF",
    "MAIN_HOLYSTAFF_MORGANA",
    "2H_HOLYSTAFF_HELL",
    "2H_HOLYSTAFF_UNDEAD",
    "MAIN_HOLYSTAFF_AVALON",
    "2H_HOLYSTAFF_CRYSTAL",
    "MAIN_NATURESTAFF",
    "2H_NATURESTAFF",
    "2H_WILDSTAFF",
    "MAIN_NATURESTAFF_KEEPER",
    "2H_NATURESTAFF_HELL",
    "2H_NATURESTAFF_KEEPER",
    "MAIN_NATURESTAFF_AVALON",
    "MAIN_NATURESTAFF_CRYSTAL",
]

# --------------------------------------------------------------------------------------------------
# ALBION STATS
# --------------------------------------------------------------------------------------------------
QUALITY_IP = {
    "0": 0,
    "1": 0,
    "2": 20,
    "3": 40,
    "4": 60,
    "5": 100,
}
LETHAL_5V5_SOFTCAP_PERCENT = 35
LETHAL_5V5_IP_CAP = 1100
LETHAL_2V2_SOFTCAP_PERCENT = 35
LETHAL_2V2_IP_CAP = 1100
OVERCHARGE_BONUS_IP = 100
BASE_IP = 300


PRIMARY_ACCENT = (100, 0, 0)  # A nice blue accent line
DARK_BAR = (35, 35, 38)        # Darker header bar
LARGE_FONT_SIZE = 42
MEDIUM_FONT_SIZE = 32
GLOBAL_PADDING = 30