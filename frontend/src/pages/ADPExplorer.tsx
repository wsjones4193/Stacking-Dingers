/**
 * ADP Explorer — four tabs built from pre-computed historical draft data:
 *   1. ADP Leaderboard — sortable table: who went where, ownership %, consistency
 *   2. Positional Scarcity — avg cumulative count of each position by pick number
 *   3. Round Composition — stacked bar: what positions went in each round
 *   4. ADP vs Draft % — ownership % vs avg pick scatter by position
 */
import { useState } from "react";
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
import { Link, useSearchParams } from "react-router-dom";
import { useAdpLeaderboard, useAdpRoundComposition, useAdpScarcityCache } from "@/hooks/useAdp";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import DataAsOf from "@/components/DataAsOf";
import LoadingSpinner from "@/components/LoadingSpinner";
import type { AdpPlayerSummaryEntry } from "@/types/api";

const SEASONS = [2025, 2024, 2023, 2022];
const POSITIONS = ["All", "P", "IF", "OF"];

const POSITION_COLORS: Record<string, string> = {
  P: "#8B5CF6",
  IF: "#14B8A6",
  OF: "#F97316",
};

// ---------------------------------------------------------------------------
// Tab 1: ADP Leaderboard
// ---------------------------------------------------------------------------

type LBSortKey = "avg_pick" | "ownership_pct" | "pick_std" | "draft_count";
type SortDir = "asc" | "desc";

function LeaderboardTab({ season, position }: { season: number; position: string }) {
  const [sortBy, setSortBy] = useState<LBSortKey>("avg_pick");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
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
      setSortDir(col === "avg_pick" ? "asc" : "desc");
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
    const va = (a[sortBy] ?? 9999) as number;
    const vb = (b[sortBy] ?? 9999) as number;
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
        Average draft position derived from {data.data[0]?.total_season_drafts?.toLocaleString() ?? "—"} drafts
        in {season}. Ownership % = share of all drafts that selected this player.
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
                  onClick={() => toggleSort("avg_pick")}
                >
                  Avg Pick<SortIcon col="avg_pick" />
                </th>
                <th
                  className="pb-2 text-right cursor-pointer hover:text-foreground select-none"
                  onClick={() => toggleSort("pick_std")}
                >
                  Std Dev<SortIcon col="pick_std" />
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
                return (
                  <tr key={p.player_id} className="border-b border-border/50 hover:bg-accent/20">
                    <td className="py-1.5 text-xs text-muted-foreground">{rank}</td>
                    <td className="py-1.5 font-medium">
                      <Link to={`/players/${p.player_id}`} className="hover:text-primary hover:underline">
                        {p.player_name}
                      </Link>
                    </td>
                    <td className="py-1.5">
                      <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${posBadge(p.position)}`}>
                        {p.position}
                      </span>
                    </td>
                    <td className="py-1.5 text-right font-semibold">{p.avg_pick.toFixed(1)}</td>
                    <td className="py-1.5 text-right text-muted-foreground">
                      {p.pick_std != null ? `±${p.pick_std.toFixed(1)}` : "—"}
                    </td>
                    <td className="py-1.5 text-right">{p.ownership_pct.toFixed(1)}%</td>
                    <td className="py-1.5 text-right text-muted-foreground">
                      {p.draft_count.toLocaleString()}
                    </td>
                  </tr>
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

function ScarcityTab({ season }: { season: number }) {
  const { data, loading, error } = useAdpScarcityCache(season);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="py-8 text-center text-sm text-destructive">{error}</p>;
  if (!data) return null;

  if (data.data.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No scarcity data for {season}. Run <code>python scripts/precompute_adp.py</code>.
      </div>
    );
  }

  const positions = ["P", "IF", "OF"];

  // Sample every 5 picks for cleaner chart
  const sampled = data.data.filter((d) => d.pick_number % 5 === 0 || d.pick_number === 1);

  // Reshape: {pick_number, P: avg, IF: avg, OF: avg}
  const byPick: Record<number, Record<string, number>> = {};
  for (const row of sampled) {
    if (!byPick[row.pick_number]) byPick[row.pick_number] = { pick_number: row.pick_number };
    byPick[row.pick_number][row.position] = row.avg_per_draft;
  }
  const chartData = Object.values(byPick).sort((a, b) => a.pick_number - b.pick_number);

  // Max avg count per position (at pick 240) for summary cards
  const maxByPos: Record<string, number> = {};
  for (const pos of positions) {
    const last = data.data.filter((d) => d.position === pos).at(-1);
    maxByPos[pos] = last?.avg_per_draft ?? 0;
  }

  // Pick where avg crosses round milestones (1, 2, 3 ... players of that position)
  const milestones: Record<string, { pick: number; count: number }[]> = {};
  for (const pos of positions) {
    const posRows = data.data.filter((d) => d.position === pos);
    const max = Math.floor(maxByPos[pos]);
    milestones[pos] = [];
    for (let n = 1; n <= Math.min(max, 5); n++) {
      const row = posRows.find((d) => d.avg_per_draft >= n);
      if (row) milestones[pos].push({ pick: row.pick_number, count: n });
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Average cumulative number of players at each position drafted per team by pick X.
        Shows when the draft field starts taking a position — and when supply runs dry.
      </p>

      {/* Milestone cards */}
      <div className="grid grid-cols-3 gap-3">
        {positions.map((pos) => (
          <Card key={pos}>
            <CardHeader className="pb-1 pt-3 px-4">
              <CardTitle className="text-sm" style={{ color: POSITION_COLORS[pos] }}>
                {pos} <span className="text-muted-foreground font-normal text-xs">avg {maxByPos[pos].toFixed(1)} per roster</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3 text-xs space-y-1">
              {milestones[pos].map(({ pick, count }) => (
                <div key={count} className="flex justify-between">
                  <span className="text-muted-foreground">{count}st drafted by pick</span>
                  <span className="font-semibold">{pick}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Avg Cumulative {positions.join(" / ")} Drafted per Team — {season}</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 16, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="pick_number"
                label={{ value: "Overall Pick #", position: "insideBottom", offset: -8, fontSize: 11 }}
                tick={{ fontSize: 11 }}
              />
              <YAxis
                tickFormatter={(v) => v.toFixed(1)}
                tick={{ fontSize: 11 }}
                label={{ value: "Avg # Drafted", angle: -90, position: "insideLeft", offset: 10, fontSize: 11 }}
              />
              <Tooltip
                formatter={(v: number, name: string) => [`${v.toFixed(2)} players`, name]}
                labelFormatter={(l) => `Pick ${l}`}
              />
              <Legend verticalAlign="top" />
              {positions.map((pos) => (
                <Line
                  key={pos}
                  type="monotone"
                  dataKey={pos}
                  stroke={POSITION_COLORS[pos]}
                  dot={false}
                  strokeWidth={2.5}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <DataAsOf dataAsOf={data.data_as_of} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 4: ADP vs Draft % scatter
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

  // Split into per-position datasets for color coding
  const byPos: Record<string, typeof data.data> = {};
  for (const p of data.data) {
    if (!byPos[p.position]) byPos[p.position] = [];
    byPos[p.position].push(p);
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Each dot is a player: X = average draft position, Y = ownership % across all {season} rosters.
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
                dataKey="avg_pick"
                name="Avg Pick"
                type="number"
                domain={[1, 240]}
                label={{ value: "Avg Draft Pick", position: "insideBottom", offset: -12, fontSize: 11 }}
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
                  const p = payload[0].payload;
                  return (
                    <div className="rounded-md border bg-popover p-2 text-xs shadow-md">
                      <p className="font-semibold">{p.player_name}</p>
                      <p className="text-muted-foreground">{p.position}</p>
                      <p>Avg pick: {p.avg_pick?.toFixed(1)}</p>
                      <p>Ownership: {p.ownership_pct?.toFixed(1)}%</p>
                      <p className="text-muted-foreground">±{p.pick_std?.toFixed(1)} std dev</p>
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
// Tab 3: Round Composition
// ---------------------------------------------------------------------------

function RoundCompositionTab({ season }: { season: number }) {
  const { data, loading, error } = useAdpRoundComposition(season);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="py-8 text-center text-sm text-destructive">{error}</p>;
  if (!data) return null;

  if (data.data.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No round composition data for {season}. Run <code>python scripts/precompute_adp.py</code>.
      </div>
    );
  }

  // Reshape: {round: 1, P: 45.2, IF: 33.1, OF: 21.7}
  const byRound: Record<number, Record<string, number | string>> = {};
  for (const row of data.data) {
    if (!byRound[row.round_number]) byRound[row.round_number] = { round: row.round_number };
    byRound[row.round_number][row.position] = row.pct_of_round;
  }
  const chartData = Object.values(byRound).sort((a, b) => (a.round as number) - (b.round as number));

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Percentage of picks in each round taken at each position. Pitchers dominate early rounds
        in high-upside drafts; position group shifts show positional run timing.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Position % by Round — {season}</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={380}>
            <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 16, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="round"
                label={{ value: "Round", position: "insideBottom", offset: -8, fontSize: 11 }}
                tick={{ fontSize: 11 }}
              />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} domain={[0, 100]} />
              <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} labelFormatter={(l) => `Round ${l}`} />
              <Legend verticalAlign="top" />
              <Bar dataKey="P" stackId="a" fill={POSITION_COLORS["P"]} name="P" />
              <Bar dataKey="IF" stackId="a" fill={POSITION_COLORS["IF"]} name="IF" />
              <Bar dataKey="OF" stackId="a" fill={POSITION_COLORS["OF"]} name="OF" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Summary table */}
      <Card>
        <CardContent className="pt-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="pb-2">Round</th>
                <th className="pb-2 text-right" style={{ color: POSITION_COLORS["P"] }}>P %</th>
                <th className="pb-2 text-right" style={{ color: POSITION_COLORS["IF"] }}>IF %</th>
                <th className="pb-2 text-right" style={{ color: POSITION_COLORS["OF"] }}>OF %</th>
              </tr>
            </thead>
            <tbody>
              {chartData.map((row) => (
                <tr key={row.round as number} className="border-b border-border/50 hover:bg-accent/20">
                  <td className="py-1.5 font-medium">Round {row.round}</td>
                  <td className="py-1.5 text-right">{((row["P"] as number) ?? 0).toFixed(1)}%</td>
                  <td className="py-1.5 text-right">{((row["IF"] as number) ?? 0).toFixed(1)}%</td>
                  <td className="py-1.5 text-right">{((row["OF"] as number) ?? 0).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <DataAsOf dataAsOf={data.data_as_of} />
    </div>
  );
}

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
          <TabsTrigger value="scarcity">Positional Scarcity</TabsTrigger>
          <TabsTrigger value="composition">Round Composition</TabsTrigger>
          <TabsTrigger value="adp-draft-rate">ADP vs Draft %</TabsTrigger>
        </TabsList>

        <TabsContent value="leaderboard">
          <LeaderboardTab season={season} position={position} />
        </TabsContent>

        <TabsContent value="scarcity">
          <ScarcityTab season={season} />
        </TabsContent>

        <TabsContent value="composition">
          <RoundCompositionTab season={season} />
        </TabsContent>

        <TabsContent value="adp-draft-rate">
          <AdpVsDraftRateTab season={season} position={position} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
