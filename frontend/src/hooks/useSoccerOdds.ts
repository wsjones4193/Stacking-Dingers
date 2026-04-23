import { useEffect, useState } from "react";
import { getSoccerTeamOdds } from "@/lib/api";
import type { TeamOddsRow } from "@/types/soccer";

export function useSoccerTeamOdds() {
  const [data, setData] = useState<TeamOddsRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getSoccerTeamOdds()
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}
