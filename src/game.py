"""
Depthcrawl Generator - game logic (Pyodide edition)

This module is a refactor of the original Flask-based `depthcrawl.py`.
All the actual generator logic (dice rolling, tables, treasure/encounter
rules) is unchanged. What changed:

  * No Flask / no HTTP request handling.
  * `session` (server-side, cookie-backed) is replaced by a single
    in-memory `SESSION` dict, since everything now runs inside the
    visitor's own browser tab (via Pyodide) - there is no server and
    no other visitor to separate sessions from.
  * The Jinja2 template (`templates/index.html`) is replaced by a
    small set of pure-Python HTML-rendering functions
    (`render_page`, `_render_location_view`, ...) that build the same
    markup the template used to produce. The CSS/JS shell around it
    now lives in the surrounding .html file instead of Flask.
"""

import math
import random
import re

import markdown

from data import (
    LEVEL_MODIFIERS,
    LOCATIONS, DETAILS,
    LOCATION_MODIFIERS, DETAIL_MODIFIERS,
    LOCATION_DESCRIPTIONS, DETAIL_DESCRIPTIONS,
    LOCATION_TRAITS, DETAIL_TRAITS,
    TREASURE_TABLES, TREASURE_QUALITY_TABLE, TREASURE_EXTRA_ITEMS_TABLE,
    SAFE_MUNDANE_CONTENTS, BULKY_TREASURE_TABLES,
    MINE_TREASURE_TABLES, ROCK_GARDEN_TREASURE_TABLES,
    CONSUMABLE_SUBTYPES, AMPULES_TABLE, POTIONS_TABLE, MISCELLANY_TABLE, ARTIFACTS_TABLE,
    NEXT_LEVEL, ROLL_TWICE, MONSTERS, NON_HOSTILE_MONSTERS, ENCOUNTER_TABLES,
)

Table = list[tuple[int, str]]

DEFAULT_TREASURE_DC = 8
DEFAULT_ENCOUNTER_DC = 8
DEFAULT_ROUND_LENGTH_MINUTES = 15


# Inline SVGs traced directly from Tabler Icons (MIT License,
# Copyright (c) 2020-2024 Paweł Kuna) - path data only, no font file,
# so there's nothing to host or load at runtime. See
# THIRD_PARTY_LICENSES.md for the full license text and which icon
# each of these six came from (elevator/door/flame/skull/treasure-
# chest/hourglass-high, all from the "outline" style). Sized for a
# ~20px badge; color comes from the badge's own inline `color` via
# `currentColor`, so these automatically match whatever background/
# text pairing that badge already uses.
_ICON_LIFT = (
    '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<path d="M5 5a1 1 0 0 1 1 -1h12a1 1 0 0 1 1 1v14a1 1 0 0 1 -1 1h-12a1 1 0 0 1 -1 -1l0 -14" />'
    '<path d="M10 10l2 -2l2 2" />'
    '<path d="M10 14l2 2l2 -2" />'
    '</svg>'
)
_ICON_SECRET_PASSAGE = (
    '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<path d="M14 12v.01" />'
    '<path d="M3 21h18" />'
    '<path d="M6 21v-16a2 2 0 0 1 2 -2h8a2 2 0 0 1 2 2v16" />'
    '</svg>'
)
_ICON_FIREPLACE = (
    '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 10.941c2.333 -3.308 .167 -7.823 -1 -8.941c0 3.395 -2.235 5.299 -3.667 6.706'
    'c-1.43 1.408 -2.333 3.294 -2.333 5.588c0 3.704 3.134 6.706 7 6.706c3.866 0 7 -3.002 7 -6.706'
    'c0 -1.712 -1.232 -4.403 -2.333 -5.588c-2.084 3.353 -3.257 3.353 -4.667 2.235" />'
    '</svg>'
)
_ICON_MONSTER = (
    '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 4c4.418 0 8 3.358 8 7.5c0 1.901 -.755 3.637 -2 4.96l0 2.54a1 1 0 0 1 -1 1'
    'h-10a1 1 0 0 1 -1 -1v-2.54c-1.245 -1.322 -2 -3.058 -2 -4.96c0 -4.142 3.582 -7.5 8 -7.5" />'
    '<path d="M10 17v3" />'
    '<path d="M14 17v3" />'
    '<path d="M8 11a1 1 0 1 0 2 0a1 1 0 1 0 -2 0" />'
    '<path d="M14 11a1 1 0 1 0 2 0a1 1 0 1 0 -2 0" />'
    '</svg>'
)
_ICON_TREASURE = (
    '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<path d="M4 19h16a1 1 0 0 0 1 -1v-9a4 4 0 0 0 -4 -4h-10a4 4 0 0 0 -4 4v9a1 1 0 0 0 1 1" />'
    '<path d="M3 11h18" />'
    '<path d="M16 5v14" />'
    '<path d="M8 5v14" />'
    '<path d="M12 11v2" />'
    '</svg>'
)
# An hourglass, not a clock - The Well has no mechanical clocks (it's a
# medieval/fantasy setting), so a clock face would be an anachronism.
# Used as a small leading icon inside Crawling Mode's time-costing
# buttons (see _render_crawling_view / _render_special_connection_
# controls / _render_room_treasures's "Ransack Room" button) - NOT as
# a Dungeon Map badge like the five above, so it's wrapped in its own
# `.button-time-icon` span (see style.css) rather than one of the
# `.dtree-badge-*` classes. "hourglass-high" specifically (sand still
# mostly at the top) rather than plain "hourglass" or "hourglass-low" -
# reads as "time about to be spent", matching what clicking the button
# is about to do, not "time already spent" or "time running out".
_ICON_HOURGLASS = (
    '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<path d="M6.5 7h11" />'
    '<path d="M6 20v-2a6 6 0 1 1 12 0v2a1 1 0 0 1 -1 1h-10a1 1 0 0 1 -1 -1z" />'
    '<path d="M6 4v2a6 6 0 1 0 12 0v-2a1 1 0 0 0 -1 -1h-10a1 1 0 0 0 -1 1z" />'
    '</svg>'
)
# Torch and Lantern - hand-drawn for this project, NOT traced from
# Tabler like the six icons above (so NOT covered by THIRD_PARTY_
# LICENSES.md) - Tabler's icon set has nothing for either; its
# closest match, "lamp", is a modern desk lamp, exactly the kind of
# anachronism _ICON_HOURGLASS's own comment already explains avoiding
# a clock for. Same visual grammar as the traced ones regardless
# (24x24 viewBox, 2px round stroke, currentColor) so they sit
# comfortably alongside them wherever they're used.
_ICON_TORCH = (
    '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 2.5c1.2 1.8 -.8 3 -.8 4.8a1.3 1.3 0 0 0 2.6 0c0 -.6 -.2 -1.1 -.5 -1.5" />'
    '<path d="M9.5 8.5h5l-1 4h-3z" />'
    '<path d="M11 12.5h2l-.6 9h-.8z" />'
    '</svg>'
)
_ICON_LANTERN = (
    '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<path d="M10.5 2h3v2.2h-3z" />'
    '<path d="M8.5 4.2h7l1 3.8h-9z" />'
    '<path d="M7.5 8h9v9.5a1 1 0 0 1 -1 1h-7a1 1 0 0 1 -1 -1z" />'
    '<path d="M12 10.8v5" />'
    '<path d="M10.2 20.2h3.6" />'
    '<path d="M11 18.5h2v1.7h-2z" />'
    '</svg>'
)
# Traced from Tabler Icons like the six at the top of this block
# (MIT License - see THIRD_PARTY_LICENSES.md, updated to cover these
# two as well): "diamond" for _ICON_GEM, "package" for _ICON_CRATE.
# Both used inline within a treasure entry's own small context label
# (see _TREASURE_CONTEXT_ICONS/_render_room_treasures), not as a
# Dungeon Map badge like the others - just a plain 13px glyph sitting
# in text, so no separate wrapper span/CSS class needed the way
# _time_cost_icon_html's button icons get.
_ICON_GEM = (
    '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<path d="M6 5h12l3 5l-8.5 9.5a.7 .7 0 0 1 -1 0l-8.5 -9.5l3 -5" />'
    '<path d="M10 12l-2 -2.2l.6 -1" />'
    '</svg>'
)
_ICON_CRATE = (
    '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 3l8 4.5l0 9l-8 4.5l-8 -4.5l0 -9l8 -4.5" />'
    '<path d="M12 12l8 -4.5" />'
    '<path d="M12 12l0 9" />'
    '<path d="M12 12l-8 -4.5" />'
    '<path d="M16 5.25l-8 4.5" />'
    '</svg>'
)
_SPECIAL_CONNECTION_ICONS = {
    "lift": _ICON_LIFT,
    "secret_passage": _ICON_SECRET_PASSAGE,
    "fireplace": _ICON_FIREPLACE,
}

# Extensibility point for the (optional) light-source timer, the same
# "add new keys rather than special-casing individual names" pattern
# as DETAIL_TRAITS/LOCATION_TRAITS - adding a third light source later
# is meant to mean extending this dict, not restructuring anything
# that reads it (_render_light_gauges, _advance_crawl_clock, the
# "refuel_light" action). The one thing this dict *can't* cover on
# its own: each source still needs its own explicit `..._burn_minutes
# _form` parameter on handle_action and its own settings-view input,
# since every dispatch()/handle_action argument is an explicit,
# named, positional slot in this codebase (see handle_action's own
# docstring) - there's no generic "any settings field" plumbing to
# hook into instead.
LIGHT_SOURCES = {
    "torch": {
        "label": "Torch",
        "icon": _ICON_TORCH,
        "default_burn_minutes": 120,
        "refuel_label": "Light Torch",
    },
    "lantern": {
        "label": "Lantern",
        "icon": _ICON_LANTERN,
        "default_burn_minutes": 360,
        "refuel_label": "Refuel Lantern",
    },
}


def _time_cost_icon_html(large=False):
    """
    Small leading hourglass icon for a Crawling Mode button whose
    action advances the crawl clock (see crawl_elapsed_minutes) -
    Go Back/Stay/Go Deeper, Go Here, Use Lift/Secret Passage/
    Fireplace, Ransack Room. Deliberately NOT shown on a free action
    (Block/Unblock Entrance, Pick the Lock, the small "x" remove
    buttons) - the icon's whole job is to distinguish the two, so it
    only ever appears on the costly side of that line.

    `large=True` (see .button-time-icon-lg in style.css) sizes the
    icon up for the top row (Go Back/Stay/Go Deeper) - those buttons
    run noticeably bigger text (1rem, or 1.15rem bold for Go Deeper's
    own .primary-action) than the smaller room-card buttons (Go Here,
    Ransack Room, Use Lift, ...) the icon's base size was set against,
    so left at the base size it read as undersized next to them.
    """
    cls = "button-time-icon button-time-icon-lg" if large else "button-time-icon"
    return f'<span class="{cls}">{_ICON_HOURGLASS}</span>'




# ----------------------------
# LOGIC (unchanged from the Flask version)
# ----------------------------

def roll_table(table: Table, depth: int) -> tuple[int, str]:
    roll = random.randint(1, 20) + depth
    for max_value, result in table:
        if roll <= max_value:
            return roll, result
    raise RuntimeError("Invalid table")


def roll_dice(dice_str) -> int:
    """Parses strings like '1d3', '2d6' and returns a total."""
    if isinstance(dice_str, int):
        return dice_str
    n, die = map(int, dice_str.lower().split("d"))
    return sum(random.randint(1, die) for _ in range(n))


def collect_modifiers(room: dict | None, trigger: str) -> dict:
    """
    trigger: "room" | "ransack"

    `room` may be None (e.g. a "check_encounter" roll made before any
    location has been generated yet) - that's treated as "no
    location/detail modifiers apply", not an error.
    """

    # Safe defaults
    loc_mod = LOCATION_MODIFIERS.get((room or {}).get("location"), {}) or {}
    det_mod = DETAIL_MODIFIERS.get((room or {}).get("detail"), {}) or {}

    sources = [loc_mod, det_mod]

    mods = {
        "treasure_roll": 0,
        "treasure_quality": 0,
        "encounter_roll": 0,
        "no_treasure": False,
    }

    # --- blocking flags ---
    block_pos_treasure_roll = any(
        s.get("block_positive_treasure_roll", False) for s in sources
    )

    block_pos_treasure_quality = any(
        s.get("block_positive_treasure_quality", False) for s in sources
    )

    # --- absolute blockers ---
    if any(s.get("no_treasure", False) for s in sources):
        mods["no_treasure"] = True
        return mods  # early exit, nothing else matters

    # --- aggregate modifiers ---
    for source in sources:
        scope = source.get("scope", "all")
        if scope != "all" and scope != trigger:
            continue

        # TREASURE ROLL
        val = source.get("treasure_roll", 0)
        if val > 0 and block_pos_treasure_roll:
            pass  # suppressed
        else:
            mods["treasure_roll"] += val

        # TREASURE QUALITY
        val = source.get("treasure_quality", 0)
        if val > 0 and block_pos_treasure_quality:
            pass
        else:
            mods["treasure_quality"] += val

        # ENCOUNTER ROLL (nothing ever blocks a positive encounter_roll modifier)
        mods["encounter_roll"] += source.get("encounter_roll", 0)

    return mods


def generate_treasure(quality_mod=0, dungeon_level=1, forced_quality=None):
    if forced_quality:
        # A specific quality tier was chosen (Treasure Generator's
        # dropdown) instead of rolled - still pick uniformly among the
        # TREASURE_QUALITY_TABLE rolls that map to that tier, so the
        # item-count variant within it stays a little random, just
        # like it naturally would if you'd rolled into that tier.
        matching_rolls = [
            roll for roll, (_, name) in TREASURE_QUALITY_TABLE.items()
            if name == forced_quality
        ]
        quality_roll = random.choice(matching_rolls)
        raw_roll = None
    else:
        raw_roll = random.randint(1, 6)
        quality_roll = max(0, min(12, raw_roll + quality_mod))

    count, quality = TREASURE_QUALITY_TABLE[quality_roll]

    # base treasure items. Each gets a stable "id" (just its position
    # at creation time, never reassigned or reused) so a specific
    # item can be individually removed later - e.g. "N Silver Bars"
    # marked as collected - without the fragile assumption that its
    # position in the list won't have shifted by then (it will, once
    # any earlier item has already been removed).
    item_list = [
        {"id": i, "text": TREASURE_TABLES[quality][random.randint(1, 20)]}
        for i in range(count)
    ]

    # --- ADD EXTRA ITEMS (paint, consumables, artifacts, ...) ---
    extra_items = generate_extra_items(quality_roll, dungeon_level)
    item_list.extend(
        {"id": count + i, "text": text} for i, text in enumerate(extra_items)
    )

    return {
        "quality_roll": quality_roll,
        "quality_mod": quality_mod,
        "raw_quality_roll": raw_roll,
        "base_item_count": count,
        "extra_item_count": len(extra_items),
        "number_of_items": count + len(extra_items),
        "quality": quality,
        "item_list": item_list,
    }


def _generate_single_tier_item(table, item_die, quality_mod=0):
    """
    Shared logic behind generate_bulky_treasure/generate_mine_treasure/
    generate_rock_garden_treasure - each "this always resolves to
    exactly one item, not a whole haul" generator. Rolls a quality
    tier the same way generate_treasure() does (so wealth modifiers
    etc. apply the same way), then picks one entry from `table`
    (keyed 1..item_die - 6 for BULKY_TREASURE_TABLES, 3 for the
    smaller MINE_TREASURE_TABLES/ROCK_GARDEN_TREASURE_TABLES: The
    Well is a d6-based game with no d4s, and these only ever come up
    on a 1-in-3 roll to begin with, so they're seen far less often
    and don't need as much variety to avoid repeats feeling stale)
    for that tier. No "extra items" layered on top the way
    generate_treasure() does - this is one large or singular find,
    not a haul of several things.
    """
    raw_roll = random.randint(1, 6)
    quality_roll = max(0, min(12, raw_roll + quality_mod))
    _, quality = TREASURE_QUALITY_TABLE[quality_roll]

    item_text = table[quality][random.randint(1, item_die)]

    return {
        "quality_roll": quality_roll,
        "quality_mod": quality_mod,
        "raw_quality_roll": raw_roll,
        "base_item_count": 1,
        "extra_item_count": 0,
        "number_of_items": 1,
        "quality": quality,
        "item_list": [{"id": 0, "text": item_text}],
    }


def generate_bulky_treasure(quality_mod=0):
    """
    The dedicated generator for a "Bulky Treasure" detail's own
    guaranteed find (see DETAIL_TRAITS' "guaranteed_treasure_source":
    "bulky") - "something valuable that is hard to move... a lavish
    piece of furniture, a huge ornate rug, or a musical instrument".
    """
    return _generate_single_tier_item(BULKY_TREASURE_TABLES, 6, quality_mod)


def generate_mine_treasure(quality_mod=0):
    """
    The dedicated generator for a "Mine" location's own pickaxe-
    extractable find (see LOCATION_TRAITS' "extra_treasure_source":
    "mine") - "there is a 1 in 3 chance that a valuable ore vein can
    be found here".
    """
    return _generate_single_tier_item(MINE_TREASURE_TABLES, 3, quality_mod)


def generate_rock_garden_treasure(quality_mod=0):
    """
    The dedicated generator for a "Public Rock Garden" location's own
    pickaxe-extractable find (see LOCATION_TRAITS' "extra_treasure_
    source": "rock_garden") - "1 in 3 chance that something valuable
    can be extracted with time and a pickaxe".
    """
    return _generate_single_tier_item(ROCK_GARDEN_TREASURE_TABLES, 3, quality_mod)


def generate_paint():
    return "Dose of paint"


def generate_consumable(subtype=None):
    if subtype is None:
        subtype = random.choice(CONSUMABLE_SUBTYPES)
    if subtype == "potion":
        return f"Potion: {POTIONS_TABLE[random.randint(1, len(POTIONS_TABLE))]}"
    elif subtype == "ampule":
        return f"Ampule: {AMPULES_TABLE[random.randint(1, len(AMPULES_TABLE))]}"
    elif subtype == "arrow":
        return f"Arrow: {AMPULES_TABLE[random.randint(1, len(AMPULES_TABLE))]}"
    elif subtype == "miscellany":
        return f"Magic Item: {MISCELLANY_TABLE[random.randint(1, len(MISCELLANY_TABLE))]}"
    else:
        return None


def generate_artifact(level):
    roll = random.randint(1, 18)
    if level > 6:
        roll += 6
    return f"Artifact: {ARTIFACTS_TABLE[roll]}"


def generate_extra_items(treasure_quality, dungeon_level):
    items = []

    rules = TREASURE_EXTRA_ITEMS_TABLE.get(treasure_quality, [])
    for rule in rules:
        count = roll_dice(rule["amount"])
        for _ in range(count):
            category = rule["category"]

            if category == "paint":
                items.append(generate_paint())
            elif category == "artifact":
                items.append(generate_artifact(dungeon_level))
            elif category == "consumable":
                # pick random subtype if none given
                items.append(generate_consumable())
            elif category == "paint_or_consumable":
                if random.choice([True, False]):
                    items.append(generate_paint())
                else:
                    items.append(generate_consumable())
    return items


def roll_location_treasure(current_dc: int, mods: dict, default_dc: int, dungeon_level=1, forced_quality=None) -> dict:
    """
    `default_dc` is what the DC pool resets to on a success (see
    "next_dc" below) - the Settings view's "Default Treasure DC"
    (SESSION["default_treasure_dc"]), passed in explicitly rather
    than read from a module constant so it can be changed at runtime.
    """
    if mods["no_treasure"]:
        return {
            "blocked": True,
            "raw_roll": None,
            "mod": 0,
            "roll": None,
            "success": False,
            "treasure": None,
            "next_dc": current_dc,
        }

    raw_roll = random.randint(1, 6)
    treasure_mod = mods["treasure_roll"]
    roll = raw_roll + treasure_mod

    if roll >= current_dc:
        treasure = generate_treasure(
            quality_mod=mods["treasure_quality"],
            dungeon_level=dungeon_level,
            forced_quality=forced_quality,
        )

        return {
            "roll": roll,
            "raw_roll": raw_roll,
            "mod": treasure_mod,
            "success": True,
            "treasure": treasure,
            "next_dc": default_dc,
        }
    else:
        reduction = max(0, math.ceil(roll / 2))
        next_dc = max(1, current_dc - reduction)
        return {
            "roll": roll,
            "raw_roll": raw_roll,
            "mod": treasure_mod,
            "success": False,
            "treasure": None,
            "next_dc": next_dc,
        }


def roll_random_encounter(current_dc: int, mods: dict, default_dc: int):
    """Same idea as roll_location_treasure's own `default_dc` - the
    Settings view's "Default Encounter DC"."""
    raw_roll = random.randint(1, 6)
    encounter_mod = mods["encounter_roll"]
    roll = raw_roll + encounter_mod

    if roll >= current_dc:
        return {
            "roll": roll,
            "raw_roll": raw_roll,
            "mod": encounter_mod,
            "success": True,
            "next_dc": default_dc,
        }
    else:
        reduction = max(0, math.ceil(roll / 2))
        next_dc = max(1, current_dc - reduction)
        return {
            "roll": roll,
            "raw_roll": raw_roll,
            "mod": encounter_mod,
            "success": False,
            "next_dc": next_dc,
        }


# ----------------------------
# ENCOUNTER MONSTER GROUPS
# ----------------------------
# See the big comment above ENCOUNTER_TABLES / MONSTERS in data.py for
# the data format this operates on.

class EncounterDataError(RuntimeError):
    """Raised when ENCOUNTER_TABLES / MONSTERS in data.py are invalid."""


_DICE_RE = re.compile(r"^(\d+)d(\d+)$", re.IGNORECASE)
_RANGE_RE = re.compile(r"^(\d+)-(\d+)$")
_INT_RE = re.compile(r"^-?\d+$")


def _half_level(level: int) -> int:
    return level // 2  # rounds down (level 3 -> 1)


def _roll_formula_term_detailed(term: str, level: int) -> tuple:
    """Like _roll_formula_term(), but also returns a short human-
    readable fragment describing what was rolled, e.g. "1d6\u21924" or
    "half-level\u21922"."""
    term = term.strip()

    dice_match = _DICE_RE.match(term)
    if dice_match:
        count, sides = int(dice_match.group(1)), int(dice_match.group(2))
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        if count > 1:
            return total, f"{term}\u2192{'+'.join(str(r) for r in rolls)}"
        return total, f"{term}\u2192{total}"

    range_match = _RANGE_RE.match(term)
    if range_match:
        low, high = int(range_match.group(1)), int(range_match.group(2))
        value = random.randint(low, high)
        return value, f"{term}\u2192{value}"

    normalized = term.lower().replace("_", "-").replace(" ", "-")
    if normalized == "level":
        return level, f"level\u2192{level}"
    if normalized == "half-level":
        value = _half_level(level)
        return value, f"half-level\u2192{value}"

    if _INT_RE.match(term):
        return int(term), term

    raise ValueError(f"Can't parse encounter formula term {term!r}.")


def _roll_formula_term(term: str, level: int) -> int:
    value, _ = _roll_formula_term_detailed(term, level)
    return value


def roll_monster_count_detailed(formula: str, level: int) -> tuple:
    """
    Evaluates a monster's "number formula" (e.g. "3-5 + half-level")
    for the given dungeon level, returning (count, description) - the
    resulting number (never less than 1) plus a short human-readable
    breakdown of how it was rolled, for display in the UI.
    """
    parts = re.split(r"\s+([+-])\s+", formula.strip())
    value, first_desc = _roll_formula_term_detailed(parts[0], level)
    total = value
    desc_parts = [first_desc]

    i = 1
    while i < len(parts):
        sign_str, term = parts[i], parts[i + 1]
        term_value, term_desc = _roll_formula_term_detailed(term, level)
        total += term_value if sign_str == "+" else -term_value
        desc_parts.append(f"{sign_str} {term_desc}")
        i += 2

    clamped = max(1, total)
    description = " ".join(desc_parts)
    if len(desc_parts) > 1 or clamped != total:
        description = f"{description} = {clamped}"

    return clamped, description


def roll_monster_count(formula: str, level: int) -> int:
    """
    Evaluates a monster's "number formula" (e.g. "3-5 + half-level")
    for the given dungeon level, returning how many of that monster
    appear in one group. The result is never less than 1.
    """
    value, _ = roll_monster_count_detailed(formula, level)
    return value


_MAX_ENCOUNTER_SUBROLLS = 50


class _RollBudget:
    """
    Guards against pathological ENCOUNTER_TABLES data (e.g. a
    NEXT_LEVEL/ROLL_TWICE combination that never settles on an actual
    monster) causing runaway recursion. Shared across one whole call
    to roll_encounter_group(), including all of its ROLL_TWICE
    branches.
    """

    __slots__ = ("remaining",)

    def __init__(self, remaining: int):
        self.remaining = remaining

    def spend(self) -> None:
        self.remaining -= 1
        if self.remaining < 0:
            raise EncounterDataError(
                f"Encounter roll used up its safety budget of "
                f"{_MAX_ENCOUNTER_SUBROLLS} sub-rolls - check "
                "ENCOUNTER_TABLES for a NEXT_LEVEL/ROLL_TWICE chain "
                "that never resolves to an actual monster."
            )


def roll_encounter_group(level: int, forced_monster: str = None) -> dict:
    """
    Rolls on the encounter table for `level` - one d6 picks the row
    (1-2 / 3-4 / 5-6), the other picks the column (1-6) - and returns
    the resulting monster group(s) plus some info about each roll,
    for display purposes.

    Normally this resolves to exactly one group, but ROLL_TWICE
    entries make it resolve to two (or more, if one of those two also
    happens to be ROLL_TWICE) - see the ENCOUNTER_TABLES comment in
    data.py.

    `forced_monster`, if given (the Encounter Generator's dropdown),
    skips the table roll entirely and always resolves to exactly that
    one monster - only its number formula still gets rolled.
    """
    level = max(1, min(12, level))

    if forced_monster:
        count, breakdown = roll_monster_count_detailed(MONSTERS[forced_monster], level)
        groups = [{
            "id": 0,
            "rolled_on_level": level,
            "dice": None,
            "row": None,
            "column": None,
            "monster": forced_monster,
            "multiplier": 1,
            "count": count,
            "count_breakdown": breakdown,
        }]
        return {"requested_level": level, "groups": groups}

    groups = _roll_encounter_groups_at(level, _RollBudget(_MAX_ENCOUNTER_SUBROLLS))
    # Ids are assigned here, once the final (possibly ROLL_TWICE-
    # flattened) list is known - each group's "id" is just its
    # position in that final list, never reassigned or reused, so a
    # specific group ("3x Goblin") stays individually identifiable
    # even after some other group in the same encounter has already
    # been removed (see "remove_monster_group").
    for i, group in enumerate(groups):
        group["id"] = i
    return {"requested_level": level, "groups": groups}


def _roll_encounter_groups_at(level: int, budget: _RollBudget) -> list:
    budget.spend()
    current_level = level

    while True:
        table = ENCOUNTER_TABLES[current_level]
        row_die, col_die = random.randint(1, 6), random.randint(1, 6)
        row_index = (row_die - 1) // 2  # 1-2 -> 0, 3-4 -> 1, 5-6 -> 2
        col_index = col_die - 1
        entry = table[row_index][col_index]

        if entry == NEXT_LEVEL:
            current_level += 1
            if current_level > 12:
                # _validate_encounter_data() should already have
                # caught this at import time - this is just a
                # runtime safety net against the same data bug.
                raise EncounterDataError(
                    "Encounter table cascaded past level 12 - level "
                    "12's table must not contain a NEXT_LEVEL entry."
                )
            budget.spend()
            continue

        if entry == ROLL_TWICE:
            return (
                _roll_encounter_groups_at(current_level, budget)
                + _roll_encounter_groups_at(current_level, budget)
            )

        rolls = [
            roll_monster_count_detailed(MONSTERS[entry["monster"]], current_level)
            for _ in range(entry["multiplier"])
        ]
        count = sum(value for value, _ in rolls)
        count_breakdown = (
            rolls[0][1]
            if len(rolls) == 1
            else " + ".join(f"({desc})" for _, desc in rolls) + f" = {count}"
        )
        return [{
            "rolled_on_level": current_level,
            "dice": (row_die, col_die),
            "row": row_index + 1,
            "column": col_die,
            "monster": entry["monster"],
            "multiplier": entry["multiplier"],
            "count": count,
            "count_breakdown": count_breakdown,
        }]


def roll_monster_treasure(monsters, level, level_modifiers, current_dc, default_dc):
    """
    Rolls (against `current_dc` - the same running "treasure DC" a
    location's own treasure uses) whether an encountered monster
    group is carrying treasure, using only the current dungeon
    level's modifiers (LEVEL_MODIFIERS "wealth") - deliberately *not*
    the location/detail modifiers a location's own treasure uses,
    since this loot belongs to the monster(s), not the place they
    were found in. `default_dc` is what current_dc resets to on a
    success - see roll_location_treasure's own parameter of the same
    name.

    Returns None if there's nothing to roll for at all (no encounter,
    or every monster present is in NON_HOSTILE_MONSTERS - e.g. a
    plain "Critters" swarm never carries loot, no roll even attempted).
    If an encounter mixes a treasure-less monster with one that can
    carry treasure, this still rolls (once) for the encounter as a
    whole.

    Otherwise returns a dict shaped exactly like
    roll_location_treasure()'s result: "roll", "raw_roll", "mod",
    "success", "treasure" (None on failure), "next_dc".
    """
    if not monsters:
        return None

    monster_names = {group["monster"] for group in monsters["groups"]}
    if not (monster_names - NON_HOSTILE_MONSTERS):
        return None

    wealth_mod = level_modifiers.get("wealth", 0) if level else 0
    mods = {
        "treasure_roll": wealth_mod,
        "treasure_quality": wealth_mod,
        "encounter_roll": 0,
        "no_treasure": False,
    }
    raw_result = roll_location_treasure(
        current_dc, mods, default_dc, dungeon_level=level if level else 1
    )

    # Normalize to the same shape room["treasure_result"] uses, so
    # _render_treasure_check_result() can render either one.
    return {
        "raw_roll": raw_result["raw_roll"],
        "mod": raw_result["mod"],
        "treasure_dc_before": current_dc,
        "found_treasure": raw_result["treasure"],
        "blocked": raw_result.get("blocked", False),
        "next_dc": raw_result["next_dc"],
    }


def _roll_monster_treasure_if_enabled(monsters, level, level_modifiers, treasure_dc, default_treasure_dc, enabled):
    """
    Thin wrapper around roll_monster_treasure() for the two Encounter
    Generator actions ("check_encounter" and "generate_encounter"),
    which otherwise both repeat the same "roll it, then advance
    treasure_dc if it actually rolled" dance. `enabled` is the
    Encounter Generator's "Roll for Treasure" checkbox - when off, no
    roll is attempted at all and treasure_dc is left untouched.

    Returns (monster_treasure_or_None, updated_treasure_dc).
    """
    if not enabled:
        return None, treasure_dc

    monster_treasure = roll_monster_treasure(monsters, level, level_modifiers, treasure_dc, default_treasure_dc)
    if monster_treasure is not None:
        treasure_dc = monster_treasure["next_dc"]
    return monster_treasure, treasure_dc


def _validate_encounter_data() -> None:
    """
    Sanity-checks ENCOUNTER_TABLES / MONSTERS from data.py. Runs once
    at import time so authoring mistakes (typo'd monster name, a
    missing cell, a NEXT_LEVEL on level 12, ...) surface immediately
    with a clear message instead of as a confusing crash mid-game.
    """
    expected_levels = set(range(1, 13))
    actual_levels = set(ENCOUNTER_TABLES.keys())
    if actual_levels != expected_levels:
        raise EncounterDataError(
            f"ENCOUNTER_TABLES must have exactly levels 1-12, got {sorted(actual_levels)}."
        )

    for level, table in ENCOUNTER_TABLES.items():
        if len(table) != 3:
            raise EncounterDataError(
                f"Encounter table for level {level} must have exactly "
                f"3 rows, got {len(table)}."
            )

        for row_index, row in enumerate(table):
            row_number = row_index + 1
            if len(row) != 6:
                raise EncounterDataError(
                    f"Level {level}, row {row_number} must have exactly "
                    f"6 entries (one per column die 1-6), got {len(row)}."
                )

            for col_index, entry in enumerate(row):
                col_number = col_index + 1

                if entry == NEXT_LEVEL:
                    if level >= 12:
                        raise EncounterDataError(
                            "Level 12's encounter table must not contain "
                            "a NEXT_LEVEL entry (there is no level 13 to "
                            f"cascade to) - check row {row_number}, "
                            f"column {col_number}."
                        )
                    continue

                if entry == ROLL_TWICE:
                    # Allowed on every level, including 12 - it rerolls
                    # on the *same* level's table, so it never needs a
                    # higher level to exist.
                    continue

                monster = entry.get("monster")
                if monster not in MONSTERS:
                    raise EncounterDataError(
                        f"Level {level}, row {row_number}, column "
                        f"{col_number} references unknown monster "
                        f"{monster!r}. Add it to MONSTERS in data.py."
                    )

                try:
                    roll_monster_count(MONSTERS[monster], level)
                except ValueError as exc:
                    raise EncounterDataError(
                        f"Monster {monster!r} has an invalid number "
                        f"formula {MONSTERS[monster]!r}: {exc}"
                    ) from exc


_validate_encounter_data()


# ----------------------------
# UI HELPERS (unchanged from the Flask version)
# ----------------------------

def format_roll(raw, mod):
    if raw is None:
        return "-"
    if mod is None or mod == 0:
        return str(raw)

    sign = "+" if mod > 0 else "\u2212"
    return f"{raw} {sign} {abs(mod)}"


def _format_roll_total(raw, mod, total=None):
    """
    format_roll(), plus the resulting total - "3 + 1 = 4" - unless
    there's nothing to add (mod is 0/None), in which case the total
    would just repeat the same number ("3 = 3") and is dropped, same
    as roll_monster_count_detailed's own "only show '= total' when
    there's actually a distinct computation" rule. The single shared
    piece behind every "X roll: ..." display in the UI (see
    _render_room_roll_badge/_render_quality_roll_line/
    _render_treasure_check_result/_render_encounter_result) - kept
    here as one function specifically so those can't drift back out
    of sync with each other the way they had before.

    `total`, if given, overrides the displayed total instead of
    computing raw+mod directly - needed for a quality roll, whose
    real total is clamped to 0..12 (see generate_treasure) and so
    can differ from the raw arithmetic sum for a large enough mod.
    """
    rendered = format_roll(raw, mod)
    if raw is None:
        return rendered
    if total is None:
        total = raw + (mod or 0)
    if rendered == str(total):
        return rendered
    return f"{rendered} = {total}"


def format_modifier(mod):
    sign = "+" if mod is None or mod >= 0 else "\u2212"
    return f"{sign}{abs(mod)}"


def render_md(text):
    return markdown.markdown(text)


def get_modifier_badge_class(key: str, value: int) -> str:
    if value == 0:
        return ""  # no badge needed

    if key == "population":
        return "negative" if value > 0 else "positive"
    else:
        return "positive" if value > 0 else "negative"


# ----------------------------
# STATE
# ----------------------------
# Replaces Flask's server-side `session`. There is only ever one
# "visitor" (the person looking at this browser tab), so a single
# module-level dict is all we need.

def _default_session() -> dict:
    return {
        "depth": 0,
        "room": None,
        "crawl_depth": 0,
        "crawl_history": [],
        "crawl_current_id": None,
        "crawl_viewed_id": None,
        "crawl_elapsed_minutes": 0,
        "round_length_minutes": DEFAULT_ROUND_LENGTH_MINUTES,
        "track_light": {key: False for key in LIGHT_SOURCES},
        "light_burn_minutes": {key: cfg["default_burn_minutes"] for key, cfg in LIGHT_SOURCES.items()},
        "light_remaining_minutes": {key: 0 for key in LIGHT_SOURCES},
        "treasure": None,
        "treasure_dc": DEFAULT_TREASURE_DC,
        "encounter_dc": DEFAULT_ENCOUNTER_DC,
        "default_treasure_dc": DEFAULT_TREASURE_DC,
        "default_encounter_dc": DEFAULT_ENCOUNTER_DC,
        "encounter_check": None,
        "level": None,
        "level_modifiers": {},
        "active_view": "crawling",
        "roll_treasure": True,
        "roll_encounter": True,
        "encounter_roll_treasure": True,
        "forced_location": None,
        "forced_detail": None,
        "forced_monster": None,
        "forced_quality": None,
        "show_roll_details": False,
        "show_treasure_quality": False,
    }


SESSION = _default_session()


# ----------------------------
# ACTION HANDLING
# (this is the former POST-branch of the Flask `index()` view)
# ----------------------------

def _to_int_or_none(value):
    if value is None or value == "":
        return None
    return int(value)


# The three little "resolve this field from the incoming form, or
# fall back to whatever was already in the session" patterns that
# handle_action's growing list of form fields all reduce to. Pulling
# them out here is what keeps that function's parameter-reading section
# from re-growing into a wall of near-identical `if x_form is not
# None: ...` blocks every time a new form field gets added.

def _resolve_int(form_value, current):
    """For plain numeric fields (depth, the two DC inputs): use the
    submitted value if it parses to a number, otherwise keep the
    current session value unchanged."""
    value = _to_int_or_none(form_value)
    return current if value is None else value


def _resolve_bool(form_value, current):
    """For checkboxes: `None` means the checkbox isn't in the DOM
    right now (a different view is active) - keep the current value.
    Anything else is the checkbox's actual (JS boolean) state."""
    return current if form_value is None else bool(form_value)


def _resolve_choice(form_value, current):
    """For the "pick a specific X, or leave on Random" dropdowns:
    `None` means the field isn't in the DOM right now - keep the
    current value. An empty string means "present, but set back to
    Random" - resolves to None (no forced choice)."""
    if form_value is None:
        return current
    return form_value or None


def _room_blocks_deeper(room) -> bool:
    """
    True if this room's location or detail has a trait that rules out
    going deeper from here (currently just "Dead End", see
    DETAIL_TRAITS in data.py) - used to disable/reject "Go Deeper"
    from Crawling Mode while standing in such a room.
    """
    if room is None:
        return False
    loc_traits = LOCATION_TRAITS.get(room["location"], {})
    det_traits = DETAIL_TRAITS.get(room["detail"], {})
    return bool(loc_traits.get("blocks_deeper") or det_traits.get("blocks_deeper"))


def _room_has_guaranteed_treasure(room) -> bool:
    """
    True if this room's location or detail has a trait meaning its
    treasure is simply sitting out in the open (e.g. "Treasure Pile",
    "Portcullis", "Bulky Treasure") rather than something that has to
    be searched for. Such treasure always turns up something - no DC
    check at all, unlike the normal search-based roll (see
    roll_location_treasure).
    """
    if room is None:
        return False
    loc_traits = LOCATION_TRAITS.get(room["location"], {})
    det_traits = DETAIL_TRAITS.get(room["detail"], {})
    return bool(loc_traits.get("guaranteed_treasure") or det_traits.get("guaranteed_treasure"))


def _room_guaranteed_treasure_source(room) -> str:
    """
    Which generator this room's guaranteed treasure (see
    _room_has_guaranteed_treasure - meaningless to call this without
    checking that first) should come from - "bulky"
    (generate_bulky_treasure(), e.g. "Bulky Treasure") or "normal"
    (plain generate_treasure(), e.g. "Treasure Pile"/"Portcullis" -
    also the default when a location/detail has guaranteed_treasure
    but no explicit source of its own). See DETAIL_TRAITS'/
    LOCATION_TRAITS' "guaranteed_treasure_source".
    """
    if room is None:
        return "normal"
    loc_traits = LOCATION_TRAITS.get(room["location"], {})
    det_traits = DETAIL_TRAITS.get(room["detail"], {})
    return (
        loc_traits.get("guaranteed_treasure_source")
        or det_traits.get("guaranteed_treasure_source")
        or "normal"
    )


def _room_extra_treasure_traits(room):
    """
    Every distinct extra-treasure traits dict that applies to this
    room - one per location/detail trait declaring an
    "extra_treasure_context", from its location's trait, its detail's
    trait, or (not disallowed, just rare - e.g. a "Mine" location
    that also happens to roll a "Safe" detail) both at once,
    deduplicated by context value. Returns the whole traits dict
    rather than just the context value, so a context-specific
    generator lookup (e.g. "extra_treasure_source", used by
    "pickaxe" to tell "Mine" and "Public Rock Garden" apart even
    though they share the same context/label) can ride along with
    it. See DETAIL_TRAITS'/LOCATION_TRAITS' "extra_treasure_context"
    and _generate_room for how each context actually gets rolled.
    """
    loc_traits = LOCATION_TRAITS.get(room["location"], {})
    det_traits = DETAIL_TRAITS.get(room["detail"], {})
    result = []
    seen_contexts = set()
    for traits in (loc_traits, det_traits):
        context = traits.get("extra_treasure_context")
        if context and context not in seen_contexts:
            seen_contexts.add(context)
            result.append(traits)
    return result


def _room_special_connection_kind(room):
    """
    "lift" / "secret_passage" / "fireplace" if this room's detail has
    one of those special-movement traits (see DETAIL_TRAITS), else
    None. Only details carry this trait for now - locations could in
    principle too, but none currently do.
    """
    if room is None:
        return None
    return DETAIL_TRAITS.get(room["detail"], {}).get("special_connection")


def _room_has_monster(room) -> bool:
    """
    True if this room's entering encounter actually turned up a
    monster group (not just an encounter check that happened but came
    up "Safe") - used for the Dungeon Map's small monster marker.
    Whatever was rolled when the room was generated is what this
    reflects forever after - there's no way for a room's own contents
    to change once it exists.
    """
    encounter = room.get("entering_encounter")
    if not encounter or not encounter.get("success"):
        return False
    monsters = encounter.get("monsters")
    return bool(monsters and monsters.get("groups"))


def _room_has_hostile_monster(room) -> bool:
    """
    True if _room_has_monster(room) AND at least one present group is
    an actual combat threat - not just NON_HOSTILE_MONSTERS (Critters/
    Gravediggers/Exiles - see that set's own comment in data.py: these
    aren't "monsters" in the dangerous sense, an encounter with only
    these can be entirely peaceful). Drives the UI's danger styling
    (the red "Monster" pill and "Encounter:" label, the Dungeon Map's
    red monster badge) - conservatively: a room mixing one of these
    with a real threat still counts as hostile, same as
    roll_monster_treasure's own "does this encounter carry loot"
    check treats a mix as "yes, roll for it".

    A room where _room_has_monster is True but this is False (only
    non-hostile creatures present) still gets a presence indicator -
    just the calmer, non-red one - not no indicator at all.
    """
    if not _room_has_monster(room):
        return False
    groups = room["entering_encounter"]["monsters"]["groups"]
    return any(g["monster"] not in NON_HOSTILE_MONSTERS for g in groups)


# Contexts revealed together by a general room search ("ransack_room"
# / room["ransacked"]) - as opposed to "safe", which needs its own
# separate "pick the lock" action, or "open"/"monster"/"crevice",
# which are never gated behind anything.
_ROOM_SEARCH_GATED_CONTEXTS = {"ransack"}


def _treasure_entry_is_visible(room, entry) -> bool:
    """
    Whether this one treasure entry is currently revealed to the
    players - the single source of truth for that, used by
    _room_has_treasure/_room_treasure_pending_search and by
    _render_room_treasures alike, so the three can't drift apart on
    what "visible" means for a given context.
    """
    context = entry["context"]
    if context in _ROOM_SEARCH_GATED_CONTEXTS:
        return bool(room.get("ransacked"))
    if context == "safe":
        return bool(room.get("safe_opened"))
    return True  # "open", "monster", and any other always-visible context


def _room_has_treasure(room) -> bool:
    """
    True if this room currently has at least one *visible* treasure
    item across any of its treasure entries (see "treasures" and
    _treasure_entry_is_visible) - used for the Dungeon Map's real
    treasure marker. Individually removing items (see "remove_
    treasure_item") can empty an entry's item_list out entirely
    without clearing found_treasure itself (the quality/roll info is
    still meaningful history), so this checks item_list specifically
    rather than just found_treasure's truthiness.
    """
    for entry in room.get("treasures", []):
        if not _treasure_entry_is_visible(room, entry):
            continue
        found = entry.get("found_treasure")
        if found and found.get("item_list"):
            return True
    return False


def _room_has_valuable_treasure(room) -> bool:
    """
    True if _room_has_treasure(room) AND at least one visible entry
    is actually worth getting excited about - quality anything other
    than "mundane" (see TREASURE_QUALITY_TABLE - roll 0, the bottom
    tier: broken pottery, spoilt food, rusty keys, ... flavor clutter,
    not treasure). Covers the Safe's own failure consolation too
    (SAFE_MUNDANE_CONTENTS) for free - that substitute is explicitly
    tagged "quality": "mundane" already (see handle_action's
    "open_safe"), so no separate check is needed for it.

    Extra items (paint/consumables/artifacts - see generate_extra_
    items) never appear on a "mundane" roll in the first place
    (TREASURE_EXTRA_ITEMS_TABLE only starts at "valuable"), so there's
    no edge case where a "mundane"-tier entry is secretly worth more
    than its quality tier suggests.

    Drives the UI's loot styling (the gold "Treasure" pill vs. a
    muted one) - a room where _room_has_treasure is True but this is
    False (only mundane-quality junk present) still gets a presence
    indicator, just the quieter one, not no indicator at all.
    """
    for entry in room.get("treasures", []):
        if not _treasure_entry_is_visible(room, entry):
            continue
        found = entry.get("found_treasure")
        if found and found.get("item_list") and found.get("quality") != "mundane":
            return True
    return False


def _room_treasure_pending_search(room) -> bool:
    """
    True if this room has at least one treasure entry that hasn't
    been revealed yet - regardless of whether anything was actually
    found there, since that's exactly the point: showing a marker
    only when treasure is actually there (even a distinct "nothing
    here" non-marker) would let the Dungeon Map spoil the search
    before it happens. Used for the Dungeon Map's grey "?" marker,
    shown instead of (never alongside) the real treasure marker.
    Covers "safe" the same as "ransack" - from the Dungeon Map's
    point of view, "there's something here you haven't revealed yet"
    reads the same regardless of which specific action (searching vs.
    picking a lock) would reveal it.
    """
    return any(
        not _treasure_entry_is_visible(room, entry)
        for entry in room.get("treasures", [])
    )


def _room_treasure_icon(room):
    """
    Which icon represents this room's treasure - in the Dungeon Map
    badge (_render_dungeon_map) and the room card's presence pill
    (_render_presence_pills) alike, so the two stay consistent with
    each other. The plain chest (_ICON_TREASURE) by default, or a
    more specific glyph (see _TREASURE_CONTEXT_ICONS) if a visible
    entry's own context has one - checked in a fixed priority order
    ("bulky" before the gem contexts) for a deterministic pick on the
    rare room where more than one such context is visible at once;
    no ordering here is obviously more "correct" than another, so
    this is just a tiebreaker, not a meaningful ranking.

    Only meaningful to call once _room_has_treasure(room) is already
    known True - falls back to the default chest either way if
    nothing visible matches a specific context, same as "nothing
    visible at all" would.
    """
    visible_contexts = {
        entry["context"] for entry in room.get("treasures", [])
        if _treasure_entry_is_visible(room, entry)
        and entry.get("found_treasure")
        and entry["found_treasure"].get("item_list")
    }
    for context in ("bulky", "crevice", "pickaxe"):
        if context in visible_contexts:
            return _TREASURE_CONTEXT_ICONS[context]
    return _ICON_TREASURE


# (background, text) colors cycled across distinct Lift/Secret Passage
# pairs - reused if there are more pairs than colors, since the L1/L2/
# S1/S2 label (not the color) is what's actually relied on to tell
# them apart; color is just a bonus visual match for the two ends of
# the same pair. Deliberately avoids: the app's amber/gold accent
# (#8a6716/#c99a2e - current room, path, primary actions), the
# "viewed" outline's blue (#6a9fd8), and the warning red (#b71c1c) -
# all already mean something else everywhere else in the app.
_SPECIAL_CONNECTION_COLORS = [
    ("#2a9d8f", "#ffffff"),  # teal
    ("#e07a5f", "#ffffff"),  # coral
    ("#9b6fb5", "#ffffff"),  # purple
    ("#5aa469", "#ffffff"),  # green
    ("#b56aa0", "#ffffff"),  # magenta
    ("#5b7c99", "#ffffff"),  # slate blue
]
_FIREPLACE_BADGE_COLOR = ("#f4a261", "#3a2410")
# A room with a Lift/Secret Passage/Fireplace detail that hasn't been
# used yet at all - no pair/network exists to match colors with, so
# this is deliberately neutral/muted rather than picking one of the
# colors above (which would wrongly suggest it's already linked to
# whatever else happens to have that same color).
_UNCONNECTED_BADGE_COLOR = ("#3a3a3a", "#999999")


def _compute_special_connection_badges(history):
    """
    {room_id: {"icon", "number", "bg", "fg", "partner_id"}} for every
    room whose Location/Detail has a special-connection trait
    (Lift/Secret Passage/Fireplace) - computed fresh on every render
    rather than stored anywhere, since it's entirely derivable from
    special_link_id / detail.

    Shows a badge even before anything is actually connected yet -
    same icon, same shape, just a neutral/muted color, no "number",
    and no partner to click through to (`partner_id: None`) - so the
    map consistently flags "this room has one of these" everywhere,
    not only once it's been used for the first time.

    Once actually linked, Lift and Secret Passage (fixed pairs) each
    get their own sequential "number" per kind (1, 2, ...), assigned
    in order of the lower room id in the pair - stable across renders
    without needing to store it anywhere - shown next to the icon so
    it's still clear which specific pair a badge belongs to. Colors,
    though, are assigned from a single sequence shared across *both*
    kinds, in the order each pair was actually established - not
    restarted per kind - so e.g. the first Lift pair and the first
    Secret Passage pair (often created around a similar time) don't
    both default to the same first color just because each is
    "first" within its own kind. Fireplace never gets a number: every
    room with that detail belongs to the one single network the
    rules describe, so there's never more than one to tell apart.
    """
    badges = {}

    pairs_by_kind = {"lift": [], "secret_passage": []}
    unconnected_by_kind = {"lift": [], "secret_passage": []}
    seen_pairs = set()
    for room in history:
        kind = _room_special_connection_kind(room)
        if kind not in pairs_by_kind:
            continue
        partner_id = room.get("special_link_id")
        if partner_id is None:
            unconnected_by_kind[kind].append(room["id"])
            continue
        pair = (min(room["id"], partner_id), max(room["id"], partner_id))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        pairs_by_kind[kind].append(pair)

    all_pairs = sorted(
        ((kind, pair) for kind, pairs in pairs_by_kind.items() for pair in pairs),
        key=lambda item: item[1],
    )
    kind_counts = {"lift": 0, "secret_passage": 0}
    for color_index, (kind, (a, b)) in enumerate(all_pairs):
        kind_counts[kind] += 1
        bg, fg = _SPECIAL_CONNECTION_COLORS[color_index % len(_SPECIAL_CONNECTION_COLORS)]
        icon = _SPECIAL_CONNECTION_ICONS[kind]
        number = str(kind_counts[kind])
        badges[a] = {"icon": icon, "number": number, "bg": bg, "fg": fg, "partner_id": b}
        badges[b] = {"icon": icon, "number": number, "bg": bg, "fg": fg, "partner_id": a}

    unc_bg, unc_fg = _UNCONNECTED_BADGE_COLOR
    for kind, room_ids in unconnected_by_kind.items():
        icon = _SPECIAL_CONNECTION_ICONS[kind]
        for room_id in room_ids:
            badges[room_id] = {
                "icon": icon, "number": "", "bg": unc_bg, "fg": unc_fg, "partner_id": None,
            }

    fireplace_rooms = [r for r in history if r["detail"] == "Fireplace"]
    if len(fireplace_rooms) >= 2:
        bg, fg = _FIREPLACE_BADGE_COLOR
        for room in fireplace_rooms:
            # Just a quick "yes, this connects somewhere" preview -
            # picks any other fireplace room to jump to. Reaching a
            # *specific* one when there are several is still what the
            # room card's own "Use Fireplace" dropdown is for.
            other = next(r for r in fireplace_rooms if r["id"] != room["id"])
            badges[room["id"]] = {
                "icon": _ICON_FIREPLACE, "number": "", "bg": bg, "fg": fg,
                "partner_id": other["id"],
            }
    elif len(fireplace_rooms) == 1:
        badges[fireplace_rooms[0]["id"]] = {
            "icon": _ICON_FIREPLACE, "number": "", "bg": unc_bg, "fg": unc_fg,
            "partner_id": None,
        }

    return badges


def _roll_special_link_depth(current_depth):
    """
    The depth rule Lift's own text spells out ("1d6 layers deeper, or
    less deep if the current depth is greater than 5") - also reused
    for Secret Passage's "new location" branch, which uses the exact
    same rule (see DETAIL_TRAITS/handle_action's "use_secret_passage").
    """
    roll = roll_dice("1d6")
    if current_depth > 5:
        return max(0, current_depth - roll)
    return current_depth + roll


def _find_special_link_match(crawl_history, current_room):
    """
    Finds an existing room to auto-connect a Lift/Secret Passage to,
    instead of rolling up a brand new one - same detail as
    current_room (a matching counterpart, not just any nearby room)
    and not already paired with something else (special_link_id is
    None - a room that already has its own counterpart isn't
    available to link to a second one).

    Shallower candidates are preferred: among any that are strictly
    shallower than current_room, the shallowest one wins. Only if
    there's no shallower candidate at all does this fall back to
    deeper ones instead - among those, the *deepest* one wins, the
    same "reach as far as possible in whichever direction actually has
    something" logic mirrored the other way. Ties (equal depth) are
    broken by whichever room was created first (lowest id), purely
    for a deterministic result - a tie here should be rare in
    practice either way.

    Fully automatic, no user choice involved - this replaced what used
    to be a dropdown for picking among several candidates (see
    handle_action's "use_lift"/"use_secret_passage" and
    _render_special_connection_controls). Returns None if no matching
    room exists at all yet, in which case the caller rolls up a new
    one instead (_roll_special_link_depth + _create_linked_room).
    """
    same_detail_unlinked = [
        r for r in crawl_history
        if r["detail"] == current_room["detail"]
        and r["id"] != current_room["id"]
        and r.get("special_link_id") is None
    ]

    shallower = [r for r in same_detail_unlinked if r["used_depth"] < current_room["used_depth"]]
    if shallower:
        return min(shallower, key=lambda r: (r["used_depth"], r["id"]))

    deeper = [r for r in same_detail_unlinked if r["used_depth"] > current_room["used_depth"]]
    if deeper:
        return max(deeper, key=lambda r: (r["used_depth"], -r["id"]))

    return None


# Whether a room's entering encounter should also roll (and reveal,
# under the "monster" treasure context) loot carried by the monsters
# themselves - see _generate_room. Turned off for now: the "monster"
# context, roll_monster_treasure() call, and _render_room_treasures'
# grouping for it all still work and stay ready to go the moment this
# flips back to True; just nothing currently triggers that code path
# for a room's own entering encounter. (The standalone Encounter
# Generator's "check_encounter"/"generate_encounter" actions are
# unaffected either way - they call roll_monster_treasure() directly,
# not through here.)
_CRAWLING_MONSTER_LOOT_ENABLED = False


def _room_next_treasure_item_id(room) -> int:
    """
    The next unused treasure-item id for this room, across every
    entry in room["treasures"] - not just one of them. See that
    field's own comment (in _generate_room) for why ids need to stay
    unique room-wide rather than restarting per entry.
    """
    used = [
        item["id"]
        for entry in room.get("treasures", [])
        for item in (entry.get("found_treasure") or {}).get("item_list", [])
    ]
    return (max(used) + 1) if used else 0


def _renumber_treasure_items(room, found_treasure) -> None:
    """
    Assigns every item in `found_treasure["item_list"]` a fresh,
    room-unique id, continuing from _room_next_treasure_item_id(room).
    Call this on any newly-generated found_treasure before adding it
    to room["treasures"] (whether at room generation or, e.g., a
    retroactive re-roll like Amphoras' "smash" bonus flipping a
    failure into a success after the fact).
    """
    if not found_treasure:
        return
    next_id = _room_next_treasure_item_id(room)
    for item in found_treasure["item_list"]:
        item["id"] = next_id
        next_id += 1


def _room_ransack_choice(room):
    """
    The optional bonus-on-ransack choice for this room's detail (see
    DETAIL_TRAITS' "ransack_choice", e.g. "Amphoras"), or None if it
    doesn't have one. Shape: {"label": str, "treasure_roll_bonus": int}.
    """
    if room is None:
        return None
    return DETAIL_TRAITS.get(room["detail"], {}).get("ransack_choice")


def _roll_flat_chance_treasure(context, generate_fn):
    """
    Shared by "crevice" and "pickaxe" (see DETAIL_TRAITS'/LOCATION_
    TRAITS' "extra_treasure_context") - both are a flat 1-in-3
    chance, no DC check at all, always visible immediately (you can
    see the crevice/ore vein just by being in the room, no search
    needed). The entry is added either way, hit or miss - a default-
    visible, chance-based context still needs its own labeled group
    in the UI even when it turns up nothing, the same way a fresh
    "ransack" roll does; silently omitting the entry on a miss would
    make an already-generated, empty one look identical to a room
    that never had one to check in the first place.

    `generate_fn` is a zero-arg callable performing the actual roll
    on a hit, already bound to whichever generator/quality_mod/
    dungeon_level the caller needs. Ids are *not* renumbered here -
    the caller still has to do that against the rest of the room's
    treasures (see _generate_room's own `_renumber_items`).
    """
    found = generate_fn() if random.randint(1, 3) == 1 else None
    return {
        "context": context,
        "raw_roll": None,
        "mod": None,
        "treasure_dc_before": None,
        "found_treasure": found,
        "blocked": False,
    }


def _generate_room(
    used_depth, level, level_modifiers, roll_treasure, roll_encounter,
    treasure_dc, encounter_dc, default_treasure_dc, default_encounter_dc,
    forced_location=None, forced_detail=None,
):
    """
    Rolls a fresh location at `used_depth` - optionally its own
    treasure and an entering encounter, depending on the two flags.
    Shared by the Location Generator's "room" action (where
    roll_treasure/roll_encounter come from the person's checkboxes)
    and Crawling Mode's "go_deeper" (where both are always True - no
    checkboxes there).

    `default_treasure_dc`/`default_encounter_dc` are what the two DC
    pools reset to on a success (see roll_location_treasure/
    roll_random_encounter's own `default_dc`) - the Settings view's
    two "Default ... DC" fields.

    `forced_location` / `forced_detail`, if given, are used directly
    instead of rolling on LOCATIONS / DETAILS (the Location
    Generator's two dropdowns - Crawling Mode never sets these, it
    always rolls randomly). The room's "location_roll"/"detail_roll"
    are then None, since nothing was actually rolled for that part.

    Returns (room, treasure_dc, encounter_dc) - the room, plus the
    shared DC pools after whichever rolls happened.
    """
    if forced_location:
        loc_roll, location = None, forced_location
    else:
        loc_roll, location = roll_table(LOCATIONS, used_depth)

    if forced_detail:
        det_roll, detail = None, forced_detail
    else:
        det_roll, detail = roll_table(DETAILS, used_depth)

    room = {
        "used_depth": used_depth,
        "location_roll": loc_roll,
        "location": location,
        "location_text": LOCATION_DESCRIPTIONS.get(location, "No description available."),
        "detail_roll": det_roll,
        "detail": detail,
        "detail_text": DETAIL_DESCRIPTIONS.get(detail, "No description available."),
        # A room can end up with more than one of these at once - a
        # hidden stash found by searching, treasure sitting out in
        # the open, loot dropped by a defeated monster - each tagged
        # with a "context" ("ransack" / "open" / "monster" / "crevice"
        # / "safe") so the room card can group and label them
        # separately rather than dumping every item into one
        # undifferentiated list (see _render_room_treasures). Every
        # item across every entry in this same list shares one
        # running id sequence (assigned via _renumber_treasure_items)
        # - not restarted per entry - since "remove_treasure_item"
        # only takes a room id and an item id, no separate "which
        # entry" dimension, so ids need to stay unique across the
        # whole room, not just within the one generate_treasure()
        # call that produced them.
        "treasures": [],
        # Whether this room's *hidden* treasure (the "ransack"-context
        # entry, if there is one) has actually been revealed to the
        # players yet - "open", "monster", and "crevice" entries are
        # never gated by this, they're visible the moment they exist,
        # and "safe" has its own separate gate ("safe_opened" below,
        # picking a lock isn't "searching the room") - see
        # _render_room_treasures/_treasure_entry_is_visible. Starts
        # False - the room card shows a "Ransack Room" button in that
        # entry's place until "ransack_room" flips this - except when
        # there's definitely nothing to search for in the first
        # place: a location/detail with the "no_treasure" modifier
        # (already known to be empty, e.g. "Looted") sets this True
        # immediately further down instead. A "guaranteed_treasure"
        # location/detail (lying out in the open, e.g. "Treasure
        # Pile"/"Portcullis") does *not* skip this on its own - its
        # "open" entry is always visible regardless, but the room can
        # still separately have its own hidden stash worth searching
        # for, same as any other room.
        "ransacked": False,
        # Same idea as "ransacked" above, but specifically for a
        # "safe"-context entry (see DETAIL_TRAITS' "extra_treasure_
        # context") - picking a lock is its own action ("open_safe"),
        # not part of generally searching the room, so it needs its
        # own independent gate rather than sharing "ransacked".
        # Unused (stays False, but nothing ever checks it) for a room
        # that doesn't have a "safe" entry in the first place.
        "safe_opened": False,
        "entering_encounter": None,
        # Whether this room's own connection to its parent (in
        # Crawling Mode's room tree) is currently passable - only
        # meaningful there; the Location Generator's room never gets

        # a parent_id in the first place. See _is_adjacent_room() and
        # the "toggle_connection" action.
        "connection_blocked": False,
        # The other room this one is specially linked to via a Lift
        # or Secret Passage (see DETAIL_TRAITS/_room_special_connection_kind)
        # - None until first used, then fixed for good. Fireplace
        # needs no such field: which rooms it connects to is just
        # "every other room with the same detail", worked out fresh
        # each time from crawl_history rather than stored anywhere.
        "special_link_id": None,
    }

    def _renumber_items(found_treasure):
        _renumber_treasure_items(room, found_treasure)

    # --- Roll the treasure hidden in this location, right now. Shown
    # immediately - there's no separate "search" step for treasure
    # anymore. Skipped entirely (no "ransack"/"open" entry added to
    # room["treasures"]) if roll_treasure is False - the Treasure
    # section then just isn't shown, rather than shown empty.
    if roll_treasure:
        if _room_has_guaranteed_treasure(room):
            # "Treasure Pile"/"Portcullis" etc. - lying out in the
            # open, not something that has to be searched for: skip
            # the DC check entirely and just always find something,
            # the same unconditional roll the Treasure Generator's
            # "Generate Treasure" button uses. Doesn't touch
            # treasure_dc, since no check actually happened. raw_roll
            # stays None, which is what tells
            # _render_treasure_check_result to always render this
            # plainly - no "Search roll: ... vs DC ..." framing, ever -
            # instead of only when revisiting (see its show_roll
            # handling). This is independent of (and doesn't skip)
            # the normal hidden-treasure search roll right below - a
            # room can have obvious treasure in plain view *and* a
            # separate stash still worth searching for.
            #
            # "Bulky Treasure" is guaranteed the same way, but isn't
            # ordinary portable loot - a piece of furniture or a rug
            # doesn't belong on the same tables as coins and gems, so
            # it comes from its own generator instead (see
            # _room_guaranteed_treasure_source/generate_bulky_treasure)
            # and its own "bulky" context/label ("Bulky Treasure"
            # rather than "Lying in the open") - both are visible
            # immediately either way, this is purely so the room card
            # makes clear *which* guaranteed find this is, matching
            # what the detail's own description calls it.
            bulky = _room_guaranteed_treasure_source(room) == "bulky"
            if bulky:
                generated = generate_bulky_treasure(
                    quality_mod=level_modifiers.get("wealth", 0),
                )
            else:
                generated = generate_treasure(
                    quality_mod=level_modifiers.get("wealth", 0),
                    dungeon_level=used_depth,
                )
            _renumber_items(generated)
            room["treasures"].append({
                "context": "bulky" if bulky else "open",
                "raw_roll": None,
                "mod": None,
                "treasure_dc_before": None,
                "found_treasure": generated,
                "blocked": False,
            })

        # The room's own *hidden* treasure - searched for the normal
        # way regardless of whether it also happens to have obvious,
        # guaranteed treasure lying out in the open (see above): those
        # are two independent sources, not alternatives.
        treasure_mods = collect_modifiers(room, trigger="ransack")
        treasure_mods["treasure_roll"] += level_modifiers.get("wealth", 0)
        treasure_mods["treasure_quality"] += level_modifiers.get("wealth", 0)

        treasure_dc_before = treasure_dc
        treasure_check = roll_location_treasure(
            treasure_dc, treasure_mods, default_treasure_dc, dungeon_level=used_depth
        )
        treasure_dc = treasure_check["next_dc"]

        _renumber_items(treasure_check["treasure"])
        room["treasures"].append({
            "context": "ransack",
            "treasure_roll": treasure_check["roll"],
            "raw_roll": treasure_check["raw_roll"],
            "mod": treasure_check["mod"],
            "treasure_dc_before": treasure_dc_before,
            "found_treasure": treasure_check["treasure"],
            "blocked": treasure_check.get("blocked", False),
        })
        if treasure_check.get("blocked"):
            # A location/detail with the "no_treasure" modifier (only
            # "Looted" right now, via DETAIL_MODIFIERS - see
            # collect_modifiers) means there's definitely nothing here
            # at all, known upfront from the room's own description
            # ("There is no treasure to be found here.") - the
            # opposite of guaranteed_treasure, but the same reasoning
            # for skipping the search step: nothing to reveal by
            # ransacking that isn't already obvious just from being in
            # the room, so there's no "Ransack Room" button for this
            # either (see _render_room_treasures).
            room["ransacked"] = True

        for extra_traits in _room_extra_treasure_traits(room):
            extra_context = extra_traits["extra_treasure_context"]
            quality_mod = level_modifiers.get("wealth", 0)

            if extra_context == "crevice":
                # Something visible at the bottom of the gap, same
                # idea as "open"/guaranteed_treasure above (an
                # unconditional roll on the treasure table), just
                # chance-based instead of guaranteed - see
                # _roll_flat_chance_treasure's own docstring for the
                # full "why always add the entry" reasoning.
                entry = _roll_flat_chance_treasure(
                    "crevice",
                    lambda: generate_treasure(quality_mod=quality_mod, dungeon_level=used_depth),
                )
                if entry["found_treasure"]:
                    _renumber_items(entry["found_treasure"])
                room["treasures"].append(entry)

            elif extra_context == "pickaxe":
                # "Mine"/"Public Rock Garden" locations - same flat
                # 1-in-3 mechanic as "crevice" above, just a different
                # thing you can see is there without searching (an
                # ore vein/mineral deposit rather than something at
                # the bottom of a gap). Both locations share this one
                # context/label, but "extra_treasure_source" (on the
                # same traits dict the context itself came from)
                # points at each one's own dedicated table
                # (MINE_TREASURE_TABLES/ROCK_GARDEN_TREASURE_TABLES) -
                # a vein of ore and an ornamental crystal cluster are
                # both "something extractable with a pickaxe", but
                # not the same *kind* of find. "Mine"'s own
                # description additionally says to "replace improper
                # results with larger quantities of something less
                # valuable" - a judgment call on which results even
                # count as "improper" for a chunk of raw ore, left to
                # whoever's running the game rather than enforced
                # here, same as the note about halving brute-force
                # rolls on a "Safe" isn't encoded as a real mechanic
                # either.
                source = extra_traits.get("extra_treasure_source")
                if source == "mine":
                    generate_fn = lambda: generate_mine_treasure(quality_mod=quality_mod)
                elif source == "rock_garden":
                    generate_fn = lambda: generate_rock_garden_treasure(quality_mod=quality_mod)
                else:
                    generate_fn = lambda: generate_treasure(quality_mod=quality_mod, dungeon_level=used_depth)

                entry = _roll_flat_chance_treasure("pickaxe", generate_fn)
                if entry["found_treasure"]:
                    _renumber_items(entry["found_treasure"])
                room["treasures"].append(entry)

            elif extra_context == "safe":
                # "roll for treasure as if ransacking the location" - the
                # exact same DC-gated mechanic (and the exact same shared
                # treasure_dc pool, advanced same as any other check) as
                # the room's own hidden-treasure roll just above, just a
                # second, independent roll for the safe specifically.
                # Gated behind its own "safe_opened" flag/"open_safe"
                # action instead of "ransacked" - picking a lock isn't
                # part of generally searching the room.
                safe_dc_before = treasure_dc
                safe_check = roll_location_treasure(
                    treasure_dc, treasure_mods, default_treasure_dc, dungeon_level=used_depth
                )
                treasure_dc = safe_check["next_dc"]

                safe_success = not safe_check.get("blocked") and bool(safe_check["treasure"])
                safe_found = safe_check["treasure"]
                if not safe_check.get("blocked") and not safe_found:
                    # "If no treasure is found, place something mundane
                    # inside" - a single flavor item instead of the usual
                    # rolled-quality-tier result, still shaped like one
                    # (found_treasure dict with a one-item item_list) so
                    # it renders through the exact same path as anything
                    # else here. This is a consolation, not a success -
                    # "success" above is fixed at the real roll's outcome
                    # *before* this substitution, specifically so the
                    # rendered badge still reads "Failure" (the roll
                    # itself found nothing of value) even though
                    # found_treasure ends up non-empty either way.
                    safe_found = {
                        "quality_roll": None,
                        "quality_mod": None,
                        "raw_quality_roll": None,
                        "base_item_count": 1,
                        "extra_item_count": 0,
                        "number_of_items": 1,
                        "quality": "mundane",
                        "item_list": [{"id": 0, "text": random.choice(SAFE_MUNDANE_CONTENTS)}],
                    }

                _renumber_items(safe_found)
                room["treasures"].append({
                    "context": "safe",
                    "treasure_roll": safe_check["roll"],
                    "raw_roll": safe_check["raw_roll"],
                    "mod": safe_check["mod"],
                    "treasure_dc_before": safe_dc_before,
                    "found_treasure": safe_found,
                    "blocked": safe_check.get("blocked", False),
                    "success": safe_success,
                })

    # --- Random encounter check for entering the location. Skipped
    # entirely (room["entering_encounter"] stays None) if
    # roll_encounter is False.
    if roll_encounter:
        encounter_mods = collect_modifiers(room, trigger="room")
        encounter_mods["encounter_roll"] += level_modifiers.get("population", 0)

        encounter_dc_before = encounter_dc
        entering_check = roll_random_encounter(encounter_dc, encounter_mods, default_encounter_dc)
        encounter_dc = entering_check["next_dc"]

        monsters = (
            roll_encounter_group(level if level else 1)
            if entering_check["success"]
            else None
        )
        room["entering_encounter"] = {
            "raw_roll": entering_check["raw_roll"],
            "mod": entering_check["mod"],
            "dc_before": encounter_dc_before,
            "monsters": monsters,
            # Not rendered from here - a monster group's loot (if any)
            # is instead added to room["treasures"] below, tagged
            # "monster", so it shows up grouped alongside the room's
            # own treasure rather than duplicated in both places. Kept
            # as its own (always-None, for this caller) key anyway,
            # matching the shape _render_encounter_result expects -
            # the standalone Encounter Generator's "check_encounter"/
            # "generate_encounter" actions populate this same key for
            # real, for their own inline (non-room, non-grouped)
            # display.
            "treasure": None,
            "success": entering_check["success"],
        }

        if _CRAWLING_MONSTER_LOOT_ENABLED and roll_treasure and monsters:
            monster_treasure, treasure_dc = _roll_monster_treasure_if_enabled(
                monsters, level, level_modifiers, treasure_dc, default_treasure_dc, enabled=True
            )
            if monster_treasure is not None:
                _renumber_items(monster_treasure["found_treasure"])
                monster_treasure["context"] = "monster"
                room["treasures"].append(monster_treasure)

    return room, treasure_dc, encounter_dc


def _create_linked_room(
    crawl_history, source_room, target_depth, level, level_modifiers,
    treasure_dc, encounter_dc, default_treasure_dc, default_encounter_dc,
):
    """
    Generates a brand new room at `target_depth`, forced to have the
    same detail as `source_room` (a Lift/Secret Passage connects two
    ends of the same mechanism - it should exist, and work, on both
    sides, hence "symmetric"), and links it to `source_room` via
    special_link_id on both, for instant travel between them from
    then on regardless of where the party currently stands - the
    shared "roll up a new location" mechanic behind both "use_lift"
    and "use_secret_passage".

    Deliberately gets no parent_id at all (unlike a normal
    "go_deeper" room) - reaching it this way isn't "connected" in the
    ordinary sense the Dungeon Map's tree/connecting lines represent,
    so it starts as its own separate root there instead.

    Mutates `crawl_history` (appends the new room) and `source_room`
    (sets its special_link_id) in place. Returns
    (new_room, treasure_dc, encounter_dc).
    """
    new_room, treasure_dc, encounter_dc = _generate_room(
        target_depth, level, level_modifiers, True, True,
        treasure_dc, encounter_dc, default_treasure_dc, default_encounter_dc,
        forced_detail=source_room["detail"],
    )
    new_room["id"] = len(crawl_history)
    new_room["parent_id"] = None
    new_room["special_link_id"] = source_room["id"]
    crawl_history.append(new_room)
    source_room["special_link_id"] = new_room["id"]
    return new_room, treasure_dc, encounter_dc


def handle_action(
    action,
    depth_form=None,
    level_form=None,
    view_form=None,
    roll_treasure_form=None,
    roll_encounter_form=None,
    encounter_roll_treasure_form=None,
    encounter_dc_form=None,
    treasure_dc_form=None,
    location_form=None,
    detail_form=None,
    monster_form=None,
    quality_form=None,
    room_form=None,
    entry_form=None,
    smash_amphoras_form=None,
    default_encounter_dc_form=None,
    default_treasure_dc_form=None,
    show_roll_details_form=None,
    show_treasure_quality_form=None,
    round_length_minutes_form=None,
    track_torch_form=None,
    track_lantern_form=None,
    torch_burn_minutes_form=None,
    lantern_burn_minutes_form=None,
    light_source_form=None,
):
    """
    Mirrors the POST branch of the original Flask route.

    `action` is one of "room", "check_encounter", "generate_encounter",
    "treasure", "check_treasure", "switch_view", "reset", or None
    (None happens when only the Level dropdown changed, just like the
    original template's `onchange="this.form.submit()"` produced a
    plain POST without an `action` field).

    `view_form` is only used by "switch_view" - which view
    ("location" | "encounter" | "treasure") to make active.

    `roll_treasure_form` / `roll_encounter_form` are the Location
    Generator's two checkboxes (JS booleans, or None when the field
    isn't in the DOM right now - e.g. any view other than Location).
    They control whether "room" rolls for treasure / an entering
    encounter at all; when off, that part of the location isn't
    rolled - and so isn't shown - rather than being rolled and hidden.

    `encounter_roll_treasure_form` is the Encounter Generator's own
    "Roll for Treasure" checkbox (separate preference from the
    Location Generator's) - controls whether an encountered monster's
    own loot is even attempted, for both "check_encounter" and
    "generate_encounter".

    `encounter_dc_form` / `treasure_dc_form` are the two DC fields,
    shown per-view (Location gets both; Encounter/Treasure get just
    their own one; Crawling Mode gets neither - it won't be edited
    directly there much) rather than always present in the header -
    like `depth_form`, they let the person directly edit the shared
    running DC pools instead of just watching them drift from rolls.
    Not being rendered in the current view just means "leave it
    as-is" (same `None`-means-unchanged handling as everything else
    here), so the two pools stay shared and continuous across every
    view and Crawling Mode regardless of which of them currently
    expose an input for them.

    `default_encounter_dc_form` / `default_treasure_dc_form` are the
    Settings view's own two fields - what each pool above resets to
    on a success (see roll_location_treasure/roll_random_encounter's
    own `default_dc` parameter), instead of the fixed
    DEFAULT_ENCOUNTER_DC/DEFAULT_TREASURE_DC constants every prior
    version of this used unconditionally. "reset_settings" restores
    both back to those original constants specifically - the
    Settings view's own "Reset to Defaults" button.

    `location_form` / `detail_form` are the Location Generator's two
    dropdowns for picking a specific location/detail by name instead
    of rolling for it - empty string (or None, meaning "field not in
    the DOM right now") means "Random", the usual roll.

    `monster_form` is the Encounter Generator's monster dropdown
    (picks a specific monster instead of rolling the encounter table
    - only its number formula still gets rolled). `quality_form` is
    the Treasure Generator's quality dropdown (picks a specific tier
    instead of rolling into one). Same empty-string-or-None-means-
    Random convention as the other dropdowns.

    `room_form` is Crawling Mode's "Enter Room" dropdown - the id of
    an already-visited, deeper room to step into (only used by
    "enter_room"; not a standing preference, so it's read fresh from
    the form each time rather than persisted in SESSION). It's also
    reused, the same way "toggle_connection"/"view_room" already do,
    to identify *which* room's data to mutate for "remove_monster_
    group" and "remove_treasure_item".

    `entry_form` is only used by those same two actions - the stable
    id (assigned once, at generation time, in roll_encounter_group /
    generate_treasure - never reused) of the specific monster group
    or treasure item within that room to remove for good.

    `smash_amphoras_form` is only used by "ransack_room" - the "smash
    the amphoras" checkbox's checked state, read at the moment
    Ransack Room is clicked (see DETAIL_TRAITS' "ransack_choice" and
    _room_ransack_choice). Ignored entirely for a room whose detail
    doesn't have a ransack_choice in the first place.

    `show_roll_details_form` is the Settings view's own "Show Roll
    Details" checkbox - a global, cross-view display preference (see
    _show_roll_details), off by default, rather than something tied
    to any one action. When off, every roll display in the UI
    (Location/Detail's small badges, a Quality roll, a Search roll,
    an Encounter roll, the count-breakdown formula behind a monster
    group) collapses to its plain "what it produced" form - the same
    fallback already used for a revisited Crawling Mode room - instead
    of the raw numbers, modifiers, and DC comparisons behind it.
    Doesn't affect anything else - what a room/encounter/treasure
    actually turned out to be is unchanged, only whether the dice
    behind it are shown.

    `show_treasure_quality_form` is the Settings view's own "Show
    Treasure Quality" checkbox - another global, cross-view display
    preference (see _show_treasure_quality), also off by default and
    independent of `show_roll_details_form`. When off, a treasure's
    quality tier name (mundane/minor/moderate/valuable/excellent/
    rare/legendary - see TREASURE_QUALITY_TABLE) is never shown,
    regardless of the roll-details setting - and neither is the item
    count that goes with it, since that count is framed as "what this
    tier produced" rather than a fact worth stating on its own; the
    items themselves are still listed either way. When on, whether
    the *roll* behind that tier is also shown still depends on
    `show_roll_details_form` separately.

    `round_length_minutes_form` is the Settings view's own "Crawling
    Round Length" field - how many minutes of in-fiction time one
    "round" of Crawling Mode represents (default
    DEFAULT_ROUND_LENGTH_MINUTES). Doesn't advance the clock by
    itself - see crawl_elapsed_minutes below for what does - just
    sets how big each advance is going forward. Changing it doesn't
    retroactively rescale time already elapsed.

    `track_torch_form`/`track_lantern_form` are the Settings view's
    own "Track Torch"/"Track Lantern" checkboxes - independent,
    off-by-default toggles for each half of the optional torch/
    lantern timer (see LIGHT_SOURCES, _advance_crawl_clock,
    _render_light_gauges) - deliberately two separate switches, not
    one master one, so a table that only cares about one of the two
    isn't stuck seeing (or clock-ticking) a gauge for the other.
    `torch_burn_minutes_form`/`lantern_burn_minutes_form` are that
    same view's per-source "how long does a full one last" fields
    (default each source's own `default_burn_minutes` in
    LIGHT_SOURCES) - same relationship to light_remaining_minutes
    that round_length_minutes_form has to crawl_elapsed_minutes:
    configures the rate, doesn't move the number itself.

    `light_source_form` is only used by "refuel_light" - which gauge
    (a key into LIGHT_SOURCES, e.g. "torch") to reset back to its own
    full burn time, same idea as lighting a fresh torch or topping up
    a lantern's oil. An unrecognized key is a no-op, the same
    "nothing else validates this before it gets here" treatment
    "toggle_connection"'s `room_form` gets.
    """
    global SESSION

    depth = SESSION.get("depth", 0)
    room = SESSION.get("room")
    crawl_depth = SESSION.get("crawl_depth", 0)
    crawl_history = list(SESSION.get("crawl_history", []))
    crawl_current_id = SESSION.get("crawl_current_id")
    crawl_viewed_id = SESSION.get("crawl_viewed_id")
    crawl_elapsed_minutes = SESSION.get("crawl_elapsed_minutes", 0)
    treasure = SESSION.get("treasure")
    encounter_check = SESSION.get("encounter_check")
    active_view = SESSION.get("active_view", "crawling")

    level = _to_int_or_none(level_form)
    level_modifiers = LEVEL_MODIFIERS.get(level, {})

    depth = _resolve_int(depth_form, depth)
    encounter_dc = _resolve_int(encounter_dc_form, SESSION.get("encounter_dc", DEFAULT_ENCOUNTER_DC))
    treasure_dc = _resolve_int(treasure_dc_form, SESSION.get("treasure_dc", DEFAULT_TREASURE_DC))
    default_encounter_dc = _resolve_int(
        default_encounter_dc_form, SESSION.get("default_encounter_dc", DEFAULT_ENCOUNTER_DC)
    )
    default_treasure_dc = _resolve_int(
        default_treasure_dc_form, SESSION.get("default_treasure_dc", DEFAULT_TREASURE_DC)
    )
    round_length_minutes = _resolve_int(
        round_length_minutes_form, SESSION.get("round_length_minutes", DEFAULT_ROUND_LENGTH_MINUTES)
    )

    # Light-source timer settings (see LIGHT_SOURCES) - both dicts
    # are copied (not mutated in place) since a resolved value has to
    # replace just its own source's entry, never the whole dict.
    # track_light is per-source (not one master on/off) - see this
    # function's own docstring on track_torch_form/track_lantern_form.
    track_light = dict(SESSION.get("track_light") or {key: False for key in LIGHT_SOURCES})
    track_light["torch"] = _resolve_bool(track_torch_form, track_light.get("torch", False))
    track_light["lantern"] = _resolve_bool(track_lantern_form, track_light.get("lantern", False))
    light_burn_minutes = dict(
        SESSION.get("light_burn_minutes")
        or {key: cfg["default_burn_minutes"] for key, cfg in LIGHT_SOURCES.items()}
    )
    light_burn_minutes["torch"] = _resolve_int(
        torch_burn_minutes_form,
        light_burn_minutes.get("torch", LIGHT_SOURCES["torch"]["default_burn_minutes"]),
    )
    light_burn_minutes["lantern"] = _resolve_int(
        lantern_burn_minutes_form,
        light_burn_minutes.get("lantern", LIGHT_SOURCES["lantern"]["default_burn_minutes"]),
    )
    light_remaining_minutes = dict(
        SESSION.get("light_remaining_minutes") or {key: 0 for key in LIGHT_SOURCES}
    )

    roll_treasure = _resolve_bool(roll_treasure_form, SESSION.get("roll_treasure", True))
    roll_encounter = _resolve_bool(roll_encounter_form, SESSION.get("roll_encounter", True))
    encounter_roll_treasure = _resolve_bool(
        encounter_roll_treasure_form, SESSION.get("encounter_roll_treasure", True)
    )
    show_roll_details = _resolve_bool(
        show_roll_details_form, SESSION.get("show_roll_details", False)
    )
    show_treasure_quality = _resolve_bool(
        show_treasure_quality_form, SESSION.get("show_treasure_quality", False)
    )

    forced_location = _resolve_choice(location_form, SESSION.get("forced_location"))
    forced_detail = _resolve_choice(detail_form, SESSION.get("forced_detail"))
    forced_monster = _resolve_choice(monster_form, SESSION.get("forced_monster"))
    forced_quality = _resolve_choice(quality_form, SESSION.get("forced_quality"))

    if action == "room":
        used_depth = depth
        room, treasure_dc, encounter_dc = _generate_room(
            used_depth, level, level_modifiers, roll_treasure, roll_encounter,
            treasure_dc, encounter_dc, default_treasure_dc, default_encounter_dc,
            forced_location=forced_location, forced_detail=forced_detail,
        )
        depth = used_depth + 1

    elif action == "go_deeper":
        # Crawling Mode: always rolls both treasure and an entering
        # encounter (no checkboxes here) and always advances its own,
        # separate depth counter - never user-editable, unlike the
        # Location Generator's depth field.
        #
        # Every room gets an "id" and a "parent_id" (the room it was
        # reached from - None for the very first one) instead of just
        # relying on its position in crawl_history. Right now, with
        # only "go_deeper" implemented, parent_id always points at
        # whatever was current, so this can only ever produce a single
        # straight line - but once "Go Back" exists and lets someone
        # go_deeper again from an *earlier* room, the same linking
        # scheme naturally produces a second branch from that room,
        # with no changes needed to how rooms are stored. crawl_history
        # itself stays a flat, append-only list of every room ever
        # generated (across all branches) - crawl_current_id marks
        # which one is "where we are now", and _crawl_path_to_current()
        # walks parent_id links to reconstruct the active path through
        # it for display.
        #
        # A room whose location/detail is a dead end (see
        # _room_blocks_deeper) refuses this outright - checked here
        # too, not just via the disabled button in the UI, since the
        # button state is just a convenience, not the actual guard.
        current_room = _room_by_id(crawl_history, crawl_current_id)
        if not _room_blocks_deeper(current_room):
            new_room, treasure_dc, encounter_dc = _generate_room(
                crawl_depth, level, level_modifiers, True, True,
                treasure_dc, encounter_dc, default_treasure_dc, default_encounter_dc,
            )
            new_room["id"] = len(crawl_history)
            new_room["parent_id"] = crawl_current_id
            crawl_history.append(new_room)
            crawl_current_id = new_room["id"]
            crawl_depth += 1
            crawl_viewed_id = None  # show the newly-entered room, not whatever was being viewed
            crawl_elapsed_minutes, light_remaining_minutes = _advance_crawl_clock(
                crawl_elapsed_minutes, light_remaining_minutes, round_length_minutes, track_light
            )

    elif action == "go_back":
        # Moves focus to whatever the current room opens onto: its
        # parent for a normal room, same as before - but a depth-0
        # room has no parent_id at all (it's always a root; see
        # _render_dungeon_map's Grand Avenue docstring paragraph), so
        # for one of those, "back" means the Grand Avenue itself
        # (crawl_current_id -> None, crawl_depth -> 0) rather than a
        # no-op. A root NOT at depth 0 (a Lift/Secret Passage landing
        # elsewhere) still has nothing to go back to - it was never
        # connected to the Avenue in the first place, just floating
        # on its own - so that case is unchanged.
        #
        # Doesn't touch crawl_history at all either way - the room
        # (or the whole dungeon, from the Avenue) is still there,
        # just no longer "current".
        current_room = _room_by_id(crawl_history, crawl_current_id)
        if (
            current_room is not None
            and current_room["parent_id"] is not None
            and not current_room.get("connection_blocked")
        ):
            # crawl_depth resets to right after the parent room, so a
            # subsequent "go_deeper" branches off from there rather
            # than continuing from however deep the abandoned path
            # had gotten.
            parent_room = _room_by_id(crawl_history, current_room["parent_id"])
            crawl_current_id = current_room["parent_id"]
            crawl_depth = parent_room["used_depth"] + 1
            crawl_viewed_id = None
            crawl_elapsed_minutes, light_remaining_minutes = _advance_crawl_clock(
                crawl_elapsed_minutes, light_remaining_minutes, round_length_minutes, track_light
            )
        elif (
            current_room is not None
            and current_room["parent_id"] is None
            and current_room["used_depth"] == 0
        ):
            # Same idea, one level further up: crawl_depth resets to
            # 0, so a subsequent "go_deeper" digs a brand new depth-0
            # entrance rather than continuing this one.
            crawl_current_id = None
            crawl_depth = 0
            crawl_viewed_id = None
            crawl_elapsed_minutes, light_remaining_minutes = _advance_crawl_clock(
                crawl_elapsed_minutes, light_remaining_minutes, round_length_minutes, track_light
            )

    elif action == "stay":
        # No longer a stub - "waiting a round" without moving still
        # advances the crawl clock (see crawl_elapsed_minutes), the
        # same as any of the moves above. Nothing else changes:
        # doesn't touch crawl_current_id/crawl_depth/crawl_viewed_id,
        # unlike every action above it. Allowed from the Grand Avenue
        # too (crawl_current_id is None) - waiting around there still
        # takes time the same way.
        crawl_elapsed_minutes, light_remaining_minutes = _advance_crawl_clock(
            crawl_elapsed_minutes, light_remaining_minutes, round_length_minutes, track_light
        )

    elif action == "view_room":
        # Purely passive: changes which room's card is shown, never
        # moves the party. Any room in the whole history can be
        # viewed this way, regardless of how it relates to where we
        # are now - clicking around the Dungeon Map to look at things
        # is always safe. `room_form` is validated against the real
        # room list rather than trusted outright.
        target_id = _to_int_or_none(room_form)
        if target_id is not None and _room_by_id(crawl_history, target_id) is not None:
            crawl_viewed_id = target_id

    elif action == "enter_room":
        # Actually moves the party into a room someone is currently
        # viewing (the Crawling Mode room card's "Go Here" button) -
        # only offered, and only allowed here, when that room is a
        # *direct* neighbor of wherever we are now (its parent, or
        # one of its direct children): one step away, same as "Go
        # Back"/"Go Deeper" would take you, just without generating
        # anything since the room already exists. `room_form` is
        # re-validated against that adjacency rule rather than
        # trusted outright.
        target_id = _to_int_or_none(room_form)
        if target_id is not None and _is_adjacent_room(target_id, crawl_current_id, crawl_history):
            target_room = _room_by_id(crawl_history, target_id)
            crawl_current_id = target_id
            crawl_depth = target_room["used_depth"] + 1
            crawl_viewed_id = None
            crawl_elapsed_minutes, light_remaining_minutes = _advance_crawl_clock(
                crawl_elapsed_minutes, light_remaining_minutes, round_length_minutes, track_light
            )

    elif action == "toggle_connection":
        # Blocks or unblocks the room currently being viewed's own
        # connection to its parent - a manual, general-purpose switch
        # for now (a room card button), but the same flag a future
        # automatic effect (e.g. a "Fragile" detail's "collapsing
        # entrance" outcome) would set. Only meaningful for a room
        # that actually has a parent - the very first room has
        # nothing to toggle. `room_form` identifies which room's card
        # the button was clicked from (normally crawl_viewed_id, but
        # re-validated rather than trusted outright).
        target_id = _to_int_or_none(room_form)
        if target_id is not None:
            target_room = _room_by_id(crawl_history, target_id)
            if target_room is not None and target_room["parent_id"] is not None:
                target_room["connection_blocked"] = not target_room.get("connection_blocked")

    elif action == "ransack_room":
        # Reveals whatever treasure was already rolled for this room
        # at generation time (see _generate_room) - permanently, same
        # "fixed once generated" idea as everything else about a
        # room's own contents (see _room_has_monster's docstring).
        # `room_form` identifies the room (validated against
        # crawl_history the same way "toggle_connection"/"view_room"
        # already do). A no-op for a room with no treasure entries at
        # all (roll_treasure was off) or one that's guaranteed/already
        # ransacked - the button that triggers this isn't even shown
        # in either case (see _render_room_treasures), so reaching
        # this branch for one of those would mean something odd
        # already happened upstream, not a real user action to honor
        # twice. The "already ransacked" guard also protects the
        # Amphoras bonus below from being (re-)applied more than once
        # if this ever somehow fires again for the same room.
        #
        # Also advances the crawl clock (see crawl_elapsed_minutes) -
        # searching a room properly takes time, same as moving does.
        target_id = _to_int_or_none(room_form)
        if target_id is not None:
            target_room = _room_by_id(crawl_history, target_id)
            if target_room is not None and target_room.get("treasures") and not target_room.get("ransacked"):
                target_room["ransacked"] = True
                crawl_elapsed_minutes, light_remaining_minutes = _advance_crawl_clock(
                    crawl_elapsed_minutes, light_remaining_minutes, round_length_minutes, track_light
                )

                choice = _room_ransack_choice(target_room)
                if choice and smash_amphoras_form:
                    # "Smash the amphoras" - retroactively bumps the
                    # room's own hidden-treasure entry's mod by the
                    # bonus, since that entry was already rolled back
                    # at generation time (see _generate_room), and
                    # re-checks it against the *same* DC it was
                    # originally rolled against (treasure_dc_before,
                    # frozen at that point) - not the current, by now
                    # possibly-moved-on, shared treasure_dc pool.
                    # Deliberately doesn't touch that pool at all, so
                    # this one choice doesn't ripple into every other
                    # room's future rolls.
                    ransack_entry = next(
                        (e for e in target_room["treasures"] if e["context"] == "ransack"),
                        None,
                    )
                    if (
                        ransack_entry is not None
                        and not ransack_entry.get("blocked")
                        and ransack_entry.get("raw_roll") is not None
                    ):
                        bonus = choice["treasure_roll_bonus"]
                        ransack_entry["mod"] += bonus
                        ransack_entry["treasure_roll"] = ransack_entry["raw_roll"] + ransack_entry["mod"]
                        if (
                            not ransack_entry["found_treasure"]
                            and ransack_entry["treasure_roll"] >= ransack_entry["treasure_dc_before"]
                        ):
                            # The bonus flipped a failure into a
                            # success - generate what would've been
                            # found, using the same modifier logic
                            # (location/detail + wealth) the original
                            # roll used, recomputed fresh rather than
                            # stored, since nothing about it changes
                            # between generation and now.
                            treasure_mods = collect_modifiers(target_room, trigger="ransack")
                            quality_mod = treasure_mods["treasure_quality"] + level_modifiers.get("wealth", 0)
                            generated = generate_treasure(
                                quality_mod=quality_mod,
                                dungeon_level=target_room["used_depth"],
                            )
                            _renumber_treasure_items(target_room, generated)
                            ransack_entry["found_treasure"] = generated

    elif action == "open_safe":
        # "Pick the Lock" - the "safe"-context counterpart to
        # "ransack_room", but independently gated (see "safe_opened")
        # since picking a lock isn't part of a general room search.
        # Same no-op reasoning as "ransack_room" for a room with
        # nothing to open or one already opened.
        target_id = _to_int_or_none(room_form)
        if target_id is not None:
            target_room = _room_by_id(crawl_history, target_id)
            has_safe = target_room is not None and any(
                e["context"] == "safe" for e in target_room.get("treasures", [])
            )
            if has_safe and not target_room.get("safe_opened"):
                target_room["safe_opened"] = True

    elif action == "refuel_light":
        # "Light Torch" / "Refuel Lantern" (see _render_light_gauges) -
        # resets one light source's remaining burn time back to its
        # own configured full duration (light_burn_minutes), same
        # idea as lighting a fresh torch or topping up a lantern's
        # oil. Free - no crawl-clock cost (see _advance_crawl_clock) -
        # the same treatment "open_safe" gets, not "ransack_room"'s.
        # `light_source_form` picks which gauge; an unrecognized key
        # (or the feature being off entirely) is a no-op rather than
        # raising, same "nothing else validates this before it gets
        # here" reasoning "toggle_connection"'s room_form gets.
        if light_source_form in LIGHT_SOURCES:
            light_remaining_minutes[light_source_form] = light_burn_minutes.get(
                light_source_form, LIGHT_SOURCES[light_source_form]["default_burn_minutes"]
            )

    elif action == "remove_monster_group":
        # Marks one monster group ("3x Goblin") as dealt with -
        # removed from the room's entering encounter for good, not
        # just hidden in the UI. `room_form` identifies the room
        # (validated against crawl_history the same way "toggle_
        # connection"/"view_room" already do - normally the room
        # currently being viewed, but re-validated rather than
        # trusted outright); `entry_form` the specific group's stable
        # id. Once every group here has been removed, _room_has_
        # monster() naturally stops reporting a monster present (its
        # "groups" check is already just a truthiness check on the
        # now-empty list) - nothing extra needed for the Dungeon
        # Map's marker to update itself.
        target_id = _to_int_or_none(room_form)
        group_id = _to_int_or_none(entry_form)
        if target_id is not None and group_id is not None:
            target_room = _room_by_id(crawl_history, target_id)
            encounter = target_room.get("entering_encounter") if target_room else None
            monsters = encounter.get("monsters") if encounter else None
            if monsters and monsters.get("groups"):
                monsters["groups"] = [
                    g for g in monsters["groups"] if g["id"] != group_id
                ]

    elif action == "remove_treasure_item":
        # Same idea for a single treasure item ("N Silver Bars") -
        # removed once it's been collected. `entry_form` is the
        # item's stable id (assigned in _generate_room's
        # _next_treasure_item_id - unique across every treasure entry
        # in the room, not just within the one that produced it, so
        # no separate "which entry" identifier is needed here: this
        # just checks each of the room's treasure entries in turn and
        # removes the item from whichever one actually has it).
        # found_treasure itself is deliberately left in place even
        # once item_list is fully emptied (its quality/roll info is
        # still meaningful history) - see _room_has_treasure and
        # _render_treasure_check_result for how an emptied-but-
        # present found_treasure is told apart from "nothing was
        # ever found here".
        target_id = _to_int_or_none(room_form)
        item_id = _to_int_or_none(entry_form)
        if target_id is not None and item_id is not None:
            target_room = _room_by_id(crawl_history, target_id)
            for entry in (target_room.get("treasures", []) if target_room else []):
                found = entry.get("found_treasure")
                if found and any(it["id"] == item_id for it in found["item_list"]):
                    found["item_list"] = [
                        it for it in found["item_list"] if it["id"] != item_id
                    ]
                    break

    elif action == "use_lift":
        # Only usable while standing in a room with the "Lift" detail
        # (see _room_special_connection_kind). First use looks for an
        # existing, unlinked Lift room to connect to instead of
        # rolling up a brand new one (see _find_special_link_match) -
        # a shallower one preferred (the shallowest, if more than one
        # qualifies), a deeper one only if no shallower match exists
        # at all (the deepest, if more than one of those) - no user
        # choice involved either way. Every use after that just
        # travels the now-fixed link directly, since it's the same
        # fixed shaft each time.
        current_room = _room_by_id(crawl_history, crawl_current_id)
        if current_room is not None and _room_special_connection_kind(current_room) == "lift":
            if current_room.get("special_link_id") is not None:
                target_room = _room_by_id(crawl_history, current_room["special_link_id"])
            else:
                target_room = _find_special_link_match(crawl_history, current_room)
                if target_room is not None:
                    current_room["special_link_id"] = target_room["id"]
                    target_room["special_link_id"] = current_room["id"]
                else:
                    target_depth = _roll_special_link_depth(current_room["used_depth"])
                    target_room, treasure_dc, encounter_dc = _create_linked_room(
                        crawl_history, current_room, target_depth,
                        level, level_modifiers, treasure_dc, encounter_dc,
                        default_treasure_dc, default_encounter_dc,
                    )
            if target_room is not None:
                crawl_current_id = target_room["id"]
                crawl_depth = target_room["used_depth"] + 1
                crawl_viewed_id = None
                crawl_elapsed_minutes, light_remaining_minutes = _advance_crawl_clock(
                    crawl_elapsed_minutes, light_remaining_minutes, round_length_minutes, track_light
                )

    elif action == "use_secret_passage":
        # Only usable while standing in a room with the "Secret
        # Passage" detail. Same rule as "use_lift" now, just for
        # this detail: first use looks for an existing, unlinked
        # Secret Passage room to connect to instead of rolling up a
        # brand new one (see _find_special_link_match) - a shallower
        # one preferred (the shallowest, if more than one qualifies),
        # a deeper one only if no shallower match exists at all (the
        # deepest, if more than one of those) - no user choice
        # involved either way (this used to offer a dropdown when
        # there was more than one candidate; picking among them is
        # now fully deterministic, so there's nothing left to choose).
        # Every use after the first just travels the now-fixed link
        # directly.
        current_room = _room_by_id(crawl_history, crawl_current_id)
        if current_room is not None and _room_special_connection_kind(current_room) == "secret_passage":
            if current_room.get("special_link_id") is not None:
                target_room = _room_by_id(crawl_history, current_room["special_link_id"])
            else:
                target_room = _find_special_link_match(crawl_history, current_room)
                if target_room is not None:
                    current_room["special_link_id"] = target_room["id"]
                    target_room["special_link_id"] = current_room["id"]
                else:
                    target_depth = _roll_special_link_depth(current_room["used_depth"])
                    target_room, treasure_dc, encounter_dc = _create_linked_room(
                        crawl_history, current_room, target_depth,
                        level, level_modifiers, treasure_dc, encounter_dc,
                        default_treasure_dc, default_encounter_dc,
                    )

            if target_room is not None:
                crawl_current_id = target_room["id"]
                crawl_depth = target_room["used_depth"] + 1
                crawl_viewed_id = None
                crawl_elapsed_minutes, light_remaining_minutes = _advance_crawl_clock(
                    crawl_elapsed_minutes, light_remaining_minutes, round_length_minutes, track_light
                )

    elif action == "use_fireplace":
        # Only usable while standing in a room with the "Fireplace"
        # detail. Unlike Lift/Secret Passage this is never a fixed
        # pair - it's a standing network between every room that has
        # this same detail, worked out fresh each time rather than
        # stored on the rooms themselves. No candidates yet -> climb
        # the chimney to a brand new fireplace room (which everyone
        # else can then reach too); exactly one -> go straight there;
        # more than one -> `room_form` picks which (the room card
        # shows a dropdown for that).
        current_room = _room_by_id(crawl_history, crawl_current_id)
        if current_room is not None and _room_special_connection_kind(current_room) == "fireplace":
            candidates = [
                r for r in crawl_history
                if r["detail"] == "Fireplace" and r["id"] != crawl_current_id
            ]
            target_room = None

            if not candidates:
                new_room, treasure_dc, encounter_dc = _generate_room(
                    current_room["used_depth"] + 1, level, level_modifiers, True, True,
                    treasure_dc, encounter_dc, default_treasure_dc, default_encounter_dc,
                    forced_detail="Fireplace",
                )
                new_room["id"] = len(crawl_history)
                # No parent_id, same reasoning as _create_linked_room:
                # reached via the chimney, not a normal doorway - it
                # starts its own root in the Dungeon Map rather than
                # hanging off the room it was found from.
                new_room["parent_id"] = None
                crawl_history.append(new_room)
                target_room = new_room
            elif len(candidates) == 1:
                target_room = candidates[0]
            else:
                chosen_id = _to_int_or_none(room_form)
                target_room = next((r for r in candidates if r["id"] == chosen_id), None)

            if target_room is not None:
                crawl_current_id = target_room["id"]
                crawl_depth = target_room["used_depth"] + 1
                crawl_viewed_id = None
                crawl_elapsed_minutes, light_remaining_minutes = _advance_crawl_clock(
                    crawl_elapsed_minutes, light_remaining_minutes, round_length_minutes, track_light
                )

    elif action == "check_encounter":
        # A standalone risk check (e.g. searching around, listening at
        # a door, ...) shown in its own Encounter Generator view - not
        # tied to a location's own treasure at all, but an encountered
        # monster can still be carrying loot of its own - see
        # roll_monster_treasure(). Works even with no location
        # generated yet (room is None): collect_modifiers() then simply
        # applies no location/detail modifiers, just the current level's.
        mods = collect_modifiers(room, trigger="ransack")
        mods["encounter_roll"] += level_modifiers.get("population", 0)

        encounter_dc_before = encounter_dc
        check = roll_random_encounter(encounter_dc, mods, default_encounter_dc)
        encounter_dc = check["next_dc"]

        monsters = (
            roll_encounter_group(level if level else 1, forced_monster=forced_monster)
            if check["success"]
            else None
        )
        monster_treasure, treasure_dc = _roll_monster_treasure_if_enabled(
            monsters, level, level_modifiers, treasure_dc, default_treasure_dc, encounter_roll_treasure
        )

        encounter_check = {
            "mode": "rolled",
            "raw_roll": check["raw_roll"],
            "mod": check["mod"],
            "dc_before": encounter_dc_before,
            "monsters": monsters,
            "treasure": monster_treasure,
            "success": check["success"],
        }

    elif action == "generate_encounter":
        # Skips the "does an encounter even happen" DC check entirely
        # and just directly rolls a monster group - the Encounter
        # Generator's equivalent of the Treasure Generator's
        # unconditional "Generate Treasure" button. Doesn't touch
        # encounter_dc, since no check actually happened; the
        # monster's own loot (if any) is still a real DC-gated
        # treasure roll though, same as everywhere else.
        monsters = roll_encounter_group(level if level else 1, forced_monster=forced_monster)
        monster_treasure, treasure_dc = _roll_monster_treasure_if_enabled(
            monsters, level, level_modifiers, treasure_dc, default_treasure_dc, encounter_roll_treasure
        )

        encounter_check = {
            "mode": "generated",
            "raw_roll": None,
            "mod": None,
            "dc_before": None,
            "monsters": monsters,
            "treasure": monster_treasure,
            "success": True,
        }

    elif action == "check_treasure":
        # The Treasure Generator's DC-gated counterpart to "treasure"
        # below - a real check against the same shared treasure_dc
        # pool everything else uses, using only the current level's
        # wealth modifier (no location/detail context, same as
        # roll_monster_treasure()). Can fail ("nothing found").
        wealth_mod = level_modifiers.get("wealth", 0) if level else 0
        mods = {
            "treasure_roll": wealth_mod,
            "treasure_quality": wealth_mod,
            "encounter_roll": 0,
            "no_treasure": False,
        }
        treasure_dc_before = treasure_dc
        check = roll_location_treasure(
            treasure_dc, mods, default_treasure_dc, dungeon_level=level if level else 1,
            forced_quality=forced_quality,
        )
        treasure_dc = check["next_dc"]

        treasure = {
            "mode": "rolled",
            "raw_roll": check["raw_roll"],
            "mod": check["mod"],
            "treasure_dc_before": treasure_dc_before,
            "found_treasure": check["treasure"],
            "blocked": check.get("blocked", False),
        }

    elif action == "treasure":
        # Unconditional - always finds something, no DC check, no
        # treasure_dc consumption. The Treasure Generator's equivalent
        # of the Encounter Generator's "generate_encounter".
        generated = generate_treasure(
            quality_mod=level_modifiers.get("wealth", 0) if level else 0,
            dungeon_level=room["used_depth"] if room else 1,
            forced_quality=forced_quality,
        )
        treasure = {
            "mode": "generated",
            "raw_roll": None,
            "mod": None,
            "treasure_dc_before": None,
            "found_treasure": generated,
            "blocked": False,
        }

    elif action == "switch_view":
        if view_form in ("location", "encounter", "treasure", "crawling", "settings"):
            active_view = view_form

    elif action == "reset_settings":
        # The Settings view's own "Reset to Defaults" - restores
        # every Settings-view field (both "Default ... DC" fields,
        # "Show Roll Details", "Show Treasure Quality", "Crawling
        # Round Length", "Track Torch"/"Track Lantern" and their two
        # burn-time fields) back to its original, hardcoded default.
        # Deliberately narrower than "reset" above: this doesn't
        # touch the actual in-progress dungeon (crawl_history, the
        # live treasure_dc/encounter_dc pools, generated rooms,
        # crawl_elapsed_minutes, light_remaining_minutes, ...) at all,
        # only the settings themselves - elapsed time and light
        # already burned aren't "settings" any more than crawl_
        # history is, so both stay exactly like every other piece of
        # in-progress dungeon state here.
        default_encounter_dc = DEFAULT_ENCOUNTER_DC
        default_treasure_dc = DEFAULT_TREASURE_DC
        show_roll_details = False
        show_treasure_quality = False
        round_length_minutes = DEFAULT_ROUND_LENGTH_MINUTES
        track_light = {key: False for key in LIGHT_SOURCES}
        light_burn_minutes = {key: cfg["default_burn_minutes"] for key, cfg in LIGHT_SOURCES.items()}

    elif action == "reset":
        SESSION = _default_session()
        return

    SESSION = {
        "depth": depth,
        "room": room,
        "crawl_depth": crawl_depth,
        "crawl_history": crawl_history,
        "crawl_current_id": crawl_current_id,
        "crawl_viewed_id": crawl_viewed_id,
        "crawl_elapsed_minutes": crawl_elapsed_minutes,
        "treasure": treasure,
        "treasure_dc": treasure_dc,
        "encounter_dc": encounter_dc,
        "default_treasure_dc": default_treasure_dc,
        "default_encounter_dc": default_encounter_dc,
        "encounter_check": encounter_check,
        "level": level,
        "level_modifiers": level_modifiers,
        "active_view": active_view,
        "roll_treasure": roll_treasure,
        "roll_encounter": roll_encounter,
        "encounter_roll_treasure": encounter_roll_treasure,
        "forced_location": forced_location,
        "forced_detail": forced_detail,
        "forced_monster": forced_monster,
        "forced_quality": forced_quality,
        "show_roll_details": show_roll_details,
        "show_treasure_quality": show_treasure_quality,
        "round_length_minutes": round_length_minutes,
        "track_light": track_light,
        "light_burn_minutes": light_burn_minutes,
        "light_remaining_minutes": light_remaining_minutes,
    }


# ----------------------------
# RENDERING
# (this replaces templates/index.html)
# ----------------------------

def _render_level_options(level):
    parts = [
        '<option value="" {} disabled>\u2014 Select Level \u2014</option>'.format(
            "selected" if level is None else ""
        )
    ]
    for lvl in range(1, 13):
        selected = "selected" if lvl == level else ""
        parts.append(f'<option value="{lvl}" {selected}>Level {lvl}</option>')
    return "\n".join(parts)


def _render_choice_options(names, current_value):
    """Builds <option> tags for a "pick one, or leave on Random"
    dropdown - used by the Location Generator's Location/Detail
    selects, the Encounter Generator's monster select, and the
    Treasure Generator's quality select."""
    parts = [
        '<option value="" {}>Random</option>'.format(
            "selected" if not current_value else ""
        )
    ]
    for name in names:
        selected = "selected" if name == current_value else ""
        parts.append(f'<option value="{name}" {selected}>{name}</option>')
    return "\n".join(parts)


def _render_getting_started_placeholder(text):
    """The "nothing generated yet" section shown below a standalone
    generator's controls (Location/Encounter/Treasure) before its
    first result exists."""
    return f'<div class="section"><em>{text}</em></div>'


def _monsters_in_level_table(level):
    """
    All distinct monster names that can appear on `level`'s encounter
    table (NEXT_LEVEL / ROLL_TWICE entries excluded), sorted
    alphabetically - the pool for the Encounter Generator's monster
    dropdown. Falls back to level 1 if no level is selected, matching
    how encounter rolling itself defaults elsewhere.
    """
    level = max(1, min(12, level or 1))
    names = set()
    for row in ENCOUNTER_TABLES[level]:
        for entry in row:
            if entry in (NEXT_LEVEL, ROLL_TWICE):
                continue
            names.add(entry["monster"])
    return sorted(names)


def _treasure_quality_names():
    """
    All distinct treasure quality tiers, in ascending rarity order (as
    TREASURE_QUALITY_TABLE already lists them) - the pool for the
    Treasure Generator's quality dropdown.
    """
    names = []
    seen = set()
    for roll in sorted(TREASURE_QUALITY_TABLE.keys()):
        name = TREASURE_QUALITY_TABLE[roll][1]
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _render_meta_badges(level_modifiers):
    parts = []
    for key, value in level_modifiers.items():
        if value != 0:
            cls = get_modifier_badge_class(key, value)
            label = key.replace("_", " ").title()
            parts.append(
                f'<span class="meta-badge {cls}">{label} {format_modifier(value)}</span>'
            )
    return "".join(parts)


def _render_item_list(item_list, room_id=None, interactive=False):
    """
    `interactive=True` (only ever passed from Crawling Mode's own
    room card - see _render_room_card) adds a subtle "x" next to each
    item that removes just that one item, permanently, via
    "remove_treasure_item" - for marking it as collected. `room_id`
    identifies which room to mutate; every other caller (Location/
    Encounter/Treasure Generator - none of which have a persistent,
    revisitable room to mutate) leaves both at their defaults and
    gets the old, plain, non-interactive list.
    """
    lines = []
    for item in item_list:
        remove_btn = ""
        if interactive and room_id is not None:
            remove_btn = (
                f' <span class="entry-remove-btn" '
                f'onclick="removeTreasureItem({room_id}, {item["id"]})" '
                f'title="Mark as collected" role="button" tabindex="0">&times;</span>'
            )
        lines.append(f"\u2022 {item['text']}{remove_btn}<br>")
    return "".join(lines)


def _pluralize(count, singular, plural=None):
    plural = plural or f"{singular}s"
    return f"{count} {singular if count == 1 else plural}"


def _format_elapsed_time(total_minutes) -> str:
    """
    "45 minutes" / "1 hour" / "2 hours 15 minutes" - used for
    crawl_elapsed_minutes in Crawling Mode's own meta-line (see
    _render_crawling_view). Deliberately not HH:MM - this is elapsed
    in-fiction time since entering the dungeon, not a clock reading,
    so a couple of rounded, spelled-out units reads more naturally
    than a timestamp would.
    """
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{_pluralize(hours, 'hour')} {_pluralize(minutes, 'minute')}"
    if hours:
        return _pluralize(hours, "hour")
    return _pluralize(minutes, "minute")


def _advance_crawl_clock(elapsed_minutes, light_remaining_minutes, round_length_minutes, track_light):
    """
    Advances the shared crawl clock by one round (round_length_minutes)
    - both the running elapsed-time total (crawl_elapsed_minutes) and
    every *individually* tracked light source's remaining burn time
    (see LIGHT_SOURCES - `track_light` is a per-source dict, e.g.
    {"torch": True, "lantern": False}, not one master on/off), each
    floored at 0 rather than going negative. Called from every action
    that counts as "a round" for elapsed time - "go_deeper", both
    branches of "go_back", "enter_room", "ransack_room", "use_lift",
    "use_secret_passage", "use_fireplace", "stay" - so light burns
    down in perfect lockstep with elapsed time, never on some
    separate schedule of its own. Kept as one shared helper
    specifically so a future 9th trigger can't be added to the
    elapsed-time side of this without also remembering the light
    side - that split is exactly the kind of bug a shared helper
    heads off.

    A source with tracking off passes through unchanged, deliberately
    - it doesn't deplete silently in the background while hidden, so
    turning it on later starts from whatever was last actually shown
    (0, fresh, until something is lit) rather than some number that
    had been secretly ticking down the whole time.
    """
    elapsed_minutes += round_length_minutes
    light_remaining_minutes = {
        key: (max(0, minutes - round_length_minutes) if track_light.get(key) else minutes)
        for key, minutes in light_remaining_minutes.items()
    }
    return elapsed_minutes, light_remaining_minutes


def _with_optional_lead_line(line_html, body_html):
    """
    Joins an optional lead line (e.g. a Quality line that may have
    been suppressed entirely by _show_treasure_quality) with whatever
    comes after it - omitting the `<br><br>` separator too when
    there's no lead line, rather than leaving a stray blank gap above
    the body.
    """
    if not line_html:
        return body_html
    return f"{line_html}<br><br>{body_html}"


def _render_quality_summary(treasure, show_quality=True):
    """
    Just "Quality: X, N items" - no roll/formula info at all. Used
    when revisiting an older Crawling Mode room via "Go Back" (the
    dice that produced what's there aren't re-litigated every time)
    and for guaranteed treasure that was never rolled for at all
    (open/bulky/pickaxe/crevice - see _room_has_guaranteed_treasure).

    Deliberately plain label text + a small muted `.meta-badge`
    rather than a bold `<strong>` tag - the same visual weight
    _render_quality_roll_line's own badge already uses, so this reads
    as the same kind of secondary, supporting detail either way
    instead of competing with the actual item text listed right below
    it for attention.

    `show_quality=False` (see _show_treasure_quality) drops this
    whole line, not just the tier name - the item count is presented
    here specifically as "how many things this quality tier rolled
    up", so showing it without the tier it belongs to reads as an odd
    half-answer. The item list right below still shows regardless -
    this is only ever the framing line above it.
    """
    if not show_quality:
        return ""
    count_phrase = _pluralize(treasure["base_item_count"], "item")
    if treasure["extra_item_count"] > 0:
        count_phrase += f' + {_pluralize(treasure["extra_item_count"], "extra")}'
    return f'Quality: <span class="meta-badge">{treasure["quality"]}, {count_phrase}</span>'


def _render_quality_roll_line(treasure, show_quality=True):
    """
    Quality tier and item count both fall out of one roll, indexed
    into TREASURE_QUALITY_TABLE (see generate_treasure()). Same
    "{label} roll: ... \u2192 outcome" template every other roll
    display in the UI uses (see _format_roll_total) - "Quality roll:"
    rather than the more generic "Rolled ..." specifically so it
    reads as its own distinct roll when it's sitting right below a
    Search/Encounter roll's own line, not a repeat of it.

    Base items (from the quality tier's own table) and extra treasure
    (paint, consumables, artifacts, ... from generate_extra_items())
    come from separate rolls, so they're called out separately rather
    than folded into one "number of items".

    `show_quality=False` (see _show_treasure_quality) drops this
    whole line - not just the tier name, and not just the roll, but
    the item count with it too (see _render_quality_summary's own
    docstring for why: the count is framed as "what this tier
    produced", not a fact worth stating on its own). A "Quality roll:
    ... \u2192 ???" line with the outcome blanked out would also be
    worse than no line at all, since the raw roll number alone can
    still leak which tier it landed on to anyone who knows
    TREASURE_QUALITY_TABLE.
    """
    if not show_quality:
        return ""

    count_phrase = _pluralize(treasure["base_item_count"], "item")
    if treasure["extra_item_count"] > 0:
        count_phrase += f' + {_pluralize(treasure["extra_item_count"], "extra")}'

    if treasure["raw_quality_roll"] is None:
        # Quality tier was chosen directly (Treasure Generator's
        # dropdown), not rolled - nothing to show as "Quality roll:".
        return (
            f'<span class="meta-badge">Quality chosen '
            f'\u2192 {treasure["quality"]}, {count_phrase}</span>'
        )

    rolled = _format_roll_total(
        treasure["raw_quality_roll"], treasure["quality_mod"], total=treasure["quality_roll"],
    )
    return (
        f'Quality roll: <span class="recent-roll">{rolled}</span> '
        f'<span class="meta-badge">\u2192 {treasure["quality"]}, {count_phrase}</span>'
    )


def _render_treasure_check_result(
    result, fail_message="There doesn't seem to be anything of value here.",
    show_roll=True, show_quality=True, room_id=None, interactive=False,
):
    """
    `result["success"]`, if explicitly set, overrides found_treasure's
    truthiness for the Success/Failure outcome text specifically -
    normally the two agree (found something <=> the roll succeeded),
    but the "safe" context substitutes a mundane fallback item into
    found_treasure even on a failed roll (see _generate_room), which
    would otherwise make a failed safe check read as a "Success".
    Every other context leaves this key unset, so it falls back to
    the old bool(found) behavior - unaffected.

    `show_quality` (see _show_treasure_quality) is independent of
    `show_roll` - passed straight down to whichever of
    _render_quality_roll_line/_render_quality_summary ends up used.
    """
    if result.get("blocked"):
        return "<em>No treasure can be found here.</em>"

    found = result["found_treasure"]

    # Once every individual item has been removed ("collected") via
    # "remove_treasure_item", found_treasure itself is still there
    # (its quality/roll info is still meaningful history) but
    # item_list is now empty - render that as "already collected"
    # rather than the quality summary claiming "0 items".
    if found and not found["item_list"]:
        return "<em>Everything of value here has already been collected.</em>"

    # raw_roll is None for treasure that was never actually rolled
    # for at all - either revisiting an old room (show_roll=False,
    # handled the same way already) or treasure that's simply lying
    # out in the open (a "Treasure Pile"/"Portcullis" etc. - see
    # _room_has_guaranteed_treasure) and was never subject to a DC
    # check in the first place. The latter always renders plainly,
    # regardless of show_roll/freshness - there's no roll to frame.
    if not show_roll or result.get("raw_roll") is None:
        if found:
            return _with_optional_lead_line(
                _render_quality_summary(found, show_quality=show_quality),
                _render_item_list(found["item_list"], room_id=room_id, interactive=interactive),
            )
        return f"<em>{fail_message}</em>"

    outcome = "Success" if result.get("success", bool(found)) else "Failure"

    html = (
        f"Search roll: "
        f'<span class="recent-roll">{_format_roll_total(result["raw_roll"], result["mod"])}</span> '
        f'vs DC {result["treasure_dc_before"]} \u2192 {outcome}<br><br>'
    )

    if found:
        html += _with_optional_lead_line(
            _render_quality_roll_line(found, show_quality=show_quality),
            _render_item_list(found["item_list"], room_id=room_id, interactive=interactive),
        )
    else:
        html += f"<em>{fail_message}</em>"

    return html


def _render_monster_lines(monsters, show_rolls=True, room_id=None, interactive=False):
    """Renders the "N× Monster (breakdown)" lines for an encounter's
    monster groups. Assumes `monsters` is not None and has groups.

    `show_rolls=False` drops the count-breakdown formula and cascade
    note, leaving just "N× Monster" - used when revisiting an older
    Crawling Mode room.

    `interactive=True` (only ever passed from Crawling Mode's own
    room card) adds a subtle "x" next to each group that removes just
    that one group, permanently, via "remove_monster_group" - for
    marking it as defeated. `room_id` identifies which room to
    mutate; every other caller (Encounter Generator, a location's own
    entering encounter shown from the Location Generator) leaves both
    at their defaults and gets the old, plain, non-interactive lines.
    """
    requested_level = monsters["requested_level"]
    lines = []
    for group in monsters["groups"]:
        remove_btn = ""
        if interactive and room_id is not None:
            remove_btn = (
                f' <span class="entry-remove-btn" '
                f'onclick="removeMonsterGroup({room_id}, {group["id"]})" '
                f'title="Mark as defeated" role="button" tabindex="0">&times;</span>'
            )

        if not show_rolls:
            lines.append(f'<span class="recent-roll">{group["count"]}&times; {group["monster"]}</span>{remove_btn}')
            continue

        cascade_note = ""
        if group["rolled_on_level"] != requested_level:
            cascade_note = (
                f' <span class="meta-badge">rolled on Level '
                f'{group["rolled_on_level"]} table</span>'
            )

        count_note = ""
        if group["count"] > 1:
            count_note = f' <span class="meta-badge">{group["count_breakdown"]}</span>'

        lines.append(
            f'<span class="recent-roll">{group["count"]}&times; {group["monster"]}</span>'
            f"{count_note}{cascade_note}{remove_btn}"
        )

    return "<br>".join(lines)


def _render_encounter_treasure(result, show_rolls=True, show_quality=True, room_id=None, interactive=False):
    """`result` is a roll_monster_treasure()-shaped dict, or None if
    every monster present is one that never carries treasure."""
    if result is None:
        return (
            '<hr><strong>Treasure:</strong><br>'
            "<em>This kind of encounter never carries any treasure.</em>"
        )

    return f"""
    <hr>
    <strong>Treasure:</strong><br>
    {_render_treasure_check_result(result, show_roll=show_rolls, show_quality=show_quality, room_id=room_id, interactive=interactive)}
    """


def _render_encounter_result(result, show_treasure=True, show_rolls=True, show_quality=True, room_id=None, interactive=False):
    """
    Renders one encounter-check result - shared between a location's
    own "entering encounter" and the standalone Encounter Generator
    view, since both produce the same shape of result (see
    handle_action's "room", "check_encounter", and "generate_encounter"
    branches).

    `show_treasure=False` omits the Treasure sub-section entirely -
    used for a location's entering encounter, which never carries its
    own treasure (see handle_action's "room" branch), so there's
    nothing to explain there, not even a "carries no treasure" note.

    `show_rolls=False` hides all roll/DC mechanics entirely (no
    "Search/Encounter roll: ... vs DC ..." line, no count-breakdown formula) - used
    when revisiting an older Crawling Mode room via "Go Back": what's
    in the room is still shown, but the dice that produced it (back
    when it was first generated) aren't re-litigated every time.

    `show_quality` (see _show_treasure_quality) is forwarded into
    _render_encounter_treasure the same way, independent of
    `show_rolls` - a monster group's own loot follows the same
    Quality-display rule as any other treasure.

    `result["mode"] == "generated"` (from "generate_encounter") skips
    the "Search/Encounter roll: ... vs DC ..." framing entirely too, since no check
    actually happened there - mirrors how the Treasure Generator's
    unconditional "Generate Treasure" skips DC framing too.

    `room_id`/`interactive` are only ever passed from Crawling Mode's
    own room card (see _render_room_card) - forwarded down into
    _render_monster_lines/_render_encounter_treasure so each monster
    group there gets its own "mark as defeated" control. A group list
    that's present but now empty (every group in it already removed)
    gets its own distinct message rather than being folded into the
    genuine "no encounter happened here" case.
    """
    groups_now_empty = (
        result["success"] and result["monsters"] is not None
        and not result["monsters"]["groups"]
    )

    if not show_rolls or result.get("mode") == "generated":
        if result["success"] and result["monsters"] and result["monsters"]["groups"]:
            body = _render_monster_lines(
                result["monsters"], show_rolls=show_rolls, room_id=room_id, interactive=interactive
            )
            treasure_html = (
                _render_encounter_treasure(
                    result["treasure"], show_rolls=show_rolls, show_quality=show_quality,
                    room_id=room_id, interactive=interactive,
                )
                if show_treasure else ""
            )
        elif result.get("mode") == "generated":
            # "generate_encounter" always succeeds and always rolls a
            # group - this branch shouldn't normally be reachable for
            # it, but render *something* sensible if it ever is.
            body = "<em>Nothing generated.</em>"
            treasure_html = ""
        elif groups_now_empty:
            body = "<em>All monsters here have already been dealt with.</em>"
            treasure_html = ""
        else:
            body = "<em>No encounter.</em>"
            treasure_html = ""
        return f"{body}\n    {treasure_html}"

    outcome = "Encounter" if result["success"] else "Safe"

    if result["success"] and result["monsters"] and result["monsters"]["groups"]:
        body = _render_monster_lines(result["monsters"], room_id=room_id, interactive=interactive)
        treasure_html = (
            _render_encounter_treasure(
                result["treasure"], show_quality=show_quality, room_id=room_id, interactive=interactive
            )
            if show_treasure else ""
        )
    elif groups_now_empty:
        body = "<em>All monsters here have already been dealt with.</em>"
        treasure_html = ""
    else:
        body = "<em>No encounter.</em>"
        treasure_html = ""

    return f"""
    Encounter roll:
    <span class="recent-roll">
        {_format_roll_total(result['raw_roll'], result['mod'])}
    </span>
    vs DC {result['dc_before']}
    \u2192 {outcome}
    <br><br>
    {body}
    {treasure_html}
    """


# ----------------------------
# VIEWS
# Each view is self-contained: its own controls plus its own result -
# only one of these is shown at a time (see render_page()).
# ----------------------------

def _render_room_roll_badge(label, roll, depth, show_rolls):
    """
    One small "how this was determined" badge for a room's Location
    or Detail. Value-first design: the actual name is the headline
    (see _render_room_card below), this is just the subtle footnote
    explaining the roll behind it - the same "{label} roll: ... =
    total" template used for every other roll display in the UI (see
    _format_roll_total), just without a "\u2192 outcome" suffix -
    unlike Quality/Search/Encounter rolls, the outcome here is
    already the room's own title sitting right above, so repeating it
    in the badge too would just be noise.

    `roll` is the room's stored location_roll/detail_roll - the
    *total* (d20 + depth) roll_table() actually rolled against the
    table, or None if that field was chosen from a dropdown instead
    (see _generate_room's forced_location/forced_detail). The raw d20
    itself isn't stored separately, but depth is known, so it's
    simply `roll - depth`.

    Blank entirely when `show_rolls` is False (Crawling Mode
    revisiting an older room via "Go Back").
    """
    if not show_rolls:
        return ""
    if roll is None:
        return f'<span class="meta-badge">{label} chosen</span>'
    raw = roll - depth
    return f'<span class="meta-badge">{label} roll: {_format_roll_total(raw, depth)}</span>'


_TREASURE_CONTEXT_LABELS = {
    "ransack": "Hidden in room",
    "open": "Lying in the open",
    "monster": "Looted from the monsters",
    "crevice": "At the bottom of the crevice",
    "safe": "Inside the safe",
    "bulky": "Bulky Treasure",
    "pickaxe": "Extractable with a pickaxe",
}

# Which icon represents a room's treasure in the Dungeon Map badge and
# the room card's presence pill (see _room_treasure_icon,
# _render_presence_pills, _render_dungeon_map) - the plain chest
# (_ICON_TREASURE) by default, but a couple of contexts get their own
# more specific glyph instead, since "chest" doesn't really describe
# what's actually there for these: "crevice"/"pickaxe" (both from
# _roll_flat_chance_treasure() - same idea, something mineral pried
# out of an opening in the rock, just different flavor text depending
# on the location) get a gem; "bulky" gets a crate. Every other
# context ("ransack"/"open"/"monster"/"safe") falls back to the
# default chest via .get()'s own fallback.
_TREASURE_CONTEXT_ICONS = {
    "crevice": _ICON_GEM,
    "pickaxe": _ICON_GEM,
    "bulky": _ICON_CRATE,
}


def _render_room_treasures(room, show_rolls, show_quality, room_id, interactive):
    """
    Renders every entry in room["treasures"], each under its own
    small context label (see _TREASURE_CONTEXT_LABELS) - a room can
    have more than one at once, e.g. a hidden stash the party still
    has to search for *and* a locked safe they haven't picked yet.

    Two independent reveal gates exist (see _treasure_entry_is_visible
    and _ROOM_SEARCH_GATED_CONTEXTS): "ransack" comes from generally
    searching the room - shown as a "Ransack Room" button until then
    (if more than one context ever shares this gate, they're combined
    into a single button/label rather than repeating it); "safe" gets
    its own "Pick the Lock" button instead, since picking a lock is
    its own action, not part of a general search. Both only appear
    when `interactive` (Crawling Mode) - the Location Generator's own
    room has no persistent state to search/unlock later, so everything
    is just shown immediately there, same as "open"/"monster"/
    "crevice" always are regardless of context (you can see a crevice,
    and whatever's visible at the bottom of it, without any action).
    Returns "" if the room has no treasure entries at all (roll_treasure
    was off).

    A detail with an optional "smash while ransacking"-style bonus
    (see DETAIL_TRAITS' "ransack_choice", e.g. "Amphoras") gets a
    checkbox next to the Ransack Room button for it.
    """
    entries = room.get("treasures", [])
    room_search_pending = interactive and not room.get("ransacked") and any(
        e["context"] in _ROOM_SEARCH_GATED_CONTEXTS for e in entries
    )
    safe_pending = interactive and not room.get("safe_opened") and any(
        e["context"] == "safe" for e in entries
    )
    ransack_choice = _room_ransack_choice(room) if room_search_pending else None

    blocks = []
    room_search_group_rendered = False
    for entry in entries:
        context = entry["context"]
        label = _TREASURE_CONTEXT_LABELS.get(context, context.title())

        if context in _ROOM_SEARCH_GATED_CONTEXTS and room_search_pending:
            if room_search_group_rendered:
                continue  # already covered by the combined block below
            room_search_group_rendered = True
            group_labels = " &amp; ".join(
                _TREASURE_CONTEXT_LABELS.get(e["context"], e["context"].title())
                for e in entries
                if e["context"] in _ROOM_SEARCH_GATED_CONTEXTS
            )
            choice_html = ""
            if ransack_choice:
                choice_html = (
                    f'<label class="ransack-choice">'
                    f'<input type="checkbox" id="smash-amphoras"> {ransack_choice["label"]}'
                    f"</label>"
                )
            blocks.append(
                f'<div class="treasure-context">'
                f'<div class="treasure-context-label">{group_labels}</div>'
                f'<button type="button" class="ransack-button" onclick="ransackRoom({room_id})">'
                f"{_time_cost_icon_html()}Ransack Room</button>"
                f"{choice_html}"
                f"</div>"
            )
            continue

        if context == "safe" and safe_pending:
            # No time-cost icon here (see _time_cost_icon_html) -
            # unlike "Ransack Room" just above, picking a lock doesn't
            # advance the crawl clock at all (see handle_action's
            # "open_safe" - deliberately not in the same list of
            # crawl_elapsed_minutes-advancing actions as "ransack_room").
            body = (
                f'<button type="button" class="ransack-button" onclick="openSafe({room_id})">'
                f"Pick the Lock</button>"
            )
        else:
            body = _render_treasure_check_result(
                entry, show_roll=show_rolls, show_quality=show_quality, room_id=room_id, interactive=interactive
            )

        blocks.append(
            f'<div class="treasure-context">'
            f'<div class="treasure-context-label">{label}</div>'
            f"{body}"
            f"</div>"
        )

    return "".join(blocks)


def _render_presence_pills(room):
    """
    Always-visible (independent of _show_roll_details) "is there
    currently a monster/treasure here" indicators for the room card's
    meta-line - reuses _room_has_monster/_room_has_hostile_monster/
    _room_has_treasure/_room_has_valuable_treasure, the same facts
    already driving the Dungeon Map's own badges (see
    _render_dungeon_map), so the two stay in lockstep by construction
    rather than via two separately-maintained checks. Each disappears
    the moment the underlying fact stops being true (last monster
    group removed, every treasure item collected) - "is there right
    now", not "was there ever".

    Each of the two has its own two-tier severity, not just an on/off:
    - Monster: red/bold "Monster" pill only once a genuinely hostile
      creature is present (_room_has_hostile_monster); a room with
      only NON_HOSTILE_MONSTERS (Critters/Gravediggers/Exiles) gets a
      calmer, neutral "Encounter" pill instead - present, but not a
      warning. Also gets its own colored "Encounter:" section label
      (see _render_room_card) when hostile - Treasure never does,
      regardless of tier - since an active threat is the more
      dangerous fact of the two and is meant to be unmissable at a
      glance, before reading a word of the room's description.
    - Treasure: gold/bold "Treasure" pill once something actually
      worth having is visible (_room_has_valuable_treasure); a room
      with only mundane-quality junk (or a Safe's failure consolation
      - see that helper's own docstring) gets a muted, quiet version
      of the same pill instead - there's still something to pick up,
      it's just not exciting. Either tier's icon can vary by context
      too (gem/crate instead of the default chest - see
      _room_treasure_icon), independent of the color tier.
    """
    pills = ""
    if _room_has_monster(room):
        if _room_has_hostile_monster(room):
            pills += (
                '<span class="presence-pill presence-pill-monster" '
                'title="There is an active monster in this room">'
                f'{_ICON_MONSTER}Monster</span>'
            )
        else:
            pills += (
                '<span class="presence-pill presence-pill-encounter" '
                'title="Something is here, but it is not hostile">'
                f'{_ICON_MONSTER}Encounter</span>'
            )
    if _room_has_treasure(room):
        treasure_icon = _room_treasure_icon(room)
        if _room_has_valuable_treasure(room):
            pills += (
                '<span class="presence-pill presence-pill-treasure" '
                'title="There is treasure to collect in this room">'
                f'{treasure_icon}Treasure</span>'
            )
        else:
            pills += (
                '<span class="presence-pill presence-pill-treasure-mundane" '
                'title="There is something to collect in this room, though nothing of real value">'
                f'{treasure_icon}Treasure</span>'
            )
    return pills


def _render_room_card(room, show_rolls=True, show_quality=True, status_note="", status_extra_html="", room_id=None):
    """
    Renders a room's Location/Detail title, how it was determined,
    both descriptions, and (if present) its Encounter/Treasure
    sections - shared by the Location Generator and Crawling Mode's
    current-room card, so both stay visually consistent and any
    future tweak to how a room is presented only needs to happen once.

    Location + Detail are the headline - the two most important facts
    about a room, and the first thing meant to catch the eye - with
    the roll (or "chosen" note) that produced them demoted to a small
    meta-badge underneath, rather than a bare roll number sitting in
    front of the name itself. The monster/treasure presence pills
    (see _render_presence_pills) sit in that same meta-line, and -
    unlike the roll badges - render regardless of `show_rolls`: "is
    there a monster here" is a fact about the room, not a roll detail,
    so it isn't gated behind the same setting that hides dice.

    `show_quality` (see _show_treasure_quality) is forwarded into
    _render_room_treasures/_render_encounter_result independent of
    `show_rolls` - whether a treasure's quality tier is named is its
    own setting, not tied to whether the roll behind it is shown.

    `status_note`, if given (Crawling Mode's "You are here" / "You
    are here (revisited)" / "Viewing only"), is folded into the same
    meta-line as the depth and roll badges, rather than a separate
    line above it. `status_extra_html`, if given, is placed right
    after it - used for the small "Go Here" button that shows up next
    to "Viewing only" when that room happens to be a direct neighbor
    of wherever the party actually is.

    `room_id`, if given (only ever passed from Crawling Mode - see
    _render_crawl_entry_full), is this room's stable id in
    crawl_history and switches the Encounter/Treasure sections into
    "interactive" mode: each monster group / treasure item gets its
    own small "x" to permanently remove it (defeated / collected).
    The Location Generator's own room never gets one - its contents
    aren't part of any persistent, revisitable dungeon, so there's
    nothing meaningful to mutate.
    """
    interactive = room_id is not None
    room_has_hostile_monster = _room_has_hostile_monster(room)

    loc_badge = _render_room_roll_badge("Location", room["location_roll"], room["used_depth"], show_rolls)
    det_badge = _render_room_roll_badge("Detail", room["detail_roll"], room["used_depth"], show_rolls)

    meta_line = f"Depth {room['used_depth']}"
    if status_note:
        meta_line += f" &middot; {status_note}"
    if status_extra_html:
        meta_line += f" {status_extra_html}"
    presence_pills = _render_presence_pills(room)
    if presence_pills:
        meta_line += f" {presence_pills}"
    for badge in (loc_badge, det_badge):
        if badge:
            meta_line += f" {badge}"

    entering_html = ""
    if room.get("entering_encounter"):
        # Bold either way, but only picks up the warning color (and
        # its own small icon) once a genuinely hostile monster is
        # actually here right now - a room with only NON_HOSTILE_
        # MONSTERS present stays plain, same as no encounter at all.
        # See room_has_hostile_monster above and _render_presence_
        # pills' own docstring on why Monster gets this extra weight
        # Treasure doesn't.
        encounter_label = (
            f'<strong class="section-label-danger">{_ICON_MONSTER} Encounter:</strong>'
            if room_has_hostile_monster else '<strong>Encounter:</strong>'
        )
        entering_html = f"""
        <hr>
        {encounter_label}<br>
        {_render_encounter_result(room["entering_encounter"], show_treasure=False, show_rolls=show_rolls, show_quality=show_quality, room_id=room_id, interactive=interactive)}
        """

    treasure_html = ""
    treasures_body = _render_room_treasures(room, show_rolls, show_quality, room_id, interactive)
    if treasures_body:
        treasure_html = f"""
        <hr>
        <strong>Treasure:</strong>
        {treasures_body}
        """

    return f"""
    <div class="room-title">{room['location']} <span class="room-title-sep">&middot;</span> {room['detail']}</div>
    <div class="meta-line">{meta_line}</div>

    <div class="description">{render_md(room['location_text'])}</div>
    <div class="description">{render_md(room['detail_text'])}</div>
    {entering_html}
    {treasure_html}
    """


def _show_roll_details() -> bool:
    """
    The Settings view's global "Show Roll Details" toggle - whether
    roll displays (raw roll, modifier, total, DC, outcome) render at
    all anywhere in the UI, independent of any per-room freshness
    logic. Off by default (see _default_session) - a first-time user
    sees clean "what it produced" results; the raw dice are opt-in.
    Every top-level view reads this once and passes it down as that
    view's own `show_rolls`/`show_roll` argument - the actual hiding
    logic (falling back to a plain "what it produced" summary)
    already exists throughout the rendering functions for the
    Crawling Mode "revisited room" case; this just becomes another,
    global reason for that same fallback to kick in.
    """
    return bool(SESSION.get("show_roll_details", False))


def _show_treasure_quality() -> bool:
    """
    The Settings view's global "Show Treasure Quality" toggle -
    whether a treasure's quality tier name (mundane/minor/moderate/
    valuable/excellent/rare/legendary - see TREASURE_QUALITY_TABLE)
    is shown at all, anywhere in the UI. Off by default (see
    _default_session), same reasoning as _show_roll_details - clean
    results by default, the tier name is opt-in.

    Deliberately independent of _show_roll_details: whether the tier
    name is shown and whether the roll that produced it is shown are
    two separate questions. When this is off, the item count that
    normally accompanies the tier name is dropped along with it (see
    _render_quality_summary's own docstring for why) - the item list
    itself is unaffected either way, only the framing line above it.
    When this is off, _render_quality_roll_line drops the roll
    entirely too (not just the tier name) rather than showing a roll
    with its own outcome blanked out, since the raw number alone
    could still leak the tier to anyone who knows the table.

    Every top-level view reads this once and passes it down as that
    view's own `show_quality` argument, the same way _show_roll_details
    does for `show_rolls`.
    """
    return bool(SESSION.get("show_treasure_quality", False))


def _render_location_view():
    room = SESSION.get("room")
    depth = SESSION.get("depth", 0)
    roll_treasure = SESSION.get("roll_treasure", True)
    roll_encounter = SESSION.get("roll_encounter", True)
    forced_location = SESSION.get("forced_location")
    forced_detail = SESSION.get("forced_detail")
    encounter_dc = SESSION.get("encounter_dc", DEFAULT_ENCOUNTER_DC)
    treasure_dc = SESSION.get("treasure_dc", DEFAULT_TREASURE_DC)

    treasure_checked = "checked" if roll_treasure else ""
    encounter_checked = "checked" if roll_encounter else ""

    location_names = [name for _, name in LOCATIONS]
    detail_names = [name for _, name in DETAILS]

    controls = f"""
    <div class="section">
        <div class="form-row">
            <label for="depth">Depth:</label>
            <input type="number" id="depth" name="depth" value="{depth}">
        </div>
        <div class="form-row">
            <label for="location-select">Location:</label>
            <select id="location-select">
                {_render_choice_options(location_names, forced_location)}
            </select>
            <label for="detail-select">Detail:</label>
            <select id="detail-select">
                {_render_choice_options(detail_names, forced_detail)}
            </select>
        </div>
        <div class="form-row checkbox-row">
            <label>
                <input type="checkbox" id="roll-treasure" {treasure_checked}>
                Roll for Treasure
            </label>
            <label>
                <input type="checkbox" id="roll-encounter" {encounter_checked}>
                Roll for Encounter
            </label>
        </div>
        <div class="form-row">
            <label for="encounter-dc">Encounter DC:</label>
            <input type="number" id="encounter-dc" name="encounter-dc" value="{encounter_dc}">
            <label for="treasure-dc">Treasure DC:</label>
            <input type="number" id="treasure-dc" name="treasure-dc" value="{treasure_dc}">
        </div>
        <button type="button" class="primary-action" onclick="runAction('room')">
            Generate Location
        </button>
    </div>
    """

    if not room:
        return controls + _render_getting_started_placeholder(
            "Press 'Generate Location' to generate a new location."
        )

    return controls + f"""
    <div class="section">
        {_render_room_card(room, show_rolls=_show_roll_details(), show_quality=_show_treasure_quality())}
    </div>
    """


def _render_encounter_view():
    result = SESSION.get("encounter_check")
    roll_treasure = SESSION.get("encounter_roll_treasure", True)
    level = SESSION.get("level")
    forced_monster = SESSION.get("forced_monster")
    encounter_dc = SESSION.get("encounter_dc", DEFAULT_ENCOUNTER_DC)
    treasure_checked = "checked" if roll_treasure else ""

    monster_names = _monsters_in_level_table(level)

    controls = f"""
    <div class="section">
        <div class="form-row">
            <label for="monster-select">Monster:</label>
            <select id="monster-select">
                {_render_choice_options(monster_names, forced_monster)}
            </select>
        </div>
        <div class="form-row checkbox-row">
            <label>
                <input type="checkbox" id="encounter-roll-treasure" {treasure_checked}>
                Roll for Treasure
            </label>
        </div>
        <div class="form-row">
            <label for="encounter-dc">Encounter DC:</label>
            <input type="number" id="encounter-dc" name="encounter-dc" value="{encounter_dc}">
        </div>
        <button type="button" class="primary-action" onclick="runAction('check_encounter')">
            Roll for Encounter
        </button>
        <button type="button" onclick="runAction('generate_encounter')">
            Generate Encounter
        </button>
    </div>
    """

    if not result:
        return controls + _render_getting_started_placeholder(
            "Press 'Roll for Encounter' or 'Generate Encounter' above to get started."
        )

    return controls + f"""
    <div class="section">
        {_render_encounter_result(result, show_rolls=_show_roll_details(), show_quality=_show_treasure_quality())}
    </div>
    """


def _render_treasure_view_result(result, show_rolls=True, show_quality=True):
    """
    Renders the standalone Treasure Generator's current result -
    either a DC-gated "Roll for Treasure" outcome (can fail) or an
    unconditional "Generate Treasure" one (always finds something, no
    DC framing) - mirrors _render_encounter_result's "generated" mode.

    `show_rolls=False` (see _show_roll_details) drops the Quality
    roll's own formula down to the plain "Quality: X, N items"
    summary, same fallback _render_quality_summary already provides
    for a revisited Crawling Mode room - and is threaded into the
    DC-gated branch's own `show_roll` the same way.

    `show_quality` (see _show_treasure_quality) is independent of
    `show_rolls` - threaded into both branches the same way.
    """
    if result.get("mode") == "generated":
        found = result["found_treasure"]
        quality_line = (
            _render_quality_roll_line(found, show_quality=show_quality) if show_rolls
            else _render_quality_summary(found, show_quality=show_quality)
        )
        return _with_optional_lead_line(quality_line, _render_item_list(found["item_list"]))

    return _render_treasure_check_result(
        result, fail_message="Nothing turns up this time.", show_roll=show_rolls, show_quality=show_quality
    )


def _render_treasure_view():
    treasure = SESSION.get("treasure")
    forced_quality = SESSION.get("forced_quality")
    treasure_dc = SESSION.get("treasure_dc", DEFAULT_TREASURE_DC)

    controls = f"""
    <div class="section">
        <div class="form-row">
            <label for="quality-select">Quality:</label>
            <select id="quality-select">
                {_render_choice_options(_treasure_quality_names(), forced_quality)}
            </select>
        </div>
        <div class="form-row">
            <label for="treasure-dc">Treasure DC:</label>
            <input type="number" id="treasure-dc" name="treasure-dc" value="{treasure_dc}">
        </div>
        <button type="button" class="primary-action" onclick="runAction('check_treasure')">
            Roll for Treasure
        </button>
        <button type="button" onclick="runAction('treasure')">
            Generate Treasure
        </button>
    </div>
    """

    if not treasure:
        return controls + _render_getting_started_placeholder(
            "Press 'Roll for Treasure' or 'Generate Treasure' above to get started."
        )

    return controls + f"""
    <div class="section">
        {_render_treasure_view_result(treasure, show_rolls=_show_roll_details(), show_quality=_show_treasure_quality())}
    </div>
    """


def _render_crawl_entry_full(room, is_current_position, is_fresh, extra_buttons_html=""):
    """
    Card for whichever room the Crawling Mode view is currently
    showing:

    - The actual current position: highlighted border, "You are here"
      (or "... (revisited)" if it wasn't just generated), and rolls
      shown only when it's the freshest room in the whole history
      (see _render_crawling_view's is_fresh) AND the global "Show
      Roll Details" setting is on (see _show_roll_details) - either
      one being false hides them.
    - Any other room someone clicked in the Dungeon Map just to look
      at: plain styling, "Viewing only" instead of "You are here", no
      rolls (same as revisiting).

    Treasure quality (see _show_treasure_quality) is NOT tied to
    freshness the way rolls are - it's shown (or not) purely based on
    that global setting, for the current position and any other room
    alike. Unlike a roll, a treasure's quality tier isn't "dice being
    re-litigated" when shown for an older room; it's a static fact
    about what's there, the same as the item list right below it.

    `extra_buttons_html` (e.g. "Go Here" / "Block Entrance") is placed
    right after that status note either way - which buttons actually
    apply (some, like "Go Here", only make sense for a room other
    than the current position) is decided by the caller, not here.
    """
    show_quality = _show_treasure_quality()
    if is_current_position:
        card_class = "crawl-entry-current"
        status_note = "You are here" + ("" if is_fresh else " (revisited)")
        show_rolls = is_fresh and _show_roll_details()
    else:
        card_class = "crawl-entry-viewing"
        status_note = "Viewing only"
        show_rolls = False

    return f"""
    <div class="{card_class}">
        {_render_room_card(room, show_rolls=show_rolls, show_quality=show_quality, status_note=status_note, status_extra_html=extra_buttons_html, room_id=room["id"])}
    </div>
    """


def _room_by_id(history, room_id):
    for room in history:
        if room["id"] == room_id:
            return room
    return None


def _crawl_path_to_current(history, current_id):
    """
    Walks parent_id links from `current_id` back to the root, returning
    the path in root-to-current order (oldest first). This is the
    actual currently-active path through the room "tree" - once
    branching exists (a future "Go Back" followed by "go_deeper" from
    an earlier room), this is what tells apart "the path leading to
    where we are now" from "every room ever generated across every
    branch" (crawl_history, which just keeps growing and is no longer
    usable as a single ordered trail on its own).
    """
    if current_id is None:
        return []
    by_id = {room["id"]: room for room in history}
    path = []
    node_id = current_id
    while node_id is not None:
        room = by_id[node_id]
        path.append(room)
        node_id = room["parent_id"]
    path.reverse()
    return path


def _build_children_map(history):
    """room_id (or None for the root) -> list of that room's direct
    children, so the tree can be walked top-down from the root(s)."""
    children = {}
    for room in history:
        children.setdefault(room["parent_id"], []).append(room)
    return children


def _is_adjacent_room(room_id, current_id, history):
    """
    True if `room_id` is a direct neighbor of the current position -
    its parent, or one of its direct children - AND the connection
    between them hasn't been blocked (see "toggle_connection").

    `current_id` of None means "standing at the Grand Avenue" (see
    _render_dungeon_map's docstring) rather than "no current room" -
    every depth-0 room is a direct neighbor of the Avenue, the same
    way it's a direct neighbor of its own parent, so all of them
    count as adjacent to it. (There's no "connection_blocked" check
    for this case - that flag can only ever be set on a room with a
    parent_id, i.e. never on a root; see "toggle_connection".)

    Determines when the Crawling Mode room card's "Go Here" button
    appears: viewing any room is always fine, but actually moving
    there is only offered (and only allowed, by handle_action's
    "enter_room") when it's a single, passable step away - the same
    reach "Go Back"/"Go Deeper" have, just onto a room that already
    exists.
    """
    if room_id is None:
        return False
    room = _room_by_id(history, room_id)
    if room is None:
        return False
    if current_id is None:
        return room["used_depth"] == 0
    if room_id == current_id:
        return False
    current_room = _room_by_id(history, current_id)
    if current_room is None:
        return False
    if room["parent_id"] == current_id:
        return not room.get("connection_blocked")
    if current_room["parent_id"] == room_id:
        return not current_room.get("connection_blocked")
    return False


_TREE_CHILD_VISIBLE_LIMIT = 4
_TREE_COL_WIDTH = 150
_TREE_ROW_HEIGHT = 64
_TREE_NODE_WIDTH = 132
_TREE_NODE_HEIGHT = 40

# The Grand Avenue - lore-wise (see HANDOFF.md), the long main tunnel
# of a level of The Well, which every depth-0 location branches off
# from and therefore always opens back onto. Purely a map decoration:
# a thin strip added below the shallowest row, with a short stub down
# to it from every depth-0 room. _AVENUE_COLOR is a warm, muted sand
# tone chosen to read as "daylight/the way out" while staying clearly
# distinct from every other color already in the map - the amber
# accent (current/path), the viewed outline's blue, the warning red,
# the full Lift/Secret Passage/Fireplace badge palette, and the
# monster/treasure badge colors (see _render_dungeon_map's docstring
# for the full existing list this was checked against).
_AVENUE_SECTION_HEIGHT = 34
_AVENUE_LINE_GAP = 10
_AVENUE_COLOR = "#c2a878"


def _build_visible_tree(room, children_map, path_ids):
    """
    Builds a plain nested dict {"room", "is_more", "hidden_count",
    "children"} for `room` and its descendants - deciding, up front,
    which children are actually shown. If a room has more than
    _TREE_CHILD_VISIBLE_LIMIT children, the ones NOT on the path to
    the currently active room are collapsed into a single synthetic
    "+N more" leaf (the child that actually leads toward "where we
    are now" is always kept visible, never hidden). Keeping this
    decision separate from the layout math below means the layout
    only ever has to deal with what's actually going to be drawn.
    """
    kids = sorted(children_map.get(room["id"], []), key=lambda r: r["id"])
    node = {"room": room, "is_more": False, "hidden_count": 0, "children": []}

    if kids:
        on_path_kids = [k for k in kids if k["id"] in path_ids]
        other_kids = [k for k in kids if k["id"] not in path_ids]

        if len(kids) > _TREE_CHILD_VISIBLE_LIMIT:
            visible = list(on_path_kids)
            for k in other_kids:
                if len(visible) >= _TREE_CHILD_VISIBLE_LIMIT:
                    break
                visible.append(k)
            visible_ids = {k["id"] for k in visible}
            hidden = [k for k in kids if k["id"] not in visible_ids]
        else:
            visible, hidden = kids, []

        for k in visible:
            node["children"].append(_build_visible_tree(k, children_map, path_ids))

        if hidden:
            node["children"].append({
                "room": None, "is_more": True,
                "hidden_count": len(hidden), "children": [],
                # Synthetic - a placeholder standing in for several
                # hidden rooms (possibly at different actual depths)
                # doesn't have one true used_depth of its own; one
                # step below its parent is a reasonable default for
                # layout purposes only, since it's never meant to be
                # pixel-precise anyway.
                "used_depth": room["used_depth"] + 1,
            })

    return node


def _compute_tree_x(node, slot_counter, x_cache):
    """
    Post-order: assigns every leaf the next free integer "column slot"
    (0, 1, 2, ...), and every internal node the *average* of its
    children's slots - the standard, simple tree-layout algorithm.
    Stores every node's x in `x_cache` (keyed by the node dict's
    identity) and returns it. This is plain arithmetic on integers -
    nothing here depends on how wide any room's name happens to
    render, unlike centering a browser flexbox would.
    """
    if not node["children"]:
        x = float(slot_counter[0])
        slot_counter[0] += 1
    else:
        xs = [_compute_tree_x(c, slot_counter, x_cache) for c in node["children"]]
        x = sum(xs) / len(xs)
    x_cache[id(node)] = x
    return x


def _flatten_tree(node, x_cache, parent_entry, out):
    """
    Pre-order walk producing one flat entry per visible node, each
    carrying its own (x, used_depth) and a reference to its parent's
    entry (or None for a root) - everything _render_dungeon_map needs
    to place a box and draw one line up to its parent.

    Y-position is based on the room's actual used_depth, not how many
    tree-hops it is from the root - a normal "go_deeper" step is
    always exactly 1 used_depth, so ordinary rooms look exactly as
    before, but a Lift/Secret Passage landing several layers away
    visibly stretches the gap instead of looking like just another
    single step.
    """
    used_depth = node["room"]["used_depth"] if node["room"] else node["used_depth"]
    entry = {"node": node, "x": x_cache[id(node)], "used_depth": used_depth, "parent": parent_entry}
    out.append(entry)
    for child in node["children"]:
        _flatten_tree(child, x_cache, entry, out)
    return out


def _render_dungeon_map(history, current_id, viewed_id=None):
    """
    A tree diagram of every room ever generated (across every branch)
    - not just the path to the current one. The room we're at now is
    highlighted; everything on the path leading to it is subtly
    marked too, so the route taken is visible at a glance among
    unrelated branches. Whichever room the card below is currently
    showing (which may or may not be the current position - see
    "view_room") gets its own marker too, so it's clear at a glance
    which box the card corresponds to.

    This can show more than one separate tree at once: a room reached
    via Lift/Secret Passage/Fireplace has no parent_id at all (see
    _create_linked_room), so it starts its own root rather than
    hanging off the room it was reached from - it isn't "connected"
    in the ordinary sense that deserves a connecting line.

    Every box's position is a plain (column, used_depth) pair
    computed in Python (_compute_tree_x / _flatten_tree) and placed
    with an explicit pixel offset - deeper rooms get a smaller pixel
    "row" so they end up higher on the page, and since this is based
    on actual used_depth rather than how many tree-hops from the root
    a room is, a big jump (e.g. a Lift landing 1d6 layers down)
    visibly stretches that gap instead of looking like an ordinary
    single step. Connecting lines are drawn between those exact,
    known coordinates via an SVG overlay. None of this depends on a
    browser auto-centering nested boxes of differing width, which is
    what caused rooms to drift sideways in an earlier version.

    Since used_depth 0 always renders at the bottom row (the smallest
    used_depth gets the largest cy - see `center()` below), a thin
    "Grand Avenue" strip is drawn below that row, with a short stub
    connecting every depth-0 room down to it - see the constants
    above and the block just before the final `return` for how. A
    depth-0 room is always a root (a normal "go_deeper" child's
    used_depth is always its parent's plus one, so it can never be 0
    unless its parent were at depth -1, which never happens), so this
    only ever needs to check `roots`, not every room in the flattened
    tree. Like Fireplace's network, nothing is stored on the room
    dict for this - it's recomputed fresh from used_depth every
    render.
    """
    if not history:
        return ""

    path_ids = {room["id"] for room in _crawl_path_to_current(history, current_id)}
    children_map = _build_children_map(history)
    roots = sorted(children_map.get(None, []), key=lambda r: r["id"])
    if not roots:
        return ""

    # A Lift/Secret Passage/Fireplace landing isn't "connected in the
    # classical sense" (see _create_linked_room) - it gets no
    # parent_id at all, making it a root of its own. So there can be
    # more than one root/tree here now; each gets its own x-slots
    # (via the shared slot_counter, so they land side by side without
    # overlapping columns) with a bit of breathing room between them -
    # less than a full extra column's worth, which read as an
    # oversized gap compared to the normal spacing within one tree.
    slot_counter = [0]
    x_cache = {}
    flat = []
    for root in roots:
        tree = _build_visible_tree(root, children_map, path_ids)
        _compute_tree_x(tree, slot_counter, x_cache)
        _flatten_tree(tree, x_cache, None, flat)
        slot_counter[0] += 0.4

    max_x = max(e["x"] for e in flat)
    max_used_depth = max(e["used_depth"] for e in flat)
    min_used_depth = min(e["used_depth"] for e in flat)

    canvas_width = (max_x + 1) * _TREE_COL_WIDTH
    canvas_height = (max_used_depth - min_used_depth + 1) * _TREE_ROW_HEIGHT

    # See the Grand Avenue paragraph in this function's docstring -
    # every depth-0 root gets a stub down to a shared strip, so extend
    # the canvas by just enough to fit it (only if a depth-0 room is
    # actually present at all - always true for an in-progress crawl,
    # since the very first room generated is always used_depth 0 and
    # is never removed from history, but a defensive check costs
    # nothing).
    depth0_root_ids = {r["id"] for r in roots if r["used_depth"] == 0}
    if depth0_root_ids:
        canvas_height += _AVENUE_SECTION_HEIGHT

    def center(entry):
        cx = entry["x"] * _TREE_COL_WIDTH + _TREE_COL_WIDTH / 2
        # deepest used_depth gets the smallest cy, so it ends up at
        # the top of the canvas - and since this is actual used_depth
        # rather than a tree-hop count, a big jump (e.g. Lift landing
        # 1d6 layers down) stretches this gap proportionally, instead
        # of looking like an ordinary single step.
        cy = (max_used_depth - entry["used_depth"]) * _TREE_ROW_HEIGHT + _TREE_ROW_HEIGHT / 2
        return cx, cy

    special_badges = _compute_special_connection_badges(history)

    # A subtle, straight dashed line directly between two rooms
    # actually linked via Lift/Secret Passage/Fireplace - drawn first
    # (so the normal tree connectors and room boxes paint over it
    # wherever they'd otherwise overlap) and very muted, since it's a
    # bonus visual cue on top of the badges, not the primary way to
    # tell they're connected. Runs from badge center to badge center
    # rather than room center to room center, so it's unambiguous
    # which specific thing the line is about.
    entry_by_room_id = {
        entry["node"]["room"]["id"]: entry
        for entry in flat
        if not entry["node"]["is_more"]
    }

    def _badge_center(room_id):
        entry = entry_by_room_id.get(room_id)
        if entry is None:
            return None  # hidden behind a "+more" right now
        cx, cy = center(entry)
        return cx + _TREE_NODE_WIDTH / 2, cy - _TREE_NODE_HEIGHT / 2

    def _special_line(id_a, id_b):
        a = _badge_center(id_a)
        b = _badge_center(id_b)
        if a is None or b is None:
            return None
        return (
            f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" '
            f'stroke="#555" stroke-width="1.5" stroke-dasharray="4,4" opacity="0.4" />'
        )

    lines = []
    seen_special_pairs = set()
    for room in history:
        if _room_special_connection_kind(room) not in ("lift", "secret_passage"):
            continue
        partner_id = room.get("special_link_id")
        if partner_id is None:
            continue
        pair_key = (min(room["id"], partner_id), max(room["id"], partner_id))
        if pair_key in seen_special_pairs:
            continue
        seen_special_pairs.add(pair_key)
        line = _special_line(room["id"], partner_id)
        if line:
            lines.append(line)

    # Fireplace is a real network, not a fixed pair - every room with
    # this detail connects to every other one, so every pair gets its
    # own line. In practice these networks tend to stay small enough
    # (a handful of rooms at most) that this doesn't turn into visual
    # noise the way it might for a much larger network.
    fireplace_rooms = [r for r in history if r["detail"] == "Fireplace"]
    for i, room_a in enumerate(fireplace_rooms):
        for room_b in fireplace_rooms[i + 1:]:
            line = _special_line(room_a["id"], room_b["id"])
            if line:
                lines.append(line)

    for entry in flat:
        if entry["parent"] is None:
            continue
        cx1, cy1 = center(entry)
        cx2, cy2 = center(entry["parent"])
        # Elbow connector: straight down from the child, a horizontal
        # jog to line up with the parent's column, then straight down
        # into the parent - classic org-chart style, and it stays
        # readable even when child/parent sit in very different
        # columns, unlike a single diagonal line would.
        y_child_bottom = cy1 + _TREE_NODE_HEIGHT / 2
        y_parent_top = cy2 - _TREE_NODE_HEIGHT / 2
        mid_y = (y_child_bottom + y_parent_top) / 2

        # A blocked connection (see "toggle_connection") still shows
        # the line at its normal solid gray - the entrance existed,
        # it's just not usable right now - marked with a small red
        # cross where it crosses the horizontal jog, instead of
        # vanishing and making the room look unreachable from
        # anywhere, or turning the whole line into a busier
        # dashed style.
        child_room = entry["node"].get("room")
        is_blocked = bool(child_room and child_room.get("connection_blocked"))

        lines.append(
            f'<path d="M {cx1:.1f} {y_child_bottom:.1f} '
            f'V {mid_y:.1f} H {cx2:.1f} V {y_parent_top:.1f}" '
            f'fill="none" stroke="#555" stroke-width="2" />'
        )

        if is_blocked:
            mark_x = (cx1 + cx2) / 2
            mark_y = mid_y
            r = 6
            lines.append(
                f'<line x1="{mark_x - r:.1f}" y1="{mark_y - r:.1f}" '
                f'x2="{mark_x + r:.1f}" y2="{mark_y + r:.1f}" '
                f'stroke="#b71c1c" stroke-width="2.5" stroke-linecap="round" />'
                f'<line x1="{mark_x - r:.1f}" y1="{mark_y + r:.1f}" '
                f'x2="{mark_x + r:.1f}" y2="{mark_y - r:.1f}" '
                f'stroke="#b71c1c" stroke-width="2.5" stroke-linecap="round" />'
            )

    # The Grand Avenue strip itself, plus a short stub from every
    # depth-0 room down to it - see this function's docstring. Drawn
    # after the normal parent-child connectors so it doesn't get
    # visually buried under them, but it's a thin, dashed, muted line
    # deliberately kept far enough below the last room row that it
    # can't be mistaken for one.
    avenue_label_html = ""
    if depth0_root_ids:
        depth0_entries = [
            entry for entry in flat
            if not entry["node"]["is_more"] and entry["node"]["room"]["id"] in depth0_root_ids
        ]
        avenue_y = canvas_height - _AVENUE_SECTION_HEIGHT + _AVENUE_LINE_GAP
        xs = [center(entry)[0] for entry in depth0_entries]
        pad = _TREE_NODE_WIDTH / 2 + 12
        avenue_x1 = max(0.0, min(xs) - pad)
        avenue_x2 = min(canvas_width, max(xs) + pad)

        lines.append(
            f'<line x1="{avenue_x1:.1f}" y1="{avenue_y:.1f}" x2="{avenue_x2:.1f}" y2="{avenue_y:.1f}" '
            f'stroke="{_AVENUE_COLOR}" stroke-width="2" stroke-linecap="round" '
            f'stroke-dasharray="1,4" opacity="0.65">'
            f'<title>The Grand Avenue - the main tunnel of this level, and a way out of the dungeon.</title>'
            f'</line>'
        )
        for entry in depth0_entries:
            cx, cy = center(entry)
            y_box_bottom = cy + _TREE_NODE_HEIGHT / 2
            lines.append(
                f'<line x1="{cx:.1f}" y1="{y_box_bottom:.1f}" x2="{cx:.1f}" y2="{avenue_y:.1f}" '
                f'stroke="{_AVENUE_COLOR}" stroke-width="1.5" stroke-dasharray="1,3" opacity="0.55">'
                f'<title>Opens onto the Grand Avenue - a way out of the dungeon.</title>'
                f'</line>'
            )

        label_cx = (avenue_x1 + avenue_x2) / 2
        avenue_label_html = (
            f'<div class="dtree-avenue-label" style="left:{label_cx:.1f}px; top:{avenue_y + 6:.1f}px;" '
            f'title="The main tunnel of this level of The Well - every depth 0 location opens onto it.">'
            f'Grand Avenue</div>'
        )

    boxes = []
    badges_html = []
    for entry in flat:
        cx, cy = center(entry)
        left = cx - _TREE_NODE_WIDTH / 2
        top = cy - _TREE_NODE_HEIGHT / 2
        node = entry["node"]
        box_style = (
            f"left:{left:.1f}px; top:{top:.1f}px; "
            f"width:{_TREE_NODE_WIDTH}px; min-height:{_TREE_NODE_HEIGHT}px;"
        )

        if node["is_more"]:
            boxes.append(
                f'<div class="dtree-node dtree-node-more" style="{box_style}">'
                f'+{node["hidden_count"]} more</div>'
            )
            continue

        room = node["room"]
        cls = "dtree-node dtree-node-clickable"
        room_id = room["id"]
        if room["id"] == current_id:
            # Always clickable too - if some other room is currently
            # being viewed, this is how the view snaps back to the
            # actual current position.
            cls += " dtree-node-current"
            attrs = (
                f' onclick="viewRoom({room_id})" '
                f'title="View current room" role="button" tabindex="0"'
            )
        else:
            # Every room other than the current one is viewable -
            # click it to show its card below (without moving there;
            # see _render_crawling_view / "view_room"). The
            # highlighting itself (path vs. an unrelated branch)
            # stays exactly as before - this only adds the ability to
            # click, on top of whichever style already applies.
            if room["id"] in path_ids:
                cls += " dtree-node-path"
            attrs = (
                f' onclick="viewRoom({room_id})" '
                f'title="View this room" role="button" tabindex="0"'
            )

        if room["id"] == viewed_id:
            # Whichever room the card below is actually showing right
            # now - separate from "current" (where the party is) and
            # "path" (how we got there), since viewing a room never
            # moves anyone; this can be any of the three at once (e.g.
            # the current room is, by default, also the viewed one).
            cls += " dtree-node-viewed"

        badge = special_badges.get(room["id"])
        if badge:
            # Positioned on the canvas itself at the box's top-right
            # corner, like the connector lines - not nested inside
            # the room's own box, since that box clips overflowing
            # content (for its text truncation) and would otherwise
            # cut the badge off wherever it pokes past the edge.
            badge_cx = cx + _TREE_NODE_WIDTH / 2
            badge_cy = cy - _TREE_NODE_HEIGHT / 2
            if badge["partner_id"] is not None:
                badge_cls = "dtree-badge dtree-badge-clickable"
                badge_attrs = f' onclick="viewRoom({badge["partner_id"]})"'
                badge_title = f'Linked via {room["detail"]} - click to view'
            else:
                badge_cls = "dtree-badge"
                badge_attrs = ""
                badge_title = f'{room["detail"]} - not yet connected to anything'

            if badge["number"]:
                # Wide "pill" so the icon and its pairing number both
                # fit - a plain circle would be too cramped for two
                # things side by side.
                badge_width = 28
                badge_content = f'{badge["icon"]}<span class="dtree-badge-number">{badge["number"]}</span>'
            else:
                badge_width = 20
                badge_content = badge["icon"]

            badges_html.append(
                f'<span class="{badge_cls}" '
                f'style="left:{badge_cx - badge_width / 2:.1f}px; top:{badge_cy - 10:.1f}px; '
                f'width:{badge_width}px; '
                f'background:{badge["bg"]}; color:{badge["fg"]};"{badge_attrs} '
                f'title="{badge_title}">{badge_content}</span>'
            )

        # Monster/treasure markers share a single corner (bottom-left)
        # instead of one each on bottom-left/top-left. Reason: with
        # only two occupied corners total per box - top-right for the
        # special-connection badge, bottom-left for these - adjacent
        # rooms never have occupied corners facing each other, whether
        # they're side-by-side siblings (left room's right edge meets
        # right room's left edge: top-right vs top-left-which-is-now-
        # empty, bottom-right-which-is-empty vs bottom-left) or
        # parent/child stacked in the same column (bottom edge meets
        # top edge: same logic). That's what actually caused the
        # crowding this replaced - two badges sitting right on facing
        # corners of neighboring boxes, closer together than the
        # (deliberately tight, since dungeons can get large) gap
        # between boxes. Moving both to one corner fixes that
        # structurally instead of just shrinking badges or widening
        # gaps.
        #
        # When a room has both, they overlap slightly rather than
        # stacking cleanly above/below one another - monster in front
        # (written last, so it paints on top at equal z-index),
        # treasure peeking out behind it: you deal with the monster
        # before you get to loot the room. The offset is horizontal
        # only - purely sideways, not upward - so treasure stays at
        # the same height as monster (the box's actual bottom edge)
        # instead of drifting up into the box interior, where it
        # would sit closer to (and partially cover) the room's own
        # location/detail text.
        #
        # A room not yet ransacked gets a distinct, more subdued grey
        # "?" here instead - same slot, same offset-when-a-monster's-
        # -also-present logic, just never both at once: either the
        # real treasure marker (searched) or the "?" (not searched
        # yet), never neither-nor-both. Shown regardless of whether
        # anything was actually rolled up for this room - a marker
        # that only appeared for rooms that actually have treasure
        # would spoil the search before it happens, same reasoning as
        # _room_treasure_pending_search's docstring.
        has_monster = _room_has_monster(room)
        has_hostile_monster = _room_has_hostile_monster(room)
        has_treasure = _room_has_treasure(room)
        has_valuable_treasure = _room_has_valuable_treasure(room)
        pending_search = _room_treasure_pending_search(room)
        anchor_cx = cx - _TREE_NODE_WIDTH / 2
        anchor_cy = cy + _TREE_NODE_HEIGHT / 2

        if has_treasure or pending_search:
            if has_monster:
                treasure_cx, treasure_cy = anchor_cx + 8, anchor_cy
            else:
                treasure_cx, treasure_cy = anchor_cx, anchor_cy
            if has_treasure:
                # Muted variant once everything visible here is
                # "mundane"-quality junk (or a Safe's own failure
                # consolation) - see _room_has_valuable_treasure's
                # docstring. Still a real marker, not the "?" below -
                # there IS something to pick up, it's just not the
                # exciting kind. Icon shape itself can vary by context
                # too (gem/crate instead of the default chest - see
                # _room_treasure_icon), independent of this color tier.
                treasure_class = "dtree-badge-treasure" if has_valuable_treasure else "dtree-badge-treasure-mundane"
                treasure_title = (
                    "There's treasure here" if has_valuable_treasure
                    else "There's something here, though nothing of real value"
                )
                badges_html.append(
                    f'<span class="dtree-badge {treasure_class}" '
                    f'style="left:{treasure_cx - 10:.1f}px; top:{treasure_cy - 10:.1f}px; width:20px;" '
                    f'title="{treasure_title}">{_room_treasure_icon(room)}</span>'
                )
            else:
                badges_html.append(
                    f'<span class="dtree-badge dtree-badge-treasure-unknown" '
                    f'style="left:{treasure_cx - 10:.1f}px; top:{treasure_cy - 10:.1f}px; width:20px;" '
                    f'title="This room has not been searched yet">?</span>'
                )

        if has_monster:
            # Calmer variant when nothing hostile is actually present
            # (only NON_HOSTILE_MONSTERS - see _room_has_hostile_
            # monster's own docstring) - still flags "something is
            # here", just not as a warning.
            monster_class = "dtree-badge-monster" if has_hostile_monster else "dtree-badge-monster-calm"
            monster_title = (
                "There's a monster here" if has_hostile_monster
                else "Something is here, but it is not hostile"
            )
            badges_html.append(
                f'<span class="dtree-badge {monster_class}" '
                f'style="left:{anchor_cx - 10:.1f}px; top:{anchor_cy - 10:.1f}px; width:20px;" '
                f'title="{monster_title}">{_ICON_MONSTER}</span>'
            )

        boxes.append(
            f'<div class="{cls}" style="{box_style}"{attrs}>'
            f'{room["location"]}<br><small>{room["detail"]}</small></div>'
        )

    return f"""
    <div class="section">
        <strong>Dungeon Map</strong>
        <div class="dtree-wrapper">
            <div class="dtree-canvas" style="width:{canvas_width:.0f}px; height:{canvas_height:.0f}px;">
                <svg class="dtree-lines" viewBox="0 0 {canvas_width:.0f} {canvas_height:.0f}"
                     width="{canvas_width:.0f}" height="{canvas_height:.0f}">
                    {''.join(lines)}
                </svg>
                {''.join(boxes)}
                {''.join(badges_html)}
                {avenue_label_html}
            </div>
        </div>
    </div>
    """


def _render_room_option_list(rooms):
    """<option> tags for a "pick a destination room" dropdown - used
    by Secret Passage's (2+ existing shallower rooms) and Fireplace's
    (2+ existing fireplace rooms) destination pickers."""
    return "".join(
        f'<option value="{r["id"]}">{r["location"]} \u00b7 {r["detail"]} (Depth {r["used_depth"]})</option>'
        for r in sorted(rooms, key=lambda r: r["id"])
    )


def _render_special_connection_controls(room, history):
    """
    "Use Lift" / "Use Secret Passage" / "Use Fireplace" - only ever
    called for the room the party is actually standing in (see
    _render_crawling_view). Fireplace is the only one of the three
    that can still need a destination picked from more than one
    candidate before it can be used at all - in that case, a small
    inline dropdown accompanies the button instead of it working on
    its own. Lift and Secret Passage never need this: which existing
    room (if any) they connect to is fully automatic (see
    _find_special_link_match) - shallowest match preferred, deepest
    one only if no shallower match exists - no choice involved - so
    their own buttons always work on their own.
    """
    kind = _room_special_connection_kind(room)
    if kind is None:
        return ""

    if kind == "lift":
        return (
            '<button type="button" class="go-here-button" '
            f'onclick="runAction(\'use_lift\')">{_time_cost_icon_html()}Use Lift</button>'
        )

    if kind == "secret_passage":
        return (
            '<button type="button" class="go-here-button" '
            f'onclick="runAction(\'use_secret_passage\')">{_time_cost_icon_html()}Use Secret Passage</button>'
        )

    if kind == "fireplace":
        candidates = [r for r in history if r["detail"] == "Fireplace" and r["id"] != room["id"]]
        if len(candidates) > 1:
            return (
                '<select id="fireplace-select">'
                f'{_render_room_option_list(candidates)}'
                '</select>'
                '<button type="button" class="go-here-button" '
                f'onclick="useFireplace()">{_time_cost_icon_html()}Use Fireplace</button>'
            )
        return (
            '<button type="button" class="go-here-button" '
            f'onclick="runAction(\'use_fireplace\')">{_time_cost_icon_html()}Use Fireplace</button>'
        )

    return ""


def _render_light_gauges():
    """
    The optional torch/lantern timer (see LIGHT_SOURCES) - one small
    row per *individually* tracked source (track_light is a
    per-source dict, e.g. {"torch": True, "lantern": False} - see
    handle_action's track_torch_form/track_lantern_form): its own
    icon (recolored by state), a depleting bar, and a "Light Torch"/
    "Refuel Lantern" button that resets it back to full. A source
    with tracking off contributes no row at all, not a disabled/
    empty one - and if nothing at all is tracked, this returns ""
    outright rather than an empty wrapper div.

    Three visual states, purely informational - no action in this app
    is ever blocked by running low or hitting zero (see handle_action's
    "refuel_light" and _advance_crawl_clock: nothing reads these
    numbers except this function itself):
    - normal (>20% remaining): the accent-ish warm tone every other
      "this is fine" indicator in the app already uses.
    - low (1-20%): shifts to an amber/orange warning tone - a calmer
      heads-up, nothing urgent yet.
    - out (0%, including "never lit yet" - both look the same, there's
      nothing to distinguish them by): a dim, muted icon plus a slow,
      gentle pulse on the bar - noticeable without being jarring or
      demanding immediate action (see the "soft warning only, no
      blocking" scope this was deliberately kept to).
    """
    track_light = SESSION.get("track_light") or {}
    remaining = SESSION.get("light_remaining_minutes") or {}
    full = SESSION.get("light_burn_minutes") or {}

    rows = []
    for key, cfg in LIGHT_SOURCES.items():
        if not track_light.get(key):
            continue

        rem = remaining.get(key, 0)
        cap = full.get(key, cfg["default_burn_minutes"])
        pct = max(0, min(100, round(rem / cap * 100))) if cap else 0

        if rem <= 0:
            state = "out"
        elif pct <= 20:
            state = "low"
        else:
            state = "normal"

        tooltip = f"{cfg['label']}: {_pluralize(rem, 'minute')} left of {_pluralize(cap, 'minute')}"
        rows.append(f"""
        <div class="light-gauge-row light-gauge-{state}">
            <span class="light-gauge-icon" title="{tooltip}">{cfg['icon']}</span>
            <div class="light-gauge-bar" title="{tooltip}">
                <div class="light-gauge-fill" style="width:{pct}%"></div>
            </div>
            <button type="button" class="go-here-button light-gauge-refuel"
                    onclick="refuelLight('{key}')">{cfg['refuel_label']}</button>
        </div>
        """)

    if not rows:
        return ""
    return f'<div class="light-gauges">{"".join(rows)}</div>'


def _render_crawling_view():
    history = SESSION.get("crawl_history", [])
    current_id = SESSION.get("crawl_current_id")

    current_room = _room_by_id(history, current_id)

    # "Go Back" steps up to whatever the current room opens onto: its
    # parent for a normal room (unchanged) - or, since every depth-0
    # room is a root that opens directly onto the Grand Avenue (see
    # _render_dungeon_map's docstring), the Avenue itself for one of
    # those. Standing at the Avenue already (current_room is None)
    # has nothing further back to go to - same as the very first room
    # used to be, before the Avenue exted this far back. A root NOT
    # at depth 0 (a Lift/Secret Passage landing elsewhere) isn't
    # connected to the Avenue either - it's just floating on its own.
    entrance_blocked = bool(current_room and current_room.get("connection_blocked"))
    if current_room is None:
        can_go_back = False
        go_back_title = "You're already at the Grand Avenue"
    elif current_room["parent_id"] is not None:
        can_go_back = not entrance_blocked
        go_back_title = (
            "The entrance to this room is blocked - you can't go back this way"
            if entrance_blocked else "Go back to the previous room"
        )
    elif current_room["used_depth"] == 0:
        can_go_back = True
        go_back_title = "Go back to the Grand Avenue"
    else:
        can_go_back = False
        go_back_title = "No previous room to go back to"
    go_back_disabled = "" if can_go_back else "disabled"

    blocks_deeper = _room_blocks_deeper(current_room)
    go_deeper_disabled = "disabled" if blocks_deeper else ""
    if blocks_deeper:
        go_deeper_title = "This is a dead end - there's no way to go deeper from here"
    elif current_room is None:
        go_deeper_title = "Dig a new entrance into the dungeon from the Grand Avenue"
    else:
        go_deeper_title = "Descend to a new location"

    round_length_minutes = SESSION.get("round_length_minutes", DEFAULT_ROUND_LENGTH_MINUTES)
    elapsed_minutes = SESSION.get("crawl_elapsed_minutes", 0)
    position_note = (
        "You are at the Grand Avenue" if current_room is None
        else f"You are at Depth {current_room['used_depth']}"
    )

    controls = f"""
    <div class="section">
        <div class="meta-line position-line">{position_note}</div>
        <div class="meta-line elapsed-time-line">{_time_cost_icon_html()}{_format_elapsed_time(elapsed_minutes)} elapsed</div>
        {_render_light_gauges()}
        <div class="button-row">
            <button type="button" {go_back_disabled} title="{go_back_title}" onclick="runAction('go_back')">
                {_time_cost_icon_html(large=True)}Go Back
            </button>
            <button type="button" title="Wait one round ({_pluralize(round_length_minutes, 'minute')}) without moving" onclick="runAction('stay')">
                {_time_cost_icon_html(large=True)}Stay
            </button>
            <button type="button" class="primary-action" {go_deeper_disabled} title="{go_deeper_title}" onclick="runAction('go_deeper')">
                {_time_cost_icon_html(large=True)}Go Deeper
            </button>
        </div>
    </div>
    """

    if not history:
        # A genuinely fresh session - nothing generated at all yet,
        # not even a first entrance. Still the Grand Avenue (there's
        # nowhere else to start from - see the docstring on
        # _render_dungeon_map), just with no dungeon behind it yet to
        # show a map of, and no existing entrance to offer stepping
        # back into - see the "with history" wording just below,
        # which this is deliberately kept in the same voice as.
        return controls + (
            '<div class="section">'
            "<em>You're standing on the Grand Avenue. Press 'Go Deeper' to dig "
            "your first entrance into the dungeon.</em>"
            "</div>"
        )

    # Whichever room was last clicked in the Dungeon Map (or the
    # current room itself, if nothing was clicked / after moving -
    # see handle_action resetting crawl_viewed_id on every move).
    # While standing at the Avenue (current_room is None) with
    # nothing clicked yet, there's no sensible room to default to, so
    # `viewed_room` stays None and no card is shown - just the map.
    viewed_id = SESSION.get("crawl_viewed_id")
    if viewed_id is None:
        viewed_id = current_id
    viewed_room = _room_by_id(history, viewed_id) or current_room

    avenue_note_html = ""
    if current_room is None:
        avenue_note_html = (
            '<div class="section">'
            "<em>You're standing on the Grand Avenue. Press 'Go Deeper' to dig a "
            "new entrance into the dungeon, or pick an existing depth 0 location "
            "on the map below to step back into it.</em>"
            "</div>"
        )

    room_card_html = ""
    if viewed_room is not None:
        is_current_position = viewed_room["id"] == current_id

        # A room is "fresh" (just generated, rolls still shown) only
        # if it's the most recently created room across the whole
        # history - i.e. nothing has been generated after it yet.
        # Revisiting it later via "Go Back" naturally makes it
        # non-fresh, and going deeper again from it (a new branch, or
        # a new entrance from the Avenue) creates a new room that
        # takes over as the fresh one. Only actually read by
        # _render_crawl_entry_full when is_current_position is True -
        # see that function's own docstring - so it doesn't matter
        # which room this is computed against otherwise.
        is_fresh = viewed_room["id"] == len(history) - 1

        go_here_html = ""
        if not is_current_position and _is_adjacent_room(viewed_room["id"], current_id, history):
            go_here_html = (
                f'<button type="button" class="go-here-button" '
                f'onclick="enterRoom({viewed_room["id"]})">{_time_cost_icon_html()}Go Here</button>'
            )

        toggle_connection_html = ""
        if viewed_room["parent_id"] is not None:
            # Available on any room with a parent - including the
            # current position itself (e.g. blocking your own way
            # back), not just while merely viewing some other room.
            # A root (parent_id None) has no toggle at all - its only
            # connection is either to nothing, or to the Grand
            # Avenue, and that one isn't blockable (yet). Free - no
            # time-cost icon - this is bookkeeping, not an action the
            # party actually takes in the fiction.
            toggle_label = "Unblock Entrance" if viewed_room.get("connection_blocked") else "Block Entrance"
            toggle_connection_html = (
                f'<button type="button" class="go-here-button" '
                f'onclick="toggleConnection({viewed_room["id"]})">{toggle_label}</button>'
            )

        # Lift / Secret Passage / Fireplace - only usable while
        # actually standing in the room (the backend action reads
        # crawl_current_id, not whatever's merely being viewed),
        # never while just looking at one via the Dungeon Map (and
        # never while standing at the Avenue, since is_current_position
        # is always False there - current_id is None, and no room's
        # id ever equals that).
        special_connection_html = ""
        if is_current_position:
            special_connection_html = _render_special_connection_controls(viewed_room, history)

        # Time-costing buttons (Go Here, Use Lift/Secret Passage/
        # Fireplace) grouped together first, with the free one (Block/
        # Unblock Entrance) set off after a small divider - see
        # .button-time-icon/.button-group-divider in style.css. Only
        # adds the divider when there's actually something to divide.
        cost_buttons_html = go_here_html + special_connection_html
        extra_buttons_html = cost_buttons_html
        if toggle_connection_html:
            if cost_buttons_html:
                extra_buttons_html += '<span class="button-group-divider">&middot;</span>'
            extra_buttons_html += toggle_connection_html

        room_card_html = f"""
        <div class="section">
            <div class="crawl-history">
                {_render_crawl_entry_full(
                    viewed_room, is_current_position, is_fresh,
                    extra_buttons_html,
                )}
            </div>
        </div>
        """

    viewed_id_for_map = viewed_room["id"] if viewed_room is not None else None
    return (
        controls + avenue_note_html + room_card_html
        + _render_dungeon_map(history, current_id, viewed_id_for_map)
    )


# ----------------------------
# HEADER / SIDEBAR NAVIGATION
# ----------------------------

def _render_settings_view():
    """
    Global, cross-view settings: the two "Default ... DC" fields (see
    roll_location_treasure/roll_random_encounter's own `default_dc`
    parameter - what the shared treasure_dc/encounter_dc pools reset
    to on a success), "Show Roll Details" (see _show_roll_details -
    whether roll displays render at all anywhere in the UI, or
    collapse to their plain "what it produced" form), "Show Treasure
    Quality" (see _show_treasure_quality - whether a treasure's
    quality tier name is shown at all, independent of the
    roll-details setting), "Crawling Round Length" (how many minutes
    each round of Crawling Mode advances the clock by - see
    crawl_elapsed_minutes), and "Track Torch"/"Track Lantern" (see
    LIGHT_SOURCES - two independent toggles, not one master switch,
    for the optional torch/lantern timer - each has its own burn-time
    field, only shown once that source's own toggle is on).
    Explanations live in each field's own `title` tooltip rather than
    a permanent line of text underneath, to keep this view scannable
    as more settings get added here.

    All of these take effect immediately, same as every other input
    in this app - no separate "Save" step. Unlike the DC/round-length/
    burn-time fields (only read the next time some other action fires
    - nothing watches them), the checkboxes have their own onchange
    so toggling one alone re-renders the page right away, the same
    way the Level dropdown's onLevelChange() does - the whole point of
    a display/feature toggle like these is to see its effect
    immediately, not on the next unrelated click. That's also why a
    source's burn-time field only appears once *that* source's own
    "Track ..." checkbox is checked: it'd otherwise be a dead,
    meaningless input for a feature that isn't even on.

    "Reset to Defaults" (the "reset_settings" action) restores every
    field on this page - all Settings-view fields, and only those -
    to its original hardcoded default. Deliberately narrower than the
    "reset" action Crawling Mode uses, which wipes the entire
    in-progress dungeon: settings are meant to persist across that
    kind of reset, not be reset by it - and light already burned
    (light_remaining_minutes) is dungeon state, not a setting, so it
    isn't touched here either, the same as crawl_elapsed_minutes.
    """
    default_encounter_dc = SESSION.get("default_encounter_dc", DEFAULT_ENCOUNTER_DC)
    default_treasure_dc = SESSION.get("default_treasure_dc", DEFAULT_TREASURE_DC)
    round_length_minutes = SESSION.get("round_length_minutes", DEFAULT_ROUND_LENGTH_MINUTES)
    show_roll_details_checked = "checked" if _show_roll_details() else ""
    show_treasure_quality_checked = "checked" if _show_treasure_quality() else ""
    track_light = SESSION.get("track_light") or {key: False for key in LIGHT_SOURCES}
    track_torch_checked = "checked" if track_light.get("torch") else ""
    track_lantern_checked = "checked" if track_light.get("lantern") else ""
    light_burn_minutes = SESSION.get("light_burn_minutes") or {
        key: cfg["default_burn_minutes"] for key, cfg in LIGHT_SOURCES.items()
    }

    # Each source's burn-time field only appears once that source's
    # own toggle is on - independent of the other one, unlike the
    # single shared "if track_light:" this used to be (see this
    # function's own docstring on why there are two switches now, not
    # one). "torch"/"lantern" are still explicit rather than a loop
    # over LIGHT_SOURCES, same reasoning as before: only these two
    # have their own wired-up handle_action parameter and DOM id.
    torch_burn_field_html = ""
    if track_light.get("torch"):
        torch_burn_field_html = f"""
        <div class="form-row">
            <label for="torch-burn-minutes" title="How many minutes a freshly-lit torch lasts.">
                Torch Burn Time (minutes):
            </label>
            <input type="number" id="torch-burn-minutes" name="torch-burn-minutes"
                   value="{light_burn_minutes.get('torch', LIGHT_SOURCES['torch']['default_burn_minutes'])}">
        </div>
        """

    lantern_burn_field_html = ""
    if track_light.get("lantern"):
        lantern_burn_field_html = f"""
        <div class="form-row">
            <label for="lantern-burn-minutes" title="How many minutes a freshly-refueled lantern lasts.">
                Lantern Burn Time (minutes):
            </label>
            <input type="number" id="lantern-burn-minutes" name="lantern-burn-minutes"
                   value="{light_burn_minutes.get('lantern', LIGHT_SOURCES['lantern']['default_burn_minutes'])}">
        </div>
        """

    return f"""
    <div class="section">
        <div class="form-row">
            <label for="default-encounter-dc" title="What the Encounter DC pool resets to after a success.">
                Default Encounter DC:
            </label>
            <input type="number" id="default-encounter-dc" name="default-encounter-dc"
                   value="{default_encounter_dc}">
        </div>
        <div class="form-row">
            <label for="default-treasure-dc" title="What the Treasure DC pool resets to after a success.">
                Default Treasure DC:
            </label>
            <input type="number" id="default-treasure-dc" name="default-treasure-dc"
                   value="{default_treasure_dc}">
        </div>
        <div class="form-row">
            <label for="round-length-minutes" title="How many minutes one round of Crawling Mode advances the clock by - moving, waiting (Stay), or searching a room (Ransack Room) all count as a round.">
                Crawling Round Length (minutes):
            </label>
            <input type="number" id="round-length-minutes" name="round-length-minutes"
                   value="{round_length_minutes}">
        </div>
        <div class="form-row checkbox-row">
            <label title="When off, rolled numbers, modifiers, and DC comparisons are hidden throughout the app - only what they produced is still shown.">
                <input type="checkbox" id="show-roll-details" {show_roll_details_checked}
                       onchange="onSettingsChange()">
                Show Roll Details
            </label>
        </div>
        <div class="form-row checkbox-row">
            <label title="When off, a treasure's quality tier (mundane, minor, moderate, valuable, excellent, rare, legendary) and its item count are hidden - only the items themselves are still shown.">
                <input type="checkbox" id="show-treasure-quality" {show_treasure_quality_checked}
                       onchange="onSettingsChange()">
                Show Treasure Quality
            </label>
        </div>
        <div class="form-row checkbox-row">
            <label title="Optional torch timer in Crawling Mode - purely informational, never blocks anything, just a quiet visual reminder of how much torchlight you have left.">
                <input type="checkbox" id="track-torch" {track_torch_checked}
                       onchange="onSettingsChange()">
                Track Torch
            </label>
        </div>
        {torch_burn_field_html}
        <div class="form-row checkbox-row">
            <label title="Optional lantern timer in Crawling Mode - purely informational, never blocks anything, just a quiet visual reminder of how much lantern oil you have left.">
                <input type="checkbox" id="track-lantern" {track_lantern_checked}
                       onchange="onSettingsChange()">
                Track Lantern
            </label>
        </div>
        {lantern_burn_field_html}
        <button type="button" title="Restores every setting above to its original default."
                onclick="runAction('reset_settings')">
            Reset to Defaults
        </button>
    </div>
    """


_VIEWS = [
    ("crawling", "Crawling Mode"),
    ("location", "Location Generator"),
    ("encounter", "Encounter Generator"),
    ("treasure", "Treasure Generator"),
    ("settings", "Settings"),
]


def _render_header():
    level = SESSION.get("level")
    level_modifiers = SESSION.get("level_modifiers", {})

    modifier_badges = _render_meta_badges(level_modifiers)
    modifiers_text = modifier_badges or "<em>none</em>"

    return f"""
    <div class="header-row">
        <label for="level">Level:</label>
        <select name="level" id="level" onchange="onLevelChange()">
            {_render_level_options(level)}
        </select>
    </div>
    <div class="meta-line">Modifiers: {modifiers_text}</div>
    """


def _render_sidebar():
    active_view = SESSION.get("active_view", "crawling")
    links = []
    for view_id, label in _VIEWS:
        cls = "sidebar-link active" if view_id == active_view else "sidebar-link"
        links.append(
            f'<button type="button" class="{cls}" '
            f'onclick="switchView(\'{view_id}\')">{label}</button>'
        )

    return f"""
    <div id="sidebar-backdrop" class="sidebar-backdrop" onclick="closeSidebar()"></div>
    <nav id="sidebar" class="sidebar">
        {''.join(links)}
    </nav>
    """


_VIEW_RENDERERS = {
    "location": _render_location_view,
    "encounter": _render_encounter_view,
    "treasure": _render_treasure_view,
    "crawling": _render_crawling_view,
    "settings": _render_settings_view,
}


def render_page():
    """Builds the full inner HTML for the #app container, based on
    the current SESSION state. Only one view's content is rendered at
    a time (see SESSION["active_view"]); the header/sidebar are always
    shown regardless of which view is active."""

    active_view = SESSION.get("active_view", "crawling")
    view_fn = _VIEW_RENDERERS.get(active_view, _render_crawling_view)

    return _render_sidebar() + _render_header() + view_fn()
