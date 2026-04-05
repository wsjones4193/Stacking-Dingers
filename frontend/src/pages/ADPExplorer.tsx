/**
 * ADP Explorer — three tabs:
 *   1. Scatter plot: ADP rank vs. BPCOR rank
 *   2. ADP movement: per-player ADP trend lines
 *   3. Positional scarcity: cumulative draft % by pick number
 */
import { useState } from "react";
import {
  CartesianGrid,
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
import { useAdpMovement, useAdpScarcity, useAdpScatter } from "@/hooks/useAdp";
import { useProjectionPreference } from "@/hooks/useProjectionPreference";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import DataAsOf from "@/components/DataAsOf";
import LoadingSpinner from "@/components/LoadingSpinner";
import SampleSizeWarning from "@/components/SampleSizeWarning";
import { Link } from "react-router-dom";

const SEASONS = [2026, 2025, 2024, 2023, 2022];
const POSITIONS = ["All", "P", "IF", "OF"];
const POSITION_COLORS: Record<string, string> = {
  P: "hsl(200 80% 55%)",
  IF: "hsl(38 92% 50%)",
  OF: "hsl(160 60% 45%)",
};

// ---------------------------------------------------------------------------
// Tab 1: Scatter
// ---------------------------------------------------------------------------

function ScatterTab({ season, position, proj }: { season: number; position: string; proj: string }) {
  const filters = {
    season,
    position: position === "All" ? undefined : position,
    proj,
  };
  const { data, loading, error } = useAdpScatter(filters);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="py-8 text-center text-sm text-destructive">{error}</p>;
  if (!data) return null;

  const points = data.data;
  const topValue = [...points].sort((a, b) => b.bpcor - a.bpcor).slice(0, 10);
  const busts = [...points]
    .filter((p) => p.adp_rank <= 50)
    .sort((a, b) => a.bpcor - b.bpcor)
    .slice(0, 5);

  return (
    <div className="space-y-4">
      <SampleSizeWarning sampleSize={data.sample_size} show={data.low_confidence} />
      <div className="grid grid-cols-4 gap-4">
        <div className="col-span-3">
          <Card>
            <CardHeader>
              <CardTitle>ADP Rank vs. BPCOR Rank</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={340}>
                <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="adp_rank" name="ADP Rank" label={{ value: "ADP Rank", position: "insideBottom", offset: -4, fontSize: 11 }} tick={{ fontSize: 11 }} />
                  <YAxis dataKey="bpcor_rank" name="BPCOR Rank" label={{ value: "BPCOR Rank", angle: -90, position: "insideLeft", fontSize: 11 }} tick={{ fontSize: 11 }} />
                  <ZAxis range={[30, 30]} />
                  <Tooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const p = payload[0].payload;
                      return (
                        <div className="rounded-md border bg-popover p-2 text-xs shadow-md">
                          <p className="font-semibold">{p.name}</p>
                          <p className="text-muted-foreground">{p.position} · ADP {p.adp?.toFixed(1)}</p>
                          <p>BPCOR: {p.bpcor?.toFixed(1)}</p>
                        </div>
                      );
                    }}
                  />
                  <Scatter
                    data={points}
                    fill="hsl(160 60% 45%)"
                  />
                </ScatterChart>
              </ResponsiveContainer>
              {points.length === 0 && (
                <p className="py-8 text-center text-sm text-muted-foreground">No data for selected filters.</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar: top values + busts */}
        <div className="space-y-3">
          <Card>
            <CardHeader>
              <CardTitle>Top Values</CardTitle>
            </CardHeader>
            <CardContent>
              {topValue.map((p, i) => (
                <div key={p.player_id} className="flex items-center gap-2 py-1 text-xs">
                  <span className="text-muted-foreground w-4">{i + 1}.</span>
                  <Link to={`/players/${p.player_id}`} className="flex-1 hover:text-primary hover:underline">
                    {p.name}
                  </Link>
                  <span className="font-medium">{p.bpcor.toFixed(0)}</span>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Top Busts</CardTitle>
            </CardHeader>
            <CardContent>
              {busts.map((p, i) => (
                <div key={p.player_id} className="flex items-center gap-2 py-1 text-xs">
                  <span className="text-muted-foreground w-4">{i + 1}.</span>
                  <Link to={`/players/${p.player_id}`} className="flex-1 hover:text-primary hover:underline">
                    {p.name}
                  </Link>
                  <span className="text-destructive font-medium">{p.bpcor.toFixed(0)}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
      <DataAsOf dataAsOf={data.data_as_of} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 2: Movement
// ---------------------------------------------------------------------------

function MovementTab({ season, position }: { season: number; position: string }) {
  const { data, loading, error } = useAdpMovement({
    season,
    position: position === "All" ? undefined : position,
  });

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="py-8 text-center text-sm text-destructive">{error}</p>;
  if (!data) return null;

  const points = data.data;

  // Group by player for multi-line chart.
  const playerMap = new Map<number, { name: string; position: string; points: typeof points }>();
  for (const pt of points) {
    if (!playerMap.has(pt.player_id)) {
      playerMap.set(pt.player_id, { name: pt.name, position: pt.position, points: [] });
    }
    playerMap.get(pt.player_id)!.points.push(pt);
  }

  // Show top 20 most-drafted players only to avoid chart clutter.
  const topPlayers = [...playerMap.entries()]
    .sort((a, b) => {
      const latestA = a[1].points.at(-1)?.draft_rate ?? 0;
      const latestB = b[1].points.at(-1)?.draft_rate ?? 0;
      return latestB - latestA;
    })
    .slice(0, 20);

  // Reshape for recharts: each point is {date, [player_name]: adp}
  const allDates = [...new Set(points.map((p) => p.snapshot_date))].sort();
  const chartData = allDates.map((d) => {
    const row: Record<string, string | number> = { date: d.slice(5) };
    for (const [pid, { name }] of topPlayers) {
      const pt = playerMap.get(pid)?.points.find((p) => p.snapshot_date === d);
      if (pt) row[name] = pt.adp;
    }
    return row;
  });

  const colors = ["hsl(160 60% 45%)", "hsl(38 92% 50%)", "hsl(200 80% 55%)", "hsl(270 60% 60%)", "hsl(0 60% 55%)"];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>ADP Movement (Top 20 by draft rate)</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis reversed tick={{ fontSize: 11 }} />
              <Tooltip />
              {topPlayers.map(([, { name }], i) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  stroke={colors[i % colors.length]}
                  dot={false}
                  strokeWidth={1.5}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
          {chartData.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">No ADP movement data.</p>
          )}
        </CardContent>
      </Card>
      <DataAsOf dataAsOf={data.data_as_of} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 3: Scarcity
// ---------------------------------------------------------------------------

function ScarcityTab({ season }: { season: number }) {
  const { data, loading, error } = useAdpScarcity({ season });

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="py-8 text-center text-sm text-destructive">{error}</p>;
  if (!data) return null;

  const grouped: Record<string, typeof data.data> = {};
  for (const pt of data.data) {
    if (!grouped[pt.position]) grouped[pt.position] = [];
    grouped[pt.position].push(pt);
  }

  const allPicks = [...new Set(data.data.map((p) => p.pick_number))].sort((a, b) => a - b);
  const chartData = allPicks.map((pick) => {
    const row: Record<string, number> = { pick };
    for (const pos of Object.keys(grouped)) {
      const pt = grouped[pos].find((p) => p.pick_number === pick);
      if (pt) row[pos] = +(pt.cumulative_pct_drafted * 100).toFixed(1);
    }
    return row;
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Positional Scarcity Curves</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="pick" label={{ value: "Pick #", position: "insideBottom", offset: -4, fontSize: 11 }} tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => `${v}%`} />
              {Object.keys(grouped).map((pos) => (
                <Line
                  key={pos}
                  type="monotone"
                  dataKey={pos}
                  stroke={POSITION_COLORS[pos] ?? "hsl(215 20% 60%)"}
                  dot={false}
                  strokeWidth={2}
                  name={pos}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
          {chartData.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">No scarcity data.</p>
          )}
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
  const [proj, setProj] = useProjectionPreference();
  const [season, setSeason] = useState(2026);
  const [position, setPosition] = useState("All");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold">ADP Explorer</h1>
          <p className="text-sm text-muted-foreground">Analyze draft value, movement, and positional scarcity.</p>
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
          <Select value={proj} onValueChange={(v) => setProj(v as typeof proj)}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="blended">Blended</SelectItem>
              <SelectItem value="steamer">Steamer</SelectItem>
              <SelectItem value="atc">ATC</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <Tabs defaultValue="scatter">
        <TabsList>
          <TabsTrigger value="scatter">Value Scatter</TabsTrigger>
          <TabsTrigger value="movement">ADP Movement</TabsTrigger>
          <TabsTrigger value="scarcity">Positional Scarcity</TabsTrigger>
        </TabsList>
        <TabsContent value="scatter">
          <ScatterTab season={season} position={position} proj={proj} />
        </TabsContent>
        <TabsContent value="movement">
          <MovementTab season={season} position={position} />
        </TabsContent>
        <TabsContent value="scarcity">
          <ScarcityTab season={season} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
