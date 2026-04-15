import json
import os
import random

from config import FALLBACK_IMAGE_DIRS, IMAGES_DIR, INDEX_JSON_FILE, RARITY_WEIGHTS, ROOT_INDEX_JSON_FILE
from utils import normalize_name


VEHICLES_CACHE = {}
VEHICLES_CACHE_MTIME = None
VEHICLES_CACHE_PATH = None


def load_vehicles():
    global VEHICLES_CACHE, VEHICLES_CACHE_MTIME, VEHICLES_CACHE_PATH

    try:
        index_path = INDEX_JSON_FILE if os.path.exists(INDEX_JSON_FILE) else ROOT_INDEX_JSON_FILE
        if not os.path.exists(index_path):
            return {}

        current_mtime = os.path.getmtime(index_path)
        if VEHICLES_CACHE_PATH == index_path and VEHICLES_CACHE_MTIME == current_mtime and VEHICLES_CACHE:
            return VEHICLES_CACHE

        with open(index_path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)

        processed = {}
        for key, value in data.items():
            if isinstance(value, dict):
                image_url = value.get('pic_link') or value.get('url') or ""
                vehicle_data = {
                    "url": image_url,
                    "rarity": value.get('rarity', 'Common')
                }
            else:
                vehicle_data = {"url": str(value), "rarity": "Common"}

            local_path = None
            image_search_dirs = [IMAGES_DIR] + FALLBACK_IMAGE_DIRS
            for extension in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                for image_dir in image_search_dirs:
                    test_path = os.path.join(image_dir, f"{key}.{extension}")
                    if os.path.exists(test_path):
                        local_path = test_path
                        break
                if local_path:
                    break

            if local_path:
                vehicle_data['local_path'] = local_path

            processed[key] = vehicle_data

        VEHICLES_CACHE = processed
        VEHICLES_CACHE_PATH = index_path
        VEHICLES_CACHE_MTIME = current_mtime
        return VEHICLES_CACHE
    except Exception as error:
        print(f"Error loading index.json: {error}")
        return {}


def refresh_vehicles():
    global VEHICLES_CACHE_MTIME, VEHICLES_CACHE_PATH
    VEHICLES_CACHE_MTIME = None
    VEHICLES_CACHE_PATH = None
    return load_vehicles()


def get_vehicle_map():
    return load_vehicles()


def get_random_vehicle(vehicles):
    if not vehicles:
        return None

    spawnable = {
        name: data for name, data in vehicles.items()
        if data.get('local_path') or (data.get('url') and str(data['url']).startswith('http'))
    }
    if not spawnable:
        return None

    by_rarity = {}
    for name, data in spawnable.items():
        rarity = data.get('rarity', 'Common').lower()
        by_rarity.setdefault(rarity, []).append(name)

    available_rarities = [rarity for rarity in RARITY_WEIGHTS if rarity in by_rarity]
    weights = [RARITY_WEIGHTS[rarity] for rarity in available_rarities]
    if not available_rarities:
        return random.choice(list(spawnable.keys()))

    selected_rarity = random.choices(available_rarities, weights=weights, k=1)[0]
    return random.choice(by_rarity[selected_rarity])


def find_best_vehicle_match(vehicle_names, query):
    normalized_query = normalize_name(query)
    if not normalized_query:
        return None

    matches = [name for name in vehicle_names if normalized_query in normalize_name(name)]
    if not matches:
        return None

    for name in matches:
        if normalize_name(name) == normalized_query:
            return name

    return sorted(matches, key=len)[0]
