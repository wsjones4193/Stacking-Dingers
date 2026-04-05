/**
 * Hook for the public leaderboard endpoint. Supports sorting, filtering,
 * and pagination.
 */
import { useEffect, useState } from "react";
import { getLeaderboard } from "@/lib/api";
import type { DataResponse, GlobalFilters, LeaderboardEntry } from "@/types/api";

interface LeaderboardResult {
  entries: LeaderboardEntry[];
  total: number;
  page: number;
  page_size: number;
}

export function useLeaderboard(
  filters: GlobalFilters & { sort_by?: string; page?: number; page_size?: number }
) {
  const [data, setData] = useState<DataResponse<LeaderboardResult> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getLeaderboard(filters)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);

  return { data, loading, error };
}
