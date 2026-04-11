/**
 * Hooks for the three ADP Explorer views: scatter, movement, and scarcity.
 */
import { useEffect, useState } from "react";
import { getAdpLeaderboard, getAdpMovement, getAdpPlayerPicks, getAdpRoundComposition, getAdpScarcity, getAdpScarcityCache, getAdpScatter, getAdpTimeseries } from "@/lib/api";
import type {
  AdpDailyTimeseriesEntry,
  AdpMovementPoint,
  AdpPlayerSummaryEntry,
  AdpRoundCompositionEntry,
  AdpScarcityCacheEntry,
  AdpScatterPoint,
  DataResponse,
  GlobalFilters,
  ScarcityPoint,
} from "@/types/api";

export function useAdpScatter(filters: GlobalFilters & { proj?: string }) {
  const [data, setData] = useState<DataResponse<AdpScatterPoint[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getAdpScatter(filters)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);

  return { data, loading, error };
}

export function useAdpMovement(filters: GlobalFilters & { player_ids?: string }) {
  const [data, setData] = useState<DataResponse<AdpMovementPoint[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getAdpMovement(filters)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);

  return { data, loading, error };
}

export function useAdpScarcity(filters: GlobalFilters) {
  const [data, setData] = useState<DataResponse<ScarcityPoint[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getAdpScarcity(filters)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);

  return { data, loading, error };
}

export function useAdpLeaderboard(season: number, position?: string) {
  const [data, setData] = useState<DataResponse<AdpPlayerSummaryEntry[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getAdpLeaderboard(season, position)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [season, position]);

  return { data, loading, error };
}

export function useAdpScarcityCache(season: number) {
  const [data, setData] = useState<DataResponse<AdpScarcityCacheEntry[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getAdpScarcityCache(season)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [season]);

  return { data, loading, error };
}

export function useAdpRoundComposition(season: number) {
  const [data, setData] = useState<DataResponse<AdpRoundCompositionEntry[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getAdpRoundComposition(season)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [season]);

  return { data, loading, error };
}

export function useAdpTimeseries(season: number, playerIds?: string, position?: string) {
  const [data, setData] = useState<DataResponse<AdpDailyTimeseriesEntry[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getAdpTimeseries(season, playerIds, position)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [season, playerIds, position]);

  return { data, loading, error };
}

export function useAdpPlayerPicks(playerId: number | null, season: number) {
  const [data, setData] = useState<DataResponse<{ pick_number: number; count: number }[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (playerId == null) { setData(null); return; }
    setLoading(true);
    getAdpPlayerPicks(playerId, season)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [playerId, season]);

  return { data, loading, error };
}
