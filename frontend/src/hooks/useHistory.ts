/**
 * Hooks for each of the five History Browser modules.
 */
import { useEffect, useState } from "react";
import {
  getHistoryAdpAccuracy,
  getHistoryCeiling,
  getHistoryCombos,
  getHistoryDraftStructure,
  getHistoryStacking,
} from "@/lib/api";
import type {
  AdpAccuracyEntry,
  CeilingData,
  ComboData,
  DataResponse,
  DraftStructureData,
  GlobalFilters,
  StackData,
} from "@/types/api";

export function useCeilingData(filters: GlobalFilters) {
  const [data, setData] = useState<DataResponse<CeilingData> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setLoading(true);
    getHistoryCeiling(filters)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);
  return { data, loading, error };
}

export function useStackData(filters: GlobalFilters) {
  const [data, setData] = useState<DataResponse<StackData> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setLoading(true);
    getHistoryStacking(filters)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);
  return { data, loading, error };
}

export function useDraftStructureData(filters: GlobalFilters) {
  const [data, setData] = useState<DataResponse<DraftStructureData> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setLoading(true);
    getHistoryDraftStructure(filters)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);
  return { data, loading, error };
}

export function useComboData(filters: GlobalFilters & { player_id?: number }) {
  const [data, setData] = useState<DataResponse<ComboData> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setLoading(true);
    getHistoryCombos(filters)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);
  return { data, loading, error };
}

export function useAdpAccuracyData(filters: GlobalFilters) {
  const [data, setData] = useState<DataResponse<AdpAccuracyEntry[]> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setLoading(true);
    getHistoryAdpAccuracy(filters)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);
  return { data, loading, error };
}
