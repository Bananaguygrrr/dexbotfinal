import json
import os

import app_state
from config import DATA_DIR, USER_INVENTORIES_FILE


INVENTORIES_CACHE = None


def acquire_instance_lock():
    global INVENTORIES_CACHE

    lock_path = os.path.join(DATA_DIR, 'bot.lock')
    try:
        with open(lock_path, 'w') as lock_file:
            lock_file.write(str(os.getpid()))
        app_state.INSTANCE_LOCK_HANDLE = lock_path
        return True
    except Exception as e:
        print(f"Warning: Could not acquire lock: {e}")
        return True  # Continue anyway in cloud environments


def load_inventories():
    global INVENTORIES_CACHE

    if INVENTORIES_CACHE is not None:
        return INVENTORIES_CACHE

    if os.path.exists(USER_INVENTORIES_FILE):
        try:
            with open(USER_INVENTORIES_FILE, 'r', encoding='utf-8') as handle:
                data = json.load(handle)

            migrated = False
            for user_id, items in data.items():
                if isinstance(items, list):
                    new_items = {}
                    for item in items:
                        new_items[item] = new_items.get(item, 0) + 1
                    data[user_id] = new_items
                    migrated = True

            INVENTORIES_CACHE = data
            if migrated:
                save_inventories(INVENTORIES_CACHE)
            return INVENTORIES_CACHE
        except Exception as error:
            print(f"Error loading {USER_INVENTORIES_FILE}: {error}")
            INVENTORIES_CACHE = {}
            return INVENTORIES_CACHE

    INVENTORIES_CACHE = {}
    return INVENTORIES_CACHE


def save_inventories(inventories):
    global INVENTORIES_CACHE

    try:
        with open(USER_INVENTORIES_FILE, 'w', encoding='utf-8') as handle:
            json.dump(inventories, handle, indent=4)
        INVENTORIES_CACHE = inventories
    except Exception as error:
        print(f"Error saving {USER_INVENTORIES_FILE}: {error}")


def add_to_inventory(user_id, vehicle_name):
    inventories = load_inventories()
    user_id_str = str(user_id)
    if user_id_str not in inventories:
        inventories[user_id_str] = {}

    user_inventory = inventories[user_id_str]
    if not isinstance(user_inventory, dict):
        user_inventory = {}

    user_inventory[vehicle_name] = user_inventory.get(vehicle_name, 0) + 1
    inventories[user_id_str] = user_inventory
    save_inventories(inventories)
    return True
