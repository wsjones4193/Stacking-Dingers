import { useEffect, useState } from "react";
import {
  getSoccerAdpHistory,
  getSoccerAdpMovement,
  getSoccerAdpScarcity,
  getSoccerAdpScatter,
} from "@/lib/api";
import type {
  AdpHistoryPoint,
  SoccerAdpMovement,
  SoccerAdpScarcity,
  SoccerAdpScatterPoint,
} from "@/types/soccer";

export function useSoccerAdpScatter(position?: string, nationality?: string) {
  const [data, setData] = useState<SoccerAdpScatterPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getSoccerAdpScatter(position, nationality)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [position, nationality]);

  return { data, loading, error };
}

export function useSoccerAdpMovement(days: number = 7, position?: string) {
  const [data, setData] = useState<SoccerAdpMovement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getSoccerAdpMovement(days, position)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [days, position]);

  return { data, loading, error };
}

export function useSoccerAdpScarcity() {
  const [data, setData] = useState<SoccerAdpScarcity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getSoccerAdpScarcity()
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}

export function useSoccerAdpHistory(playerId: number | null, days: number = 30) {
  const [data, setData] = useState<AdpHistoryPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!playerId) return;
    setLoading(true);
    getSoccerAdpHistory(playerId, days)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [playerId, days]);

  return { data, loading, error };
}
