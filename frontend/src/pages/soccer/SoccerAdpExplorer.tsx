import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import LoadingSpinner from "@/components/LoadingSpinner";
import { useSoccerAdpMovement, useSoccerAdpScarcity, useSoccerAdpScatter } from "@/hooks/useSoccerAdp";
import type { SoccerAdpScatterPoint } from "@/types/soccer";

const POSITIONS = ["ALL", "GK", "DEF", "MID", "FWD"];
const POSITION_COLORS: Record<string, string> = {
  GK: "#eab308",
  DEF: "#3b82f6",
  MID: "#22c55e",
  FWD: "#ef4444",
};

function ScatterTab({ position }: { position: string | undefined }) {
  const { data, loading, error } = useSoccerAdpScatter(position === "ALL" ? undefined : position);
  const navigate = useNavigate();

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!data.length) return <p className="text-sm text-muted-foreground py-8 text-center">No ADP data yet. Run the scraper to populate.</p>;

  const CustomDot = (props: any) => {
    const { cx, cy, payload } = props as { cx: number; cy: number; payload: SoccerAdpScatterPoint };
    return (
      <circle
        cx={cx}
        cy={cy}
        r={4}
        fill={POSITION_COLORS[payload.position] ?? "#888"}
        fillOpacity={0.7}
        className="cursor-pointer hover:r-6"
        onClick={() => navigate(`/soccer/players/${payload.player_id}`)}
      />
    );
  };

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-3">
        X = ADP (lower = earlier pick) · Y = points/90 club season · Click a dot to open player
      </p>
      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="adp"
            name="ADP"
            type="number"
            domain={["auto", "auto"]}
            tick={{ fontSize: 11 }}
            label={{ value: "ADP", position: "insideBottom", offset: -5, fontSize: 11 }}
          />
          <YAxis
            dataKey="points_per_90"
            name="Pts/90"
            tick={{ fontSize: 11 }}
            label={{ value: "Pts/90", angle: -90, position: "insideLeft", fontSize: 11 }}
          />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload as SoccerAdpScatterPoint;
              return (
                <div className="bg-card border border-border rounded-md p-2 text-xs shadow-md">
                  <p className="font-semibold">{d.name}</p>
                  <p className="text-muted-foreground">{d.position} · {d.nationality ?? "—"}</p>
                  <p>ADP: {d.adp.toFixed(1)}</p>
                  <p>Pts/90: {d.points_per_90?.toFixed(2) ?? "—"}</p>
                  {d.draft_rate && <p>Owned: {(d.draft_rate * 100).toFixed(1)}%</p>}
                </div>
              );
            }}
          />
          <Scatter data={data} shape={<CustomDot />} />
        </ScatterChart>
      </ResponsiveContainer>
      <div className="flex gap-3 mt-2 text-xs">
        {Object.entries(POSITION_COLORS).map(([pos, color]) => (
          <span key={pos} className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} />
            {pos}
          </span>
        ))}
      </div>
    </div>
  );
}

function MovementTab({ position }: { position: string | undefined }) {
  const { data, loading } = useSoccerAdpMovement(7, position === "ALL" ? undefined : position);

  if (loading) return <LoadingSpinner />;
  if (!data.length) return <p className="text-sm text-muted-foreground py-8 text-center">No movement data yet.</p>;

  const risers = data.filter((d) => (d.movement ?? 0) > 0).slice(0, 15);
  const fallers = data.filter((d) => (d.movement ?? 0) < 0).slice(-15).reverse();

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
      <div>
        <h3 className="text-sm font-semibold mb-2 text-green-600">Rising (ADP falling) ↑</h3>
        <div className="space-y-1">
          {risers.map((p) => (
            <div key={p.player_id} className="flex items-center gap-2 text-sm py-1">
              <Badge variant="outline" className="text-[10px]">{p.position}</Badge>
              <span className="flex-1 truncate">{p.name}</span>
              <span className="text-green-600 font-medium">+{p.movement?.toFixed(1)}</span>
              <span className="text-muted-foreground text-xs">{p.adp_today?.toFixed(1)}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <h3 className="text-sm font-semibold mb-2 text-red-500">Falling (ADP rising) ↓</h3>
        <div className="space-y-1">
          {fallers.map((p) => (
            <div key={p.player_id} className="flex items-center gap-2 text-sm py-1">
              <Badge variant="outline" className="text-[10px]">{p.position}</Badge>
              <span className="flex-1 truncate">{p.name}</span>
              <span className="text-red-500 font-medium">{p.movement?.toFixed(1)}</span>
              <span className="text-muted-foreground text-xs">{p.adp_today?.toFixed(1)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ScarcityTab() {
  const { data, loading } = useSoccerAdpScarcity();

  if (loading) return <LoadingSpinner />;
  if (!data.length) return <p className="text-sm text-muted-foreground py-8 text-center">No scarcity data yet.</p>;

  const byPosition: Record<string, { pick_number: number; cumulative_pct: number }[]> = {};
  for (const row of data) {
    if (!byPosition[row.position]) byPosition[row.position] = [];
    byPosition[row.position].push({ pick_number: row.pick_number, cumulative_pct: row.cumulative_pct });
  }

  // Build unified data for recharts (pick_number as key)
  const allPicks = [...new Set(data.map((d) => d.pick_number))].sort((a, b) => a - b);
  const chartData = allPicks.map((pick) => {
    const row: Record<string, number | undefined> = { pick };
    for (const pos of Object.keys(byPosition)) {
      const match = byPosition[pos].find((d) => d.pick_number === pick);
      row[pos] = match?.cumulative_pct;
    }
    return row;
  });

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-3">
        Cumulative % of each position drafted by pick number — steeper = scarcer
      </p>
      <ResponsiveContainer width="100%" height={350}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="pick" tick={{ fontSize: 11 }} label={{ value: "Pick #", position: "insideBottom", offset: -5, fontSize: 11 }} />
          <YAxis tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
          {Object.keys(byPosition).map((pos) => (
            <Line
              key={pos}
              type="monotone"
              dataKey={pos}
              stroke={POSITION_COLORS[pos] ?? "#888"}
              dot={false}
              strokeWidth={2}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function SoccerAdpExplorer() {
  const [position, setPosition] = useState("ALL");

  return (
    <div className="p-4 max-w-4xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">ADP Explorer</h1>
          <p className="text-sm text-muted-foreground">The World Pup · 2026 World Cup</p>
        </div>
        <Select value={position} onValueChange={setPosition}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {POSITIONS.map((p) => (
              <SelectItem key={p} value={p}>{p}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Tabs defaultValue="scatter">
        <TabsList>
          <TabsTrigger value="scatter">Value Scatter</TabsTrigger>
          <TabsTrigger value="movement">ADP Movement</TabsTrigger>
          <TabsTrigger value="scarcity">Positional Scarcity</TabsTrigger>
        </TabsList>
        <TabsContent value="scatter" className="pt-4">
          <ScatterTab position={position} />
        </TabsContent>
        <TabsContent value="movement" className="pt-4">
          <MovementTab position={position} />
        </TabsContent>
        <TabsContent value="scarcity" className="pt-4">
          <ScarcityTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
