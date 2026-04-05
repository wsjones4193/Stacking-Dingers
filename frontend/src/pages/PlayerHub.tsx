/**
 * Player Hub — shows player scoring trajectory, ADP trend, value panel,
 * ownership, and roster context for a selected player.
 *
 * Two modes driven by the current date:
 *   Draft Season  (before March 25): projections and ADP are primary.
 *   In-Season     (March 25+):       scoring trajectory and BPCOR are primary.
 */
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertCircle } from "lucide-react";
import { usePlayer, usePlayerHistory } from "@/hooks/usePlayer";
import { useProjectionPreference } from "@/hooks/useProjectionPreference";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import DataAsOf from "@/components/DataAsOf";
import LoadingSpinner from "@/components/LoadingSpinner";
import SampleSizeWarning from "@/components/SampleSizeWarning";
import { formatPct, formatScore } from "@/lib/utils";

const OPENING_DAY = new Date("2026-03-25");

const SEASONS = [2026, 2025, 2024, 2023, 2022];

type ScoreView = "game" | "weekly" | "cumulative";
type HubMode = "in-season" | "draft";

// Round transition reference lines for Recharts — weeks 18, 20, 22 mark R1/R2/R3 ends.
const ROUND_TRANSITIONS = [
  { week: "Wk 18", label: "R1 end" },
  { week: "Wk 20", label: "R2 end" },
  { week: "Wk 22", label: "R3 end" },
];

export default function PlayerHub() {
  const { playerId } = useParams<{ playerId: string }>();
  const navigate = useNavigate();
  const [proj, setProj] = useProjectionPreference();
  const [season, setSeason] = useState(2026);
  const [scoreView, setScoreView] = useState<ScoreView>("game");
  const [hubMode, setHubMode] = useState<HubMode>(
    new Date() >= OPENING_DAY ? "in-season" : "draft"
  );

  const numericId = playerId ? parseInt(playerId, 10) : null;
  const { data, loading, error } = usePlayer(numericId, season, proj);
  const { data: histData } = usePlayerHistory(numericId);

  // Redirect to players list if no ID is provided.
  useEffect(() => {
    if (!playerId) navigate("/players");
  }, [playerId, navigate]);

  if (!numericId) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
        <p className="text-sm">Search for a player using the sidebar.</p>
      </div>
    );
  }

  if (loading) return <LoadingSpinner />;

  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
        <AlertCircle className="h-4 w-4 shrink-0" />
        {error}
      </div>
    );
  }

  if (!data) return null;

  const player = data.data;

  // Build chart datasets from API data.
  const gameChartData = player.scoring_trajectory.map((pt) => ({
    date: pt.game_date.slice(5),   // "MM-DD"
    score: pt.calculated_score,
    cumulative: pt.cumulative_score,
    hot: pt.is_hot,
  }));

  const weeklyChartData = player.weekly_scores.map((pt) => ({
    week: `Wk ${pt.week_number}`,
    score: pt.calculated_score,
    slot: pt.is_starter ? "starter" : pt.is_flex ? "flex" : "bench",
  }));

  const adpChartData = player.adp_trend.map((pt) => ({
    date: pt.snapshot_date.slice(5),
    adp: pt.adp,
    rate: +(pt.draft_rate * 100).toFixed(1),
  }));

  const historyRows = histData?.data ?? [];

  return (
    <div className="space-y-5">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold">{player.name}</h1>
            <Badge variant="outline">{player.position}</Badge>
            {player.mlb_team && (
              <Badge variant="secondary">{player.mlb_team}</Badge>
            )}
            {player.il_status && (
              <Badge variant="destructive">IL</Badge>
            )}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {player.days_since_last_game != null
              ? `Last played ${player.days_since_last_game} day${player.days_since_last_game !== 1 ? "s" : ""} ago`
              : "No game log data"}
            {" · "}
            {player.draft_count} roster{player.draft_count !== 1 ? "s" : ""}
            {player.ownership_pct != null && ` · ${formatPct(player.ownership_pct)} owned`}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Mode toggle */}
          <div className="flex rounded-md border border-border overflow-hidden text-xs">
            <button
              onClick={() => setHubMode("in-season")}
              className={`px-3 py-1.5 font-medium transition-colors ${
                hubMode === "in-season"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent"
              }`}
            >
              In-Season
            </button>
            <button
              onClick={() => setHubMode("draft")}
              className={`px-3 py-1.5 font-medium transition-colors ${
                hubMode === "draft"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent"
              }`}
            >
              Draft Season
            </button>
          </div>

          {/* Season selector */}
          <Select value={String(season)} onValueChange={(v) => setSeason(Number(v))}>
            <SelectTrigger className="w-24">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SEASONS.map((s) => (
                <SelectItem key={s} value={String(s)}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Projection system selector */}
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

      <SampleSizeWarning sampleSize={data.sample_size} show={data.low_confidence} />
      <DataAsOf dataAsOf={data.data_as_of} />

      {/* ── Stat chips ─────────────────────────────────────────── */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Season BPCOR", value: formatScore(player.season_bpcor) },
          { label: "Current ADP", value: player.current_adp != null ? player.current_adp.toFixed(1) : "—" },
          { label: "Draft Rate", value: formatPct(player.current_draft_rate) },
          { label: "Peer Group", value: player.peer_group ?? "—" },
        ].map(({ label, value }) => (
          <Card key={label}>
            <CardContent className="pt-4">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="mt-1 text-lg font-semibold">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── Main tabs ──────────────────────────────────────────── */}
      <Tabs defaultValue={hubMode === "in-season" ? "scoring" : "adp"}>
        <TabsList>
          {hubMode === "in-season" && <TabsTrigger value="scoring">Scoring</TabsTrigger>}
          {hubMode === "draft" && <TabsTrigger value="draft-profile">Draft Profile</TabsTrigger>}
          <TabsTrigger value="adp">ADP Trend</TabsTrigger>
          <TabsTrigger value="value">Value vs ADP</TabsTrigger>
          <TabsTrigger value="ownership">Ownership</TabsTrigger>
          <TabsTrigger value="history">Historical</TabsTrigger>
        </TabsList>

        {/* ── Draft Season profile ───────────────────────────── */}
        {hubMode === "draft" && (
          <TabsContent value="draft-profile">
            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardHeader><CardTitle>Draft Profile</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <p className="text-xs text-muted-foreground">Positional rank by ADP</p>
                    <p className="font-semibold">{player.peer_group ?? "—"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Current ADP</p>
                    <p className="font-semibold">{player.current_adp?.toFixed(1) ?? "—"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Projected draft rate ({proj})</p>
                    <p className="font-semibold">{formatPct(player.current_draft_rate)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Projected points ({proj})</p>
                    <p className="font-semibold">{formatScore(player.projected_points)}</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>Historical Performance</CardTitle></CardHeader>
                <CardContent>
                  {(histData?.data ?? []).length === 0 ? (
                    <p className="py-4 text-center text-sm text-muted-foreground">No prior season data.</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border text-left text-xs text-muted-foreground">
                          <th className="pb-2">Season</th>
                          <th className="pb-2 text-right">BPCOR</th>
                          <th className="pb-2 text-right">ADP</th>
                          <th className="pb-2 text-right">Owned</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(histData?.data ?? []).map((row) => (
                          <tr key={row.season} className="border-b border-border/50">
                            <td className="py-1.5">{row.season}</td>
                            <td className="py-1.5 text-right">{formatScore(row.bpcor)}</td>
                            <td className="py-1.5 text-right">{row.adp?.toFixed(1) ?? "—"}</td>
                            <td className="py-1.5 text-right">{formatPct(row.ownership_pct)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        )}

        {/* ── Scoring trajectory ─────────────────────────────── */}
        {hubMode === "in-season" && (
          <TabsContent value="scoring">
            <Card>
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle>Scoring Trajectory</CardTitle>
                <div className="flex gap-1">
                  {(["game", "weekly", "cumulative"] as ScoreView[]).map((v) => (
                    <button
                      key={v}
                      onClick={() => setScoreView(v)}
                      className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                        scoreView === v
                          ? "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:bg-accent"
                      }`}
                    >
                      {v === "game" ? "Game" : v === "weekly" ? "Weekly" : "Cumulative"}
                    </button>
                  ))}
                </div>
              </CardHeader>
              <CardContent>
                {scoreView === "weekly" ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={weeklyChartData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      {/* Round transition markers */}
                      {ROUND_TRANSITIONS.map((rt) => (
                        <ReferenceLine
                          key={rt.week}
                          x={rt.week}
                          stroke="hsl(215 20% 35%)"
                          strokeDasharray="4 4"
                          label={{ value: rt.label, fontSize: 9, fill: "hsl(215 20% 55%)" }}
                        />
                      ))}
                      <Bar
                        dataKey="score"
                        radius={[3, 3, 0, 0]}
                        name="Best Ball Score"
                      >
                        {weeklyChartData.map((entry, index) => (
                          <Cell
                            key={index}
                            fill={
                              entry.slot === "bench"
                                ? "hsl(215 20% 35%)"
                                : "hsl(160 60% 45%)"
                            }
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={gameChartData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Line
                        type="monotone"
                        dataKey={scoreView === "cumulative" ? "cumulative" : "score"}
                        stroke="hsl(160 60% 45%)"
                        dot={(props) => {
                          // Hot games get an orange dot; cold games get a muted dot.
                          const entry = gameChartData[props.index];
                          if (!entry) return <circle key={props.index} />;
                          const fill = entry.hot
                            ? "hsl(38 92% 50%)"
                            : "hsl(215 20% 45%)";
                          return (
                            <circle
                              key={props.index}
                              cx={props.cx}
                              cy={props.cy}
                              r={3}
                              fill={fill}
                              stroke="none"
                            />
                          );
                        }}
                        strokeWidth={2}
                        name={scoreView === "cumulative" ? "Cumulative" : "Score"}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                )}
                {gameChartData.length === 0 && (
                  <p className="py-8 text-center text-sm text-muted-foreground">No game log data for this season.</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* ── ADP Trend ──────────────────────────────────────── */}
        <TabsContent value="adp">
          <Card>
            <CardHeader>
              <CardTitle>ADP Trend</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-3 flex gap-6 text-sm">
                {[
                  { label: "Current", value: player.current_adp?.toFixed(1) ?? "—" },
                  { label: "Peak (low)", value: player.peak_adp?.toFixed(1) ?? "—" },
                  { label: "High (worst)", value: player.low_adp?.toFixed(1) ?? "—" },
                  { label: "Draft Rate", value: formatPct(player.current_draft_rate) },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <p className="font-semibold">{value}</p>
                  </div>
                ))}
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={adpChartData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis reversed tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="adp" stroke="hsl(160 60% 45%)" dot={false} strokeWidth={2} name="ADP" />
                </LineChart>
              </ResponsiveContainer>
              {adpChartData.length === 0 && (
                <p className="py-8 text-center text-sm text-muted-foreground">No ADP history available.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Value vs ADP ───────────────────────────────────── */}
        <TabsContent value="value">
          <Card>
            <CardHeader>
              <CardTitle>Value vs. ADP</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground">Season BPCOR</p>
                  <p className="text-lg font-semibold">{formatScore(player.season_bpcor)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Projected Points ({proj})</p>
                  <p className="text-lg font-semibold">{formatScore(player.projected_points)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Peer Group</p>
                  <p className="text-lg font-semibold">{player.peer_group ?? "—"}</p>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                Value delta = actual BPCOR minus projected value at draft ADP. Positive = outperforming expectation.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Ownership ──────────────────────────────────────── */}
        <TabsContent value="ownership">
          <Card>
            <CardHeader>
              <CardTitle>Ownership</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-8">
                <div>
                  <p className="text-xs text-muted-foreground">Overall Ownership</p>
                  <p className="text-2xl font-bold">{formatPct(player.ownership_pct)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Roster Count</p>
                  <p className="text-2xl font-bold">{player.draft_count}</p>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                Ownership = percentage of drafts in which this player was selected (season {season}).
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Historical ─────────────────────────────────────── */}
        <TabsContent value="history">
          <Card>
            <CardHeader>
              <CardTitle>Historical Performance</CardTitle>
            </CardHeader>
            <CardContent>
              {historyRows.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">No multi-season history.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-muted-foreground">
                      <th className="pb-2 font-medium">Season</th>
                      <th className="pb-2 font-medium">BPCOR</th>
                      <th className="pb-2 font-medium">ADP</th>
                      <th className="pb-2 font-medium">Owned</th>
                      <th className="pb-2 font-medium">Peak Wk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historyRows.map((row) => (
                      <tr key={row.season} className="border-b border-border/50">
                        <td className="py-2 font-medium">{row.season}</td>
                        <td className="py-2">{formatScore(row.bpcor)}</td>
                        <td className="py-2">{row.adp?.toFixed(1) ?? "—"}</td>
                        <td className="py-2">{formatPct(row.ownership_pct)}</td>
                        <td className="py-2">{formatScore(row.peak_week_score)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
