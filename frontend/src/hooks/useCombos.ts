import { useEffect, useState } from "react";
import { getCombosLeaderboard } from "@/lib/api";
import type { ComboPair, DataResponse } from "@/types/api";

export function useCombosLeaderboard(season: number, comboSize: number) {
  const [data, setData] = useState<DataResponse<ComboPair[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setData(null);
    setError(null);
    getCombosLeaderboard(season, comboSize)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [season, comboSize]);

  return { data, loading, error };
}
