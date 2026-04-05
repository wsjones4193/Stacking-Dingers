/**
 * Public Leaderboard — all teams across seasons, sortable and filterable.
 * Paginated at 25 per page. Links to Team Analyzer for each team.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from "lucide-react";
import { useLeaderboard } from "@/hooks/useLeaderboard";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import DataAsOf from "@/components/DataAsOf";
import LoadingSpinner from "@/components/LoadingSpinner";
import SampleSizeWarning from "@/components/SampleSizeWarning";
import { formatScore } from "@/lib/utils";

const SEASONS = [2026, 2025, 2024, 2023, 2022];
const ROUNDS = [
  { label: "All", value: "" },
  { label: "Round 1", value: "1" },
  { label: "Round 2", value: "2" },
  { label: "Round 3", value: "3" },
  { label: "Finals", value: "4" },
];
const POSITIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
const PAGE_SIZE = 25;

type SortKey = "total_score" | "round_reached" | "peak_week_score" | "consistency_score";
type SortDir = "asc" | "desc";

export default function Leaderboard() {
  const [season, setSeason] = useState(2026);
  const [roundFilter, setRoundFilter] = useState("");
  const [draftPosition, setDraftPosition] = useState<number | undefined>();
  const [sortBy, setSortBy] = useState<SortKey>("total_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(1);

  const { data, loading, error } = useLeaderboard({
    season,
    draft_position: draftPosition,
    sort_by: `${sortBy}:${sortDir}`,
    page,
    page_size: PAGE_SIZE,
  });

  function toggleSort(col: SortKey) {
    if (sortBy === col) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
    setPage(1);
  }

  function SortIcon({ col }: { col: SortKey }) {
    if (sortBy !== col) return <ChevronDown className="ml-1 h-3 w-3 opacity-30 inline" />;
    return sortDir === "desc" ? (
      <ChevronDown className="ml-1 h-3 w-3 text-primary inline" />
    ) : (
      <ChevronUp className="ml-1 h-3 w-3 text-primary inline" />
    );
  }

  const entries = data?.data.entries ?? [];
  const total = data?.data.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  const filteredEntries = roundFilter
    ? entries.filter((e) => e.round_reached === Number(roundFilter))
    : entries;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">Leaderboard</h1>
        <p className="text-sm text-muted-foreground">
          All teams ranked by total score. {total > 0 && `${total.toLocaleString()} teams.`}
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Select value={String(season)} onValueChange={(v) => { setSeason(Number(v)); setPage(1); }}>
          <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
          <SelectContent>
            {SEASONS.map((s) => <SelectItem key={s} value={String(s)}>{s}</SelectItem>)}
          </SelectContent>
        </Select>

        <Select value={roundFilter} onValueChange={(v) => { setRoundFilter(v); setPage(1); }}>
          <SelectTrigger className="w-28"><SelectValue placeholder="Round" /></SelectTrigger>
          <SelectContent>
            {ROUNDS.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
          </SelectContent>
        </Select>

        <Select
          value={draftPosition != null ? String(draftPosition) : ""}
          onValueChange={(v) => { setDraftPosition(v ? Number(v) : undefined); setPage(1); }}
        >
          <SelectTrigger className="w-32"><SelectValue placeholder="Draft seat" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="">All seats</SelectItem>
            {POSITIONS.map((p) => <SelectItem key={p} value={String(p)}>Seat {p}</SelectItem>)}
          </SelectContent>
        </Select>

        {(roundFilter || draftPosition) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { setRoundFilter(""); setDraftPosition(undefined); setPage(1); }}
          >
            Clear filters
          </Button>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {loading && <LoadingSpinner />}

      {!loading && data && (
        <>
          <SampleSizeWarning sampleSize={data.sample_size} show={data.low_confidence} />
          <Card>
            <CardContent className="pt-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="pb-2 w-8">#</th>
                    <th className="pb-2">Username</th>
                    <th className="pb-2">Season</th>
                    <th className="pb-2">Draft Date</th>
                    <th className="pb-2">Seat</th>
                    <th
                      className="pb-2 text-right cursor-pointer hover:text-foreground select-none"
                      onClick={() => toggleSort("total_score")}
                    >
                      Total Pts<SortIcon col="total_score" />
                    </th>
                    <th
                      className="pb-2 text-right cursor-pointer hover:text-foreground select-none"
                      onClick={() => toggleSort("round_reached")}
                    >
                      Round<SortIcon col="round_reached" />
                    </th>
                    <th
                      className="pb-2 text-right cursor-pointer hover:text-foreground select-none"
                      onClick={() => toggleSort("peak_week_score")}
                    >
                      Peak Wk<SortIcon col="peak_week_score" />
                    </th>
                    <th
                      className="pb-2 text-right cursor-pointer hover:text-foreground select-none"
                      onClick={() => toggleSort("consistency_score")}
                    >
                      Consistency<SortIcon col="consistency_score" />
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEntries.map((entry, i) => {
                    const globalRank = (page - 1) * PAGE_SIZE + i + 1;
                    return (
                      <tr
                        key={entry.draft_id}
                        className="border-b border-border/50 hover:bg-accent/20"
                      >
                        <td className="py-1.5 text-muted-foreground text-xs">{globalRank}</td>
                        <td className="py-1.5 font-medium">
                          <Link
                            to={`/teams/${entry.draft_id}`}
                            className="hover:text-primary hover:underline"
                          >
                            {entry.username}
                          </Link>
                        </td>
                        <td className="py-1.5 text-muted-foreground">{entry.season}</td>
                        <td className="py-1.5 text-muted-foreground text-xs">
                          {entry.draft_date.slice(0, 10)}
                        </td>
                        <td className="py-1.5 text-muted-foreground">#{entry.draft_position}</td>
                        <td className="py-1.5 text-right font-semibold">
                          {formatScore(entry.total_score)}
                        </td>
                        <td className="py-1.5 text-right">
                          {entry.round_reached === 4 ? (
                            <span className="font-medium text-yellow-400">Finals</span>
                          ) : (
                            `R${entry.round_reached}`
                          )}
                        </td>
                        <td className="py-1.5 text-right">{formatScore(entry.peak_week_score)}</td>
                        <td className="py-1.5 text-right text-muted-foreground">
                          {entry.consistency_score != null
                            ? entry.consistency_score.toFixed(1)
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {filteredEntries.length === 0 && (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No teams match the current filters.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="icon"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="icon"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}

          <DataAsOf dataAsOf={data.data_as_of} />
        </>
      )}
    </div>
  );
}
