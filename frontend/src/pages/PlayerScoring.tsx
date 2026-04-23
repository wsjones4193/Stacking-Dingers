/**
 * Player Scoring — weekly point totals from player_weekly_scores.
 * Supports 2024 and 2025 seasons.
 */
import { useState, useRef, useEffect } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { usePlayerSearch } from "@/hooks/usePlayerSearch";
import { usePlayerWeeklyScoring } from "@/hooks/usePlayerScoring";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import LoadingSpinner from "@/components/LoadingSpinner";
import DataAsOf from "@/components/DataAsOf";
import type { PlayerSearchResult, PlayerWeekRow } from "@/types/api";

const SEASONS = [2025, 2024];

// Colors per round
const ROUND_COLORS: Record<number, string> = {
  1: "#60a5fa",  // blue — regular season
  2: "#34d399",  // green — R2
  3: "#f97316",  // orange — R3
  4: "#a78bfa",  // purple — R4
  0: "#94a3b8",  // gray — non-playoff
};

const ROUND_LABELS: Record<number, string> = {
  1: "Round 1",
  2: "Round 2",
  3: "Round 3",
  4: "Round 4",
  0: "N/A",
};

// ---------------------------------------------------------------------------
// Player search autocomplete
// ---------------------------------------------------------------------------

function PlayerSearch({
  onSelect,
  selected,
}: {
  onSelect: (p: PlayerSearchResult) => void;
  selected: PlayerSearchResult | null;
}) {
  const [query, setQuery] = useState(selected?.name ?? "");
  const [open, setOpen] = useState(false);
  const { results } = usePlayerSearch(query);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className="relative w-72" ref={ref}>
      <Input
        placeholder="Search player..."
        value={query}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        className="text-sm"
      />
      {open && results.length > 0 && (
        <div className="absolute z-10 mt-1 w-full rounded-md border border-border bg-popover shadow-md">
          {results.map((p) => (
            <button
              key={p.player_id}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent"
              onMouseDown={() => {
                onSelect(p);
                setQuery(p.name);
                setOpen(false);
              }}
            >
              <span className="font-medium">{p.name}</span>
              <span className="text-xs text-muted-foreground">{p.position} · {p.mlb_team ?? "—"}</span>
              {p.current_adp && (
                <span className="ml-auto text-xs text-muted-foreground">ADP {p.current_adp.toFixed(1)}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Custom tooltip
// ---------------------------------------------------------------------------

function WeekTooltip({ active, payload, label }: { active?: boolean; payload?: { payload: PlayerWeekRow }[]; label?: number }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-md border bg-popover p-2 text-xs shadow-md space-y-0.5">
      <p className="font-semibold">Week {label} — {ROUND_LABELS[row.round_number]}</p>
      <p className="text-primary font-medium">{row.total_points.toFixed(1)} pts</p>
      {row.hitting_points != null && <p className="text-muted-foreground">Hitting: {row.hitting_points.toFixed(1)}</p>}
      {row.pitching_points != null && <p className="text-muted-foreground">Pitching: {row.pitching_points.toFixed(1)}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function PlayerScoring() {
  const [selected, setSelected] = useState<PlayerSearchResult | null>(null);
  const [season, setSeason] = useState(2025);

  const { data, loading, error } = usePlayerWeeklyScoring(selected?.player_id ?? null, season);
  const scoring = data?.data;

  const isOhtani = scoring?.position === "P" && scoring.weeks.some(
    (w) => w.hitting_points != null && w.pitching_points != null
  );

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold">Player Scoring</h1>
          <p className="text-sm text-muted-foreground">
            Weekly point totals by player and season.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <PlayerSearch onSelect={setSelected} selected={selected} />
          <Select value={String(season)} onValueChange={(v) => setSeason(Number(v))}>
            <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
            <SelectContent>
              {SEASONS.map((s) => <SelectItem key={s} value={String(s)}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Empty state */}
      {!selected && (
        <div className="flex h-64 items-center justify-center rounded-md border border-dashed border-border">
          <p className="text-sm text-muted-foreground">Search for a player to view their weekly scoring.</p>
        </div>
      )}

      {loading && <LoadingSpinner />}
      {error && <p className="text-destructive text-sm">{error}</p>}

      {scoring && (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Total Points", value: scoring.summary.total_points.toFixed(1) },
              { label: "Peak Week", value: scoring.summary.peak_week.toFixed(1) },
              { label: "Avg / Week", value: scoring.summary.avg_per_week.toFixed(1) },
              { label: "Weeks Played", value: String(scoring.summary.weeks_played) },
            ].map((s) => (
              <Card key={s.label}>
                <CardContent className="pt-4">
                  <p className="text-xs text-muted-foreground">{s.label}</p>
                  <p className="text-2xl font-bold tabular-nums">{s.value}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Weekly bar chart */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <CardTitle className="text-sm">
                  {scoring.name} — {season} Weekly Scoring
                </CardTitle>
                {/* Round legend */}
                <div className="flex gap-3 flex-wrap">
                  {[1, 2, 3, 4].map((r) => (
                    <div key={r} className="flex items-center gap-1">
                      <div className="h-2.5 w-2.5 rounded-sm" style={{ background: ROUND_COLORS[r] }} />
                      <span className="text-xs text-muted-foreground">{ROUND_LABELS[r]}</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={scoring.weeks} margin={{ top: 4, right: 8, bottom: 16, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="week_number"
                    tick={{ fontSize: 11 }}
                    label={{ value: "Week", position: "insideBottom", offset: -8, fontSize: 11 }}
                  />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip content={<WeekTooltip />} />
                  {isOhtani ? (
                    <>
                      <Bar dataKey="hitting_points" stackId="a" name="Hitting" fill="#60a5fa" />
                      <Bar dataKey="pitching_points" stackId="a" name="Pitching" fill="#a78bfa" radius={[3, 3, 0, 0]} />
                    </>
                  ) : (
                    <Bar dataKey="total_points" radius={[3, 3, 0, 0]}>
                      {scoring.weeks.map((w, i) => (
                        <Cell key={i} fill={ROUND_COLORS[w.round_number]} />
                      ))}
                    </Bar>
                  )}
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Week-by-week table */}
          <Card>
            <CardContent className="pt-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="pb-2 pr-4">Week</th>
                    <th className="pb-2 pr-4">Round</th>
                    {isOhtani && <th className="pb-2 pr-4 text-right">Hitting</th>}
                    {isOhtani && <th className="pb-2 pr-4 text-right">Pitching</th>}
                    <th className="pb-2 text-right">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {scoring.weeks.map((w) => (
                    <tr key={w.week_number} className="border-b border-border/40 hover:bg-accent/20">
                      <td className="py-1.5 pr-4 font-medium">Week {w.week_number}</td>
                      <td className="py-1.5 pr-4">
                        <span
                          className="rounded px-1.5 py-0.5 text-xs font-medium"
                          style={{
                            background: ROUND_COLORS[w.round_number] + "33",
                            color: ROUND_COLORS[w.round_number],
                          }}
                        >
                          {ROUND_LABELS[w.round_number]}
                        </span>
                      </td>
                      {isOhtani && (
                        <td className="py-1.5 pr-4 text-right tabular-nums text-muted-foreground text-xs">
                          {w.hitting_points?.toFixed(1) ?? "—"}
                        </td>
                      )}
                      {isOhtani && (
                        <td className="py-1.5 pr-4 text-right tabular-nums text-muted-foreground text-xs">
                          {w.pitching_points?.toFixed(1) ?? "—"}
                        </td>
                      )}
                      <td className="py-1.5 text-right tabular-nums font-medium">
                        {w.total_points.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <DataAsOf dataAsOf={data.data_as_of} />
        </>
      )}

      {scoring && scoring.weeks.length === 0 && (
        <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-border">
          <p className="text-sm text-muted-foreground">No scoring data for {scoring.name} in {season}.</p>
        </div>
      )}
    </div>
  );
}
