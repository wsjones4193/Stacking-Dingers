import { useEffect, useState } from "react";
import { getSoccerRanking, listSoccerRankings } from "@/lib/api";
import type { RankingList, RankingListSummary } from "@/types/soccer";

export function useSoccerRankingsList() {
  const [data, setData] = useState<RankingListSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    setLoading(true);
    listSoccerRankings()
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, []);

  return { data, loading, error, refresh };
}

export function useSoccerRanking(rankingId: number | null) {
  const [data, setData] = useState<RankingList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    if (!rankingId) return;
    setLoading(true);
    getSoccerRanking(rankingId)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, [rankingId]);

  return { data, loading, error, refresh };
}
