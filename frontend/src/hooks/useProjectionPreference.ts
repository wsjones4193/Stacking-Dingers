/**
 * Reads and writes the user's preferred projection system.
 * Persisted in localStorage and synced with the ?proj= URL param.
 */
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

export type ProjectionSystem = "steamer" | "atc" | "blended";

const LS_KEY = "projectionSystem";
const DEFAULT: ProjectionSystem = "blended";

export function useProjectionPreference(): [ProjectionSystem, (p: ProjectionSystem) => void] {
  const [searchParams, setSearchParams] = useSearchParams();

  const fromUrl = searchParams.get("proj") as ProjectionSystem | null;
  const fromStorage = localStorage.getItem(LS_KEY) as ProjectionSystem | null;
  const initial: ProjectionSystem = fromUrl ?? fromStorage ?? DEFAULT;

  const [proj, setProj] = useState<ProjectionSystem>(initial);

  // Keep localStorage and URL in sync when proj changes.
  useEffect(() => {
    localStorage.setItem(LS_KEY, proj);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("proj", proj);
      return next;
    }, { replace: true });
  }, [proj, setSearchParams]);

  const update = useCallback((p: ProjectionSystem) => setProj(p), []);

  return [proj, update];
}
