/**
 * Hooks for the three ADP Explorer views: scatter, movement, and scarcity.
 */
import { useEffect, useState } from "react";
import { getAdpMovement, getAdpScarcity, getAdpScatter } from "@/lib/api";
import type {
  AdpMovementPoint,
  AdpScatterPoint,
  DataResponse,
  GlobalFilters,
  ScarcityPoint,
} from "@/types/api";

export function useAdpScatter(filters: GlobalFilters & { proj?: string }) {
  const [data, setData] = useState<DataResponse<AdpScatterPoint[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getAdpScatter(filters)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);

  return { data, loading, error };
}

export function useAdpMovement(filters: GlobalFilters & { player_ids?: string }) {
  const [data, setData] = useState<DataResponse<AdpMovementPoint[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getAdpMovement(filters)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);

  return { data, loading, error };
}

export function useAdpScarcity(filters: GlobalFilters) {
  const [data, setData] = useState<DataResponse<ScarcityPoint[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getAdpScarcity(filters)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);

  return { data, loading, error };
}
