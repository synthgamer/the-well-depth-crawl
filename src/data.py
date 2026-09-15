# ----------------------------
# LEVELS (of the Well)
# ----------------------------

LEVEL_MODIFIERS = {
    1: {"wealth": -1, "population": 0},
    2: {"wealth": 0, "population": 0, "awareness": -1, "navigation": -1},
    3: {"wealth": +1, "population": +1, "awareness": +1},
    4: {"wealth": +1, "population": 0},
    5: {"wealth": +1, "population": 0},
    6: {"wealth": +2, "population": +2},
    7: {"wealth": +1, "population": +2, "awareness": -1},
    8: {"wealth": 0, "population": 0, "navigation": -2},
    9: {"wealth": +1, "population": +1},
    10: {"wealth": +1, "population": +1, "awareness": -1},
    11: {"wealth": +3, "population": 0, "navigation": +2},
    12: {"wealth": 0, "population": +3},
}

# ----------------------------
# RANDOM ENCOUNTERS
# ----------------------------
#
# Each level (1-12) has its own encounter table with 3 rows of 6
# entries each (18 cells total). It's rolled with 2d6, but *not*
# added together - one die picks the row, the other picks the column:
#
#   - "row die"    1-2 -> row 1
#                  3-4 -> row 2
#                  5-6 -> row 3
#   - "column die" 1-6 -> that column within the chosen row
#
# A table is written as a list of 3 rows, each row a list of exactly
# 6 entries (row index 0 = row 1, column index 0 = column die "1",
# and so on). Every entry is either:
#
#   - encounter("Monster Name")        one group of that monster
#   - encounter("Monster Name", x=3)   roll that monster's own number
#                                       formula 3 separate times and
#                                       sum the results for the total
#   - NEXT_LEVEL                        instead of a monster, reroll
#                                       2d6 on the *next higher*
#                                       level's table (this can chain
#                                       through several levels; the
#                                       level 12 table must never use
#                                       this, since there's no level 13
#                                       to cascade to)
#   - ROLL_TWICE                        reroll 2d6 on this *same*
#                                       level's table twice, and
#                                       combine both results (you get
#                                       two monster groups at once -
#                                       possibly the same monster
#                                       twice, or two different ones).
#                                       Each of those two rolls can
#                                       itself be NEXT_LEVEL or even
#                                       another ROLL_TWICE. Unlike
#                                       NEXT_LEVEL, this is allowed on
#                                       level 12 too, since it doesn't
#                                       need a higher level to exist.
#
# Each monster has its own "number formula" (in MONSTERS below)
# describing how many show up in a single group. Formulas are plain
# strings, parsed by `roll_monster_count()` in game.py:
#
#   "1"                   always exactly 1
#   "1d6"                 roll 1d6
#   "3-5"                 a uniformly random whole number from 3 to 5
#   "3-5 + half-level"    as above, plus half the current dungeon
#                         level, rounded down (level 3 -> +1)
#   "1d4 + level"         1d4 plus the current dungeon level
#
# Terms are combined with " + " / " - " (the spaces matter - they are
# what tells "3-5" the range apart from "5 - 2" the subtraction).

NEXT_LEVEL = "next_level"
ROLL_TWICE = "roll_twice"


def encounter(monster: str, x: int = 1) -> dict:
    """Builds a single monster-encounter table entry for ENCOUNTER_TABLES."""
    return {"type": "monster", "monster": monster, "multiplier": x}


MONSTERS = {
    # name: number formula
    "Exiles": "2-12",
    "Gravediggers": "2-5",
    "Simple Dead": "3-5 + half-level",
    "Revenants": "1-3 + half-level",
    "Critters": "1",
    "Rot Swarm": "1",
    "Bonebats": "2-12 + half-level",
    "Tombhounds": "1-3 + half-level",
    "Small Spiders": "3-8 + half-level",
    "Serpents": "1-6 + half-level",
    "Tangles": "2-4 + half-level",
    "Toothswarm": "1",
    "Large Spiders": "3-4 + half-level",
    "Plagueborn": "1-3 + half-level",
    "Rot King": "1 + half-level",
    "Golem": "1",
    "Infected Revenants": "1-3 + half-level",
    "Infected Tombhounds": "1-3 + half-level",
    "Infected Tangles": "2-4 + half-level",
    "Gloomwright": "1",
    "Ash Ghost": "1",
    "Too Big Spiders": "1-2",
    "Ash Squall": "1",
    "THE TANGLED": "1",
    "Ash Storm Calms": "1",
    "Ash Storm Grows": "1",
    "Ash Storm Hits": "1",
}

# These creatures aren't real combat threats - encounters with them
# can be entirely peaceful (scavengers, gravediggers going about their
# work, harmless critters), not monsters in the sense every other name
# in MONSTERS is. Two consequences follow from that, both driven by
# this same set:
# - Mechanical: an encounter consisting only of these never triggers a
#   monster-treasure roll (see roll_monster_treasure() in game.py). If
#   an encounter mixes one of these with a monster not on this list,
#   treasure is still rolled.
# - Presentational: the UI's danger styling (see _room_has_hostile_
#   monster in game.py) only applies once at least one *other* monster
#   is also present - a room with only these in it reads as a calm
#   encounter, not a warning.
NON_HOSTILE_MONSTERS = {
    "Critters",
    "Gravediggers",
    "Exiles",
}

ENCOUNTER_TABLES = {
    1: [
        # Row 1
        [encounter("Exiles"), encounter("Gravediggers"), encounter("Simple Dead"),
         encounter("Simple Dead"), encounter("Revenants"), encounter("Revenants")],
        # Row 2
        [encounter("Critters"), encounter("Rot Swarm"), encounter("Bonebats"),
         encounter("Tombhounds"), encounter("Small Spiders"), encounter("Small Spiders")],
        # Row 3
        [encounter("Serpents"), encounter("Serpents"), encounter("Tangles"),
         encounter("Toothswarm"), encounter("Toothswarm"), NEXT_LEVEL],
    ],

    2: [
        # Row 1
        [encounter("Gravediggers"), encounter("Simple Dead"), encounter("Simple Dead"),
         encounter("Simple Dead"), encounter("Revenants"), encounter("Revenants")],
        # Row 2
        [encounter("Critters"), encounter("Rot Swarm"), encounter("Bonebats"),
         encounter("Tombhounds"), encounter("Small Spiders"), encounter("Small Spiders")],
        # Row 3
        [encounter("Serpents"), encounter("Serpents"), encounter("Tangles"),
         encounter("Toothswarm"), encounter("Toothswarm"), NEXT_LEVEL],
    ],

    3: [
        # Row 1
        [encounter("Gravediggers"), encounter("Simple Dead"), encounter("Simple Dead"),
         encounter("Simple Dead"), encounter("Revenants"), encounter("Revenants")],
        # Row 2
        [encounter("Rot Swarm"), encounter("Bonebats"), encounter("Bonebats"),
         encounter("Tombhounds"), encounter("Small Spiders"), encounter("Large Spiders")],
        # Row 3
        [encounter("Serpents"), encounter("Serpents"), encounter("Tangles"),
         encounter("Toothswarm"), encounter("Toothswarm"), NEXT_LEVEL],
    ],

    4: [
        # Row 1
        [encounter("Gravediggers"), encounter("Simple Dead"), encounter("Simple Dead"),
         encounter("Simple Dead"), encounter("Revenants"), encounter("Revenants")],
        # Row 2
        [encounter("Rot Swarm"), encounter("Bonebats"), encounter("Bonebats"),
         encounter("Tombhounds"), encounter("Small Spiders"), encounter("Large Spiders")],
        # Row 3
        [encounter("Serpents"), encounter("Serpents"), encounter("Tangles"),
         encounter("Tangles"), encounter("Toothswarm"), NEXT_LEVEL],
    ],

    5: [
        # Row 1
        [encounter("Simple Dead"), encounter("Simple Dead"), encounter("Plagueborn"),
         encounter("Revenants"), encounter("Revenants"), encounter("Revenants")],
        # Row 2
        [encounter("Rot King"), encounter("Bonebats"), encounter("Tombhounds"),
         encounter("Tombhounds"), encounter("Small Spiders"), encounter("Large Spiders")],
        # Row 3
        [encounter("Serpents"), encounter("Serpents"), encounter("Tangles"),
         encounter("Golem"), encounter("Toothswarm"), NEXT_LEVEL],
    ],

    6: [
        # Row 1
        [encounter("Plagueborn"), encounter("Plagueborn"), encounter("Plagueborn"),
         encounter("Revenants"), encounter("Revenants"), encounter("Infected Revenants")],
        # Row 2
        [encounter("Rot King"), encounter("Tombhounds"), encounter("Infected Tombhounds"),
         encounter("Small Spiders", 2), encounter("Large Spiders"), encounter("Large Spiders")],
        # Row 3
        [encounter("Infected Tangles"), encounter("Infected Tangles"), encounter("Golem"),
         encounter("Toothswarm"), encounter("Gloomwright"), NEXT_LEVEL],
    ],

    7: [
        # Row 1
        [encounter("Simple Dead"), encounter("Simple Dead"), encounter("Plagueborn"),
         encounter("Revenants"), encounter("Revenants"), encounter("Revenants")],
        # Row 2
        [encounter("Rot King"), encounter("Tombhounds"), encounter("Tombhounds"),
         encounter("Large Spiders"), encounter("Large Spiders"), encounter("Serpents")],
        # Row 3
        [encounter("Ash Ghost"), encounter("Tangles"), encounter("Golem"),
         encounter("Toothswarm"), encounter("Gloomwright"), NEXT_LEVEL],
    ],

    8: [
        # Row 1
        [encounter("Simple Dead"), encounter("Simple Dead"), encounter("Simple Dead"),
         encounter("Revenants"), encounter("Revenants"), encounter("Revenants")],
        # Row 2
        [encounter("Bonebats"), encounter("Tombhounds"), encounter("Tombhounds"),
         encounter("Large Spiders"), encounter("Too Big Spiders"), encounter("Serpents")],
        # Row 3
        [encounter("Ash Ghost"), encounter("Tangles"), encounter("Golem"),
         encounter("Toothswarm", 2), encounter("Gloomwright"), NEXT_LEVEL],
    ],

    9: [
        # Row 1
        [encounter("Simple Dead"), encounter("Simple Dead"), encounter("Revenants"),
         encounter("Revenants"), encounter("Revenants"), encounter("Bonebats", 2)],
        # Row 2
        [encounter("Tombhounds"), encounter("Tombhounds"), encounter("Large Spiders"),
         encounter("Too Big Spiders"), encounter("Serpents"), encounter("Serpents")],
        # Row 3
        [encounter("Ash Ghost"), encounter("Tangles"), encounter("Golem"),
         encounter("Toothswarm", 2), encounter("Gloomwright"), NEXT_LEVEL],
    ],

    10: [
        # Row 1
        [encounter("Simple Dead"), encounter("Simple Dead"), encounter("Revenants"),
         encounter("Revenants"), encounter("Revenants"), encounter("Bonebats", 2)],
        # Row 2
        [encounter("Tombhounds"), encounter("Tombhounds"), encounter("Too Big Spiders"),
         encounter("Too Big Spiders"), encounter("Ash Ghost"), encounter("Ash Squall")],
        # Row 3
        [encounter("Tangles"), encounter("Tangles"), encounter("Golem"),
         encounter("THE TANGLED"), encounter("THE TANGLED"), NEXT_LEVEL],
    ],

    11: [
        # Row 1
        [encounter("Ash Storm Calms"), encounter("Ash Storm Calms"), encounter("Ash Storm Calms"),
         encounter("Ash Storm Grows"), encounter("Ash Storm Grows"), encounter("Ash Storm Grows")],
        # Row 2
        [encounter("Ash Storm Grows"), encounter("Ash Storm Grows"), encounter("Ash Storm Grows"),
         encounter("Ash Storm Grows"), encounter("Ash Storm Grows"), encounter("Ash Storm Grows")],
        # Row 3
        [encounter("Ash Storm Hits"), encounter("Ash Storm Hits"), encounter("Ash Storm Hits"),
         encounter("Ash Storm Hits"), encounter("Ash Storm Hits"), NEXT_LEVEL],
    ],

    12: [
        # Row 1
        [encounter("Simple Dead", 2), encounter("Simple Dead", 2), encounter("Revenants"),
         encounter("Revenants"), encounter("Bonebats", 3), encounter("Serpents", 2)],
        # Row 2
        [encounter("Tombhounds", 2), encounter("Tombhounds", 2), encounter("Too Big Spiders", 2),
         encounter("Too Big Spiders", 2), encounter("Ash Ghost"), encounter("Ash Squall")],
        # Row 3
        [encounter("Tangles", 2), encounter("Golem"), encounter("Toothswarm", 3),
         encounter("Gloomwright"), encounter("Gloomwright"), ROLL_TWICE],
    ],
}


# ----------------------------
# LOCATION GENERATOR
# ----------------------------

LOCATIONS: list[tuple[int, str]] = [
    (3, "Abandoned Shop"),
    (4, "Suites"),
    (5, "Auditorium"),
    (6, "Public Fungal Garden"),
    (7, "Market"),
    (8, "Sculpture Gallery"),
    (9, "Wellguard Station"),
    (10, "Cistern"),
    (11, "Tavern"),
    (12, "Apartments"),
    (13, "Gaming Hall"),
    (14, "Guild Hall"),
    (15, "Administrative Chambers"),
    (16, "Workshop"),
    (17, "Storehouse"),
    (18, "Manufactory"),
    (19, "Slum"),
    (20, "Ossuary"),
    (21, "Crypt"),
    (22, "Dormitories"),
    (23, "Public Rock Garden"),
    (24, "Mansion"),
    (25, "Laboratory"),
    (26, "Mausoleum"),
    (27, "Lighted Farm"),
    (28, "Library"),
    (29, "Fungal Farm"),
    (10 ** 9, "Mine"),
]

DETAILS: list[tuple[int, str]] = [
    (3, "Looted"),
    (4, "Signpost"),
    (5, "Note"),
    (6, "Inactive Rune"),
    (7, "Dead Gravedigger"),
    (8, "Signs of Recent Passage"),
    (9, "Vermin"),
    (10, "Chandelier"),
    (11, "Safe"),
    (12, "Amphoras"),
    (13, "Wet"),
    (14, "Crevice"),
    (15, "Obscured"),
    (16, "Repurposed into Crypt"),
    (17, "Lift"),
    (18, "Slime Fungus"),
    (19, "Fragile"),
    (20, "Fireplace"),
    (21, "Secret Passage"),
    (22, "Bulky Treasure"),
    (23, "Portcullis"),
    (24, "Labyrinthine"),
    (25, "Treasure Pile"),
    (26, "Mine Damp"),
    (27, "Vault"),
    (28, "Holes"),
    (29, "Blocked Exit"),
    (10 ** 9, "Dead End"),
]

LOCATION_MODIFIERS = {
    "Abandoned Shop": {
        "treasure_roll": -1,
    },
    "Crypt": {
        "treasure_quality": +1,
    },
    "Dormitories": {
        "treasure_quality": -1,
    },
    "Laboratory": {
        "treasure_quality": +2,
    },
    "Library": {
        "treasure_quality": +2,
    },
    "Mausoleum": {
        "treasure_quality": +2,
    },
    "Ossuary": {
        "encounter_roll": +2,
        "treasure_quality": -2,
    },
    "Slum": {
        "block_positive_treasure_roll": True,
        "treasure_roll": -2,
    },
    "Temple": {
        "encounter_roll": +1,
        "treasure_quality": +1,
        "scope": "ransack",
    },
}

DETAIL_MODIFIERS = {
    "Amphoras": {
        # treasure_roll's +1 used to live here, applied unconditionally
        # to every ransack roll - now it's an opt-in choice instead
        # (DETAIL_TRAITS' "ransack_choice" below, applied retroactively
        # when ransacking - see handle_action's "ransack_room"),
        # matching the description's "PCs *can choose* to smash them".
        # encounter_roll stays: whatever eventually rolls an encounter
        # check under trigger="ransack" (nothing does yet) picks this
        # up automatically once it exists.
        "encounter_roll": +1,
        "scope": "ransack",
    },
    "Looted": {
        "no_treasure": True,
    },
    "Repurposed into Crypt": {
        "block_positive_treasure_quality": True,
    },
    "Treasure Pile": {
        "encounter_roll": +1,
        "scope": "ransack",
    },
    "Vault": {
        "treasure_roll": +1,
    },
}

# ----------------------------
# LOCATION/DETAIL TRAITS
# ----------------------------
# Structured, machine-readable consequences for specific locations or
# details, beyond what's described in prose in LOCATION_DESCRIPTIONS /
# DETAIL_DESCRIPTIONS - e.g. "Dead End" saying in its own text that
# there's no way to go deeper from here becomes a real, enforced rule
# here instead of just flavor text. Most locations/details have no
# entry at all (nothing structured beyond their description) - only
# add one here once there's an actual rule to enforce.
# A second, independent treasure roll beyond the room's own usual
# hidden-treasure search (same "extra_treasure_context" mechanism
# DETAIL_TRAITS uses below - see game.py's _generate_room and
# _render_room_treasures): both "Mine" ("there is a 1 in 3 chance
# that a valuable ore vein can be found here... removing it requires
# time and a pickaxe") and "Public Rock Garden" ("1 in 3 chance that
# something valuable can be extracted with time and a pickaxe") get
# the exact same flat-chance, no-DC, visible-immediately mechanic as
# "Crevice" below, sharing the same "pickaxe" context/label - it's a
# different kind of visible, extractable find (an ore vein/mineral
# deposit rather than something at the bottom of a gap), but still
# just one shared context, not two. "extra_treasure_source" is what
# tells them apart *which* dedicated table to actually roll on
# (MINE_TREASURE_TABLES / ROCK_GARDEN_TREASURE_TABLES in game.py's
# generate_mine_treasure/generate_rock_garden_treasure) - same idea
# as "guaranteed_treasure_source" above, just for this mechanism.
LOCATION_TRAITS = {
    "Mine": {"extra_treasure_context": "pickaxe", "extra_treasure_source": "mine"},
    "Public Rock Garden": {"extra_treasure_context": "pickaxe", "extra_treasure_source": "rock_garden"},
}

DETAIL_TRAITS = {
    "Dead End": {"blocks_deeper": True},
    # Both of these say outright "roll on the treasure table" with no
    # mention of a search/DC check - the treasure is just sitting
    # there in plain sight, not something that has to be found first.
    "Treasure Pile": {"guaranteed_treasure": True},
    "Portcullis": {"guaranteed_treasure": True},
    # Same idea - "pick something from the treasure table... [it]
    # can't take any other actions while moving" describes something
    # sitting there in plain view too - but "guaranteed_treasure_source"
    # points _generate_room at BULKY_TREASURE_TABLES (game.py's
    # generate_bulky_treasure) instead of the normal treasure tables:
    # a piece of furniture or a rug isn't the same kind of find as
    # coins or gems, so it gets its own dedicated table instead of
    # being picked from TREASURE_TABLES like Treasure Pile/Portcullis.
    "Bulky Treasure": {
        "guaranteed_treasure": True,
        "guaranteed_treasure_source": "bulky",
    },
    # Each of these lets the party move between rooms that aren't
    # directly connected in the normal Location Generator/Crawling
    # Mode sense - "lift" and "secret_passage" each form one fixed
    # pair between two specific rooms (set once, on first use);
    # "fireplace" instead links every room that has this same detail,
    # a network rather than a pair. See game.py's "use_lift" /
    # "use_secret_passage" / "use_fireplace" actions.
    "Lift": {"special_connection": "lift"},
    "Secret Passage": {"special_connection": "secret_passage"},
    "Fireplace": {"special_connection": "fireplace"},
    # A second, independent treasure roll beyond the room's own usual
    # hidden-treasure search - see game.py's _generate_room and
    # _render_room_treasures for how each "extra_treasure_context"
    # value is actually rolled/gated/labeled:
    #   "crevice" - a flat 1-in-3 chance, no DC check, always visible
    #     immediately (you can see the crevice, and whatever's at the
    #     bottom of it, just by being in the room - no search needed).
    #   "safe" - its own DC check ("as if ransacking"), gated behind
    #     its own separate "pick the lock" reveal rather than the
    #     room's general search, with a mundane fallback (e.g. old
    #     paperwork) if the roll doesn't find anything.
    "Crevice": {"extra_treasure_context": "crevice"},
    "Safe": {"extra_treasure_context": "safe"},
    # An optional bonus the player can choose to apply when ransacking
    # (see the "smash amphoras" checkbox next to the Ransack Room
    # button, and handle_action's "ransack_room") - applied
    # retroactively to the room's already-rolled hidden-treasure entry
    # rather than as a fresh roll, since that entry's own roll already
    # happened back at generation time (see _generate_room). Doesn't
    # touch the shared treasure_dc pool - see "ransack_room" for why.
    "Amphoras": {
        "ransack_choice": {
            "label": "Smash the amphoras",
            "treasure_roll_bonus": 1,
        },
    },
}

# ----------------------------
# TREASURE GENERATOR
# ----------------------------

# 1d6 → (number_of_items, quality)
TREASURE_QUALITY_TABLE = {
    0: (1, "mundane"),
    1: (1, "minor"),
    2: (2, "minor"),
    3: (1, "moderate"),
    4: (2, "moderate"),
    5: (1, "valuable"),
    6: (2, "valuable"),
    7: (1, "excellent"),
    8: (1, "excellent"),
    9: (1, "rare"),
    10: (1, "rare"),
    11: (1, "legendary"),
    12: (1, "legendary"),
}

# Each quality has its own 1d20 table
TREASURE_TABLES = {
    "mundane": {
        1: "Broken pottery shards",
        2: "Spoilt food",
        3: "Torn cloth scraps",
        4: "Rusty iron key",
        5: "Rotten parchment",
        6: "Dull knife",
        7: "Bag full of holes",
        8: "Damp torch",
        9: "Frayed rope",
        10: "Rusty lantern with shattered glass",
        11: "Pair of worn sandals",
        12: "Rusty pickaxe",
        13: "Dusty flask filled with booze",
        14: "Incomplete set of playing cards",
        15: "Empty water skin",
        16: "Axe with a dull blade",
        17: "Flask of oil",
        18: "Bent crowbar",
        19: "Rusty chain",
        20: "Iron spikes",
    },
    "minor": {
        1: "Bronze trinket (belt buckle, brooch, button, comb)",
        2: "Brass baubles (candlestick, goblet, incense box)",
        3: "Copper ornament (bracelet, earring, hairpin)",
        4: "Brass whistle, bell or small gong",
        5: "Bronze ceremonial item (dagger, candlesnuffer, scoop)",
        6: "Copper mirror (handheld, foldable with cracked surface, set into broken comb)",
        7: "Brass weight tool (small merchants scale, set of counterweights, broken scale arm)",
        8: "Bronze idol (religious, decorative, bookend, paperweight)",
        9: "Handful of copper coins (in leather pouch, in rusted jar, wedged in floor crack)",
        10: "Brass gear with unknown function (cog wheel, unusual key, tiny hinge joint)",
        11: "Bronze container (bowl, carafe, casket, vase)",
        12: "Copper plated dice or board-game piece",
        13: "Dusty leather armor with bronze studs (brigandine, bracers, greaves)",
        14: "Brass memory keepsake (locket or tiny casket filled with buttons or dried flowers)",
        15: "Copper trinket (key, necklace, ring)",
        16: "Copper flask etched with intricate symbols (decorative runes, floral or any animal)",
        17: "Bronze weapon (shortsword, dagger, spearhead)",
        18: "Brass baubles (inkwell, lens frame, scroll case)",
        19: "Bronze artisan kit (stonecutting, woodworking, gardening, tailoring)",
        20: "Copper wire or bronze chain",
    },
    "moderate": {
        1: "Silver jewelry (chain necklace, engraved ring, filigree bracelet)",
        2: "Carved stone object (figurine, tablet, or bowl made of alabaster or serpentine)",
        3: "Iron tool (blacksmith’s tong, carpenter’s square, engraving chisel with initials)",
        4: "Silver household item (spoon set, wine cup, ornamental comb, handheld mirror)",
        5: "Silver jewelry with gem (brooch, pin or locket with garnet, onyx or agate)",
        6: "Stone relief fragment (part of a mural or stele with worn symbols related to location)",
        7: "Iron weapon (sword, hammerhead, dagger)",
        8: "Handful of silver coins (in small pouch, wrapped in old cloth, hidden in a false book)",
        9: "Flawed gemstone (rough topaz, cracked amethyst, cloudy quartz orb)",
        10: "Iron armor piece (elbow guard, gorget, greaves with etched lines)",
        11: "Silver ritual item (anointing bowl, prayer pendant, incense spoon)",
        12: "Decorative inlaid stone box (holding dried ink, wax seal kit, or folded parchment)",
        13: "Heirloom-quality tools (stone-carver’s mallet with gem inlay, jeweler’s loupe)",
        14: "Civic tokens (silver badge of office, carved stone voting marker, iron passkey)",
        15: "Stone jewelry (beaded necklace, ring or earring made of jasper, agate or lapis lazuli)",
        16: "Silver flask or snuff box (plain but elegant, engraved with initials or a crest)",
        17: "Iron mechanical part (crank, heavy pinion, gear cluster with maker’s mark)",
        18: "Stone relic or idol (family ancestor bust or figurine, broken ceremonial plinth)",
        19: "Silver writing kit (nib pen, scroll tube with silver caps, inkpot with silver lid)",
        20: "Silver ring with gem (topaz, amethyst or garnet)",
    },
    "valuable": {
        1: "Gold jewelry (signet ring, heavy chain necklace, filigree earring)",
        2: "Masterwork quality steel weapon (+1 to maneuvers)",
        3: "Black lead writing tools (engraved stylus, compact scribe’s case)",
        4: "Rare gemstone, cut (flawless opal, brilliant-cut sapphire, star ruby, diamond)",
        5: "Gold relic (sun disk, small idol, ceremonial chalice with enamel detailing)",
        6: "Gilded armor piece (vambrace, emerald-studded gorget, gold-etched helmet)",
        7: "Black lead art object (etched relief tablet, abstract idol, black-lead mask)",
        8: "Handful of gold coins (small velvet pouch, clay jar sealed with wax, hidden stack)",
        9: "Noble insignia (gold brooch with house emblem, black-lead signet, golden scepter)",
        10: "Rare mineral (chunk of fire opal, piece of starry obsidian, unusual gem cluster)",
        11: "Gold ornate container (scroll tube, casket with gemstone inlay, perfume vial)",
        12: "Steel tools (engraver’s kit, medical instruments, chisels with jeweled handles)",
        13: "Rare gemstone fragments (cracked black opal, raw alexandrite, shard of fire agate)",
        14: "Gold-plated armor piece (engraved knee guard, pauldron or ceremonial cuirass)",
        15: "Luxury grooming kit (steel shaving blade, black-lead mirror, gold comb set in velvet)",
        16: "Relic weapon (longsword with ruby in pommel, gilded hammer, gold-hilted dagger)",
        17: "Fine jewelry set (matching emerald earrings, chain, and ring in black-lead box)",
        18: "Golden statuette (mythical creature, ancestral king, or forgotten god, finely sculpted)",
        19: "Gold lined spectacles or magnifying lense",
        20: "Gold ring with gem (diamond, emerald, ruby, sapphire)",
    },
    "excellent": {
        1: "Rare wooden object (carved box, smooth mask, writing tablet bound in leather)",
        2: "Pitchblende idol (abstract figure, hooded ancestral effigy, miniature seated king)",
        3: "Hornblende-inlaid wooden object (fireproof box, weapon shaft or furnishing)",
        4: "Wooden relic (spear shaft with name carvings, silver capped cane, hide drum)",
        5: "Pitchblende weapon component (blunt mace head, pommel core, counterweight)",
        6: "Hornblende-inlaid artisan tools (carving knife, measuring rod, wood chisel)",
        7: "Decorative wooden panels (wall or furniture remnants, fragments of an ancient door)",
        8: "Pitchblende pendant (heavily worn insignia of old rank, ritual medallion on cord)",
        9: "Hornblende ceremonial mask (faceless expression, animal motif, warrior aspect)",
        10: "Wooden game board (complete set with pieces, foldable with engraved initials)",
        11: "Pitchblende container (small thick-walled bowl, empty paint pot with wooden lid)",
        12: "Wood-carved scroll case (hollow tube with latching ends, coated with hornblende)",
        13: "Proto-paint (glows faintly but otherwise non-magical)",
        14: "Wooden statuette (guardian animal, family figure trio, fragmented shrine piece)",
        15: "Pitchblende or hornblende ore (pitch black, green shimmer, silver speckles)",
        16: "Master-crafted bow or crossbow (+1 to murder)",
        17: "Pitchblende jewelry (matte ring with etched rim, bead strand, medallion on cord)",
        18: "Pitchblende tool (ceremonial hammer, burin for etching stone, anvil fragment)",
        19: "Hornblende grooming item (finely spaced comb, nail stylus, filigree hairclip)",
        20: "Wooden personal keepsake (box with family sigil, flute, carved charm)",
    },
    "rare": {
        1: "Ancient tome bound in cracked leather (religious or philosophical essay)",
        2: "Boxwood sculpture (pale, fine-grained figurine or bust that shows precise detail)",
        3: "Scholarly treatise (stone-cutting techniques, medicinal fungi or stock farming)",
        4: "Runebook (contains instructions to paint a single rune, perhaps unknown)",
        5: "Burl walnut panel fragment (carved wall or furniture piece with intricate patterns)",
        6: "Explorer's journal (expedition report with maps, perhaps copied from older source)",
        7: "Oil painting on mahogany panel (portrait, still-life or faded scenes of court or city life)",
        8: "Artist's sketch folio (plants, humans, animals or objects)",
        9: "Book of fables (told in short poetic lines, likely once read to children)",
        10: "Inscribed padauk wood plaque (deep-carved clan vows or ancient edict)",
        11: "Sample folio (swatches of woven fungus-fiber or hide with artisan annotations)",
        12: "Poetry book (verses in an archaic dialect, mirthful, romantic or sad)",
        13: "Embroidered tapestry (family tree, floral patterns, mythical creature)",
        14: "Ceremonial record book (marked with silver studs, details rites for naming or burial)",
        15: "Tome of forgotten knowledge (alchemy, medicine, mechanics, enchantment)",
        16: "Artist’s workbox (dried pigment stones and brushes, still fragrant and glossy)",
        17: "Book with historic content (town chronicle, biography)",
        18: "Rare wood grooming item (masterwork comb or makeup brush made of satinwood)",
        19: "Finely decorated piece of porcelain (vase, bowl, jug, plate, cup)",
        20: "1 dose of paint (glowing in unusual color, made from ancient forgotten recipe)",
    },
    "legendary": {
        1: "Statuette of a sleeping beast (carved from glossy petrified black mahogany)",
        2: "Funerary stele (petrified ash, inscribed with a family tree, dates, and achievements)",
        3: "Mosaic panel (hundreds of petrified olivewood tiles, depicting a historical event)",
        4: "Gallery bust (noble portrait sculpted from dense petrified rosewood on marble base)",
        5: "Regal jewelry (bracelet, necklace or ring made of amber, coral or nacre)",
        6: "Document chest (petrified ebony coffer with gold hinges for royal correspondence)",
        7: "Luxury game set (full gameboard of petrified ebony with hand-carved ivory pieces)",
        8: "Regal funeral mask (somber ivory mask with ridged brow and inset coral eyes)",
        9: "Unique gem (colorful diamond, red sapphire or giant black opal, flawless quality)",
        10: "Oil painting on petrified walnut panel (showing some overworld landscape)",
        11: "Arch keystone (carved from petrified teak, featuring faces of judges and scholars)",
        12: "Regal crown (massive gold with diamonds and other gems, ivory marquetry)",
        13: "Nacre intarsia panel (oceanic scene set into a petrified cypress mount)",
        14: "Wall frieze fragment (red coral scrollwork mounted on petrified oak, tiny gold nails)",
        15: "Intact ivory tusk (engraved or painted with complex patterns, capped with gold)",
        16: "Giant polished amber with one or more fossilized insects inside",
        17: "Ivory scroll case (etched with landscapes and gold latches in pristine condition)",
        18: "Amber figurine (meditating figure sculpted entirely from solid, cloudy amber)",
        19: "Ivory lyre (musical instrument with intricate nacre inlay along the arms)",
        20: "Regal scepter or cane (made from petrified ebony, flawless amber as headpiece)",
    },
}

# A "Safe" detail's own fallback when its treasure roll doesn't find
# anything (see DETAIL_TRAITS' "extra_treasure_context": "safe" and
# game.py's _generate_room) - "place something mundane inside (e.g.
# business or legal papers)", per its own description. Deliberately
# its own small table rather than reusing TREASURE_TABLES["mundane"]
# (generic dungeon debris - broken pottery, rusty keys) - a locked
# safe holding paperwork instead of junk is a different, more
# specific flavor.
SAFE_MUNDANE_CONTENTS = [
    "Stack of old business ledgers, ink faded past reading",
    "Bundle of unpaid invoices, tied with string",
    "Yellowed legal documents, seals long broken",
    "Property deed for a building that no longer stands",
    "Bundle of promissory notes, debtor's name illegible",
    "Personal correspondence, water-damaged and stuck together",
    "Tax records from a defunct administration",
    "Household inventory list, nothing on it worth anything now",
]

# A "Bulky Treasure" detail's own guaranteed find (see DETAIL_TRAITS'
# "guaranteed_treasure_source": "bulky" and game.py's
# generate_bulky_treasure) - "something valuable that is hard to
# move", per its own description - a lavish piece of furniture, a
# huge rug, or a musical instrument are just examples there, not the
# whole scope, hence the wider variety of large object types below
# (chests, screens, cabinets, basins, thrones, a loom mid-weave, ...).
# Deliberately its own small 1d6-per-quality-tier table rather than
# TREASURE_TABLES' 1d20 ones - those are built for ordinary, portable
# loot (coins, gems, small trinkets), not a single big, awkward
# object. Always resolves to exactly one item (no "extra items" on
# top, unlike normal treasure) - a haul is multiple things; this is
# one large one.
#
# Follows the exact same material-per-tier convention TREASURE_TABLES
# already uses - the point there (see that table's own items) is
# being able to eyeball an item's worth straight from its material
# without needing to know its tier: bronze/brass/copper at minor,
# silver/iron/stone at moderate, gold/black-lead/cut-gems at
# valuable, pitchblende/hornblende/rare-wood at excellent, fine woods
# (boxwood/walnut/padauk/satinwood) paired with artistry/knowledge at
# rare, and petrified wood/amber/coral/nacre/ivory at legendary -
# these tables stay consistent with that so the same "read the
# material, know the worth" logic still works for a bulky find.
BULKY_TREASURE_TABLES = {
    "mundane": {
        1: "Rotted wooden trunk, lid warped shut, contents turned to dust",
        2: "Threadbare woven rug, moth holes larger than intact patches",
        3: "Cracked wash-basin stand, its bowl shattered",
        4: "Splintered wooden bench, one leg missing entirely",
        5: "Mildewed tapestry, its scene no longer recognizable",
        6: "Collapsed loom, threads rotted to nothing",
    },
    "minor": {
        1: "Oak chest bound in tarnished bronze, hinges still sound",
        2: "Wall-mounted brass birdcage, perch long rusted through",
        3: "Copper-footed washstand, basin dulled green with age",
        4: "Bronze-studded wooden bench, seat worn smooth",
        5: "Wool wall-hanging on a brass rod, faded hunting scene",
        6: "Squat cedar cabinet, drawer pulls cast in brass",
    },
    "moderate": {
        1: "Iron-banded traveling chest, lock long rusted open",
        2: "Stone bench carved from a single slab of serpentine",
        3: "Silver-inlaid wooden screen, one panel cracked",
        4: "Silver birdcage on a wrought stand, door hanging loose",
        5: "Alabaster wash-basin set into a stone pedestal",
        6: "Woven rug dyed with lapis-blue and jasper-red thread",
    },
    "valuable": {
        1: "Gilt-edged wardrobe, doors inlaid with polished emerald",
        2: "Black-lead writing desk, drawers lined in velvet",
        3: "Gold-footed banquet table, top scarred but sound",
        4: "Ruby-studded jewelry cabinet, mirrored doors intact",
        5: "Woven silk rug bordered in gold thread",
        6: "Gilded birdcage shaped like a miniature temple",
    },
    "excellent": {
        1: "Rare-wood wardrobe with pitchblende hinge fittings",
        2: "Hornblende-inlaid writing desk, surface cool to the touch",
        3: "Carved wooden screen depicting a hunt, pitchblende accents",
        4: "Wooden game table with a hornblende-ringed playing surface",
        5: "Rare-wood cradle, polished smooth by generations of use",
        6: "Pitchblende-studded armor stand, empty but well-kept",
    },
    "rare": {
        1: "Boxwood writing desk, drawers full of blank fine paper",
        2: "Burl walnut bookcase, shelves still lined with ledgers",
        3: "Oil painting on a padauk-framed panel, a city skyline at dusk",
        4: "Satinwood harpsichord, strings brittle but frame flawless",
        5: "Porcelain wash-basin set atop a carved wooden stand",
        6: "Embroidered tapestry loom, mid-weave, thread still strung",
    },
    "legendary": {
        1: "Wardrobe of petrified ebony, doors inlaid with solid ivory",
        2: "Banquet table of petrified oak, legs capped in gold",
        3: "Coral-encrusted bathing basin, carved from a single stone block",
        4: "Nacre-inlaid cabinet, every drawer a different oceanic scene",
        5: "Ivory throne with an amber-studded backrest",
        6: "Petrified rosewood organ, pipes tipped in ivory",
    },
}

# "Mine"'s own pickaxe-extractable find (see LOCATION_TRAITS'
# "extra_treasure_context": "pickaxe" + "extra_treasure_source":
# "mine", and game.py's generate_mine_treasure) - "there is a 1 in 3
# chance that a valuable ore vein can be found here (otherwise
# something mundane like coal)". Only 1d3 entries per tier rather
# than BULKY_TREASURE_TABLES' 1d6 - The Well is a d6-based game with
# no d4s, and this only ever comes up on a 1-in-3 roll to begin with,
# so it's seen far less often and doesn't need as much variety to
# avoid repeats feeling stale.
#
# Follows TREASURE_TABLES' material-per-tier convention as closely as
# an unrefined, uncut mine find reasonably can (see
# BULKY_TREASURE_TABLES' own comment for the general idea) - checked
# tier by tier against that table's own items: mundane stays
# material-free the same way it does there (rusty iron junk is junk
# *because* it's rusty/broken, not because iron itself is a mundane-
# tier material - iron proper belongs to moderate); minor is bronze/
# brass/copper only, deliberately never "iron" (that's moderate's
# signal - mixing it in here would blur the very "read the material,
# know the worth" logic this is supposed to preserve); moderate is
# silver/iron/stone; valuable leans on gold/black-lead plus that
# tier's own explicit "Rare mineral (fire opal, starry obsidian...)"
# entry, framed here as still-uncut/raw rather than already "cut"
# like the normal table's version; excellent echoes entry 15 there
# almost verbatim ("Pitchblende or hornblende ore, pitch black, green
# shimmer, silver speckles"). Past that, an actual mine has no real
# use for "fine woods" or "petrified furniture", so rare/legendary
# escalate into real, still-unclaimed-elsewhere precious materials
# instead (platinum, corundum, meteoric iron, iridium) - named
# specifically rather than left as a vague "rare ore", the same way
# every other tier here is.
MINE_TREASURE_TABLES = {
    "mundane": {
        1: "Seam of common coal, barely worth hauling out",
        2: "Crumbling iron slag, already picked clean",
        3: "Waterlogged, clay-streaked rock - worthless",
    },
    "minor": {
        1: "Vein of raw copper ore, still bright where exposed",
        2: "Nugget of tin ore, enough for a batch of bronze",
        3: "Thin seam of brass-toned pyrite - fool's gold, but sellable as a curiosity",
    },
    "moderate": {
        1: "Vein of raw silver ore threading through the rock",
        2: "Dense, well-formed iron ore deposit",
        3: "Chunk of banded agate embedded in the stone",
    },
    "valuable": {
        1: "Vein of raw gold, glinting even in torchlight",
        2: "Deposit of heavy black-lead ore",
        3: "Rough fire opal or starry obsidian, still fused to the rock",
    },
    "excellent": {
        1: "Vein of pitchblende, faintly warm to the touch",
        2: "Seam of hornblende, dark and glassy",
        3: "Where the two meet: pitch black ore flecked with silver and green",
    },
    "rare": {
        1: "Vein of raw platinum, denser and rarer than any gold seam",
        2: "Pocket of raw corundum crystals - could be ruby or sapphire once cut",
        3: "Seam of ore so pure the assayers would call it impossible",
    },
    "legendary": {
        1: "A single flawless gem, fist-sized, still embedded in the rock",
        2: "A seam of raw meteoric iron, cold to the touch despite the depths",
        3: "A vein of pure iridium, rarer than anything else this mine has yielded",
    },
}

# "Public Rock Garden"'s own pickaxe-extractable find (same
# LOCATION_TRAITS mechanism as "Mine" above, "extra_treasure_source":
# "rock_garden" - see game.py's generate_rock_garden_treasure) -
# "1 in 3 chance that something valuable can be extracted with time
# and a pickaxe", following up on the location's own "artificial
# crystal growth produced breathtaking displays". Same 1d3-per-tier
# sizing as MINE_TREASURE_TABLES above, and checked against
# TREASURE_TABLES' tiers the same careful way that one's own comment
# describes - ornamental stone/crystal instead of raw ore, so a "cut"
# or "polished" find fits here (unlike Mine's uncut framing - this
# location is already about cultivated, on-display growth, not a
# working excavation), moderate leans on the exact same stone jewelry
# materials TREASURE_TABLES itself names for that tier (jasper, agate,
# lapis lazuli), and valuable/rare/legendary name specific real gems
# throughout rather than a vague "rare crystal" - reusing fire opal/
# starry obsidian/black opal/diamond where TREASURE_TABLES already
# uses them (at the same or an escalated tier, same as how it reuses
# diamond and sapphire itself between valuable and legendary), and
# introducing peridot/moonstone/tourmaline/star sapphire where a
# fresh, still-unclaimed-elsewhere material was needed instead.
ROCK_GARDEN_TREASURE_TABLES = {
    "mundane": {
        1: "Dull grey pebble, nothing special",
        2: "Chunk of fused gravel, worthless",
        3: "Cloudy, cracked quartz nodule",
    },
    "minor": {
        1: "Small stone ringed with a dull, bronze-toned patina",
        2: "Copper-streaked pebble, pretty but common",
        3: "Cluster of brass-colored mica flakes",
    },
    "moderate": {
        1: "Polished agate stone, swirled with color",
        2: "Chunk of jasper, veined with iron-red",
        3: "Cluster of lapis lazuli fragments",
    },
    "valuable": {
        1: "Polished fire-opal shard, grown within a crystal cluster",
        2: "Vein of gold-flecked quartz",
        3: "Cluster of richly colored starry-obsidian crystals",
    },
    "excellent": {
        1: "Cluster of pitchblende crystals, faintly glinting",
        2: "Dark, glassy hornblende crystal formation",
        3: "Geode lined where the two meet - pitch black, flecked with silver",
    },
    "rare": {
        1: "Perfectly formed cluster of peridot crystals, vivid green in dim light",
        2: "Geode lined with moonstone, each crystal glowing faintly",
        3: "Fused cluster of tourmaline shards, banded in impossible colors",
    },
    "legendary": {
        1: "A single flawless diamond crystal, larger than a fist",
        2: "A fused cluster of black opal and moonstone, dazzling even unpolished",
        3: "A vein of raw star sapphire running straight through solid rock",
    },
}


TREASURE_EXTRA_ITEMS_TABLE = {
    5: [{"category": "consumable", "amount": 1}],
    6: [{"category": "consumable", "amount": 1}],
    7: [{"category": "paint_or_consumable", "amount": "1d3"}],
    8: [{"category": "paint_or_consumable", "amount": "1d6"}],
    9: [{"category": "artifact", "amount": 1}],
    10: [{"category": "paint_or_consumable", "amount": "1d6"}, {"category": "paint", "amount": 6}],
    11: [{"category": "artifact", "amount": "1d3"}],
    12: [{"category": "artifact", "amount": "1d3"}, {"category": "paint_or_consumable", "amount": "2d6"}],
}

# ----------------------------
# CONSUMABLES
# ----------------------------

CONSUMABLE_SUBTYPES = ["potion", "ampule", "arrow", "miscellany"]

AMPULES_TABLE = {
    1: "Acid (yellow)",
    2: "Concussive blast (turquoise)",
    3: "Lightning (blue)",
    4: "Fire (yellow-green)",
    5: "Air (clear)",
    6: "Freezing (grey)",
    7: "Water (lilac)",
    8: "Heal (steel)",
    9: "Disintegration (burnt mustard)",
    10: "Instant wall (tree green)",
    11: "Stone trap (chocolate)",
    12: "Tracking (green)",
    13: "Light (olive)",
    14: "Magnetism (peach)",
    15: "Smoke (black)",
    16: "Petrify (dark slate)",
    17: "Poison gas (orange)",
    18: "Sound machine (rose)"
}

POTIONS_TABLE = {
    1: "Enhanced hearing (pale yellow)",
    2: "Enhanced touch (bone)",
    3: "Enhanced smell (dark red)",
    4: "Agility (powder blue)",
    5: "Hair growth (bright yellow)",
    6: "Sanguinity (slate)",
    7: "Stoneskin (mauve)",
    8: "Strength (pale red)",
    9: "Curative (grey-purple)",
    10: "Darksight (yellow-green)",
    11: "Haste (violet)",
    12: "Awareness (blue)",
    13: "Enhanced vision (lime green)",
    14: "Healing (pink)",
    15: "Perfect direction (royal blue)",
    16: "Sustenance (blood)",
    17: "Unconsciousness (dark violet)",
    18: "Vitality (moss green)"
}

MISCELLANY_TABLE = {
    1: "Implosion pill",
    2: "Climber’s spikes",
    3: "Cloak of fire absorption",
    4: "Instant bandage",
    5: "Ice crystals",
    6: "Skeleton key",
    7: "Blademaster’s whetstone",
    8: "Shield sphere",
    9: "Jar of wind",
    10: "Eternal oil",
    11: "Rod of disruption",
    12: "Map cloth"
}

# ----------------------------
# ARTIFACTS
# ----------------------------

ARTIFACTS_TABLE = {
    1: "Instant armor",
    2: "Purification jar",
    3: "Mysterious metal lozenge",
    4: "Extensible ladder",
    5: "Weapon, minor enchantment",
    6: "Eternal brush",
    7: "Chameleon cloak",
    8: "Spectacles of defense",
    9: "Helm of breathing",
    10: "Cloak of comfort",
    11: "Architect’s spectacles",
    12: "Helms of shared thought",
    13: "Weapon, major enchantment",
    14: "Low-profile armor",
    15: "Pouch of anything",
    16: "Shield ring",
    17: "Painter’s pot",
    18: "Spectacles of mage sight",
    19: "Advanced low-profile armor",
    20: "Weapon, mighty enchantment",
    21: "Memory skull",
    22: "Stoneplanter",
    23: "Guardian ring",
    24: "Master key"
}

# ----------------------------
# DESCRIPTIONS
# ----------------------------

LOCATION_DESCRIPTIONS = {

    "Abandoned Shop": """
This place used to sell upmarket goods, but the former owner gave up on that long ago.

The rooms are now filled with dust and junk, but a thorough search might still yield something interesting.

**Add −1 on rolls to find treasure here.**
""",

    "Administrative Chambers": """
A collection of small offices and big typing pools scattered with vast amounts of loose papers.

If the PCs are looking for information about a specific location, person, or event related to the history of this level, they might find something.

Doing so requires digging through chaotic, rotting documents (**difficulty 10**).
""",

    "Apartments": """
A series of small modest apartments.

Whoever lived here was doing well enough to afford a home, but their lifestyle was anything else than luxurious.

Good hiding places, easy to defend, but usually only one exit — making them potential deathtraps.
""",

    "Auditorium": """
A large semi-circular room with a stage at the flat side.

Around it are rings of benches, each slightly more elevated than the one in front.
""",

    "Cistern": """
A large basin once used to draw fresh water.

If the PCs are lucky, they can refill waterskins here.

The water may also be brackish, contaminated, or the basin dry.
""",

    "Crypt": """
Large stone sarcophagi are lined up, each labeled with a name.

The people who got entombed here (or their families) paid considerable fees to avoid public burial.

**Add +1 to rolls on the treasure table.**
""",

    "Dormitories": """
Sparse rooms crammed with bunk beds and little room for privacy or personal belongings.

These were the homes of the lower working class of the city.

**Add −1 to rolls on the treasure table.**
""",

    "Fungal Farm": """
A cave or former mine repurposed to grow fungi for food, drugs, or other products.

The place is overgrown and jungle-like. The higher the level, the stranger and more exotic the vegetation.

PCs with a farming background may search for edible or medicinal plants.
""",

    "Gaming Hall": """
A large room filled with gambling tables and strange gaming artifacts.

There is a good chance to find money or exotic coins here.
""",

    "Guild Hall": """
A central meeting chamber surrounded by storage and workrooms.

Narrow stairs lead to a mezzanine once used as an archive or office space. Faded banners show sigils of a forgotten trade guild.

Choose one of the following options, or decide that the nature of the guild remains a mystery:

- **Artisans guild**: Change any treasure found here into rare materials (blocks of marble, petrified woods, rolls of fine cloth) or drawings of unfinished or masterful works.
- **Farmers guild**: Change any treasure found here into seeds, jars of pickled crops, or books on farming techniques, crop rotation, or soil health.
- **Mining guild**: Change any treasure found here into mining equipment (hammers, pickaxes, lanterns, ropes, etc.) or a map leading to nearby mines. If appropriate, the map may also contain information about dangers or secret passages.
- **Painters guild**: Change any treasure found here into doses of paint or runebooks.
""",

    "Laboratory": """
A large workshop full of strange apparatuses and exotic equipment (mostly broken).

Whatever happened here was already a well-kept secret when the level was still inhabited.

Ransacking this place is not without danger, for touching the broken apparatuses might trigger unknown effects — but it is usually worth it.

**Add +2 to any rolls on the treasure table.**

Choose one of the following options to determine the original purpose of the location:

- **Paint production**: Change any consumables rolled on the treasure table into doses of paint. Books always contain instructions for painting runes. While ransacking, there is a **50% chance** the PCs trigger the effect of a random rune on themselves.
- **Golem construction (level 5 or higher)**: Change any consumables rolled into twice the amount in doses of paint. While ransacking, there is a **50% chance** a half-assembled construct comes to life and attacks the PCs (treat it as a rune golem with only 1 action die and 10 resilience).
- **Alchemy (level 6 or higher)**: Consumables are always potions or ampules. For every generated potion or ampule, another one remains in an apparatus, ready to be bottled. While ransacking, there is a **50% chance** the PCs trigger the effect of a random ampule.
- **Lesser thaumaturgy (level 8 or higher)**: Consumables are always miscellany. A strange compass-like apparatus points to a nearby location 1d6 layers deeper (difficulty 10 to navigate). While ransacking or experimenting, there is a **50% chance** something blows up unexpectedly (treat as a *fragile* location).
- **Greater thaumaturgy (level 11 or higher)**: Rolls always produce at least **1 permanent artifact**. Ignore anything else from the bonus column. While ransacking, there is a **50% chance** of attracting nearby undead (roll a random encounter), in addition to normal encounters.
""",

    "Library": """
Books are extremely precious and thus rarely left behind.

Still, no gravedigger would pass the opportunity to search through the crumbled shelves, for the promise of valuable loot — and ancient knowledge — is too tempting.

**Add +2 to all rolls on the treasure table**, but ignore any consumables from the bonus column (except paint).
""",

    "Lighted Farm": """
A large cave or former mine shaft used to raise valuable crops and livestock with the help of artificial light.

In central places, one can still see where the magic runes used to be.

Now, without the light, it is a place of darkness and decay, since most light-dependent plants died long ago.
""",

    "Mansion": """
Entrance to a sprawling upper-class mansion.

Whoever lived here belonged to the upper class of their time.

Immediately roll **1d3 + 1** and generate that many interconnected locations within the current depth, using the following special table (roll 1d6 and reroll duplicates):

1. Cistern, with fresh water supply  
2. Library, with +1 to find treasure  
3. Lounge (treat like *Suites* with *Bulky Treasure* detail)  
4. Mausoleum, with +1 to find treasure  
5. Treasury (treat like *Vault* and *Treasure Pile* combined; **+3 to treasure rolls**)  
6. Pleasure garden (treat like *Public Fungal Garden* with +1 to find treasure)
""",

    "Manufactory": """
A sprawling structure with rows of workbenches.

Storage rooms contain raw materials and finished goods.
""",

    "Market": """
An open area filled with the remnants of stalls — stone counters, rotting crates, and tarnished scales.

Alcoves where merchants once displayed their wares are now littered with broken pottery and scraps of faded cloth.
""",

    "Mausoleum": """
One or several richly ornamented stone sarcophagi are placed inside a spacious chamber.

Elaborate mural reliefs and paintings might give clues about the deceased person or family, who must have been extremely wealthy.

**Add +2 to any rolls on the treasure table.**
""",

    "Mine": """
Most spaces used to be mines at some point, but were later extended and adjusted to a new purpose.

This one was still actively mined when the level was abandoned.

There is a **1 in 3 chance** that a valuable ore vein can be found here (otherwise something mundane like coal).

Roll on the treasure table and replace improper results with larger quantities of something less valuable.

Removing it requires time and a pickaxe.
""",

    "Ossuary": """
A storage room crammed with bones in every corner, maybe even up to the ceiling.

Whoever found their final rest here was either a beggar, a criminal — or both.

**Add −2 to rolls on the treasure table**, but **+2 to rolls for random encounters.**
""",

    "Public Fungal Garden": """
An eerie expanse of bioluminescent mushrooms and twisted fungi, untended for decades.

Stone pathways wind through the garden, now overgrown with moss and vines.

There is a **50% chance** the place bears an additional detail. Choose one:

- Glowing mushrooms (the area is well lit)
- Hedge maze (treat like *labyrinthine*)
- Overgrown (treat like *obscured*)
- Slime fungus (treat like that detail)
- Spore cloud (treat like *mine damp*)
""",

    "Public Rock Garden": """
A public place elaborately decorated with rocks, stones, and gravel, sometimes with additional planting.

In former times (level 6 or higher), artificial crystal growth produced breathtaking displays.

There is a **1 in 3 chance** that something valuable can be extracted with time and a pickaxe.
""",

    "Sculpture Gallery": """
A vast, echoing hall with high, crumbling walls and cracked marble floors.

Dust clings to broken statues, some toppled, others half-eroded by time.

There are **1d6 intact sculptures**, waiting to be toppled onto unwary enemies.
""",

    "Slum": """
A maze of narrow, crooked alleys choked with rubble and refuse.

Only the indigent lived here.

**Add −2 to rolls to find treasure** and ignore any further bonuses.

If a detail includes treasure (bulky treasure, portcullis, treasure pile), replace it with something mundane.
""",

    "Storehouse": """
A cavernous space with rows of shelves and crates, many collapsed under the weight of time.

Scattered barrels and sacks spill their long-rotted contents across the floor.

Choose one of the following options (or roll 1d6) when ransacking:

1. Preserved goods (salted or dried food, possibly edible)
2. Raw materials (cloth, rope, planks)
3. Tools (hammers, nails, loading equipment)
4. Containers (barrels, crates, sacks)
5. Records (shipping manifests or ledgers)
6. Hidden stashes (roll on the treasure table)
""",

    "Suites": """
A cluster of dignified dwellings with arched doorways and faded carvings.

A communal well sits at the center, now dry and clogged.

Most sites retain some furniture and are usually well defensible.

If the PCs rest here, they **do not suffer the usual −1** on stress reduction rolls.
""",

    "Tavern": """
A once-welcoming facade now marred by cracks and creeping moss.

Inside, broken tables and overturned chairs litter the stone floor.

There is a **50% chance** that one cask still contains **1d6 doses of booze**.
""",

    "Temple": """
 Walls adorned with faded carvings of family trees and solemn faces.

 Niches hold crumbling urns and plaques etched with ancestral names, some toppled and broken on the stone floor.

 A central shrine, once the focus of rituals, stands chipped and empty, surrounded by scattered offerings of dried cave flowers, burnt incense sticks, and rusted heirlooms.

 There is a strong taboo against ransacking these sacred places of ancestral worship, but what happens upwell usually stays upwell.

 If the PCs choose to do so, they get **+1 on any rolls on the treasure table**, but you also add **+1 on the roll for a random encounter**.
 """,

    "Wellguard Station": """
 A compact, sturdy structure.

 Inside, the main room holds a long table, surrounded by broken chairs.

 Rusted weapon racks stand empty or hold a few forgotten spears and swords, their blades dulled by time.

 Roll **1d6** for something intact to find while ransacking:

 1. Sword  
 2. Shield  
 3. Spear  
 4. Cuirass and hauberk  
 5. Chain (5 m)  
 6. Set of dice
 """,

    "Workshop": """
 A cluttered, shadow-filled space with heavy workbenches covered in rusted tools and half-finished projects.

 Shelves sag under the weight of dusty jars, while broken crates spill their contents across the floor.

 Choose one of the following options, or roll **1d6**, to determine what kind of craftsman had his workplace here:

 1. Blacksmith  
 2. Carpenter  
 3. Stonemason  
 4. Weaver  
 5. Potter  
 6. Bookbinder
 """,
}

DETAIL_DESCRIPTIONS = {

    "Amphoras": """
The location is crammed with large pieces of sealed crockery.

They might contain organic goods (most likely rotten) or mortal remains.

The PCs can choose to smash them while ransacking for a **+1 bonus to find treasure**, but the noise might attract something unwanted (**+1 on the roll for a random encounter**).
""",

    "Blocked Exit": """
The only other exit of this location is blocked.

Choose one of the following:

- **Barricaded door:**  
  A light door that was barricaded, maybe even nailed up with furniture from the side the PCs are on. It can be cleared easily, but is that a good idea?  
  If the PCs choose to go deeper from here, add **+1 to the next random encounter check**.

- **Locked door:**  
  A strong door with an iron lock. If the PCs want to go deeper from here, they have to find a way to open it first.  
  While ransacking the location, they have a **1 in 6 chance to find the key**.

- **Overgrown passage:**  
  A simple passage that became overgrown with fungal weeds. The PCs can hack or burn their way through, but whatever waits in the next room might ambush them.  
  They get **−1 to awareness and stealth** while going deeper from here. Consider adding the *obscured* detail to the next location.
""",

    "Bulky Treasure": """
The location contains something valuable that is hard to move.

It might be a lavish piece of furniture, a huge ornate rug, or a musical instrument.

Pick something from the treasure table that is appropriate for the current level.

If a PC wants to carry it along, they can’t take any other actions while moving between locations from now on.

The next time the group is fleeing from a fight, they have to leave the item behind.
""",

    "Chandelier": """
A large chandelier is hanging from the ceiling, held up by an old rusty chain fixed to one of the walls.

A decent hit will cause it to fall, knocking down anything underneath and causing **1d6 damage**.
""",

    "Crevice": """
The location is split in half.

A PC can simply leap over it, but in the heat of a fight it might require a **difficulty 5 roll** to not trip.

There is a **1 in 3 chance** that something valuable lies at the bottom of the crevice (roll on the treasure table).
""",

    "Dead End": """
The location forms a dead end, from which the PCs have to backtrack.

There is no way to go deeper from here.
""",

    "Dead Gravedigger": """
It might be someone the PCs know from Bastion (maybe they even came to search for them) or someone who's been lying here for centuries.

If the PCs search the body, roll **1d6** to see what they find:

1. Rotten food  
2. Two torches  
3. Booze  
4. Half-finished letter (to someone who might be long dead)  
5. Minor piece of treasure  
6. Map to a random location or some hidden treasure
""",

    "Fireplace": """
The location contains a large built-in fireplace, maybe with a bucket of coal nearby.

The chimney leads to some kind of ventilation system, from which at least one other location is reachable.

If the PCs want to climb up the chimney, they can use it to travel between any existing locations that have been generated with a fireplace.

If no such place exists yet, instead they find a new location with a fireplace.
""",

    "Fragile": """
Parts of the location are structurally weak and in danger of collapsing.

PCs who succeed on an awareness roll notice this. If the group ransacks the location (or interacts with it in any other way), something bad happens.

Choose one of the following:

- **Collapsing ceiling:**  
  Everyone in the room suffers **1d6+1 damage** from falling stones. Dodging is **difficulty 5**.  
  Halve rolls for any attempt to defend without a shield (or similar).

- **Collapsing entrance:**  
  The way back is blocked. Unless the PCs have tools to dig through (which takes time), they cannot go back.  
  Erase one of the entrances to this location.

- **Collapsing floor:**  
  The PCs suffer **1d6 damage** from falling (armor doesn’t help) and are now in another room.  
  Unless they have climbing tools, they cannot backtrack and are effectively lost.  
  Roll a new location **1d6 layers deeper**.
""",

    "Holes": """
The walls are perforated with small cracks and holes.

They lead to nearby locations but are too tight for a human to squeeze through.

Bats, spiders, tangles, and other small creatures can fit through and ambush easily.

As long as the PCs stay here, they are automatically surprised by these creatures.
""",

    "Inactive Rune": """
The magic faded away long ago, but the rune is still clearly visible. With a dose of paint, it can be reactivated.

Roll **1d6** to choose the type of rune:

1. Annul  
2. Burn  
3. Light  
4. Purify  
5. Reveal magic  
6. Scry (shows an undiscovered place; roll a new location **1d6 layers deeper**)
""",

    "Labyrinthine": """
The location is part of a larger complex of maze-like corridors, intersections, and secluded dead ends.

Going deeper from here requires a **difficulty 5 navigation check**. On a failure, the PCs are immediately lost.
""",

    "Lift": """
The location contains a lift consisting of a crank, iron cage, and counterweight.

The iron chains are in acceptable condition, but the turning mechanism is jammed. A **difficulty 5 roll** can fix it.

The lift shaft connects to a place **1d6 layers deeper** (or less deep if the current depth is greater than 5).

To use the lift, someone must stay behind to operate the crank. Roll up a new location if they do.
""",

    "Looted": """
Somebody has been here before and turned the place upside down.

There is no treasure to be found here.
""",

    "Mine Damp": """
The location is filled with dangerous gas.

A PC with a mining background notices the signs early; others might wander in carelessly.

Choose one of the following:

- **Choke damp:**  
  Torches extinguish on entering. Fire-based effects might fail.  
  Staying here reduces resilience of all living creatures by **2 per exploration round**.

- **Stink damp:**  
  The smell gives **−2 to all actions** and causes **1 stress per exploration round**.

- **Fire damp:**  
  Torches flare and cause an explosion dealing **2d6 fire damage**.  
  The noise attracts nearby threats. Roll a random encounter immediately.
""",

    "Note": """
A previous visitor has written something—either a paper note or graffiti on the wall.

It contains information useful for gravediggers about nearby threats, valuables, or the history of the level.
""",

    "Obscured": """
The location is thick with cobwebs or sprawling fungi.

PCs get **−1 to notice threats**, but **+1 to stealth** while inside.
""",

    "Portcullis": """
The location lies behind a huge portcullis.

PCs can see what’s on the other side but must pick the lock or break it down to enter.

Roll on the treasure table for something placed inside, clearly visible from outside.
""",

    "Repurposed into Crypt": """
Whatever this location used to be, it was repurposed into a public crypt.

Dozens of corpses fill the room, mostly in cheap caskets.

Ignore any bonuses to treasure rolls from the location.
""",

    "Safe": """
A small locked safe is integrated into one of the walls.

Picking the lock is time-consuming; brute force is ineffective (halve rolls for it).

If opened, roll for treasure as if ransacking the location.  
If no treasure is found, place something mundane inside (e.g. business or legal papers).
""",

    "Secret Passage": """
A secret passage is hidden behind an unobtrusive architectural feature and can be found while ransacking.

It either connects to a previously explored, less-deep location or leads to a new location **1d6 layers deeper**.
""",

    "Signpost": """
The location contains a partially destroyed map or signpost.

PCs get **+1 on their next exploration roll** starting from this location.
""",

    "Signs of Recent Passage": """
Something was here not long ago.

Roll on the encounter table to determine what left its mark.

The next random encounter near this location should involve that creature.
""",

    "Slime Fungus": """
The floor is extremely sticky, producing a smacking sound with every step.

All creatures move as if suffering a minor leg wound unless flying or ceiling-climbing.
""",

    "Treasure Pile": """
Something valuable lies here in plain sight—making every gravedigger suspicious.

Roll on the treasure table for the item.

The first random encounter rolled here gets **+1**.

Whatever appears is guarding the treasure and may attempt an ambush.
""",

    "Vault": """
The location is locked behind a strong iron or stone door.

PCs cannot see inside, but a weathered sign might give a hint.

To enter, the lock must be picked or bypassed.  
Halve rolls relying on brute force.

Inside, PCs get **+1 to find treasure**.
""",

    "Vermin": """
The place is crawling with rats or bugs.
""",

    "Wet": """
Water drips from the ceiling, forming large puddles on the floor.

Every surface is damp.
""",
}
