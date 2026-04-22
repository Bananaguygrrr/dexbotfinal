import json
import os

import app_state
from config import DATA_DIR, USER_INVENTORIES_FILE
from utils import make_inventory_key, split_inventory_key

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None


INVENTORIES_CACHE = None


def _lock_file_handle(lock_file):
    if msvcrt is not None:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        return

    if fcntl is not None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return

    raise OSError("No supported file locking implementation is available on this platform.")


def acquire_instance_lock():
    global INVENTORIES_CACHE

    lock_path = os.path.join(DATA_DIR, 'bot.lock')
    try:
        lock_file = open(lock_path, 'a+', encoding='utf-8')
        _lock_file_handle(lock_file)
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        app_state.INSTANCE_LOCK_HANDLE = lock_file
        return True
    except OSError:
        print("Another bot instance is already running for this data directory. Stop it before starting a new one.")
        return False


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
                        normalized_item = make_inventory_key(item, False)
                        new_items[normalized_item] = new_items.get(normalized_item, 0) + 1
                    data[user_id] = new_items
                    migrated = True
                elif isinstance(items, dict):
                    normalized_items = {}
                    for item_name, item_count in items.items():
                        base_name, is_fresh = split_inventory_key(item_name)
                        normalized_item = make_inventory_key(base_name, is_fresh)
                        normalized_items[normalized_item] = normalized_items.get(normalized_item, 0) + item_count
                    if normalized_items != items:
                        data[user_id] = normalized_items
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
    save_inventories(INVENTORIES_CACHE)
    return INVENTORIES_CACHE


def save_inventories(inventories):
    global INVENTORIES_CACHE

    try:
        os.makedirs(os.path.dirname(USER_INVENTORIES_FILE), exist_ok=True)
        with open(USER_INVENTORIES_FILE, 'w', encoding='utf-8') as handle:
            json.dump(inventories, handle, indent=4)
        INVENTORIES_CACHE = inventories
    except Exception as error:
        print(f"Error saving {USER_INVENTORIES_FILE}: {error}")


def add_to_inventory(user_id, vehicle_name, is_fresh=False):
    return add_vehicle_count(user_id, vehicle_name, 1, is_fresh=is_fresh)


def add_vehicle_count(user_id, vehicle_name, count, is_fresh=False):
    inventories = load_inventories()
    user_id_str = str(user_id)
    if user_id_str not in inventories:
        inventories[user_id_str] = {}

    user_inventory = inventories[user_id_str]
    if not isinstance(user_inventory, dict):
        user_inventory = {}

    inventory_key = make_inventory_key(vehicle_name, is_fresh)
    user_inventory[inventory_key] = user_inventory.get(inventory_key, 0) + count
    inventories[user_id_str] = user_inventory
    save_inventories(inventories)
    return True


def remove_vehicle_count(user_id, vehicle_name, count, is_fresh=False):
    inventories = load_inventories()
    user_id_str = str(user_id)
    user_inventory = inventories.get(user_id_str, {})
    if not isinstance(user_inventory, dict):
        return 0

    inventory_key = make_inventory_key(vehicle_name, is_fresh)
    current_count = user_inventory.get(inventory_key, 0)
    amount_removed = min(current_count, count)
    if amount_removed <= 0:
        return 0

    remaining = current_count - amount_removed
    if remaining > 0:
        user_inventory[inventory_key] = remaining
    else:
        del user_inventory[inventory_key]

    inventories[user_id_str] = user_inventory
    save_inventories(inventories)
    return amount_removed
