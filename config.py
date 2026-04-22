import os

from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

SPAWN_THRESHOLD = 100

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv('DATA_DIR', os.path.join(SCRIPT_DIR, 'data'))

os.makedirs(DATA_DIR, exist_ok=True)

USER_INVENTORIES_FILE = os.path.join(DATA_DIR, 'user_inventories.json')
IMAGES_DIR = os.path.join(DATA_DIR, 'images')
INDEX_JSON_FILE = os.path.join(DATA_DIR, 'index.json')
ROOT_INDEX_JSON_FILE = os.path.join(SCRIPT_DIR, 'data/index.json')
FALLBACK_IMAGE_DIRS = [
    os.path.join(SCRIPT_DIR, 'images'),
    os.path.join(SCRIPT_DIR, 'data/images'),
]

os.makedirs(IMAGES_DIR, exist_ok=True)

RARITY_WEIGHTS = {
    "limited edition": 0.3,
    "exotic": 3,
    "legendary": 10,
    "epic": 20,
    "rare": 30,
    "common": 37,
}

RARITY_COLORS = {
    "limited edition": 0x8B0000,
    "exotic": 0xFF00FF,
    "legendary": 0xFFD700,
    "epic": 0x800080,
    "rare": 0x0000FF,
    "common": 0x808080,
}
