/**
 * History Browser — dashboard of 6 analysis modules.
 * Routing: /history (dashboard) and /history/:moduleId (module detail).
 */
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
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
} from "recharts";
import { BarChart2, Layers, PieChart, Star, TrendingUp, Users } from "lucide-react";
import {
  useAdpAccuracyData,
  useCeilingData,
  useComboData,
  useDraftStructureData,
  useStackData,
} from "@/hooks/useHistory";
import { useAdpRoundComposition, useAdpScarcityCache } from "@/hooks/useAdp";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import DataAsOf from "@/components/DataAsOf";
import LoadingSpinner from "@/components/LoadingSpinner";
import SampleSizeWarning from "@/components/SampleSizeWarning";
import { formatPct, formatScore } from "@/lib/utils";
import { Link as RouterLink } from "react-router-dom";

const SEASONS = [2026, 2025, 2024, 2023, 2022];

const POSITION_COLORS: Record<string, string> = {
  P: "#8B5CF6",
  IF: "#14B8A6",
  OF: "#F97316",
};

const MODULES = [
  {
    id: "ceiling",
    title: "Ceiling Analysis",
    icon: Star,
    description: "Peak windows, grinder vs. peaker quadrants, playoff window distribution.",
  },
  {
    id: "stacking",
    title: "Stacking",
    icon: Layers,
    description: "MLB team stack advance rates and positional stack combinations.",
  },
  {
    id: "draft-structure",
    title: "Draft Structure",
    icon: BarChart2,
    description: "First-address position, pick sequencing heatmaps, archetype outcomes.",
  },
  {
    id: "combos",
    title: "Player Combos",
    icon: Users,
    description: "Two-player pair rates, advance rate delta, anti-combos.",
  },
  {
    id: "adp-accuracy",
    title: "ADP Accuracy",
    icon: TrendingUp,
    description: "Projected vs. actual BPCOR: over and under-performers by position.",
  },
  {
    id: "positional-scarcity",
    title: "Positional Scarcity",
    icon: PieChart,
    description: "Average cumulative positional supply by overall pick number.",
  },
  {
    id: "round-composition",
    title: "Round Composition",
    icon: BarChart2,
    description: "Position breakdown per round — when pitchers, infielders, and outfielders come off the board.",
  },
];

// ---------------------------------------------------------------------------
// Dashboard landing
// ---------------------------------------------------------------------------

function TileCard({ id, title, icon: Icon, description }: { id: string; title: string; icon: React.ElementType; description: string }) {
  return (
    <Link to={`/history/${id}`}>
      <Card className="h-full transition-colors hover:border-primary/40 hover:bg-accent/30">
        <CardContent className="pt-5">
          <div className="mb-3 flex items-center gap-2">
            <Icon className="h-5 w-5 text-primary" />
            <h2 className="text-sm font-semibold">{title}</h2>
          </div>
          <p className="text-xs text-muted-foreground">{description}</p>
          <div className="mt-3">
            <p className="text-xs text-primary">Explore →</p>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function Dashboard() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold">History Browser</h1>
        <p className="text-sm text-muted-foreground">
          Explore historical patterns from Dinger tournament data.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {MODULES.map((m) => (
          <TileCard key={m.id} {...m} />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Module 1: Ceiling
// ---------------------------------------------------------------------------

function CeilingModule({ season }: { season: number }) {
  const { data, loading, error } = useCeilingData({ season });
  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-destructive text-sm">{error}</p>;
  if (!data) return null;

  const { peak_histogram, quadrant_data, playoff_window_distribution } = data.data;

  return (
    <div className="space-y-4">
      <SampleSizeWarning sampleSize={data.sample_size} show={data.low_confidence} />
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Peak Score Distribution</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={peak_histogram} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="bucket" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="hsl(160 60% 45%)" radius={[3, 3, 0, 0]} name="Teams" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Playoff Window Distribution</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={playoff_window_distribution} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="hsl(38 92% 50%)" radius={[3, 3, 0, 0]} name="Peak Weeks" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Grinder / Peaker Quadrant</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="consistency" name="Consistency" label={{ value: "Consistency", position: "insideBottom", offset: -4, fontSize: 11 }} tick={{ fontSize: 11 }} />
              <YAxis dataKey="peak_score" name="Peak Score" label={{ value: "Peak Score", angle: -90, position: "insideLeft", fontSize: 11 }} tick={{ fontSize: 11 }} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload;
                  return (
                    <div className="rounded-md border bg-popover p-2 text-xs shadow-md">
                      <p className="font-semibold">{p.name}</p>
                      <p>Peak: {p.peak_score?.toFixed(1)} · Cons: {p.consistency?.toFixed(2)}</p>
                      <p className="text-muted-foreground">{p.quadrant}</p>
                    </div>
                  );
                }}
              />
              <Scatter data={quadrant_data} fill="hsl(160 60% 45%)" />
            </ScatterChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
      <DataAsOf dataAsOf={data.data_as_of} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Module 2: Stacking
// ---------------------------------------------------------------------------

type StackType = "hitter" | "pitcher" | "combined";

function StackingModule({ season }: { season: number }) {
  const [stackType, setStackType] = useState<StackType>("hitter");
  const [minStackSize, setMinStackSize] = useState(2);
  const { data, loading, error } = useStackData({ season });
  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-destructive text-sm">{error}</p>;
  if (!data) return null;

  const { mlb_team_stacks, positional_stacks } = data.data;

  // Filter team stacks by stack size.
  const filteredTeamStacks = mlb_team_stacks.filter(
    (s) => s.stack_size >= minStackSize
  );

  return (
    <div className="space-y-4">
      <SampleSizeWarning sampleSize={data.sample_size} show={data.low_confidence} />

      {/* Stack type + size controls */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1 text-xs">
          {(["hitter", "pitcher", "combined"] as StackType[]).map((t) => (
            <button
              key={t}
              onClick={() => setStackType(t)}
              className={`rounded px-3 py-1.5 font-medium transition-colors capitalize border ${
                stackType === t
                  ? "border-primary bg-primary/15 text-primary"
                  : "border-border text-muted-foreground hover:bg-accent"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>Min stack size:</span>
          {[2, 3, 4, 5].map((n) => (
            <button
              key={n}
              onClick={() => setMinStackSize(n)}
              className={`h-6 w-6 rounded font-medium transition-colors ${
                minStackSize === n
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-accent"
              }`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      <Tabs defaultValue="team">
        <TabsList>
          <TabsTrigger value="team">MLB Team Stacks</TabsTrigger>
          <TabsTrigger value="positional">Positional Stacks</TabsTrigger>
        </TabsList>
        <TabsContent value="team">
          <Card>
            <CardContent className="pt-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="pb-2">Team</th>
                    <th className="pb-2 text-right">Stack Size</th>
                    <th className="pb-2 text-right">Advance Rate</th>
                    <th className="pb-2 text-right">Sample</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTeamStacks.sort((a, b) => b.avg_advance_rate - a.avg_advance_rate).map((s) => (
                    <tr key={s.mlb_team} className="border-b border-border/50">
                      <td className="py-1.5 font-medium">{s.mlb_team}</td>
                      <td className="py-1.5 text-right">{s.stack_size}</td>
                      <td className="py-1.5 text-right">{formatPct(s.avg_advance_rate)}</td>
                      <td className="py-1.5 text-right text-muted-foreground">{s.sample_size}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredTeamStacks.length === 0 && (
                <p className="py-6 text-center text-sm text-muted-foreground">No data for stack size ≥ {minStackSize}.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="positional">
          <Card>
            <CardContent className="pt-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="pb-2">Position Combo</th>
                    <th className="pb-2 text-right">Advance Rate</th>
                    <th className="pb-2 text-right">Sample</th>
                  </tr>
                </thead>
                <tbody>
                  {positional_stacks.sort((a, b) => b.avg_advance_rate - a.avg_advance_rate).map((s) => (
                    <tr key={s.position_combo} className="border-b border-border/50">
                      <td className="py-1.5 font-medium">{s.position_combo}</td>
                      <td className="py-1.5 text-right">{formatPct(s.avg_advance_rate)}</td>
                      <td className="py-1.5 text-right text-muted-foreground">{s.sample_size}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      <DataAsOf dataAsOf={data.data_as_of} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Module 3: Draft Structure
// ---------------------------------------------------------------------------

function DraftStructureModule({ season }: { season: number }) {
  const { data, loading, error } = useDraftStructureData({ season });
  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-destructive text-sm">{error}</p>;
  if (!data) return null;

  const { first_address_crosstab, archetype_outcomes } = data.data;

  return (
    <div className="space-y-4">
      <SampleSizeWarning sampleSize={data.sample_size} show={data.low_confidence} />
      <Tabs defaultValue="first">
        <TabsList>
          <TabsTrigger value="first">First Address</TabsTrigger>
          <TabsTrigger value="archetypes">Archetypes</TabsTrigger>
        </TabsList>
        <TabsContent value="first">
          <Card>
            <CardHeader><CardTitle>First-Pick Position vs. Advance Rate</CardTitle></CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={first_address_crosstab} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="first_pick_pos" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                  <Bar dataKey="advance_rate" fill="hsl(160 60% 45%)" radius={[3, 3, 0, 0]} name="Advance Rate" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="archetypes">
          <Card>
            <CardContent className="pt-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="pb-2">Archetype</th>
                    <th className="pb-2 text-right">Advance Rate</th>
                    <th className="pb-2 text-right">Avg Score</th>
                    <th className="pb-2 text-right">Sample</th>
                  </tr>
                </thead>
                <tbody>
                  {archetype_outcomes.sort((a, b) => b.advance_rate - a.advance_rate).map((a) => (
                    <tr key={a.archetype} className="border-b border-border/50">
                      <td className="py-1.5 font-medium capitalize">{a.archetype.replace("_", " ")}</td>
                      <td className="py-1.5 text-right">{formatPct(a.advance_rate)}</td>
                      <td className="py-1.5 text-right">{formatScore(a.avg_score)}</td>
                      <td className="py-1.5 text-right text-muted-foreground">{a.sample_size}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      <DataAsOf dataAsOf={data.data_as_of} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Module 4: Combos
// ---------------------------------------------------------------------------

function CombosModule({ season }: { season: number }) {
  const { data, loading, error } = useComboData({ season });
  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-destructive text-sm">{error}</p>;
  if (!data) return null;

  const { top_combos } = data.data;

  return (
    <div className="space-y-4">
      <SampleSizeWarning sampleSize={data.sample_size} show={data.low_confidence} />
      <Card>
        <CardHeader><CardTitle>Top Player Combinations</CardTitle></CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="pb-2">Player A</th>
                <th className="pb-2">Player B</th>
                <th className="pb-2 text-right">Pair Rate</th>
                <th className="pb-2 text-right">Advance Δ</th>
                <th className="pb-2 text-right">Sample</th>
              </tr>
            </thead>
            <tbody>
              {top_combos.map((c, i) => (
                <tr key={i} className="border-b border-border/50">
                  <td className="py-1.5">
                    <RouterLink to={`/players/${c.player_a_id}`} className="hover:text-primary hover:underline">
                      {c.player_a_name}
                    </RouterLink>
                  </td>
                  <td className="py-1.5">
                    <RouterLink to={`/players/${c.player_b_id}`} className="hover:text-primary hover:underline">
                      {c.player_b_name}
                    </RouterLink>
                  </td>
                  <td className="py-1.5 text-right">{formatPct(c.pair_rate)}</td>
                  <td className={`py-1.5 text-right font-medium ${c.advance_rate_delta >= 0 ? "text-primary" : "text-destructive"}`}>
                    {c.advance_rate_delta >= 0 ? "+" : ""}{formatPct(c.advance_rate_delta)}
                  </td>
                  <td className="py-1.5 text-right text-muted-foreground">{c.sample_size}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {top_combos.length === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">No combo data.</p>
          )}
        </CardContent>
      </Card>
      <DataAsOf dataAsOf={data.data_as_of} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Module 5: ADP Accuracy
// ---------------------------------------------------------------------------

function AdpAccuracyModule({ season }: { season: number }) {
  const { data, loading, error } = useAdpAccuracyData({ season });
  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-destructive text-sm">{error}</p>;
  if (!data) return null;

  const sorted = [...data.data].sort((a, b) => b.value_delta - a.value_delta);
  const overPerformers = sorted.slice(0, 15);
  const underPerformers = sorted.slice(-15).reverse();

  return (
    <div className="space-y-4">
      <SampleSizeWarning sampleSize={data.sample_size} show={data.low_confidence} />
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Over-Performers</CardTitle></CardHeader>
          <CardContent>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="pb-1">Player</th>
                  <th className="pb-1 text-right">ADP</th>
                  <th className="pb-1 text-right">Value Δ</th>
                </tr>
              </thead>
              <tbody>
                {overPerformers.map((p) => (
                  <tr key={p.player_id} className="border-b border-border/40">
                    <td className="py-1">
                      <RouterLink to={`/players/${p.player_id}`} className="hover:text-primary hover:underline">
                        {p.name}
                      </RouterLink>
                    </td>
                    <td className="py-1 text-right">{p.adp?.toFixed(1) ?? "—"}</td>
                    <td className="py-1 text-right font-medium text-primary">+{formatScore(p.value_delta)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Under-Performers</CardTitle></CardHeader>
          <CardContent>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="pb-1">Player</th>
                  <th className="pb-1 text-right">ADP</th>
                  <th className="pb-1 text-right">Value Δ</th>
                </tr>
              </thead>
              <tbody>
                {underPerformers.map((p) => (
                  <tr key={p.player_id} className="border-b border-border/40">
                    <td className="py-1">
                      <RouterLink to={`/players/${p.player_id}`} className="hover:text-primary hover:underline">
                        {p.name}
                      </RouterLink>
                    </td>
                    <td className="py-1 text-right">{p.adp?.toFixed(1) ?? "—"}</td>
                    <td className="py-1 text-right font-medium text-destructive">{formatScore(p.value_delta)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
      <DataAsOf dataAsOf={data.data_as_of} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Module 6: Positional Scarcity
// ---------------------------------------------------------------------------

const SEASON_STYLES: Record<number, { stroke: string; dash?: string }> = {
  2023: { stroke: "#94a3b8", dash: "6 3" },
  2024: { stroke: "#60a5fa", dash: "4 2" },
  2025: { stroke: "#34d399" },
  2026: { stroke: "#f97316" },
};

function PositionalScarcityModule({ season: _season }: { season: number }) {
  const s2023 = useAdpScarcityCache(2023);
  const s2024 = useAdpScarcityCache(2024);
  const s2025 = useAdpScarcityCache(2025);
  const s2026 = useAdpScarcityCache(2026);

  const allSeasons = [
    { season: 2023, result: s2023 },
    { season: 2024, result: s2024 },
    { season: 2025, result: s2025 },
    { season: 2026, result: s2026 },
  ];

  const loading = allSeasons.some((s) => s.result.loading);
  const error = allSeasons.find((s) => s.result.error)?.result.error;

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-destructive text-sm">{error}</p>;

  const positions = ["P", "IF", "OF"];

  // Build chart data per position: pick_number → { 2023: val, 2024: val, ... }
  function buildChartData(pos: string) {
    const byPick: Record<number, Record<string, number | string>> = {};
    for (const { season, result } of allSeasons) {
      if (!result.data) continue;
      const sampled = result.data.data.filter(
        (d) => (d.pick_number % 5 === 0 || d.pick_number === 1) && d.position === pos
      );
      for (const row of sampled) {
        if (!byPick[row.pick_number]) byPick[row.pick_number] = { pick_number: row.pick_number };
        byPick[row.pick_number][String(season)] = row.avg_per_draft;
      }
    }
    return Object.values(byPick).sort((a, b) => (a.pick_number as number) - (b.pick_number as number));
  }

  // Milestone: pick where avg_per_draft >= n, per season per position
  function getMilestone(pos: string, season: number, n: number): number | null {
    const rows = allSeasons.find((s) => s.season === season)?.result.data?.data ?? [];
    const row = rows.find((d) => d.position === pos && d.avg_per_draft >= n);
    return row?.pick_number ?? null;
  }

  function getMax(pos: string, season: number): number {
    const rows = allSeasons.find((s) => s.season === season)?.result.data?.data ?? [];
    return rows.filter((d) => d.position === pos).at(-1)?.avg_per_draft ?? 0;
  }

  return (
    <div className="space-y-6">
      <p className="text-xs text-muted-foreground">
        Average cumulative players at each position drafted per team by pick X — all seasons overlaid.
      </p>

      {positions.map((pos) => {
        const chartData = buildChartData(pos);
        return (
          <Card key={pos}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm" style={{ color: POSITION_COLORS[pos] }}>{pos}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Milestone table */}
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground">
                      <th className="pb-1 text-left">Player #</th>
                      {allSeasons.map(({ season }) => (
                        <th key={season} className="pb-1 text-right" style={{ color: SEASON_STYLES[season].stroke }}>{season}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[1, 2, 3, 4, 5, 6].map((n) => (
                      <tr key={n} className="border-b border-border/40">
                        <td className="py-1 text-muted-foreground">#{n} drafted by</td>
                        {allSeasons.map(({ season }) => {
                          const pick = getMilestone(pos, season, n);
                          const round = pick ? Math.ceil(pick / 12) : null;
                          return (
                            <td key={season} className="py-1 text-right font-medium">
                              {pick ? `Rd ${round} / Pk ${pick}` : "—"}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                    <tr>
                      <td className="pt-1 text-muted-foreground">Avg per roster</td>
                      {allSeasons.map(({ season }) => (
                        <td key={season} className="pt-1 text-right text-muted-foreground">
                          {getMax(pos, season).toFixed(1)}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Chart */}
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 16, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="pick_number"
                    label={{ value: "Overall Pick #", position: "insideBottom", offset: -8, fontSize: 10 }}
                    tick={{ fontSize: 10 }}
                  />
                  <YAxis
                    tickFormatter={(v) => v.toFixed(1)}
                    tick={{ fontSize: 10 }}
                    label={{ value: "Avg # Drafted", angle: -90, position: "insideLeft", offset: 10, fontSize: 10 }}
                  />
                  <Tooltip
                    formatter={(v: number, name: string) => [`${v.toFixed(2)}`, name]}
                    labelFormatter={(l) => `Pick ${l}`}
                  />
                  <Legend verticalAlign="top" />
                  {allSeasons.map(({ season }) => (
                    <Line
                      key={season}
                      type="monotone"
                      dataKey={String(season)}
                      stroke={SEASON_STYLES[season].stroke}
                      strokeDasharray={SEASON_STYLES[season].dash}
                      dot={false}
                      strokeWidth={2}
                      name={String(season)}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Module 7: Round Composition
// ---------------------------------------------------------------------------

function RoundCompositionModule({ season }: { season: number }) {
  const { data, loading, error } = useAdpRoundComposition(season);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-destructive text-sm">{error}</p>;
  if (!data) return null;

  if (data.data.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No round composition data for {season}.
      </div>
    );
  }

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
// Module router
// ---------------------------------------------------------------------------

const MODULE_COMPONENTS: Record<string, React.ComponentType<{ season: number }>> = {
  ceiling: CeilingModule,
  stacking: StackingModule,
  "draft-structure": DraftStructureModule,
  combos: CombosModule,
  "adp-accuracy": AdpAccuracyModule,
  "positional-scarcity": PositionalScarcityModule,
  "round-composition": RoundCompositionModule,
};

function ModuleView({ moduleId, season }: { moduleId: string; season: number }) {
  const [, setSearchParams] = useSearchParams();
  const meta = MODULES.find((m) => m.id === moduleId);
  const Component = MODULE_COMPONENTS[moduleId];

  function setSeason(s: number) {
    setSearchParams({ season: String(s) }, { replace: true });
  }

  return (
    <div className="space-y-4">
      {meta && (
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-bold">{meta.title}</h1>
            <p className="text-sm text-muted-foreground">{meta.description}</p>
          </div>
          <Select value={String(season)} onValueChange={(v) => setSeason(Number(v))}>
            <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
            <SelectContent>
              {SEASONS.map((s) => <SelectItem key={s} value={String(s)}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      )}
      {Component ? (
        <Component season={season} />
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Module not yet implemented.
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page entry
// ---------------------------------------------------------------------------

export default function HistoryBrowser() {
  const { moduleId } = useParams<{ moduleId?: string }>();
  const [searchParams] = useSearchParams();

  const season = Number(searchParams.get("season")) || 2025;

  return moduleId ? (
    <ModuleView moduleId={moduleId} season={season} />
  ) : (
    <Dashboard />
  );
}
