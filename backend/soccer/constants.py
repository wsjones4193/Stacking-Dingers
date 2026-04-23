"""
Constants for The World Pup — Underdog Fantasy 2026 World Cup bestball tournament.
"""

from datetime import date

# ---------------------------------------------------------------------------
# Roster structure
# ---------------------------------------------------------------------------

ROSTER_SLOTS = {
    "GK":    1,
    "DEF":   1,
    "MID":   1,
    "FWD":   2,
    "FLEX":  1,   # Any outfield position (DEF/MID/FWD)
    "BENCH": 6,
    "TOTAL": 12,
}

# Positions eligible to fill the FLEX slot
FLEX_ELIGIBLE_POSITIONS = {"DEF", "MID", "FWD"}

# Underdog position codes as they appear in the API
UNDERDOG_POSITION_MAP = {
    "G":  "GK",
    "D":  "DEF",
    "MD": "MID",
    "FW": "FWD",
}

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

# Applies to all players
ALL_PLAYER_SCORING = {
    "goals":              8.0,
    "assists":            4.0,
    "shots_on_target":    2.0,
    "shots_off_target":   1.0,
    "chances_created":    1.0,
    "crosses":            0.75,
    "tackles_successful": 0.5,
    "passes_successful":  0.05,
}

# Goalkeeper-only bonuses/penalties
GK_SCORING = {
    "saves":          2.0,
    "penalty_saves":  3.0,
    "goals_conceded": -2.0,
    "win":            5.0,
}

# GK and DEF bonus
GK_DEF_SCORING = {
    "clean_sheet": 5.0,
}

# ---------------------------------------------------------------------------
# Tournament structure
# ---------------------------------------------------------------------------

TOURNAMENT_NAME = "The World Pup"

# World Cup 2026 has 48 teams — R32 is new
# Round numbers map to World Cup stages
ROUND_CONFIG = {
    1: {"label": "Group Stage",  "group_size": 6,   "advance": 2},
    2: {"label": "R32 + R16",    "group_size": 8,   "advance": 1},
    3: {"label": "QF + SF",      "group_size": 5,   "advance": 1},
    4: {"label": "Final",        "group_size": 235, "advance": None},
}

# Total entries
TOTAL_ENTRIES = 28_200
TOTAL_R1_GROUPS = 4_700   # 28200 / 6
ENTRY_FEE = 10
MAX_ENTRIES_PER_USER = 150

# 3rd place game does NOT count toward scoring
THIRD_PLACE_COUNTS = False

# ---------------------------------------------------------------------------
# World Cup 2026 stage dates (approximate — update as official schedule confirmed)
# 2026 World Cup: June 11 – July 19, 2026 (USA/Canada/Mexico)
# ---------------------------------------------------------------------------

WC_STAGE_DATES = {
    "group":  (date(2026, 6, 11), date(2026, 7, 2)),
    "r32":    (date(2026, 7, 4),  date(2026, 7, 7)),
    "r16":    (date(2026, 7, 9),  date(2026, 7, 12)),
    "qf":     (date(2026, 7, 15), date(2026, 7, 18)),
    "sf":     (date(2026, 7, 21), date(2026, 7, 23)),
    "final":  (date(2026, 7, 26), date(2026, 7, 26)),
}

# Stages that count per tournament round
ROUND_STAGES = {
    1: ["group"],
    2: ["r32", "r16"],
    3: ["qf", "sf"],
    4: ["final"],
}

# ---------------------------------------------------------------------------
# National teams in the 2026 World Cup (48 teams)
# ---------------------------------------------------------------------------

WORLD_CUP_TEAMS = [
    # CONCACAF (automatically qualified)
    "United States", "Mexico", "Canada",
    # South America (CONMEBOL)
    "Brazil", "Argentina", "Colombia", "Uruguay", "Ecuador",
    "Venezuela", "Paraguay", "Bolivia", "Chile",
    # Europe (UEFA)
    "France", "England", "Spain", "Germany", "Portugal",
    "Netherlands", "Italy", "Belgium", "Croatia", "Switzerland",
    "Austria", "Denmark", "Turkey", "Poland", "Czech Republic",
    "Hungary", "Serbia", "Slovakia", "Romania", "Ukraine",
    "Albania", "Georgia", "Greece",
    # Africa (CAF)
    "Morocco", "Nigeria", "Senegal", "Egypt", "Cameroon",
    "South Africa", "DR Congo", "Mali", "Algeria", "Tunisia",
    "Ghana",
    # Asia (AFC)
    "Japan", "South Korea", "Saudi Arabia", "Australia",
    "Iran", "Qatar",
    # Oceania/CONCACAF qualifiers (approximate)
    "Panama", "Costa Rica",
]

# ---------------------------------------------------------------------------
# Sample size thresholds (shared with MLB app)
# ---------------------------------------------------------------------------

MIN_SAMPLE_SIZE = 5
LOW_CONFIDENCE_THRESHOLD = 20

# ---------------------------------------------------------------------------
# ADP scraper config
# ---------------------------------------------------------------------------

UNDERDOG_API_BASE = "https://api.underdogfantasy.com"
UNDERDOG_TOURNAMENT_SLUG = "world-pup-2026"   # update once confirmed
