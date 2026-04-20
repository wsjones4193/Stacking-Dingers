import { useEffect, useState, useRef } from "react";
import { getCombosLeaderboard } from "@/lib/api";
import type { ComboPair, DataResponse } from "@/types/api";

export function useCombosLeaderboard(
  season: number,
  comboSize: number,
  playerA = "",
  playerB = "",
  limit = 500,
) {
  const [data, setData] = useState<DataResponse<ComboPair[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounce filter strings so we don't fire on every keystroke
  const [debouncedA, setDebouncedA] = useState(playerA);
  const [debouncedB, setDebouncedB] = useState(playerB);
  const timerA = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timerB = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerA.current) clearTimeout(timerA.current);
    timerA.current = setTimeout(() => setDebouncedA(playerA), 400);
    return () => { if (timerA.current) clearTimeout(timerA.current); };
  }, [playerA]);

  useEffect(() => {
    if (timerB.current) clearTimeout(timerB.current);
    timerB.current = setTimeout(() => setDebouncedB(playerB), 400);
    return () => { if (timerB.current) clearTimeout(timerB.current); };
  }, [playerB]);

  useEffect(() => {
    setLoading(true);
    setData(null);
    setError(null);
    getCombosLeaderboard(season, comboSize, limit, debouncedA || undefined, debouncedB || undefined)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [season, comboSize, limit, debouncedA, debouncedB]);

  return { data, loading, error };
}
