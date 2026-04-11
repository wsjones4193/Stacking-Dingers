/**
 * ADP Explorer — three tabs built from pre-computed historical draft data:
 *   1. ADP Leaderboard — sortable table: who went where, ownership %, consistency
 *   2. ADP Movement — daily line chart of projection ADP per player
 *   3. ADP vs Draft % — ownership % vs avg pick scatter by position
 */
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,

  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { useAdpLeaderboard, useAdpPlayerPicks, useAdpTimeseries } from "@/hooks/useAdp";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import DataAsOf from "@/components/DataAsOf";
import LoadingSpinner from "@/components/LoadingSpinner";
import type { AdpPlayerSummaryEntry } from "@/types/api";

const SEASONS = [2025, 2024, 2023];
const POSITIONS = ["All", "P", "IF", "OF"];

const POSITION_COLORS: Record<string, string> = {
  P: "#8B5CF6",
  IF: "#14B8A6",
  OF: "#F97316",
};

// ---------------------------------------------------------------------------
// Tab 1: ADP Leaderboard
// ---------------------------------------------------------------------------

type LBSortKey = "avg_projection_adp" | "ending_adp" | "avg_pick" | "ownership_pct" | "draft_count";
type SortDir = "asc" | "desc";

// ---------------------------------------------------------------------------
// Inline sparkline shown when a leaderboard row is expanded
// ---------------------------------------------------------------------------

function PlayerTrendChart({ playerId, season, color }: { playerId: number; season: number; color: string }) {
  const { data: tsData, loading: tsLoading } = useAdpTimeseries(season, String(playerId));
  const { data: picksData, loading: picksLoading } = useAdpPlayerPicks(playerId, season);

  if (tsLoading || picksLoading) return <p className="py-4 text-center text-xs text-muted-foreground">Loading…</p>;

  // --- Histogram: pre-bucketed by pick number from adp_cache.db ---
  const histData = (picksData?.data ?? []).map((d) => ({ pick: d.pick_number, count: d.count }));
  const totalDrafts = histData.reduce((s, d) => s + d.count, 0);

  // Convert to timestamps for numeric XAxis (required for Scatter to render in ComposedChart)
  const toTs = (dateStr: string) => new Date(dateStr + "T12:00:00Z").getTime();

  const linePoints = (tsData?.data ?? []).map((d) => ({
    x: toTs(d.snapshot_date),
    adp: d.adp,
  }));

  if (linePoints.length === 0 && histData.length === 0) {
    return <p className="py-4 text-center text-xs text-muted-foreground">No trend data available.</p>;
  }

  const adpVals = linePoints.map((d) => d.adp);
  const minAdp = Math.min(...adpVals);
  const maxAdp = Math.max(...adpVals);
  const pad = Math.max(1, (maxAdp - minAdp) * 0.15);
  const adpDomain: [number, number] = [
    Math.max(1, Math.floor(minAdp - pad)),
    Math.ceil(maxAdp + pad),
  ];

  const xDomain: [number, number] = [
    Math.min(...linePoints.map((d) => d.x)),
    Math.max(...linePoints.map((d) => d.x)),
  ];

  const fmtTs = (ts: number) => {
    const d = new Date(ts);
    return `${String(d.getUTCMonth() + 1).padStart(2, "0")}/${String(d.getUTCDate()).padStart(2, "0")}`;
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {/* Projection ADP trend — 2/3 width on desktop */}
      <div className="sm:col-span-2" style={{ height: 190 }}>
        <p className="text-[10px] text-muted-foreground mb-1">Projection ADP over time</p>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={linePoints} margin={{ top: 4, right: 16, bottom: 20, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
            <XAxis
              dataKey="x"
              type="number"
              scale="time"
              domain={xDomain}
              tickFormatter={fmtTs}
              tick={{ fontSize: 9 }}
              tickCount={6}
              label={{ value: "Date", position: "insideBottom", offset: -10, fontSize: 10 }}
            />
            <YAxis
              reversed
              domain={adpDomain}
              tick={{ fontSize: 9 }}
              width={30}
              label={{ value: "ADP", angle: -90, position: "insideLeft", offset: 12, fontSize: 10 }}
            />
            <Tooltip
              formatter={(v: number) => v.toFixed(1)}
              labelFormatter={(ts: number) => fmtTs(ts)}
              contentStyle={{ fontSize: 11 }}
            />
            <Line dataKey="adp" type="monotone" stroke={color} strokeWidth={2} dot={false} name="Projection ADP" connectNulls isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Pick number histogram — 1/3 width on desktop */}
      <div style={{ height: 190 }}>
        <p className="text-[10px] text-muted-foreground mb-1">Pick # distribution ({totalDrafts.toLocaleString()} drafts)</p>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={histData} margin={{ top: 4, right: 8, bottom: 20, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
            <XAxis
              dataKey="pick"
              tick={{ fontSize: 9 }}
              label={{ value: "Pick #", position: "insideBottom", offset: -10, fontSize: 10 }}
              interval="preserveStartEnd"
            />
            <YAxis tick={{ fontSize: 9 }} allowDecimals={false} />
            <Tooltip
              formatter={(v: number) => [v.toLocaleString(), "Drafts"]}
              labelFormatter={(p) => `Pick ${p}`}
              contentStyle={{ fontSize: 11 }}
            />
            <Bar dataKey="count" fill={color} fillOpacity={0.75} radius={[2, 2, 0, 0]} name="Drafts" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function LeaderboardTab({ season, position }: { season: number; position: string }) {
  const [sortBy, setSortBy] = useState<LBSortKey>("avg_projection_adp");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const PAGE_SIZE = 40;

  const { data, loading, error } = useAdpLeaderboard(
    season,
    position === "All" ? undefined : position
  );

  function toggleSort(col: LBSortKey) {
    if (sortBy === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir(col === "avg_projection_adp" || col === "ending_adp" || col === "avg_pick" ? "asc" : "desc");
    }
    setPage(1);
  }

  function SortIcon({ col }: { col: LBSortKey }) {
    if (sortBy !== col) return <ChevronDown className="ml-1 h-3 w-3 opacity-30 inline" />;
    return sortDir === "desc" ? (
      <ChevronDown className="ml-1 h-3 w-3 text-primary inline" />
    ) : (
      <ChevronUp className="ml-1 h-3 w-3 text-primary inline" />
    );
  }

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="py-8 text-center text-sm text-destructive">{error}</p>;
  if (!data) return null;

  if (data.data.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No ADP data for {season}. Run <code>python scripts/precompute_adp.py</code> to populate.
      </div>
    );
  }

  const filtered = search
    ? data.data.filter((p) => p.player_name.toLowerCase().includes(search.toLowerCase()))
    : data.data;

  const sorted = [...filtered].sort((a, b) => {
    const va = (sortBy === "avg_projection_adp" ? (a.avg_projection_adp ?? a.ending_adp ?? a.avg_pick)
              : sortBy === "ending_adp" ? (a.ending_adp ?? a.avg_pick)
              : (a[sortBy] ?? 9999)) as number;
    const vb = (sortBy === "avg_projection_adp" ? (b.avg_projection_adp ?? b.ending_adp ?? b.avg_pick)
              : sortBy === "ending_adp" ? (b.ending_adp ?? b.avg_pick)
              : (b[sortBy] ?? 9999)) as number;
    return sortDir === "asc" ? va - vb : vb - va;
  });

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const paginated = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Position badge colors
  const posBadge = (pos: string) =>
    pos === "P"
      ? "bg-violet-500/20 text-violet-400"
      : pos === "IF"
      ? "bg-teal-500/20 text-teal-400"
      : "bg-orange-500/20 text-orange-400";

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        ADP = most recent Underdog projection ADP. Avg Pick = season average across {data.data[0]?.total_season_drafts?.toLocaleString() ?? "—"} drafts.
        Ownership % = share of all team slots that drafted this player.
      </p>

      {/* Search */}
      <input
        type="text"
        placeholder="Search player..."
        value={search}
        onChange={(e) => { setSearch(e.target.value); setPage(1); }}
        className="w-full max-w-xs rounded-md border border-border bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
      />

      <Card>
        <CardContent className="pt-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="pb-2 w-8">#</th>
                <th className="pb-2">Player</th>
                <th className="pb-2">Pos</th>
                <th
                  className="pb-2 text-right cursor-pointer hover:text-foreground select-none"
                  onClick={() => toggleSort("avg_projection_adp")}
                  title="Average projection ADP across all drafts"
                >
                  ADP<SortIcon col="avg_projection_adp" />
                </th>
                <th
                  className="pb-2 text-right cursor-pointer hover:text-foreground select-none"
                  onClick={() => toggleSort("ending_adp")}
                  title="Most recent projection ADP"
                >
                  Current<SortIcon col="ending_adp" />
                </th>
                <th className="pb-2 text-right text-muted-foreground" title="Min – Max projection ADP">
                  Range
                </th>
                <th
                  className="pb-2 text-right cursor-pointer hover:text-foreground select-none"
                  onClick={() => toggleSort("ownership_pct")}
                >
                  Own %<SortIcon col="ownership_pct" />
                </th>
                <th
                  className="pb-2 text-right cursor-pointer hover:text-foreground select-none"
                  onClick={() => toggleSort("draft_count")}
                >
                  Drafted<SortIcon col="draft_count" />
                </th>
              </tr>
            </thead>
            <tbody>
              {paginated.map((p: AdpPlayerSummaryEntry, i: number) => {
                const rank = (page - 1) * PAGE_SIZE + i + 1;
                const expanded = expandedId === p.player_id;
                const color = POSITION_COLORS[p.position] ?? "#94a3b8";
                return (
                  <>
                    <tr
                      key={p.player_id}
                      onClick={() => setExpandedId(expanded ? null : p.player_id)}
                      className={`cursor-pointer border-b border-border/50 transition-colors ${expanded ? "bg-accent/30" : "hover:bg-accent/20"}`}
                    >
                      <td className="py-1.5 text-xs text-muted-foreground">{rank}</td>
                      <td className="py-1.5 font-medium">{p.player_name}</td>
                      <td className="py-1.5">
                        <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${posBadge(p.position)}`}>
                          {p.position}
                        </span>
                      </td>
                      <td className="py-1.5 text-right font-semibold">
                        {(p.avg_projection_adp ?? p.ending_adp ?? p.avg_pick).toFixed(1)}
                      </td>
                      <td className="py-1.5 text-right text-muted-foreground">
                        {p.ending_adp?.toFixed(1) ?? "—"}
                      </td>
                      <td className="py-1.5 text-right text-muted-foreground text-xs">
                        {p.min_projection_adp != null && p.max_projection_adp != null
                          ? `${p.min_projection_adp.toFixed(1)}–${p.max_projection_adp.toFixed(1)}`
                          : "—"}
                      </td>
                      <td className="py-1.5 text-right">{p.ownership_pct.toFixed(1)}%</td>
                      <td className="py-1.5 text-right text-muted-foreground">
                        {p.draft_count.toLocaleString()}
                      </td>
                    </tr>
                    {expanded && (
                      <tr key={`${p.player_id}-expand`} className="bg-accent/10">
                        <td colSpan={8} className="px-4 pb-3 pt-1">
                          <p className="text-xs font-medium mb-1" style={{ color }}>
                            {p.player_name} — ADP Trend ({season})
                          </p>
                          <PlayerTrendChart playerId={p.player_id} season={season} color={color} />
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
          {paginated.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">No results.</p>
          )}
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" size="icon" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
          <Button variant="outline" size="icon" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}

      <DataAsOf dataAsOf={data.data_as_of} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 2: Positional Scarcity — avg cumulative count per draft
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Tab 3: ADP vs Draft % scatter
// ---------------------------------------------------------------------------

function AdpVsDraftRateTab({ season, position }: { season: number; position: string }) {
  const { data, loading, error } = useAdpLeaderboard(
    season,
    position === "All" ? undefined : position
  );

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="py-8 text-center text-sm text-destructive">{error}</p>;
  if (!data) return null;

  if (data.data.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No data for {season}.
      </div>
    );
  }

  // Only include players with actual projection_adp data — no fallback to avg_pick
  type ScatterPoint = AdpPlayerSummaryEntry & { adp_x: number };
  const byPos: Record<string, ScatterPoint[]> = {};
  for (const p of data.data) {
    if (!byPos[p.position]) byPos[p.position] = [];
    byPos[p.position].push({ ...p, adp_x: p.avg_projection_adp ?? p.avg_pick });
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Each dot is a player: X = average projection ADP (across all drafts), Y = ownership % across all {season} rosters.
        Earlier-drafted players cluster top-left; deeper picks spread bottom-right.
      </p>
      <Card>
        <CardHeader>
          <CardTitle>ADP vs Ownership % — {season}</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={420}>
            <ScatterChart margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="adp_x"
                name="ADP"
                type="number"
                domain={[1, 240]}
                label={{ value: "ADP", position: "insideBottom", offset: -12, fontSize: 11 }}
                tick={{ fontSize: 11 }}
              />
              <YAxis
                dataKey="ownership_pct"
                name="Ownership %"
                type="number"
                tickFormatter={(v) => `${v}%`}
                tick={{ fontSize: 11 }}
                label={{ value: "Ownership %", angle: -90, position: "insideLeft", offset: 10, fontSize: 11 }}
              />
              <ZAxis range={[24, 24]} />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload as ScatterPoint;
                  return (
                    <div className="rounded-md border bg-popover p-2 text-xs shadow-md">
                      <p className="font-semibold">{p.player_name}</p>
                      <p className="text-muted-foreground">{p.position}</p>
                      <p>Avg ADP: {p.adp_x?.toFixed(1)}</p>
                      <p>ADP range: {p.min_projection_adp?.toFixed(1)} – {p.max_projection_adp?.toFixed(1)}</p>
                      <p>Ownership: {p.ownership_pct?.toFixed(1)}%</p>
                    </div>
                  );
                }}
              />
              <Legend verticalAlign="top" />
              {Object.entries(byPos).map(([pos, pts]) => (
                <Scatter
                  key={pos}
                  name={pos}
                  data={pts}
                  fill={POSITION_COLORS[pos] ?? "hsl(215 20% 60%)"}
                  fillOpacity={0.7}
                />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
      <DataAsOf dataAsOf={data.data_as_of} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 5: ADP Movement — daily ADP time series per player
// ---------------------------------------------------------------------------

// Distinct stroke styles so same-position players are still distinguishable
const STROKE_DASHES = ["", "6 3", "2 2", "8 2 2 2"];

// Label rendered only at the last data point of each line
function LineEndLabel({
  x = 0, y = 0, index = 0, value, displayName, color, dataLength,
}: {
  x?: number; y?: number; index?: number; value?: number;
  displayName: string; color: string; dataLength: number;
}) {
  if (index !== dataLength - 1 || value == null) return null;
  return (
    <text x={x + 7} y={y} fill={color} fontSize={10} dominantBaseline="middle" fontWeight={600}>
      {displayName}
    </text>
  );
}

function AdpMovementTab({ season, position }: { season: number; position: string }) {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [search, setSearch] = useState("");
  const isMobile = typeof window !== "undefined" && window.innerWidth < 640;

  const { data: lbData } = useAdpLeaderboard(season, position === "All" ? undefined : position);

  const playerIdsParam = selectedIds.length > 0 ? selectedIds.join(",") : undefined;
  const { data: tsData, loading, error } = useAdpTimeseries(
    season,
    playerIdsParam,
    position === "All" ? undefined : position,
  );

  // Players sorted by most recent ADP (ending_adp), falling back to avg_pick
  const sortedPlayers = useMemo(() => {
    if (!lbData) return [];
    return [...lbData.data].sort(
      (a, b) => (a.ending_adp ?? a.avg_pick) - (b.ending_adp ?? b.avg_pick)
    );
  }, [lbData]);

  const filteredPlayers = useMemo(() => {
    if (!search.trim()) return sortedPlayers;
    return sortedPlayers.filter((p) =>
      p.player_name.toLowerCase().includes(search.toLowerCase())
    );
  }, [sortedPlayers, search]);

  function togglePlayer(id: number) {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 12) return prev;
      return [...prev, id];
    });
  }

  // Pivot timeseries rows into [{snapshot_date, "Name__id": adp, ...}]
  const { chartData, playerKeys } = useMemo(() => {
    if (!tsData?.data.length) return { chartData: [], playerKeys: [] };

    const rows = tsData.data;
    const dateMap: Record<string, Record<string, number | string>> = {};
    const keys = new Set<string>();

    for (const row of rows) {
      if (!dateMap[row.snapshot_date]) dateMap[row.snapshot_date] = { snapshot_date: row.snapshot_date };
      const key = `${row.player_name}__${row.player_id}`;
      dateMap[row.snapshot_date][key] = row.adp;
      keys.add(key);
    }

    const sorted = Object.values(dateMap).sort((a, b) =>
      String(a.snapshot_date).localeCompare(String(b.snapshot_date))
    );

    // Sort keys by ending ADP (last date's value), ascending
    const lastDate = sorted[sorted.length - 1];
    const sortedKeys = Array.from(keys).sort((a, b) => {
      const aAdp = lastDate ? (lastDate[a] as number ?? 999) : 999;
      const bAdp = lastDate ? (lastDate[b] as number ?? 999) : 999;
      return aAdp - bAdp;
    });

    return { chartData: sorted, playerKeys: sortedKeys };
  }, [tsData]);

  const keyPositionMap = useMemo(() => {
    const m: Record<string, string> = {};
    tsData?.data.forEach((row) => {
      m[`${row.player_name}__${row.player_id}`] = row.position;
    });
    return m;
  }, [tsData]);

  const keyDashMap = useMemo(() => {
    const posCount: Record<string, number> = {};
    const m: Record<string, string> = {};
    for (const key of playerKeys) {
      const pos = keyPositionMap[key] ?? "?";
      const idx = posCount[pos] ?? 0;
      m[key] = STROKE_DASHES[idx % STROKE_DASHES.length];
      posCount[pos] = idx + 1;
    }
    return m;
  }, [playerKeys, keyPositionMap]);

  function fmtDate(d: string) {
    if (!d || typeof d !== "string") return "";
    const parts = d.split("-");
    return parts.length < 3 ? d : `${parts[1]}/${parts[2]}`;
  }

  const isDefaultView = selectedIds.length === 0;

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Daily ADP movement using Underdog's projection ADP — forward-filled on days with no drafts.
        {isDefaultView && " Showing top 10 players by ADP. Click rows to customize."}
      </p>

      <div className="flex flex-col gap-4 sm:flex-row sm:gap-4" style={{ minHeight: 0 }}>
        {/* Left: scrollable player table */}
        <div className="w-full sm:w-56 sm:shrink-0 flex flex-col gap-2 sm:h-[516px]">
          <input
            type="text"
            placeholder="Search players…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary shrink-0"
          />
          <div className="h-48 sm:flex-1 overflow-y-auto rounded-md border border-border" style={{ backgroundColor: "hsl(32, 40%, 98%)" }}>
            <table className="w-full text-xs">
              <thead className="sticky top-0 z-10" style={{ backgroundColor: "hsl(32, 40%, 98%)" }}>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="px-2 py-1.5 w-4" />
                  <th className="px-1 py-1.5">Pos</th>
                  <th className="px-2 py-1.5">Player</th>
                  <th className="px-2 py-1.5 text-right">ADP</th>
                </tr>
              </thead>
              <tbody>
                {filteredPlayers.map((p) => {
                  const selected = selectedIds.includes(p.player_id);
                  return (
                    <tr
                      key={p.player_id}
                      onClick={() => togglePlayer(p.player_id)}
                      className={`cursor-pointer border-b border-border/50 transition-colors ${
                        selected ? "bg-accent/40" : "hover:bg-accent/20"
                      }`}
                    >
                      <td className="px-2 py-1.5 text-primary font-bold">{selected ? "✓" : ""}</td>
                      <td className="px-1 py-1.5">
                        <span
                          className="rounded px-1 py-0.5 font-medium text-[10px]"
                          style={{ color: POSITION_COLORS[p.position], backgroundColor: `${POSITION_COLORS[p.position]}20` }}
                        >
                          {p.position}
                        </span>
                      </td>
                      <td className="px-2 py-1.5 truncate max-w-[100px]">{p.player_name}</td>
                      <td className="px-2 py-1.5 text-right text-muted-foreground">{(p.ending_adp ?? p.avg_pick).toFixed(1)}</td>
                    </tr>
                  );
                })}
                {filteredPlayers.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-2 py-6 text-center text-muted-foreground">No players found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {selectedIds.length > 0 && (
            <Button variant="outline" size="sm" className="text-xs w-full" onClick={() => setSelectedIds([])}>
              Reset to top 10
            </Button>
          )}
        </div>

        {/* Right: chart */}
        <div className="flex-1 min-w-0 h-[360px] sm:h-[516px]">
          {loading && <LoadingSpinner />}
          {error && <p className="py-8 text-center text-sm text-destructive">{error}</p>}
          {!loading && chartData.length > 0 && (
            <Card className="h-full flex flex-col">
              <CardHeader className="pb-2 shrink-0">
                <CardTitle>ADP Movement — {season}</CardTitle>
              </CardHeader>
              <CardContent className="flex-1 min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 4, right: isMobile ? 70 : 130, bottom: 24, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="snapshot_date"
                      tickFormatter={fmtDate}
                      tick={{ fontSize: 10 }}
                      interval="preserveStartEnd"
                      label={{ value: "Date", position: "insideBottom", offset: -12, fontSize: 11 }}
                    />
                    <YAxis
                      reversed
                      tick={{ fontSize: 11 }}
                      tickCount={8}
                      domain={([dataMin, dataMax]: [number, number]) => [
                        Math.max(1, Math.floor(dataMin) - 1),
                        Math.ceil(dataMax) + 2,
                      ]}
                      label={{ value: "ADP", angle: -90, position: "insideLeft", offset: 14, fontSize: 11 }}
                    />
                    <Tooltip
                      labelFormatter={(l) => String(l)}
                      formatter={(v: number, name: string) => [`ADP ${v.toFixed(1)}`, name.split("__")[0]]}
                      itemSorter={(item) => Number(item.value)}
                    />
                    {playerKeys.map((key) => {
                      const color = POSITION_COLORS[keyPositionMap[key]] ?? "#94a3b8";
                      const displayName = key.split("__")[0];
                      return (
                        <Line
                          key={key}
                          type="monotone"
                          dataKey={key}
                          name={key}
                          stroke={color}
                          strokeDasharray={keyDashMap[key]}
                          strokeOpacity={1}
                          dot={false}
                          strokeWidth={2.5}
                          connectNulls
                          label={(props) => (
                            <LineEndLabel
                              {...props}
                              displayName={displayName}
                              color={color}
                              dataLength={chartData.length}
                            />
                          )}
                        />
                      );
                    })}
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
          {!loading && chartData.length === 0 && !error && (
            <div className="py-12 text-center text-sm text-muted-foreground">
              No ADP movement data for {season}.
            </div>
          )}
          {tsData && <DataAsOf dataAsOf={tsData.data_as_of} />}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 3: Round Composition
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ADPExplorer() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [season, _setSeason] = useState(
    searchParams.get("season") ? Number(searchParams.get("season")) : 2025
  );
  const [position, _setPosition] = useState(searchParams.get("position") ?? "All");

  function setSeason(s: number) {
    _setSeason(s);
    setSearchParams(
      (prev) => { const n = new URLSearchParams(prev); n.set("season", String(s)); return n; },
      { replace: true }
    );
  }
  function setPosition(p: string) {
    _setPosition(p);
    setSearchParams(
      (prev) => { const n = new URLSearchParams(prev); n.set("position", p); return n; },
      { replace: true }
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold">ADP Explorer</h1>
          <p className="text-sm text-muted-foreground">
            Historical draft positions derived from actual Underdog picks data.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={String(season)} onValueChange={(v) => setSeason(Number(v))}>
            <SelectTrigger className="w-24">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SEASONS.map((s) => <SelectItem key={s} value={String(s)}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={position} onValueChange={setPosition}>
            <SelectTrigger className="w-24">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {POSITIONS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Tabs defaultValue="leaderboard">
        <TabsList>
          <TabsTrigger value="leaderboard">ADP Leaderboard</TabsTrigger>
          <TabsTrigger value="adp-movement">ADP Movement</TabsTrigger>
          <TabsTrigger value="adp-draft-rate">ADP vs Draft %</TabsTrigger>
        </TabsList>

        <TabsContent value="leaderboard">
          <LeaderboardTab season={season} position={position} />
        </TabsContent>

        <TabsContent value="adp-movement">
          <AdpMovementTab season={season} position={position} />
        </TabsContent>

        <TabsContent value="adp-draft-rate">
          <AdpVsDraftRateTab season={season} position={position} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
