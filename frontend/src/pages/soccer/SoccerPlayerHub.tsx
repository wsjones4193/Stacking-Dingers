import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import LoadingSpinner from "@/components/LoadingSpinner";
import { useSoccerPlayer, useSoccerPlayerSearch } from "@/hooks/useSoccerPlayers";
import { useSoccerAdpHistory } from "@/hooks/useSoccerAdp";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

const POSITION_COLORS: Record<string, string> = {
  GK: "bg-yellow-500/20 text-yellow-600",
  DEF: "bg-blue-500/20 text-blue-600",
  MID: "bg-green-500/20 text-green-600",
  FWD: "bg-red-500/20 text-red-600",
};

function PlayerSearch({ onSelect }: { onSelect: (id: number) => void }) {
  const [query, setQuery] = useState("");
  const { results, loading } = useSoccerPlayerSearch(query);

  return (
    <div className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search players..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      {query.length >= 2 && (
        <div className="absolute top-full mt-1 left-0 right-0 z-10 bg-card border border-border rounded-md shadow-lg max-h-64 overflow-y-auto">
          {loading && <div className="px-3 py-2 text-sm text-muted-foreground">Searching...</div>}
          {!loading && results.length === 0 && (
            <div className="px-3 py-2 text-sm text-muted-foreground">No players found</div>
          )}
          {results.map((p) => (
            <button
              key={p.player_id}
              className="w-full text-left flex items-center gap-3 px-3 py-2 hover:bg-accent text-sm"
              onClick={() => { onSelect(p.player_id); setQuery(""); }}
            >
              <Badge variant="outline" className={`text-[10px] px-1.5 ${POSITION_COLORS[p.position] ?? ""}`}>
                {p.position}
              </Badge>
              <span className="flex-1 font-medium">{p.name}</span>
              {p.nationality && <span className="text-muted-foreground text-xs">{p.nationality}</span>}
              {p.current_adp && (
                <span className="text-xs text-muted-foreground">ADP {p.current_adp.toFixed(1)}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function AdpChart({ playerId }: { playerId: number }) {
  const { data, loading } = useSoccerAdpHistory(playerId, 30);

  if (loading) return <LoadingSpinner className="py-6" />;
  if (!data || data.length < 2) return (
    <p className="text-sm text-muted-foreground py-4">Not enough ADP history yet.</p>
  );

  const chartData = data.map((d) => ({
    date: d.date.slice(5),  // MM-DD
    adp: d.adp,
  }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis reversed domain={["auto", "auto"]} tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v: number) => v?.toFixed(1)} />
        <Line type="monotone" dataKey="adp" stroke="hsl(var(--primary))" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function PlayerDetail({ playerId }: { playerId: number }) {
  const { data, loading, error } = useSoccerPlayer(playerId);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!data) return null;

  const latestStats = data.stats[0] ?? null;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-xl font-bold">{data.name}</h2>
            <Badge className={POSITION_COLORS[data.position] ?? ""}>{data.position}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            {data.nationality && <span>{data.nationality}</span>}
            {data.current_club && <span> · {data.current_club}</span>}
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold">{data.current_adp?.toFixed(1) ?? "—"}</p>
          <p className="text-xs text-muted-foreground">Current ADP</p>
          {data.draft_rate && (
            <p className="text-xs text-muted-foreground">{(data.draft_rate * 100).toFixed(1)}% owned</p>
          )}
        </div>
      </div>

      <Tabs defaultValue="stats">
        <TabsList>
          <TabsTrigger value="stats">Club Stats</TabsTrigger>
          <TabsTrigger value="adp">ADP Trend</TabsTrigger>
        </TabsList>

        <TabsContent value="stats">
          {!latestStats ? (
            <p className="text-sm text-muted-foreground py-4">No stats available yet.</p>
          ) : (
            <div className="space-y-3">
              <p className="text-xs text-muted-foreground">
                {latestStats.season} · {latestStats.club ?? "—"} · {latestStats.competition ?? "—"}
              </p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {[
                  { label: "Goals", value: latestStats.goals },
                  { label: "Assists", value: latestStats.assists },
                  { label: "Pts/90", value: latestStats.points_per_90?.toFixed(1) ?? "—" },
                  { label: "Total Pts", value: latestStats.calculated_points.toFixed(1) },
                  { label: "Shots OT", value: latestStats.shots_on_target },
                  { label: "Chances", value: latestStats.chances_created },
                  { label: "Crosses", value: latestStats.crosses },
                  { label: "Tackles", value: latestStats.tackles_successful },
                  ...(data.position === "GK" ? [
                    { label: "Saves", value: latestStats.saves },
                    { label: "Pen Saves", value: latestStats.penalty_saves },
                    { label: "Clean Sheets", value: latestStats.clean_sheets },
                    { label: "Goals Con.", value: latestStats.goals_conceded },
                  ] : data.position === "DEF" ? [
                    { label: "Clean Sheets", value: latestStats.clean_sheets },
                  ] : []),
                ].map(({ label, value }) => (
                  <div key={label} className="bg-muted/40 rounded-md px-3 py-2 text-center">
                    <p className="text-lg font-semibold">{value}</p>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                {latestStats.matches_played} apps · {latestStats.minutes_played} min
              </p>
            </div>
          )}
        </TabsContent>

        <TabsContent value="adp">
          <p className="text-xs text-muted-foreground mb-2">ADP over last 30 days (lower = earlier pick)</p>
          <AdpChart playerId={playerId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default function SoccerPlayerHub() {
  const { playerId } = useParams<{ playerId: string }>();
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState<number | null>(
    playerId ? parseInt(playerId) : null
  );

  const handleSelect = (id: number) => {
    setSelectedId(id);
    navigate(`/soccer/players/${id}`);
  };

  return (
    <div className="p-4 max-w-3xl mx-auto space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Player Hub</h1>
        <p className="text-sm text-muted-foreground">The World Pup · 2026 World Cup</p>
      </div>

      <PlayerSearch onSelect={handleSelect} />

      {selectedId && (
        <Card>
          <CardContent className="pt-5">
            <PlayerDetail playerId={selectedId} />
          </CardContent>
        </Card>
      )}

      {!selectedId && (
        <div className="text-center py-16 text-muted-foreground">
          <Search className="h-8 w-8 mx-auto mb-3 opacity-30" />
          <p className="text-sm">Search for a player to view their stats and ADP trend</p>
        </div>
      )}
    </div>
  );
}
