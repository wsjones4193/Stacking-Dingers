/**
 * API client for the Stacking Dingers FastAPI backend.
 * All functions return the parsed JSON directly. The base URL is read from the
 * VITE_API_BASE_URL env var (defaults to "" so Vite's proxy handles /api/*).
 */

import type {
  AdpAccuracyEntry,
  AdpMovementPoint,
  AdpScatterPoint,
  ArticleDetail,
  ArticleListResponse,
  CeilingData,
  ComboData,
  DataResponse,
  DraftStructureData,
  EpisodeListResponse,
  GlobalFilters,
  LeaderboardEntry,
  PlayerDetail,
  PlayerHistoryEntry,
  PlayerMapping,
  PlayerSearchResult,
  ScarcityPoint,
  ScoreAuditEntry,
  StackData,
  TeamDetail,
  TeamSummary,
} from "@/types/api";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        url.searchParams.set(k, String(v));
      }
    });
  }
  const res = await fetch(url.toString());
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Players
// ---------------------------------------------------------------------------

export const searchPlayers = (q: string) =>
  get<PlayerSearchResult[]>("/api/players/search", { q });

export const getPlayer = (playerId: number, season?: number, proj?: string) =>
  get<DataResponse<PlayerDetail>>(`/api/players/${playerId}`, { season, proj });

export const getPlayerHistory = (playerId: number) =>
  get<DataResponse<PlayerHistoryEntry[]>>(`/api/players/${playerId}/history`);

// ---------------------------------------------------------------------------
// Teams
// ---------------------------------------------------------------------------

export const searchTeams = (
  username: string,
  filters: GlobalFilters & { page?: number; page_size?: number }
) =>
  get<DataResponse<{ teams: TeamSummary[]; total: number; page: number; page_size: number }>>(
    "/api/teams/search",
    { username, ...filters }
  );

export const getTeam = (draftId: string) =>
  get<DataResponse<TeamDetail>>(`/api/teams/${draftId}`);

// ---------------------------------------------------------------------------
// ADP
// ---------------------------------------------------------------------------

export const getAdpScatter = (filters: GlobalFilters & { proj?: string }) =>
  get<DataResponse<AdpScatterPoint[]>>("/api/adp/scatter", filters);

export const getAdpMovement = (filters: GlobalFilters & { player_ids?: string }) =>
  get<DataResponse<AdpMovementPoint[]>>("/api/adp/movement", filters);

export const getAdpScarcity = (filters: GlobalFilters) =>
  get<DataResponse<ScarcityPoint[]>>("/api/adp/scarcity", filters);

// ---------------------------------------------------------------------------
// Leaderboard
// ---------------------------------------------------------------------------

export const getLeaderboard = (
  filters: GlobalFilters & { sort_by?: string; page?: number; page_size?: number }
) =>
  get<DataResponse<{ entries: LeaderboardEntry[]; total: number; page: number; page_size: number }>>(
    "/api/leaderboard",
    filters
  );

// ---------------------------------------------------------------------------
// History modules
// ---------------------------------------------------------------------------

export const getHistoryCeiling = (filters: GlobalFilters) =>
  get<DataResponse<CeilingData>>("/api/history/modules/ceiling", filters);

export const getHistoryStacking = (filters: GlobalFilters) =>
  get<DataResponse<StackData>>("/api/history/modules/stacking", filters);

export const getHistoryDraftStructure = (filters: GlobalFilters) =>
  get<DataResponse<DraftStructureData>>("/api/history/modules/draft-structure", filters);

export const getHistoryCombos = (
  filters: GlobalFilters & { player_id?: number }
) =>
  get<DataResponse<ComboData>>("/api/history/modules/combos", filters);

export const getHistoryAdpAccuracy = (filters: GlobalFilters) =>
  get<DataResponse<AdpAccuracyEntry[]>>("/api/history/modules/adp-accuracy", filters);

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export const getPlayerMappings = (params?: { confirmed?: boolean; season?: number }) =>
  get<PlayerMapping[]>("/api/admin/player-mapping", params);

export const confirmMapping = (mappingId: number, mlbId: number) =>
  patch<PlayerMapping>(`/api/admin/player-mapping/${mappingId}`, { mlb_id: mlbId, confirmed: true });

export const addMapping = (body: Partial<PlayerMapping>) =>
  post<PlayerMapping>("/api/admin/player-mapping", body);

export const getScoreAudit = (season?: number) =>
  get<ScoreAuditEntry[]>("/api/admin/score-audit", { season });

// ---------------------------------------------------------------------------
// Content — Articles
// ---------------------------------------------------------------------------

export const getArticles = (page?: number) =>
  get<ArticleListResponse>("/api/content/articles", { page });

export const getArticle = (slug: string) =>
  get<ArticleDetail>(`/api/content/articles/${slug}`);

export const adminListArticles = () =>
  get<{ article_id: number; title: string; author: string; published_date: string; slug: string; updated_at: string }[]>("/api/admin/articles");

export const adminCreateArticle = (body: {
  title: string; author: string; published_date: string;
  excerpt: string; content_html: string; thumbnail_url?: string; slug: string;
}) => post<{ article_id: number; slug: string }>("/api/admin/articles", body);

export const adminUpdateArticle = (articleId: number, body: Partial<{
  title: string; author: string; published_date: string;
  excerpt: string; content_html: string; thumbnail_url: string; slug: string;
}>) => patch<{ article_id: number; slug: string }>(`/api/admin/articles/${articleId}`, body);

export const adminDeleteArticle = (articleId: number) =>
  fetch(`${import.meta.env.VITE_API_BASE_URL ?? ""}/api/admin/articles/${articleId}`, { method: "DELETE" });

// ---------------------------------------------------------------------------
// Content — Podcasts
// ---------------------------------------------------------------------------

export const getPodcasts = (page?: number) =>
  get<EpisodeListResponse>("/api/content/podcasts", { page });

export const adminSyncPodcasts = () =>
  post<{ new_episodes: number; feed_entries?: number }>("/api/admin/podcasts/sync", {});

export const adminDeleteEpisode = (episodeId: number) =>
  fetch(`${import.meta.env.VITE_API_BASE_URL ?? ""}/api/admin/podcasts/${episodeId}`, { method: "DELETE" });
