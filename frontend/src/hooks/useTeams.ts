/**
 * Hooks for searching teams by username and fetching a single team's detail.
 */
import { useEffect, useState } from "react";
import { getTeam, searchTeams } from "@/lib/api";
import type { DataResponse, GlobalFilters, TeamDetail, TeamSummary } from "@/types/api";

interface TeamSearchResult {
  teams: TeamSummary[];
  total: number;
  page: number;
  page_size: number;
}

export function useTeamSearch(
  username: string,
  filters: GlobalFilters & { page?: number; page_size?: number }
) {
  const [data, setData] = useState<DataResponse<TeamSearchResult> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!username.trim()) return;
    setLoading(true);
    setError(null);
    searchTeams(username, filters)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // Stringify filters to detect deep changes without adding every key as dep.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [username, JSON.stringify(filters)]);

  return { data, loading, error };
}

export function useTeam(draftId: string | null) {
  const [data, setData] = useState<DataResponse<TeamDetail> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!draftId) return;
    setLoading(true);
    getTeam(draftId)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [draftId]);

  return { data, loading, error };
}
