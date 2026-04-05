/**
 * History Browser — dashboard of 6 analysis modules.
 * Routing: /history (dashboard) and /history/:moduleId (module detail).
 */
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowLeft, BarChart2, BookOpen, Layers, Star, TrendingUp, Users } from "lucide-react";
import {
  useAdpAccuracyData,
  useCeilingData,
  useComboData,
  useDraftStructureData,
  useStackData,
} from "@/hooks/useHistory";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import DataAsOf from "@/components/DataAsOf";
import LoadingSpinner from "@/components/LoadingSpinner";
import SampleSizeWarning from "@/components/SampleSizeWarning";
import { formatPct, formatScore } from "@/lib/utils";
import { Link as RouterLink } from "react-router-dom";

const SEASONS = [2026, 2025, 2024, 2023, 2022];

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
    id: "player-history",
    title: "Player Profiles",
    icon: BookOpen,
    description: "Historical season-by-season performance. Search from the sidebar.",
  },
];

// ---------------------------------------------------------------------------
// Dashboard landing
// ---------------------------------------------------------------------------

function Dashboard({ season, setSeason }: { season: number; setSeason: (s: number) => void }) {
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold">History Browser</h1>
          <p className="text-sm text-muted-foreground">
            Explore historical patterns across {"{"}2022–{season}{"}"} Dinger tournament data.
          </p>
        </div>
        <Select value={String(season)} onValueChange={(v) => setSeason(Number(v))}>
          <SelectTrigger className="w-24">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SEASONS.map((s) => <SelectItem key={s} value={String(s)}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {MODULES.map(({ id, title, icon: Icon, description }) => (
          <Link key={id} to={`/history/${id}`}>
            <Card className="h-full transition-colors hover:border-primary/40 hover:bg-accent/30">
              <CardContent className="pt-5">
                <div className="mb-3 flex items-center gap-2">
                  <Icon className="h-5 w-5 text-primary" />
                  <h2 className="text-sm font-semibold">{title}</h2>
                </div>
                <p className="text-xs text-muted-foreground">{description}</p>
                <p className="mt-3 text-xs text-primary">Explore →</p>
              </CardContent>
            </Card>
          </Link>
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
// Module router
// ---------------------------------------------------------------------------

const MODULE_COMPONENTS: Record<string, React.ComponentType<{ season: number }>> = {
  ceiling: CeilingModule,
  stacking: StackingModule,
  "draft-structure": DraftStructureModule,
  combos: CombosModule,
  "adp-accuracy": AdpAccuracyModule,
};

function ModuleView({ moduleId, season }: { moduleId: string; season: number }) {
  const navigate = useNavigate();
  const meta = MODULES.find((m) => m.id === moduleId);
  const Component = MODULE_COMPONENTS[moduleId];

  return (
    <div className="space-y-4">
      <button
        onClick={() => navigate("/history")}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> History Browser
      </button>
      {meta && (
        <div>
          <h1 className="text-xl font-bold">{meta.title}</h1>
          <p className="text-sm text-muted-foreground">{meta.description}</p>
        </div>
      )}
      {moduleId === "player-history" ? (
        <Card>
          <CardContent className="py-8">
            <p className="text-sm text-muted-foreground mb-4">
              Player historical profiles live on each player's page. Use the sidebar search to look up a player, then open the <strong>Historical</strong> tab.
            </p>
            <Link
              to="/players"
              className="text-sm text-primary underline hover:no-underline"
            >
              Search for a player →
            </Link>
          </CardContent>
        </Card>
      ) : Component ? (
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
  const [searchParams, setSearchParams] = useSearchParams();

  const seasonParam = searchParams.get("season");
  const [season, _setSeason] = useState(seasonParam ? Number(seasonParam) : 2025);

  function setSeason(s: number) {
    _setSeason(s);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("season", String(s));
      return next;
    }, { replace: true });
  }

  return moduleId ? (
    <ModuleView moduleId={moduleId} season={season} />
  ) : (
    <Dashboard season={season} setSeason={setSeason} />
  );
}
