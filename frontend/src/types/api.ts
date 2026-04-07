/** TypeScript interfaces matching the FastAPI response schemas in backend/schemas.py. */

export interface DataResponse<T> {
  data: T;
  data_as_of: string;
  sample_size: number;
  low_confidence: boolean;
}

// ---------------------------------------------------------------------------
// Players
// ---------------------------------------------------------------------------

export interface PlayerSearchResult {
  player_id: number;
  name: string;
  position: string;
  mlb_team: string | null;
  current_adp: number | null;
}

export interface ScoringPoint {
  game_date: string;
  calculated_score: number;
  cumulative_score: number;
  is_hot: boolean;
}

export interface WeeklyScoringPoint {
  week_number: number;
  calculated_score: number;
  is_starter: boolean;
  is_flex: boolean;
  is_bench: boolean;
}

export interface AdpTrendPoint {
  snapshot_date: string;
  adp: number;
  draft_rate: number;
}

export interface PlayerDetail {
  player_id: number;
  name: string;
  position: string;
  mlb_team: string | null;
  il_status: boolean;
  days_since_last_game: number | null;
  scoring_trajectory: ScoringPoint[];
  weekly_scores: WeeklyScoringPoint[];
  adp_trend: AdpTrendPoint[];
  current_adp: number | null;
  peak_adp: number | null;
  low_adp: number | null;
  current_draft_rate: number | null;
  season_bpcor: number | null;
  projected_points: number | null;
  ownership_pct: number | null;
  peer_group: string | null;
  draft_count: number;
}

export interface PlayerHistoryEntry {
  season: number;
  bpcor: number | null;
  adp: number | null;
  ownership_pct: number | null;
  peak_week_score: number | null;
}

// ---------------------------------------------------------------------------
// Teams
// ---------------------------------------------------------------------------

export interface RosterFlag {
  flag_type: string;
  flag_reason: string;
  player_id: number | null;
  player_name: string | null;
  player_position: string | null;
  week_number: number;
}

export interface TeamSummary {
  draft_id: string;
  username: string;
  draft_date: string;
  draft_position: number;
  season: number;
  total_score: number;
  round_reached: number;
  group_rank: number | null;
  gap_to_advance: number | null;
  roster_strength_score: number | null;
  advancement_probability: number | null;
  roster_flags: RosterFlag[];
}

export interface RosterSlot {
  player_id: number;
  name: string;
  position: string;
  mlb_team: string | null;
  season_score: number;
  last_week_score: number | null;
  season_bpcor: number | null;
  il_status: boolean;
  flags: RosterFlag[];
}

export interface WeekBreakdown {
  week_number: number;
  starters: RosterSlot[];
  flex: RosterSlot | null;
  bench: RosterSlot[];
  total_score: number;
  left_on_bench_score: number;
}

export interface GroupStanding {
  username: string;
  draft_id: string;
  total_score: number;
  rank: number;
  advanced: boolean;
}

export interface TeamDetail {
  draft_id: string;
  username: string;
  draft_date: string;
  draft_position: number;
  season: number;
  total_score: number;
  round_reached: number;
  group_rank: number | null;
  gap_to_advance: number | null;
  advancement_probability: number | null;
  roster_flags: RosterFlag[];
  roster: RosterSlot[];
  weekly_breakdown: WeekBreakdown[];
  group_standings: GroupStanding[];
}

// ---------------------------------------------------------------------------
// ADP
// ---------------------------------------------------------------------------

export interface AdpScatterPoint {
  player_id: number;
  name: string;
  position: string;
  adp_rank: number;
  bpcor_rank: number;
  bpcor: number;
  adp: number;
}

export interface AdpMovementPoint {
  player_id: number;
  name: string;
  position: string;
  snapshot_date: string;
  adp: number;
  draft_rate: number;
}

export interface ScarcityPoint {
  pick_number: number;
  position: string;
  cumulative_pct_drafted: number;
}

// ---------------------------------------------------------------------------
// Leaderboard
// ---------------------------------------------------------------------------

export interface LeaderboardEntry {
  draft_id: string;
  username: string;
  season: number;
  draft_date: string;
  draft_position: number;
  total_score: number;
  round_reached: number;
  peak_week_score: number | null;
  peak_window_weeks: number[] | null;
  consistency_score: number | null;
}

// ---------------------------------------------------------------------------
// History modules
// ---------------------------------------------------------------------------

export interface CeilingData {
  peak_histogram: { bucket: string; count: number }[];
  quadrant_data: {
    player_id: number;
    name: string;
    peak_score: number;
    consistency: number;
    quadrant: string;
  }[];
  playoff_window_distribution: { week: number; count: number }[];
}

export interface StackData {
  mlb_team_stacks: {
    mlb_team: string;
    stack_size: number;
    avg_advance_rate: number;
    sample_size: number;
  }[];
  positional_stacks: {
    position_combo: string;
    avg_advance_rate: number;
    sample_size: number;
  }[];
}

export interface DraftStructureData {
  first_address_crosstab: {
    first_pick_pos: string;
    advance_rate: number;
    avg_score: number;
    sample_size: number;
  }[];
  archetype_outcomes: {
    archetype: string;
    advance_rate: number;
    avg_score: number;
    sample_size: number;
  }[];
}

export interface ComboData {
  top_combos: {
    player_a_id: number;
    player_a_name: string;
    player_b_id: number;
    player_b_name: string;
    pair_rate: number;
    advance_rate_delta: number;
    sample_size: number;
  }[];
}

export interface AdpAccuracyEntry {
  player_id: number;
  name: string;
  position: string;
  adp: number;
  projected_points: number;
  actual_bpcor: number;
  value_delta: number;
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export interface PlayerMapping {
  id: number;
  underdog_name: string;
  underdog_id: string | null;
  mlb_name: string | null;
  mlb_id: number | null;
  player_id: number | null;
  confirmed: boolean;
  season: number;
}

export interface ScoreAuditEntry {
  id: number;
  player_id: number;
  player_name: string | null;
  week_number: number;
  season: number;
  calculated_score: number;
  underdog_score: number;
  delta: number;
}

// ---------------------------------------------------------------------------
// Content — Articles
// ---------------------------------------------------------------------------

export interface ArticleSummary {
  article_id: number;
  title: string;
  author: string;
  published_date: string;
  excerpt: string;
  thumbnail_url: string | null;
  slug: string;
}

export interface ArticleDetail extends ArticleSummary {
  content_html: string;
  updated_at: string;
}

export interface ArticleListResponse {
  articles: ArticleSummary[];
  total: number;
  page: number;
  page_size: number;
}

// ---------------------------------------------------------------------------
// Content — Podcasts
// ---------------------------------------------------------------------------

export interface PodcastEpisode {
  episode_id: number;
  youtube_id: string;
  title: string;
  published_date: string;
  description: string;
  thumbnail_url: string | null;
  series: string | null;
}

export interface EpisodeListResponse {
  episodes: PodcastEpisode[];
  total: number;
  page: number;
  page_size: number;
}

// ---------------------------------------------------------------------------
// Filter params (shared across endpoints)
// ---------------------------------------------------------------------------

export interface GlobalFilters {
  season?: number;
  draft_date_from?: string;
  draft_date_to?: string;
  draft_position?: number;
  position?: string;
  entry_type?: string;
  [key: string]: string | number | boolean | undefined;
}
