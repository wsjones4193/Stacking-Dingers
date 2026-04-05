/**
 * Fetches full player detail and player history for the PlayerHub page.
 */
import { useEffect, useState } from "react";
import { getPlayer, getPlayerHistory } from "@/lib/api";
import type { DataResponse, PlayerDetail, PlayerHistoryEntry } from "@/types/api";

export function usePlayer(playerId: number | null, season?: number, proj?: string) {
  const [data, setData] = useState<DataResponse<PlayerDetail> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!playerId) return;
    setLoading(true);
    setError(null);
    getPlayer(playerId, season, proj)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [playerId, season, proj]);

  return { data, loading, error };
}

export function usePlayerHistory(playerId: number | null) {
  const [data, setData] = useState<DataResponse<PlayerHistoryEntry[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!playerId) return;
    setLoading(true);
    getPlayerHistory(playerId)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [playerId]);

  return { data, loading, error };
}
