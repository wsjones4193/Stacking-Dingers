// TypeScript types for The World Pup soccer bestball API

export interface SoccerPlayerSearchResult {
  player_id: number;
  name: string;
  position: string;  // "GK" | "DEF" | "MID" | "FWD"
  nationality: string | null;
  current_club: string | null;
  current_adp: number | null;
  draft_rate: number | null;
}

export interface SoccerPlayerStats {
  season: number;
  club: string | null;
  competition: string | null;
  matches_played: number;
  minutes_played: number;
  goals: number;
  assists: number;
  shots_on_target: number;
  shots_off_target: number;
  chances_created: number;
  crosses: number;
  tackles_successful: number;
  passes_successful: number;
  saves: number;
  penalty_saves: number;
  goals_conceded: number;
  wins: number;
  clean_sheets: number;
  calculated_points: number;
  points_per_90: number | null;
}

export interface AdpHistoryPoint {
  date: string;
  adp: number | null;
  draft_rate: number | null;
}

export interface SoccerPlayerDetail {
  player_id: number;
  name: string;
  position: string;
  nationality: string | null;
  current_club: string | null;
  underdog_id: string | null;
  active: boolean;
  current_adp: number | null;
  draft_rate: number | null;
  adp_history: AdpHistoryPoint[];
  stats: SoccerPlayerStats[];
}

export interface SoccerAdpScatterPoint {
  player_id: number;
  name: string;
  position: string;
  nationality: string | null;
  current_club: string | null;
  adp: number;
  draft_rate: number | null;
  points_per_90: number | null;
}

export interface SoccerAdpMovement {
  player_id: number;
  name: string;
  position: string;
  adp_7d_ago: number | null;
  adp_today: number | null;
  movement: number | null;
}

export interface SoccerAdpScarcity {
  position: string;
  pick_number: number;
  cumulative_pct: number;
}

export interface TeamOddsRow {
  team_name: string;
  r32_prob: number | null;
  r16_prob: number | null;
  qf_prob: number | null;
  sf_prob: number | null;
  final_prob: number | null;
  winner_prob: number | null;
  updated_at: string | null;
}

export interface XIPlayer {
  player_id: number;
  name: string;
  position: string;
  position_slot: string;
  current_adp: number | null;
  is_starter: boolean;
}

export interface ProjectedXI {
  team_name: string;
  formation: string;
  starters: XIPlayer[];
  bench: XIPlayer[];
  updated_at: string | null;
}

export interface RankingEntry {
  player_id: number;
  name: string;
  position: string;
  nationality: string | null;
  current_adp: number | null;
  tier: number | null;
  notes: string | null;
}

export interface RankingList {
  ranking_id: number;
  name: string;
  description: string | null;
  position_filter: string | null;
  entries: RankingEntry[];
  created_at: string;
  updated_at: string;
}

export interface RankingListSummary {
  ranking_id: number;
  name: string;
  description: string | null;
  position_filter: string | null;
  entry_count: number;
  updated_at: string;
}

// Generic API envelope (matches backend DataResponse)
export interface SoccerDataResponse<T> {
  data: T;
  data_as_of: string | null;
  sample_size?: number;
  low_confidence?: boolean;
}
