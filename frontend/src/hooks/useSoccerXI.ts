import { useEffect, useState } from "react";
import { getAllWCTeams, getSoccerXI, getSoccerXITeams } from "@/lib/api";
import type { ProjectedXI } from "@/types/soccer";

export function useSoccerXI(teamName: string | null) {
  const [data, setData] = useState<ProjectedXI | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!teamName) return;
    setLoading(true);
    setError(null);
    getSoccerXI(teamName)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [teamName]);

  return { data, loading, error };
}

export function useWCTeams() {
  const [configured, setConfigured] = useState<string[]>([]);
  const [all, setAll] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([getSoccerXITeams(), getAllWCTeams()])
      .then(([c, a]) => { setConfigured(c); setAll(a); })
      .finally(() => setLoading(false));
  }, []);

  return { configured, all, loading };
}
