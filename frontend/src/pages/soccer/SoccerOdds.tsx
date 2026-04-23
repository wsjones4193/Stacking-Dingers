import { useState } from "react";
import { Input } from "@/components/ui/input";
import LoadingSpinner from "@/components/LoadingSpinner";
import { useSoccerTeamOdds } from "@/hooks/useSoccerOdds";

const STAGES = [
  { key: "r32_prob",    label: "R32" },
  { key: "r16_prob",    label: "R16" },
  { key: "qf_prob",     label: "QF" },
  { key: "sf_prob",     label: "SF" },
  { key: "final_prob",  label: "Final" },
  { key: "winner_prob", label: "Winner" },
] as const;

type StageKey = (typeof STAGES)[number]["key"];

function probToDisplay(p: number | null): string {
  if (p === null) return "—";
  return `${(p * 100).toFixed(1)}%`;
}

function probColor(p: number | null): string {
  if (p === null) return "";
  if (p >= 0.6) return "text-green-600 font-semibold";
  if (p >= 0.35) return "text-yellow-600";
  if (p >= 0.15) return "text-orange-500";
  return "text-muted-foreground";
}

function HeatBar({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted-foreground text-xs">—</span>;
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-2 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className={`text-xs tabular-nums ${probColor(value)}`}>{pct}%</span>
    </div>
  );
}

export default function SoccerOdds() {
  const { data, loading, error } = useSoccerTeamOdds();
  const [query, setQuery] = useState("");
  const [sortStage, setSortStage] = useState<StageKey>("winner_prob");

  if (loading) return <LoadingSpinner />;

  const filtered = data
    .filter((row) => row.team_name.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => (b[sortStage] ?? 0) - (a[sortStage] ?? 0));

  return (
    <div className="p-4 max-w-5xl mx-auto space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Team Odds</h1>
        <p className="text-sm text-muted-foreground">Advancement probability per World Cup stage</p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {!data.length && !loading && (
        <p className="text-sm text-muted-foreground py-8 text-center">
          No odds data yet. Run the team odds ETL to populate.
        </p>
      )}

      {data.length > 0 && (
        <>
          <div className="flex gap-3 items-center">
            <Input
              className="max-w-xs"
              placeholder="Filter by team..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <span className="text-xs text-muted-foreground">Sort by:</span>
            <div className="flex gap-1">
              {STAGES.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setSortStage(key)}
                  className={`text-xs px-2 py-1 rounded-md border transition-colors ${
                    sortStage === key
                      ? "bg-primary/15 border-primary/30 text-primary font-medium"
                      : "border-border text-muted-foreground hover:border-foreground/30"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Team</th>
                  {STAGES.map(({ key, label }) => (
                    <th
                      key={key}
                      className={`px-3 py-2 text-center font-medium cursor-pointer transition-colors ${
                        sortStage === key ? "text-primary" : "text-muted-foreground hover:text-foreground"
                      }`}
                      onClick={() => setSortStage(key)}
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((row, i) => (
                  <tr
                    key={row.team_name}
                    className={`border-b border-border/50 hover:bg-accent/40 transition-colors ${
                      i % 2 === 0 ? "" : "bg-muted/10"
                    }`}
                  >
                    <td className="px-3 py-2 font-medium">{row.team_name}</td>
                    {STAGES.map(({ key }) => (
                      <td key={key} className="px-3 py-2 text-center">
                        {key === "winner_prob" ? (
                          <HeatBar value={row[key]} />
                        ) : (
                          <span className={`tabular-nums text-xs ${probColor(row[key])}`}>
                            {probToDisplay(row[key])}
                          </span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data[0]?.updated_at && (
            <p className="text-xs text-muted-foreground">
              Odds updated: {new Date(data[0].updated_at).toLocaleDateString()}
            </p>
          )}
        </>
      )}
    </div>
  );
}
