import { useEffect, useState } from "react";
import { getPlayerWeeklyScoring } from "@/lib/api";
import type { DataResponse, PlayerWeeklyScoringData } from "@/types/api";

export function usePlayerWeeklyScoring(playerId: number | null, season: number) {
  const [data, setData] = useState<DataResponse<PlayerWeeklyScoringData> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!playerId) { setData(null); return; }
    setLoading(true);
    setData(null);
    setError(null);
    getPlayerWeeklyScoring(playerId, season)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [playerId, season]);

  return { data, loading, error };
}
