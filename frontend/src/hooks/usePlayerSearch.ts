/**
 * Debounced player search hook. Returns matches after 300 ms of idle input.
 */
import { useEffect, useState } from "react";
import { searchPlayers } from "@/lib/api";
import type { PlayerSearchResult } from "@/types/api";

export function usePlayerSearch(query: string) {
  const [results, setResults] = useState<PlayerSearchResult[]>([]);
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
      searchPlayers(query)
        .then(setResults)
        .catch((e: Error) => setError(e.message))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  return { results, loading, error };
}
