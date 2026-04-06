# MLB Best Ball Hub — Full App Specification

**Project Folder:** `C:\Users\wsjon\OneDrive\Stacking Dingers\Website`

---

## Overview

A public web application for MLB best ball drafters on Underdog Fantasy. Users can research players, analyze their own teams, explore ADP trends, and dig into historical strategy data. Free and publicly accessible — no login required to browse, searchable by Underdog username to find teams.

**Stack:** Python (FastAPI) backend + React (Vite) frontend  
**Storage:** SQLite for relational/draft data + Parquet for game log stats  
**Data sources:** MLB Stats API, Underdog CSV exports, Steamer/ATC preseason projections

### Underdog Source Data

| Season | URL |
|---|---|
| 2026 | Not yet available |
| 2025 | https://underdognetwork.com/baseball/analysis/mlb-best-ball-downloadable-pick-by-pick-data |
| 2024 | https://underdognetwork.com/baseball/analysis/the-dinger-2024-downloadable-pick-by-pick-data |
| 2023 | https://underdognetwork.com/baseball/analysis/downloadable-fantasy-baseball-pick-by-pick-data-the-dinger-2023 |
| 2022 | https://underdognetwork.com/baseball/news-and-lineups/downloadable-fantasy-baseball-pick-by-pick-data-the-dinger-2022 |

**Data freshness:** Nightly ETL during the season

---

## Contest Rules (Hardcoded)

All business logic is built around **The Dinger** tournament on Underdog Fantasy.

### Roster Structure

| Slot | Count |
|---|---|
| P (pitcher) | 3 |
| IF (infielder) | 3 |
| OF (outfielder) | 3 |
| FLEX (IF or OF only) | 1 |
| BENCH | 10 |
| **Total** | **20** |

**Position rules:**
- Players have exactly one position: P, IF, or OF. No multi-eligibility.
- IF and OF players are eligible for the FLEX slot. Pitchers are never eligible for FLEX.
- Each week, Underdog auto-sets the lineup by selecting the highest-scoring valid combination across slots.
- Weekly lineup optimizer: 3 best P scores + 3 best IF scores + 3 best OF scores + 1 best remaining IF or OF score (FLEX). Bench players not in the top slot-filling combination contribute zero.

### Tournament Structure (The Dinger 2026)

- Entry fee: $15, max 150 entries per user
- Total entries: 93,744 across 7,812 Round 1 groups
- Round 1: Weeks 1–18, 12-person groups, top 2 advance
- Round 2: Weeks 19–20, 8-person groups, top 1 advances
- Round 3: Weeks 21–22, 9-person groups, top 1 advances
- Round 4 (Finals): Weeks 23–24, 217-person group, prize payouts to all finalists

### Season Calendar (Hardcoded)

| Week | Start | End | Round |
|---|---|---|---|
| 1 | 3/25/2026 | 3/29/2026 | Round 1 |
| 2 | 3/30/2026 | 4/5/2026 | Round 1 |
| 3 | 4/6/2026 | 4/12/2026 | Round 1 |
| 4 | 4/13/2026 | 4/19/2026 | Round 1 |
| 5 | 4/20/2026 | 4/26/2026 | Round 1 |
| 6 | 4/27/2026 | 5/3/2026 | Round 1 |
| 7 | 5/4/2026 | 5/10/2026 | Round 1 |
| 8 | 5/11/2026 | 5/17/2026 | Round 1 |
| 9 | 5/18/2026 | 5/24/2026 | Round 1 |
| 10 | 5/25/2026 | 5/31/2026 | Round 1 |
| 11 | 6/1/2026 | 6/7/2026 | Round 1 |
| 12 | 6/8/2026 | 6/14/2026 | Round 1 |
| 13 | 6/15/2026 | 6/21/2026 | Round 1 |
| 14 | 6/22/2026 | 6/28/2026 | Round 1 |
| 15 | 6/29/2026 | 7/5/2026 | Round 1 |
| 16 | 7/6/2026 | 7/12/2026 | Round 1 |
| 17 | 7/13/2026 | 7/26/2026 | Round 1 (2 weeks) |
| 18 | 7/27/2026 | 8/2/2026 | Round 1 |
| 19 | 8/3/2026 | 8/9/2026 | Round 2 |
| 20 | 8/10/2026 | 8/16/2026 | Round 2 |
| 21 | 8/17/2026 | 8/23/2026 | Round 3 |
| 22 | 8/24/2026 | 8/30/2026 | Round 3 |
| 23 | 8/31/2026 | 9/6/2026 | Round 4 |
| 24 | 9/7/2026 | 9/13/2026 | Round 4 |

**Calendar events affecting app display:**
- **All-Star break:** Flag on timeline, exclude from per-game pace calculations
- **Trade deadline:** Flag on player pages — surface as contextual note near deadline week
- **Round transitions (end of Weeks 18, 20, 22):** Highlight in team views, show advancement status prominently
- **September call-ups:** Flag expanded rosters as a context note on player availability

### Tie-Breaking Rules

- **Advancement rounds:** Highest single-player score in that round wins. If equal, cascade to 2nd highest, then 3rd, etc. If still tied, earlier entry date wins.
- **Finals (Round 4):** Tied entries split the combined prize pool for the finishing positions they occupy.

---

## Scoring System

### Hitters

| Category | Points |
|---|---|
| 1B | 3 |
| 2B | 6 |
| 3B | 8 |
| HR | 10 |
| RBI | 2 |
| R | 2 |
| SB | 4 |
| BB | 3 |
| HBP | 3 |

Note: 1B is derived as `H - 2B - 3B - HR`

### Pitchers

| Category | Points |
|---|---|
| IP | 3 |
| K | 3 |
| W | 5 |
| QS | 5 |
| ER | -3 |

Note: QS is derived from game logs — `qs_flag = 1 if ip >= 6.0 and er <= 3 else 0`

### Dual-Score Approach

- **Primary score:** Calculated from raw MLB Stats API game logs
- **Check score:** Underdog's reported score (from CSV exports)
- **Discrepancy rule:** Differences logged silently to `score_audit` table — not shown to regular users. Admin-only debug view exposes all discrepancies.

---

## Core Business Logic

### Weekly Lineup Setting Algorithm

Given a roster of 20 players and their individual game scores for a given week:

1. Separate players by position: `pitchers[]`, `infielders[]`, `outfielders[]`
2. Sort each group by weekly score descending
3. Starters = top 3 P + top 3 IF + top 3 OF
4. FLEX candidates = remaining IF + remaining OF (not already starting)
5. FLEX starter = highest scorer among FLEX candidates
6. Weekly team score = sum of 3P + 3IF + 3OF + 1FLEX
7. Bench = all players not selected as starters or FLEX

This algorithm must be reproducible for any historical week given game log data.

### Replacement Level Definition

Replacement level is calculated **per-roster, per-week** — not a league-wide constant.

- **Hitter replacement level:** Score of the highest-scoring bench IF or OF not used as starter or FLEX that week
- **Pitcher replacement level:** Score of the highest-scoring bench P not used as a starter that week

### Best Ball Points Contributed Over Replacement (BPCOR)

BPCOR is the central metric of this app. It measures how much a player actually contributed above the alternative on their specific roster.

**Two levels of BPCOR:**

*Team-level BPCOR* is calculated per-roster, per-week using that specific team's bench as the replacement bar. This is the primary calculation — it reflects how much a player contributed to that team's success given the roster around them. The same player can have different BPCOR figures on different rosters in the same week depending on bench depth.

*Tournament-level BPCOR* aggregates a player's team-level BPCOR contributions across all rosters that drafted them in a given tournament, then averages to produce a single player-level figure representing their value across the full tournament population.

**Calculation:**

```
contributed_score = player's score if they started or played FLEX, else 0
replacement_score = that week's replacement level for their position group
weekly_BPCOR = max(0, contributed_score - replacement_score)

Season BPCOR = sum of weekly_BPCOR across all weeks
```

- Hitter replacement: score of the highest-scoring bench IF or OF not used as starter or FLEX that week
- Pitcher replacement: score of the highest-scoring bench P not used as a starter that week
- Replacement level is calculated within each individual roster

**What BPCOR is and isn't:**
- It is a measure of in-season contribution given actual roster construction
- It is **not** a measure of draft value (that's Value vs. ADP)
- It is **not** a measure of raw production (that's scoring trajectory)
- A player can have high raw scoring but low BPCOR if they never cracked the lineup on a deep roster — and vice versa

BPCOR is calculated separately for pitchers and hitters, but a pitcher's BPCOR can be compared to a hitter's.

**Where BPCOR is used:**
- **Player Hub:** average tournament-level BPCOR — the primary production metric to analyze and visualize
- **Team Analyzer:** actual team-level BPCOR shown per player in the roster table, alongside total roster points
- **Roster flags:** flag when a player has had zero BPCOR for 3 consecutive weeks (player is not hitting the lineup)

The relationship: team-level BPCOR is the input; tournament-level BPCOR is the output used for cross-player analysis. A player who appears on 5,000 rosters produces 5,000 individual weekly BPCOR figures — tournament-level BPCOR is derived from aggregating those.

**Tournament average BPCOR by player** is a dedicated view (accessible from the ADP Explorer and Player Hub) that ranks all drafted players by their average BPCOR contribution per roster that drafted them. This answers the core draft asset question: which players, regardless of where they were drafted, delivered the most best ball value across the tournament? This is the closest thing to a definitive "most valuable players" leaderboard for a given season.

### ADP Benchmark Peer Group

- Same position (P, IF, or OF)
- Drafted within ±3 position rank slots at that position
- Example: 12th IF by ADP → compared to IFs ranked 9th–15th by ADP

### Roster Flags

Flags surface on two levels simultaneously:

**Team summary level:** A position × flag matrix table appears on every team summary card. Rows are flag types, columns are position groups (P / IF / OF). Each cell shows a count of players at that position currently triggering that flag. Empty cells are blank, not zero. This lets a user scan team health in seconds without reading a full roster.

**Player level:** Within the full team page roster table, each player row shows their individual active flags inline. Clicking a flag shows the specific threshold that triggered it.

**Design rule — no nuisance flags:** Every flag is calibrated.

| Flag | Severity | Trigger | Level |
|---|---|---|---|
| Position wiped | Critical | Not enough active scoring players at a position slot to fill out the roster | Position |
| Ghost player | Warning | A player has 0 games in the last 10 days, not on IL — unknown availability | Player |
| Below replacement | Advisory | Player's BPCOR over the last 3 weeks is zero (has not contributed to the team) | Player |
| Pitcher trending wrong | Advisory | Consecutive starts with ERA > 6.00 | Player |
| Hitter usage decline | Advisory | A hitter's AB/PA over the last 10 days has declined more than 25% vs. their season average — signals platoon or benching | Player |

Multiple flags can coexist on the same player. Critical overrides Warning in the position summary display but both are shown. Advisory flags are additive — a player can carry multiple advisories.

### Advancement Probability

- **Round 1:** finish top 2 of 12 in group
- **Round 2+:** finish top 1 of group
- Display: "X pts behind 2nd" or "X pts ahead of cutline" with weeks remaining
- Probability: simplified percentile-based simulation using current rank, points gap, and historical weekly score variance

---

## Data Pipeline

### MLB Stats API (nightly)

- Library: `mlb-statsapi` (Python)
- Hitter fields: PA, AB, H, 2B, 3B, HR, R, RBI, SB, BB, HBP (derive 1B = H - 2B - 3B - HR)
- Pitcher fields: IP, ER, SO (K), W (decision) — derive QS per game
- Also pull: roster data (positions), IL transactions
- Store: Parquet partitioned by season — `data/gamelogs/{season}.parquet`

### Underdog CSV Exports (one-time load per season)

- Draft pick data: tournament name, draft_id, pick_number, round, player_id, player name, username, draft_date
- Store: SQLite `bestball.db`
- 2026 CSV: ingest when Underdog publishes (same pipeline, season=2026)

### Projections (Steamer + ATC via Fangraphs)

- Pre-season: daily downloads during spring; final snapshot on Opening Day is canonical for ADP value calculations
- In-season: nightly RoS projection updates for "rest of season outlook" and mid-season value blend
- Store: `projections` table with `source` = `steamer`, `steamer_ros`, `atc`, `atc_ros`

### Player ID Mapping

- **Underdog is the authoritative player pool** — MLB players not in Underdog's pool are irrelevant
- Auto-match: fuzzy-match Underdog player names vs. MLB Stats API names at ingest (using `rapidfuzz`)
- Store in `player_id_map` table with `confirmed = False` for fuzzy matches
- **Unmatched Underdog players:** remain in all data (picks, ADP, ownership, etc.); fields requiring MLB game log data display "N/A" until mapped
- Admin page for manual review, correction, and confirmation of matches

### SQLite Schema (bestball.db)

| Table | Key Columns |
|---|---|
| `players` | player_id, name, position (P/IF/OF), mlb_team, underdog_id, mlb_id |
| `drafts` | draft_id, draft_date, entry_type, username, draft_position (1–12), season |
| `picks` | pick_id, draft_id, pick_number, round_number, player_id, username |
| `weekly_scores` | team_id, week_number, season, player_id, raw_score, calculated_score |
| `adp_snapshots` | player_id, snapshot_date, adp, draft_rate, projected_draft_rate, projected_daily_picks, season |
| `projections` | player_id, season, source, projected_points, projected_pa_or_ip, captured_date |
| `groups` | group_id, round, season, team_ids (JSON array) |
| `group_standings` | group_id, team_id, round, total_points, rank, advanced (bool) |
| `score_audit` | player_id, week, season, calculated_score, underdog_score, delta |
| `team_season_profiles` | team_id, season, peak_2wk_score, peak_window_weeks, consistency_score, ceiling_tier, round_reached, r2_score, r3_score, r4_score |
| `draft_sequences` | draft_id, season, pick_sequence (JSON array), archetype_tag, advance_round |
| `roster_flags` | team_id, week, player_id, flag_type, flag_reason |
| `player_id_map` | underdog_id, mlb_id, underdog_name, mlb_name, confirmed (bool), season |
| `combo_projections` | player_a_id, player_b_id, player_c_id (nullable), season, support, confidence, lift, projected_pair_count, pair_rate |
| `articles` | article_id, title, author, published_date, content_html, excerpt, thumbnail_url, slug, created_at, updated_at |
| `podcast_episodes` | episode_id, youtube_id (unique), title, published_date, description, thumbnail_url, duration_seconds |

### Parquet Files

- `data/gamelogs/{season}.parquet` — one row per player-game: date, player_id, position, all stat columns, calculated_points, qs_flag
- `data/adp_history/{season}.parquet` — daily ADP snapshots for trend charting

### Nightly ETL (~2am ET, GitHub Actions, March–September)

1. Pull previous day's game logs from MLB Stats API
2. Calculate best ball points per player-game
3. Append to season Parquet
4. Recalculate weekly scores for any week that just closed
5. Recalculate ADP from latest draft data; append to `adp_snapshots`
6. Update `roster_flags`: IL status, games-played recency, BPCOR streak, pitcher ERA trend, hitter usage decline
7. Update `group_standings` for all active groups
8. Recompute `team_season_profiles` for current season teams
9. Sync YouTube RSS feed → upsert new podcast episodes into `podcast_episodes`
10. Log run status + any score audit discrepancies

---

## Feature Specifications

### 1. Player Hub

The Player Hub has two distinct modes toggled at the top of the page: **Draft Season** and **In-Season**. The app detects the current date relative to the season calendar and defaults to the appropriate mode automatically, but users can always toggle manually. During the off-season, Draft Season mode is the default.

---

#### Draft Season Mode (pre-March 25, or manually selected)

Focused on draft research. All data is historical — prior season and tournament performance, preseason projections, ADP trends from the current and prior tournaments.

**Above the fold:**
- Player name, position, MLB team
- Current ADP + projected draft rate %
- ADP trend chart: how ADP has moved across the draft window (early drafts → latest drafts, filterable date range), with prior season ADP available for context

**Draft profile panel:**
- ADP by date range
- Positional rank by ADP (e.g., "IF12") and peer group (IFs 9–15 by ADP)
- Historical ADP accuracy: was this player over or undervalued at this ADP in prior seasons?
- Projected ownership concentration: players projected to have the highest combinatorial ownership with this player

**Historical performance panel:**
- Prior season(s) BPCOR, scoring trajectory, advance rate on teams that rostered them
- Link to History Browser Module 6 (player historical profile)

---

#### In-Season Mode (March 25 onward, or manually selected)

Focused on current season monitoring.

**Above the fold:**
- Player name, position, MLB team
- Availability strip: IL status badge + games missed + days since last game
- Scoring trajectory chart (prominent, default view)

**Scoring trajectory chart:**
- Default: game-by-game bar chart
- Toggle: cumulative season total | weekly best ball score | game-by-game bars
- Hot/cold window: last 10 days highlighted as a distinct band
- Round transitions shown as vertical markers
- Active player-level flags shown as icons on the timeline at the relevant date

**ADP trend panel (in-season context):**
- ADP is fixed once the season starts; this panel shows the draft-window trend for context only, not live movement

**Value vs. ADP panel:**
- Actual BPCOR (season to date) vs. other players at same position in ADP peer group
- Value score = actual total points − projected total points (full-season projections prorated for season progress), color coded (green = value, red = bust)

**Ownership panel:**
- Overall ownership % across all drafts
- Ownership % of advancing teams

**Roster context:**
- "On X teams" count + drill-down list linking to Team Analyzer

---

### 2. Team Analyzer

**Entry point:** Search by Underdog username → paginated team list (10/page).

**Team summary card:**
- Team name / draft date / draft position
- Current round + group rank
- Total points scored
- Gap-to-advance: "Need X more pts to reach 2nd" (R1) or "X pts behind 1st" (R2+), weeks remaining
- Roster strength score (0–100 normalized + percentile)
- Advancement probability %
- Position × flag matrix (rows = flag types, columns = P/IF/OF; cell = count of players triggering that flag)

**Roster strength score:**
- Sum of each rostered player's BPCOR relative to their ADP-expected BPCOR
- Normalized 0–100 vs. all teams in dataset
- Displayed as number + percentile ("72nd percentile roster")

**Team page — full view:**

*Round progress section:*
- Visual timeline of rounds with current position marked
- Weekly score bar chart (color-coded by round)
- Group standings table: all 12/8/9 teams, points, rank, gap

*Roster diagnostic section:*
- Full 20-player table: name, position, slot (starter/flex/bench), last week score, season total, BPCOR, IL status, inline flags
- Flag severity legend

*Weekly breakdown section:*
- Per completed week: auto-set lineup (3P + 3IF + 3OF + 1FLEX), bench, total score
- Highlight highest-scoring bench player each week ("left points on bench")

**Public leaderboard:**
- All teams, searchable by username
- Sortable: total points, current rank, advancement probability, roster strength score
- Filterable: round (R1/R2/R3/R4), draft date range, draft position (1–12)

---

### 3. ADP Explorer

**Shared filters (persistent, all views):**
Season, draft date range, draft position (1–12), position (P/IF/OF/All), entry type

**View 1 — ADP vs. actual production rank:**
- Scatter plot: X = ADP rank, Y = actual BPCOR rank
- Points above diagonal = beat their slot (value); below = underperformed (bust)
- Click any dot → player page
- Highlight top 10 value picks and top 10 busts

**View 2 — ADP movement over draft window:**
- Line chart: ADP evolution from first to last drafts
- One line per player (filterable to specific players or positions)
- Identifies "early market" vs. "late market" consensus shifts

**View 3 — Positional scarcity curves:**
- Per position: pick number (X) vs. BPCOR drop-off (Y)
- Shows where "the cliff" is for each position
- Overlay current season vs. prior season

*Tournament average BPCOR by player view is also accessible from the ADP Explorer — ranks all drafted players by average BPCOR contribution per roster. The "most valuable players" leaderboard for a given season.*

---

### 4. History Browser

**Landing page:** Dashboard with 6 module cards, each showing a headline finding and "Explore →" link. Every module is designed to surface shareable findings that work as both user insights and content.

**Global filter bar:** Season(s), draft date range, draft position (seat 1–12)

**Universal sample size rule:** Min 10 instances to surface any finding. 10–29 instances → low-confidence flag. 30+ → display normally. Applies to combos, stacks, draft structures, and all segmented analysis.

---

#### Module 1 — Consecutive Week Ceiling Analysis

The core question: which roster profiles are built to peak vs. built for a strong floor; what rosters are built to peak in the money rounds of the tournament?

**2-week window definition:** A 2-week window is exactly Week N score + Week N+1 score using the tournament calendar — not two consecutive calendar weeks, and not a rolling 14-day window. Each scoring week runs from its official start date to its official end date. Scoring for each week is computed by the weekly lineup setter algorithm independently before summing — there is no combined 14-day lineup optimization. This mirrors the playoff structure precisely: Round 2 = weeks 19+20, Round 3 = weeks 21+22, Round 4 = weeks 23+24.

**Definitions:**
- *Peak window:* Highest combined 2-week score a team achieves from any consecutive week pair during the season
- *Playoff windows:* R2 = weeks 19–20, R3 = weeks 21–22, R4 = weeks 23–24
- *Ceiling tiers (three cuts):* top 1% by peak 2-week score, top 10%, advancing teams only (R2/R3/R4 qualifiers)

**Peak window distribution:**
- Histogram of peak 2-week scores for all historical teams, cut by various dimensions (roster structure, ADP value gained/lost, stacking, etc.), with the three tier thresholds overlaid
- Show which weeks of the season teams most commonly achieved their peak — is there a hot-month effect?
- Year-over-year comparison of peak score distributions by cut

**Grinder vs. peaker profiles:**
- Consistency score: standard deviation of weekly scores across the season (low SD = grinder, high SD = peaker)
- Ceiling score: peak 2-week score
- Quadrant chart: high ceiling + high consistency (ideal) / high ceiling + low consistency (boom/bust) / low ceiling + high consistency (safe floor) / low ceiling + low consistency (avoid)
- Show advance rate for each quadrant
- Show which roster construction types populate each quadrant (connects to Modules 2 and 3)

**Playoff window breakdown:**
- Per playoff round: distribution of scores among all teams that reached it
- What score was needed to advance out of each round historically?
- How does R1 weekly consistency vs. ceiling predict R2/R3/R4 performance?

**Backend:** Compute `peak_2wk_score`, `peak_window_weeks`, `consistency_score` (weekly score std dev), `ceiling_tier` for all historical teams → store in `team_season_profiles`

---

#### Module 2 — Stacking Analysis

Two fundamentally different stack types — hitter stacks and pitcher stacks — tracked separately because they represent different strategic theories.

**Hitter stacks (correlated offensive upside):** Players from the same MLB lineup who score together when that offense erupts. A 2-hitter Yankees stack means two Yankees position players on the same best ball roster. When the lineup gets hot for a week, both players score big simultaneously, driving ceiling weeks.

**Pitcher stacks (same-team pitching depth):** Two or more pitchers from the same MLB team's rotation on the same roster. Does doubling down on one rotation's upside help or hurt? Two-start weeks are essential in MLB best ball — does stacking pitchers from good teams increase W and QS equity at the detriment of two-start week variance?

**Stack type toggle:** Hitters only / pitchers only / hitter + pitcher combined (same MLB team provides both a hitter stack and a pitcher).

**Stack size toggle:** Analysis supports 2+ player stacks. Defaults to 2 and 3 (most common), but 4, 5, 6, and 7 player stacks are tracked and surfaced when sample size permits (10+ instances). Users can set the minimum and maximum stack size they want to analyze.

**Metrics per stack:**
- Advance rate vs. tournament base advance rates
- Peak 2-week score rates vs. league average
- Which MLB teams were stacked most often
- Which MLB teams historically produce the best stack value
- Association-rule view: given a player is already drafted, which players show up most commonly on the same roster
- Weekly correlation: player-level correlation within the stack; identify the weeks with the best production

**Combined stacking:** Teams employing both an MLB hitter stack AND a positional concentration — do they amplify ceiling or amplify variance? Analyzed at season-long (R1→R2) and 2-week ceiling levels.

**Display:** Sortable table (advance rate, avg peak score, sample size, confidence flag); click any row → distribution of outcomes for teams with that stack.

---

#### Module 3 — Draft Structure Analysis

**View A — How positions were addressed:**
- Line chart: cumulative count of players drafted at a position (X axis) vs. advance rate (Y axis)
- Shows at what depth each position's advance rate starts to shift

**View B — Pick-by-pick positional sequencing:**
- Heatmap: pick number (X) × position (Y) × color = advance rate of teams making that choice at that pick
- Most common positional sequences for advancing teams vs. all teams
- Highest-leverage pick decisions: which picks show the most outcome variance by position choice?

**View C — Draft archetype × ceiling and advance rate:**
- Cluster historical rosters into draft archetypes based on positional sequencing
- Archetypes (rule-based binning):
  - **P-heavy:** 2+ P picks in rounds 1–4
  - **IF-heavy:** 3+ of first 5 picks = IF
  - **OF-heavy:** 3+ of first 5 picks = OF
  - **Balanced:** no position > 2 in first 5 picks, fewer than 2 P in rounds 1–4
  - **Late-P:** no P until round 8+
- Per archetype: advance rate, avg peak 2-week score, consistency score, quadrant distribution
- Year-over-year: are the same archetypes consistently winning, or does optimal structure shift?

**Backend:** Store pick-by-pick position sequence as JSON array in `draft_sequences`; tag archetype; join to team outcomes for all cross-tab calculations.

---

#### Module 4 — Player Combo Analysis

**Scope:** 2-player and 3-player combos. Min 10 co-occurrences. Low-confidence flag for 10–29.

**Two metrics per combo:**
1. **Advance rate delta:** (advance rate together) − (avg of separate advance rates). Positive = synergistic pairing.
2. **Ceiling correlation:** Week-by-week score correlation across all shared rosters. High positive = they peak together (amplify ceiling, compress floor). Low or negative = natural hedge (more consistent team score).

**Discovery views:**
- *Search mode:* Enter a player → see all significant combos ranked by advance rate delta and ceiling correlation. "I'm drafting Correa, who pairs well with him?"
- *Leaderboard mode:* Top combos by advance rate delta, filterable by position pairing and season
- *Anti-combo view:* Combos with negative advance rate delta ("avoid pairing" signals)

3-player combos use the same two metrics, displayed separately given lower sample sizes.

---

#### Module 5 — ADP Accuracy

- ADP vs. actual BPCOR by player, per season
- Biggest over-performers and under-performers vs. ADP expectation
- By ADP range: where is upside variance highest (take shots) vs. lowest (reliable floor)?
- Year-over-year consistency: do the same players beat ADP repeatedly?

---

#### Module 6 — Player Historical Profiles (Player Hub "Historical" tab)


- Per season: BPCOR, ADP, roster % overall, roster % on advancing teams, peak 2-week score, ceiling tier reached
- Year-over-year trend: consistent producer vs. boom/bust
- How did ADP change year-over-year relative to actual production?

---

### 7. Articles

A page for written analysis and strategy content authored by site admins.

**List view (`/articles`):**
- Grid of article cards: thumbnail image, title (links to detail view), author, published date, excerpt
- Paginated (most recent first)

**Detail view (`/articles/:slug`):**
- Full article rendered from stored HTML (`content_html`)
- Supports rich text: headings, bold/italic, tables, images

**Admin (Articles tab in `/admin`):**
- List of existing articles with Edit / Delete buttons
- Create/Edit form: title, author, date, excerpt, thumbnail URL, rich-text body editor (TipTap)
- Save → `POST /api/admin/articles` or `PATCH /api/admin/articles/{article_id}`

**API endpoints:**
- `GET /api/content/articles` — paginated list (title, author, date, excerpt, thumbnail_url, slug)
- `GET /api/content/articles/{slug}` — full article including content_html
- `POST /api/admin/articles` — create
- `PATCH /api/admin/articles/{article_id}` — update
- `DELETE /api/admin/articles/{article_id}` — delete

---

### 8. Podcasts

A page for The Stacking Dingers Show episodes, auto-synced from the YouTube channel (`@StackingDingers`).

**List view (`/podcasts`):**
- Header banner with links to Apple Podcasts and Spotify (static placeholder links until provided)
- Grid of episode cards: embedded YouTube player (inline, clickable to play), title hyperlinked to YouTube, published date, description excerpt
- Paginated (most recent first)

**YouTube sync:**
- Source: YouTube public RSS feed `https://www.youtube.com/feeds/videos.xml?channel_id=<CHANNEL_ID>`
- No API key required — Atom XML parsed with stdlib `xml.etree.ElementTree`
- Returns 15 most recent videos per sync
- Upsert on `youtube_id` — existing episodes are never duplicated
- Runs as step 9 of nightly ETL

**Admin (Podcasts tab in `/admin`):**
- "Sync from YouTube" button → `POST /api/admin/podcasts/sync`
- List of episodes with Delete button

**API endpoints:**
- `GET /api/content/podcasts` — paginated list, newest first
- `POST /api/admin/podcasts/sync` — trigger YouTube RSS sync
- `DELETE /api/admin/podcasts/{episode_id}` — remove episode

---

## Global App Rules

### Filtering

All four main views support: contest type, draft date range, draft position (1–12), position, season. Filters persist in session and are shareable via URL parameters.

### Projection Preference (No Login)

- System selector: Steamer / ATC / Blended (avg)
- Stored in `localStorage.projectionSystem` and reflected/overridden by `?proj=` URL param
- Default: Blended

### Data Display Rules

- All stats labeled with as-of date: "Data through [date]"
- Sample size warnings when fewer than 3 weeks of data available
- Calendar context (round transitions, All-Star break, trade deadline) shown as markers wherever timeline data appears

### Scoring Discrepancy Handling

- Calculated scores (from raw MLB Stats API) are the primary display value
- Discrepancies vs. Underdog reported scores logged silently to `score_audit`
- Admin/debug view (not public-facing) shows all logged discrepancies for formula validation

### Position Logic

- Players have exactly one position: P, IF, or OF
- No multi-position eligibility — Underdog's designation is authoritative
- FLEX slot: only IF and OF eligible; pitchers never FLEX-eligible

### Replacement Level

- Per-roster, per-week — not a league-wide constant
- Hitter replacement = highest-scoring bench IF or OF not used as starter or FLEX
- Pitcher replacement = highest-scoring bench P not used as starter
- Used in BPCOR calculation and advisory flag logic

### Projected Draft Rate

Calculated daily during the draft window. For each player on each day drafts are occurring:

```
projected_draft_rate = weighted average of historical draft rates at equivalent ADP
                       across prior tournaments
```

Weighting scheme across prior seasons (most recent first): 40% / 30% / 20% / 10%. If fewer than 4 seasons of data exist, redistribute weights proportionally across available seasons.

```
projected_picks_today = drafts_occurring_today × projected_draft_rate
```

This allows the ADP Explorer and Player Hub (draft season mode) to show not just current ADP but projected end-of-window ownership based on draft pace — useful for identifying players being drafted faster or slower than their historical rate at that ADP.

Stored in `adp_snapshots` table with `projected_draft_rate` and `projected_daily_picks` columns per snapshot date.

### Projected Combinatorial Ownership

Leverages ADP, position, and MLB team together to project how frequently two or three players will appear on the same roster. Displayed in the ADP Explorer and surfaced as context on individual player pages in draft season mode.

**Pair-level metrics (2-player):**
- *Pair rate:* % of rosters that drafted Player A also draft Player B, given both are being drafted. Sortable leaderboard of highest pair rates in the tournament.
- *Projected pair count:* total rosters × ownership rate A × ownership rate B × correlation adjustment (players at similar ADP cluster together more than random chance)
- Filterable by: position pairing (P+IF, OF+OF, etc.), MLB team (surfaces natural team stacks), ADP range

**3-player combinatorial view** (association rule mining):
- *Support:* % of all rosters containing all three players together (raw co-occurrence frequency)
- *Confidence:* given Player A and B are on a roster, how frequently is Player C also there?
- *Lift:* confidence ÷ expected rate if drafting were independent — lift > 1 means the trio appears together more than chance; lift < 1 means they are avoided together

These three measures identify: natural clusters (high support + high lift), positional archetypes (high confidence within a position group), and avoided combinations (low lift — drafters treat them as substitutes).

**Performance overlay** (connecting to History Browser Module 4): For historically observed combos with 10+ instances, show advance rate for that combo and ceiling week rate. This bridges projected combinatorial ownership (pre-season) with historical combo performance (research), giving drafters both "how common is this pairing" and "how has it performed."

Stored in `combo_projections` table: player_a_id, player_b_id, player_c_id (nullable), season, support, confidence, lift, projected_pair_count, pair_rate. Leverages prior tournaments to build the prediction model.

### Historical Data Integrity — Advance Rate Calculations

Prior Underdog tournaments used different advancement formats including wildcards not present in The Dinger's current structure. **All advance rate calculations for R1 must use top 2 of 12 advance.** Independently recalculate the top 2 teams that advance in R1 for all historical tournaments, ignoring the original wildcard or alternative advancement logic.

---

## Technical Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI |
| Data querying | pandas, DuckDB (Parquet), sqlite3 / SQLModel (SQLite) |
| ETL | Python scripts via GitHub Actions (nightly) |
| MLB data | `mlb-statsapi` Python library |
| Projections | Steamer + ATC (Fangraphs download) |
| Storage — relational | SQLite (`bestball.db`) |
| Storage — stats | Parquet (partitioned by season) |
| Frontend | React, Vite, TypeScript |
| Charts | Recharts |
| Deployment — backend | Railway (`stacking-dingers-production.up.railway.app`) |
| Deployment — frontend | Vercel (`stacking-dingers.vercel.app`) |
| Data delivery | S3 (`us-east-2`) for Parquet/SQLite; synced on startup and after nightly ETL |
| Rich-text editor | TipTap (admin article editor) |

---

## Repository Structure

```
/
├── backend/
│   ├── main.py                     # FastAPI app, CORS, router registration
│   ├── constants.py                # season calendar, roster slots, scoring weights
│   ├── routers/
│   │   ├── players.py
│   │   ├── teams.py
│   │   ├── adp.py
│   │   ├── history.py
│   │   ├── leaderboard.py
│   │   ├── content.py              # articles + podcasts public read endpoints
│   │   └── admin.py                # player mapping, score audit, article CRUD, podcast sync
│   ├── services/
│   │   ├── scoring.py              # raw stats → best ball points
│   │   ├── lineup_setter.py        # weekly lineup optimization
│   │   ├── bpcor.py                # team-level and tournament-level BPCOR
│   │   ├── adp_service.py          # ADP, projected draft rate, peer groups
│   │   ├── combo_service.py        # association rule mining, combinatorial ownership
│   │   ├── roster_flags.py         # all flag logic
│   │   └── advancement.py          # gap-to-advance, probability
│   ├── etl/
│   │   ├── game_logs.py            # MLB Stats API → Parquet
│   │   ├── draft_data.py           # Underdog CSV → SQLite
│   │   ├── projections.py          # Fangraphs Steamer/ATC → SQLite
│   │   ├── team_profiles.py        # peak windows, consistency, archetypes
│   │   └── youtube_sync.py         # YouTube RSS → podcast_episodes table
│   └── db/
│       ├── models.py               # SQLModel table definitions
│       ├── parquet_helpers.py      # DuckDB query helpers
│       └── player_mapping.py       # name-match + admin-maintained ID map
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── PlayerHub.tsx
│   │   │   ├── TeamAnalyzer.tsx
│   │   │   ├── ADPExplorer.tsx
│   │   │   ├── HistoryBrowser.tsx
│   │   │   ├── Leaderboard.tsx
│   │   │   ├── Articles.tsx        # article list + detail view
│   │   │   ├── Podcasts.tsx        # episode grid with inline YouTube embeds
│   │   │   └── Admin.tsx           # player mapping, score audit, article editor, podcast sync
│   │   ├── components/
│   │   └── hooks/
├── data/
│   ├── gamelogs/                   # {season}.parquet
│   ├── adp_history/                # {season}.parquet
│   ├── bestball.db
│   └── player_id_mapping.csv       # admin-maintained MLB ↔ Underdog ID map
├── scripts/
│   └── nightly_etl.py
└── .github/
    └── workflows/
        └── nightly_etl.yml
```

---

## Phase Roadmap

### Phase 1 — Data Foundation (build first, before any UI)

1. Set up SQLite schema and Parquet directory structure
2. Build MLB Stats API game log ingestion script
3. Build Underdog CSV ingestion and normalization script
4. Implement scoring calculator (raw stats → best ball points)
5. Implement weekly lineup setter algorithm
6. Implement BPCOR calculator (team-level and tournament-level)
7. Load historical data (2022–2025 seasons); recalculate R1 advancement as top 2 of 12 for all seasons
8. Validate calculated scores against Underdog outputs
9. Load preseason projections (Steamer + ATC)
10. Set up nightly ETL orchestration script
11. Compute `peak_2wk_score`, `consistency_score`, `ceiling_tier`, draft archetypes for all historical teams
12. Compute association rule metrics (support, confidence, lift) for all 2 and 3-player combos with 10+ instances per season
13. Compute projected draft rate and combinatorial ownership metrics from historical data

### Phase 2 — Backend API

1. FastAPI skeleton with routers for each view
2. Player endpoint: stats, ADP trend, BPCOR (both levels), ownership, availability, flags
3. Team endpoint: roster, weekly scores, group standings, roster flags matrix, advancement gap
4. ADP endpoint: current ADP, movement, scarcity curves, projected draft rate, combinatorial ownership
5. History endpoint: all 6 modules
6. Leaderboard endpoint: all teams, filterable/sortable
7. Admin endpoints: player mapping, score audit

### Phase 3 — Frontend

1. Global search + nav
2. Player Hub page — Draft Season and In-Season modes
3. Team Analyzer — team list by username, team detail page, flag matrix
4. ADP Explorer — three views + tournament average BPCOR leaderboard + combinatorial ownership
5. History Browser — dashboard landing + six modules
6. Public leaderboard
7. Articles page — list + detail view with rich-text rendering
8. Podcasts page — inline YouTube embeds + Apple Podcasts / Spotify links
9. Admin pages (player mapping, score audit, article editor, podcast sync)

### Phase 4 — Deployment

1. Backend on Railway ✅ (`stacking-dingers-production.up.railway.app`)
2. Frontend on Vercel ✅ (`stacking-dingers.vercel.app`)
3. Parquet + SQLite on S3 ✅ (`us-east-2`, synced via `scripts/upload_to_s3.py`)
4. GitHub Action for nightly ETL ✅ (~2am ET, March–September)
5. Monitoring: ETL run logs + GitHub issue created on failure
