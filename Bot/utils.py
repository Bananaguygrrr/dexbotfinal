import discord
from discord.errors import HTTPException, NotFound


def normalize_name(name):
    if not name:
        return ""
    import re

    cleaned = re.sub(r'[^a-z0-9]', '', name.lower())
    return re.sub(r'(.)\1+', r'\1', cleaned)


def format_count(num):
    if not isinstance(num, (int, float)):
        try:
            num = float(num)
        except Exception:
            return str(num)

    if abs(num) < 1000:
        return str(int(num)) if num == int(num) else str(num)

    suffixes = ['', 'k', 'm', 'b', 't', 'q', 'Q', 's', 'S', 'o', 'n', 'd', 'U', 'D', 'T', 'Qt', 'Qd', 'Sx', 'Sp', 'Oc', 'No', 'Vg']
    magnitude = 0
    while abs(num) >= 1000 and magnitude < len(suffixes) - 1:
        magnitude += 1
        num /= 1000.0

    if magnitude >= len(suffixes) - 1 and abs(num) >= 1000:
        return f"{num:.2e}"

    result = f"{num:.2f}"
    if '.' in result:
        result = result.rstrip('0').rstrip('.')
    return f"{result}{suffixes[magnitude]}"


def parse_count(text):
    if not text:
        return None
    text = str(text).strip().replace(',', '')

    suffixes = ['', 'k', 'm', 'b', 't', 'q', 'Q', 's', 'S', 'o', 'n', 'd', 'U', 'D', 'T', 'Qt', 'Qd', 'Sx', 'Sp', 'Oc', 'No', 'Vg']
    multiplier_map = {}
    for index, suffix in enumerate(suffixes):
        if suffix:
            multiplier_map[suffix] = 1000 ** index

    sorted_suffixes = sorted([suffix for suffix in suffixes if suffix], key=len, reverse=True)
    for suffix in sorted_suffixes:
        if text.endswith(suffix):
            try:
                num_part = text[:-len(suffix)].strip()
                if not num_part:
                    return int(multiplier_map[suffix])
                return int(float(num_part) * multiplier_map[suffix])
            except (ValueError, TypeError):
                continue

    try:
        last_char = text[-1].lower()
        if last_char in ['k', 'm', 'b', 't']:
            suffix_map = {'k': 1e3, 'm': 1e6, 'b': 1e9, 't': 1e12}
            num_part = text[:-1].strip()
            if not num_part:
                return int(suffix_map[last_char])
            return int(float(num_part) * suffix_map[last_char])
        return int(float(text))
    except (ValueError, TypeError, IndexError):
        return None


async def safe_defer(interaction: discord.Interaction, *, ephemeral=False):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
        return True
    except (NotFound, HTTPException) as error:
        print(f"Failed to defer interaction for /{interaction.command.name if interaction.command else 'unknown'}: {error}")
        return False


async def safe_send(interaction: discord.Interaction, content, *, ephemeral=False, embed=None, view=None, wait=False):
    try:
        kwargs = {"ephemeral": ephemeral}
        if embed is not None:
            kwargs["embed"] = embed
        if view is not None:
            kwargs["view"] = view

        if interaction.response.is_done():
            kwargs["wait"] = wait
            return await interaction.followup.send(content, **kwargs)
        return await interaction.response.send_message(content, **kwargs)
    except (NotFound, HTTPException) as error:
        print(f"Failed to send interaction response for /{interaction.command.name if interaction.command else 'unknown'}: {error}")
        return None
