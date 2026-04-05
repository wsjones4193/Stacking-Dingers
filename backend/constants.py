"""
Hardcoded constants for The Dinger tournament on Underdog Fantasy.
These values are authoritative and inform all calculations in the app.
"""

from datetime import date

# ---------------------------------------------------------------------------
# Roster structure
# ---------------------------------------------------------------------------

ROSTER_SLOTS = {
    "P": 3,
    "IF": 3,
    "OF": 3,
    "FLEX": 1,   # IF or OF only — pitchers never eligible
    "BENCH": 10,
    "TOTAL": 20,
}

FLEX_ELIGIBLE_POSITIONS = {"IF", "OF"}

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

HITTER_SCORING = {
    "single": 3,     # 1B (derived: H - 2B - 3B - HR)
    "double": 6,     # 2B
    "triple": 8,     # 3B
    "home_run": 10,  # HR
    "rbi": 2,
    "run": 2,        # R
    "stolen_base": 4,
    "walk": 3,       # BB
    "hit_by_pitch": 3,  # HBP
}

PITCHER_SCORING = {
    "inning_pitched": 3,   # per full inning
    "strikeout": 3,
    "win": 5,
    "quality_start": 5,
    "earned_run": -3,
}

# Quality start definition: >= 6.0 IP and <= 3 ER in the same game appearance
QS_MIN_IP = 6.0
QS_MAX_ER = 3

# ---------------------------------------------------------------------------
# Tournament structure
# ---------------------------------------------------------------------------

TOURNAMENT_NAME = "The Dinger"

ROUND_CONFIG = {
    1: {"weeks": list(range(1, 19)), "group_size": 12, "advance": 2},
    2: {"weeks": [19, 20],          "group_size": 8,  "advance": 1},
    3: {"weeks": [21, 22],          "group_size": 9,  "advance": 1},
    4: {"weeks": [23, 24],          "group_size": 217, "advance": None},  # Finals
}

TOTAL_ENTRIES_2026 = 93_744
TOTAL_R1_GROUPS_2026 = 7_812
ENTRY_FEE_2026 = 15
MAX_ENTRIES_PER_USER_2026 = 150

# ---------------------------------------------------------------------------
# Season calendar — 2026
# ---------------------------------------------------------------------------

# Each entry: (week_number, start_date, end_date, round_number)
SEASON_WEEKS_2026 = [
    (1,  date(2026, 3, 25), date(2026, 3, 29),  1),
    (2,  date(2026, 3, 30), date(2026, 4, 5),   1),
    (3,  date(2026, 4, 6),  date(2026, 4, 12),  1),
    (4,  date(2026, 4, 13), date(2026, 4, 19),  1),
    (5,  date(2026, 4, 20), date(2026, 4, 26),  1),
    (6,  date(2026, 4, 27), date(2026, 5, 3),   1),
    (7,  date(2026, 5, 4),  date(2026, 5, 10),  1),
    (8,  date(2026, 5, 11), date(2026, 5, 17),  1),
    (9,  date(2026, 5, 18), date(2026, 5, 24),  1),
    (10, date(2026, 5, 25), date(2026, 5, 31),  1),
    (11, date(2026, 6, 1),  date(2026, 6, 7),   1),
    (12, date(2026, 6, 8),  date(2026, 6, 14),  1),
    (13, date(2026, 6, 15), date(2026, 6, 21),  1),
    (14, date(2026, 6, 22), date(2026, 6, 28),  1),
    (15, date(2026, 6, 29), date(2026, 7, 5),   1),
    (16, date(2026, 7, 6),  date(2026, 7, 12),  1),
    (17, date(2026, 7, 13), date(2026, 7, 26),  1),  # 2-week span
    (18, date(2026, 7, 27), date(2026, 8, 2),   1),
    (19, date(2026, 8, 3),  date(2026, 8, 9),   2),
    (20, date(2026, 8, 10), date(2026, 8, 16),  2),
    (21, date(2026, 8, 17), date(2026, 8, 23),  3),
    (22, date(2026, 8, 24), date(2026, 8, 30),  3),
    (23, date(2026, 8, 31), date(2026, 9, 6),   4),
    (24, date(2026, 9, 7),  date(2026, 9, 13),  4),
]

# Lookup: week_number → (start_date, end_date, round_number)
WEEK_MAP_2026: dict[int, tuple[date, date, int]] = {
    w: (s, e, r) for w, s, e, r in SEASON_WEEKS_2026
}

# Consecutive playoff window pairs (used for peak 2-week ceiling analysis)
PLAYOFF_WEEK_PAIRS = {
    2: (19, 20),
    3: (21, 22),
    4: (23, 24),
}

# Season start / end
SEASON_START_2026 = date(2026, 3, 25)
SEASON_END_2026 = date(2026, 9, 13)

# Round transition weeks (end of these weeks = advancement check)
ROUND_TRANSITION_WEEKS = [18, 20, 22]

# ---------------------------------------------------------------------------
# Calendar events (approximate — update as official dates confirmed)
# ---------------------------------------------------------------------------

ALL_STAR_BREAK_2026 = (date(2026, 7, 13), date(2026, 7, 17))  # approximate
TRADE_DEADLINE_2026 = date(2026, 7, 31)  # approximate
SEPTEMBER_CALLUPS_2026 = date(2026, 9, 1)

# ---------------------------------------------------------------------------
# Draft archetype thresholds (rule-based binning for Module 3)
# ---------------------------------------------------------------------------

ARCHETYPE_RULES = {
    "p_heavy":  {"min_p_in_rounds_1_to_4": 2},
    "if_heavy": {"min_if_in_first_5_picks": 3},
    "of_heavy": {"min_of_in_first_5_picks": 3},
    "late_p":   {"first_p_round_min": 8},
    # balanced = none of the above
}

# ---------------------------------------------------------------------------
# BPCOR / value blend weights by week range
# ---------------------------------------------------------------------------

# How much weight to give projections vs. actual BPCOR when blending
# Format: {week_number: projection_weight}  (actual_weight = 1 - proj_weight)
PROJECTION_BLEND_WEIGHTS = {
    **{w: 1.0 for w in range(1, 5)},    # weeks 1-4: 100% projections
    5:  0.8,
    6:  0.6,
    **{w: 0.3 for w in range(7, 13)},   # weeks 7-12: 30% projections
    **{w: 0.1 for w in range(13, 25)},  # weeks 13+: 10% projections
}

# ---------------------------------------------------------------------------
# Projected draft rate — season weighting (most recent season first)
# ---------------------------------------------------------------------------

DRAFT_RATE_SEASON_WEIGHTS = [0.40, 0.30, 0.20, 0.10]  # up to 4 prior seasons

# ---------------------------------------------------------------------------
# Historical data integrity
# ---------------------------------------------------------------------------

# All advance rate calculations use top-2-of-12 for R1,
# regardless of wildcard rules in prior tournament formats.
R1_ADVANCE_COUNT = 2
R1_GROUP_SIZE = 12

# ---------------------------------------------------------------------------
# Roster flag thresholds
# ---------------------------------------------------------------------------

GHOST_PLAYER_DAYS = 10          # 0 games in last N days = ghost player warning
BELOW_REPLACEMENT_WEEKS = 3     # 0 BPCOR for N consecutive weeks = advisory
PITCHER_BAD_ERA_THRESHOLD = 6.0 # consecutive starts above this ERA = advisory
HITTER_USAGE_DECLINE_PCT = 0.25 # AB/PA drops >25% vs season avg = advisory

# ---------------------------------------------------------------------------
# ADP peer group window
# ---------------------------------------------------------------------------

ADP_PEER_RANGE = 3  # ±3 position rank slots for peer group comparisons

# ---------------------------------------------------------------------------
# Sample size thresholds (History Browser universal rule)
# ---------------------------------------------------------------------------

MIN_SAMPLE_SIZE = 10
LOW_CONFIDENCE_THRESHOLD = 30
