/**
 * Team Analyzer — two views:
 *   1. /teams          → username search → paginated team card list
 *   2. /teams/:draftId → full team detail with roster, weekly breakdown, standings
 */
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertCircle, ArrowLeft, ChevronLeft, ChevronRight } from "lucide-react";
import { useTeam, useTeamSearch } from "@/hooks/useTeams";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import FlagBadge from "@/components/FlagBadge";
import DataAsOf from "@/components/DataAsOf";
import LoadingSpinner from "@/components/LoadingSpinner";
import { flagLabel, formatDate, formatScore } from "@/lib/utils";
import { getCurrentWeek, getWeeksRemainingInRound } from "@/lib/calendar";
import type { RosterFlag, RosterSlot, TeamSummary } from "@/types/api";

// ---------------------------------------------------------------------------
// Flag matrix: position × flag-type count grid
// ---------------------------------------------------------------------------

const FLAG_TYPES = [
  "position_wiped",
  "ghost_player",
  "below_replacement",
  "pitcher_trending_wrong",
  "hitter_usage_decline",
];
const POSITIONS = ["P", "IF", "OF"];

function FlagMatrix({ flags }: { flags: RosterFlag[] }) {
  if (flags.length === 0) return null;

  // Build a position → flag_type → count matrix.
  const matrix: Record<string, Record<string, number>> = {};
  for (const pos of POSITIONS) {
    matrix[pos] = {};
  }
  for (const f of flags) {
    const pos = f.player_position ?? "?";
    if (!POSITIONS.includes(pos)) continue;
    matrix[pos][f.flag_type] = (matrix[pos][f.flag_type] ?? 0) + 1;
  }

  // Only render rows for flag types that appear at least once.
  const activeTypes = FLAG_TYPES.filter((ft) =>
    POSITIONS.some((pos) => (matrix[pos][ft] ?? 0) > 0)
  );
  if (activeTypes.length === 0) return null;

  return (
    <div className="mt-3 overflow-hidden rounded border border-border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border bg-muted/30">
            <th className="px-2 py-1 text-left font-medium text-muted-foreground">Flag</th>
            {POSITIONS.map((pos) => (
              <th key={pos} className="px-2 py-1 text-center font-medium text-muted-foreground">{pos}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {activeTypes.map((ft) => (
            <tr key={ft} className="border-b border-border/50 last:border-0">
              <td className="px-2 py-1 text-muted-foreground">{flagLabel(ft)}</td>
              {POSITIONS.map((pos) => {
                const count = matrix[pos][ft] ?? 0;
                return (
                  <td key={pos} className="px-2 py-1 text-center">
                    {count > 0 ? (
                      <span className={`font-semibold ${ft === "position_wiped" ? "text-red-400" : ft === "ghost_player" ? "text-orange-400" : "text-yellow-400"}`}>
                        {count}
                      </span>
                    ) : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Weeks remaining helper
// ---------------------------------------------------------------------------

function getWeeksRemaining(): number {
  const current = getCurrentWeek();
  if (!current) return 0;
  return getWeeksRemainingInRound(current.week);
}

// ---------------------------------------------------------------------------
// Team list (search view)
// ---------------------------------------------------------------------------

function TeamCard({ team }: { team: TeamSummary }) {
  const weeksRemaining = getWeeksRemaining();

  return (
    <Link to={`/teams/${team.draft_id}`}>
      <Card className="transition-colors hover:border-primary/40 hover:bg-accent/30">
        <CardContent className="pt-4">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-semibold">{team.username}</p>
              <p className="text-xs text-muted-foreground">
                {formatDate(team.draft_date)} · Pick #{team.draft_position} · {team.season}
              </p>
            </div>
            <div className="text-right">
              <p className="text-lg font-bold">{formatScore(team.total_score)}</p>
              <p className="text-xs text-muted-foreground">
                Round {team.round_reached}
                {team.group_rank != null && ` · Rank #${team.group_rank}`}
              </p>
            </div>
          </div>

          {/* Roster strength */}
          {team.roster_strength_score != null && (
            <p className="mt-1 text-xs text-muted-foreground">
              Roster strength:{" "}
              <span className="font-medium text-foreground">{team.roster_strength_score.toFixed(0)}/100</span>
            </p>
          )}

          {/* Advancement probability + gap */}
          {team.advancement_probability != null && (
            <p className="mt-1 text-xs text-muted-foreground">
              Advance probability:{" "}
              <span className="font-medium text-foreground">
                {(team.advancement_probability * 100).toFixed(0)}%
              </span>
            </p>
          )}
          {team.gap_to_advance != null && team.gap_to_advance > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">
              Need{" "}
              <span className="font-medium text-foreground">{formatScore(team.gap_to_advance)} pts</span>
              {weeksRemaining > 0 && ` · ${weeksRemaining} wk${weeksRemaining !== 1 ? "s" : ""} left`}
            </p>
          )}
          {team.gap_to_advance != null && team.gap_to_advance <= 0 && (
            <p className="mt-1 text-xs text-primary font-medium">Currently advancing ✓</p>
          )}

          {/* Flag matrix (position × flag type) */}
          <FlagMatrix flags={team.roster_flags} />
        </CardContent>
      </Card>
    </Link>
  );
}

function TeamList() {
  const [searchParams] = useSearchParams();
  const urlUsername = searchParams.get("username") ?? "";
  const [username, setUsername] = useState(urlUsername);
  const [submittedUsername, setSubmittedUsername] = useState(urlUsername);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 10;

  // If the URL username param changes (sidebar search), re-submit.
  useEffect(() => {
    if (urlUsername && urlUsername !== submittedUsername) {
      setUsername(urlUsername);
      setSubmittedUsername(urlUsername);
      setPage(1);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlUsername]);

  const { data, loading, error } = useTeamSearch(submittedUsername, { page, page_size: PAGE_SIZE });

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setSubmittedUsername(username.trim());
  }

  const teams = data?.data.teams ?? [];
  const total = data?.data.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">Team Analyzer</h1>
        <p className="text-sm text-muted-foreground">Search by Underdog username to find your teams.</p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2">
        <Input
          placeholder="Underdog username…"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="max-w-xs"
        />
        <Button type="submit">Search</Button>
      </form>

      {error && (
        <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {loading && <LoadingSpinner />}

      {!loading && submittedUsername && teams.length === 0 && (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No teams found for "<strong>{submittedUsername}</strong>".
        </p>
      )}

      {teams.length > 0 && (
        <>
          <p className="text-xs text-muted-foreground">{total} team{total !== 1 ? "s" : ""} found</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {teams.map((t) => <TeamCard key={t.draft_id} team={t} />)}
          </div>
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <Button variant="outline" size="icon" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <Button variant="outline" size="icon" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
          <DataAsOf dataAsOf={data?.data_as_of} />
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Team detail view
// ---------------------------------------------------------------------------

function RosterTable({ slots }: { slots: RosterSlot[] }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-border text-left text-xs text-muted-foreground">
          <th className="pb-2 font-medium">Player</th>
          <th className="pb-2 font-medium">Pos</th>
          <th className="pb-2 font-medium">Team</th>
          <th className="pb-2 text-right font-medium">Last Wk</th>
          <th className="pb-2 text-right font-medium">Season</th>
          <th className="pb-2 text-right font-medium">BPCOR</th>
          <th className="pb-2 font-medium">Flags</th>
        </tr>
      </thead>
      <tbody>
        {slots.map((s) => (
          <tr key={s.player_id} className="border-b border-border/50 hover:bg-accent/20">
            <td className="py-1.5 font-medium">
              <Link to={`/players/${s.player_id}`} className="hover:text-primary hover:underline">
                {s.name}
              </Link>
              {s.il_status && <Badge variant="destructive" className="ml-1 text-[10px] py-0">IL</Badge>}
            </td>
            <td className="py-1.5 text-muted-foreground">{s.position}</td>
            <td className="py-1.5 text-muted-foreground">{s.mlb_team ?? "—"}</td>
            <td className="py-1.5 text-right">{formatScore(s.last_week_score)}</td>
            <td className="py-1.5 text-right font-medium">{formatScore(s.season_score)}</td>
            <td className="py-1.5 text-right">{formatScore(s.season_bpcor)}</td>
            <td className="py-1.5">
              <div className="flex flex-wrap gap-1">
                {s.flags.map((f, i) => <FlagBadge key={i} flag={f} />)}
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TeamDetailView({ draftId }: { draftId: string }) {
  const navigate = useNavigate();
  const { data, loading, error } = useTeam(draftId);

  if (loading) return <LoadingSpinner />;
  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
        <AlertCircle className="h-4 w-4 shrink-0" /> {error}
      </div>
    );
  }
  if (!data) return null;

  const team = data.data;

  const weeklyBarData = team.weekly_breakdown.map((wk) => ({
    week: `Wk ${wk.week_number}`,
    score: wk.total_score,
    leftOnBench: wk.left_on_bench_score,
  }));

  return (
    <div className="space-y-5">
      {/* Back link */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Back
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold">{team.username}</h1>
          <p className="text-sm text-muted-foreground">
            {formatDate(team.draft_date)} · Pick #{team.draft_position} · {team.season}
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold">{formatScore(team.total_score)}</p>
          <p className="text-xs text-muted-foreground">
            Round {team.round_reached}
            {team.group_rank != null && ` · Group Rank #${team.group_rank}`}
          </p>
          {team.gap_to_advance != null && (
            <p className={`text-xs font-medium ${team.gap_to_advance <= 0 ? "text-primary" : "text-muted-foreground"}`}>
              {team.gap_to_advance <= 0 ? "Currently advancing ✓" : `${formatScore(team.gap_to_advance)} pts to advance`}
            </p>
          )}
        </div>
      </div>

      {/* Flags */}
      {team.roster_flags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {team.roster_flags.map((f, i) => <FlagBadge key={i} flag={f} />)}
        </div>
      )}

      <DataAsOf dataAsOf={data.data_as_of} />

      {/* Weekly scores chart */}
      {weeklyBarData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Weekly Scores</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={weeklyBarData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="score" fill="hsl(160 60% 45%)" radius={[3, 3, 0, 0]} name="Team Score" />
                <Bar dataKey="leftOnBench" fill="hsl(215 20% 30%)" radius={[3, 3, 0, 0]} name="Left on Bench" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Group standings */}
      {team.group_standings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Group Standings</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="pb-2 font-medium">Rank</th>
                  <th className="pb-2 font-medium">Username</th>
                  <th className="pb-2 text-right font-medium">Score</th>
                  <th className="pb-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {team.group_standings.map((s) => (
                  <tr
                    key={s.draft_id}
                    className={`border-b border-border/50 ${s.draft_id === draftId ? "bg-primary/5" : ""}`}
                  >
                    <td className="py-1.5 font-medium">#{s.rank}</td>
                    <td className="py-1.5">
                      <Link to={`/teams/${s.draft_id}`} className="hover:text-primary hover:underline">
                        {s.username}
                        {s.draft_id === draftId && <span className="ml-1 text-xs text-muted-foreground">(you)</span>}
                      </Link>
                    </td>
                    <td className="py-1.5 text-right font-medium">{formatScore(s.total_score)}</td>
                    <td className="py-1.5">
                      {s.advanced && <Badge variant="default" className="text-xs">Advanced</Badge>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Full roster */}
      <Card>
        <CardHeader>
          <CardTitle>Roster ({team.roster.length} players)</CardTitle>
        </CardHeader>
        <CardContent>
          <RosterTable slots={team.roster} />
        </CardContent>
      </Card>

      {/* Weekly breakdown */}
      {team.weekly_breakdown.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Weekly Lineup Breakdown</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {team.weekly_breakdown.slice().reverse().map((wk) => (
              <div key={wk.week_number} className="rounded-md border border-border p-3">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-semibold">Week {wk.week_number}</p>
                  <p className="text-sm font-bold">{formatScore(wk.total_score)} pts</p>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <p className="mb-1 text-muted-foreground font-medium">Starters</p>
                    {wk.starters.map((s) => (
                      <div key={s.player_id} className="flex justify-between py-0.5">
                        <Link to={`/players/${s.player_id}`} className="hover:text-primary hover:underline">
                          {s.name} ({s.position})
                        </Link>
                        <span>{formatScore(s.last_week_score)}</span>
                      </div>
                    ))}
                    {wk.flex && (
                      <div className="flex justify-between py-0.5 text-yellow-400">
                        <Link to={`/players/${wk.flex.player_id}`} className="hover:underline">
                          {wk.flex.name} ({wk.flex.position}) FLEX
                        </Link>
                        <span>{formatScore(wk.flex.last_week_score)}</span>
                      </div>
                    )}
                  </div>
                  <div>
                    <p className="mb-1 text-muted-foreground font-medium">Bench</p>
                    {wk.bench.map((s) => (
                      <div key={s.player_id} className="flex justify-between py-0.5 text-muted-foreground">
                        <Link to={`/players/${s.player_id}`} className="hover:text-foreground hover:underline">
                          {s.name} ({s.position})
                        </Link>
                        <span>{formatScore(s.last_week_score)}</span>
                      </div>
                    ))}
                    {wk.left_on_bench_score > 0 && (
                      <p className="mt-1 text-yellow-400/80">
                        Left on bench: {formatScore(wk.left_on_bench_score)} pts
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page router
// ---------------------------------------------------------------------------

export default function TeamAnalyzer() {
  const { draftId } = useParams<{ draftId: string }>();
  return draftId ? <TeamDetailView draftId={draftId} /> : <TeamList />;
}
