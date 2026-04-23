import { useEffect, useState } from "react";
import { getSoccerPlayer, getSoccerPlayersByPosition, searchSoccerPlayers } from "@/lib/api";
import type { SoccerPlayerDetail, SoccerPlayerSearchResult } from "@/types/soccer";

export function useSoccerPlayerSearch(query: string, position?: string) {
  const [results, setResults] = useState<SoccerPlayerSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    setLoading(true);
    setError(null);
    const timer = setTimeout(() => {
      searchSoccerPlayers(query, position)
        .then(setResults)
        .catch((e: Error) => setError(e.message))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [query, position]);

  return { results, loading, error };
}

export function useSoccerPlayersByPosition(position: string, nationality?: string) {
  const [data, setData] = useState<SoccerPlayerSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getSoccerPlayersByPosition(position, nationality)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [position, nationality]);

  return { data, loading, error };
}

export function useSoccerPlayer(playerId: number | null) {
  const [data, setData] = useState<SoccerPlayerDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!playerId) return;
    setLoading(true);
    setError(null);
    getSoccerPlayer(playerId)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [playerId]);

  return { data, loading, error };
}
