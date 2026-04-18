/**
 * Combos Explorer — player co-ownership leaderboard.
 * Shows top combinations by pair rate for a given season and combo size.
 */
import { useSearchParams } from "react-router-dom";
import { useCombosLeaderboard } from "@/hooks/useCombos";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import LoadingSpinner from "@/components/LoadingSpinner";
import DataAsOf from "@/components/DataAsOf";
import type { ComboPair } from "@/types/api";

const SEASONS = [2026, 2025, 2024];

function PairRateBar({ pct }: { pct: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary/70"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="tabular-nums text-xs font-medium">{pct.toFixed(1)}%</span>
    </div>
  );
}

function playerCells(combo: ComboPair, k: number) {
  const players = [combo.p2_name];
  if (k >= 3 && combo.p3_name) players.push(combo.p3_name);
  if (k === 4 && combo.p4_name) players.push(combo.p4_name);
  return players;
}

export default function CombosExplorer() {
  const [searchParams, setSearchParams] = useSearchParams();
  const season = Number(searchParams.get("season")) || 2026;
  const comboSize = Number(searchParams.get("combo_size")) || 2;

  function setSeason(s: number) {
    setSearchParams({ season: String(s), combo_size: String(comboSize) }, { replace: true });
  }
  function setComboSize(k: number) {
    setSearchParams({ season: String(season), combo_size: String(k) }, { replace: true });
  }

  const { data, loading, error } = useCombosLeaderboard(season, comboSize);

  const partnerCols = comboSize === 2
    ? ["Player B"]
    : comboSize === 3
    ? ["Player B", "Player C"]
    : ["Player B", "Player C", "Player D"];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold">Combos</h1>
          <p className="text-sm text-muted-foreground">
            Top co-ownership combinations ranked by pair rate.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Combo size toggle */}
          <div className="flex gap-1">
            {[2, 3, 4].map((k) => (
              <button
                key={k}
                onClick={() => setComboSize(k)}
                className={`rounded px-3 py-1.5 text-xs font-medium transition-colors border ${
                  comboSize === k
                    ? "border-primary bg-primary/15 text-primary"
                    : "border-border text-muted-foreground hover:bg-accent"
                }`}
              >
                {k}-Player
              </button>
            ))}
          </div>
          <Select value={String(season)} onValueChange={(v) => setSeason(Number(v))}>
            <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
            <SelectContent>
              {SEASONS.map((s) => (
                <SelectItem key={s} value={String(s)}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {loading && <LoadingSpinner />}
      {error && <p className="text-destructive text-sm">{error}</p>}

      {data && (
        <Card>
          <CardContent className="pt-4 px-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="pb-2 pl-4 pr-2">#</th>
                  <th className="pb-2 pr-4">Player A</th>
                  <th className="pb-2 pr-4 text-right">Total</th>
                  {partnerCols.map((col) => (
                    <th key={col} className="pb-2 pr-4">{col}</th>
                  ))}
                  <th className="pb-2 pr-4 text-right">Pair Count</th>
                  <th className="pb-2 pr-4">Pair Rate</th>
                </tr>
              </thead>
              <tbody>
                {data.data.map((combo, i) => {
                  const partners = playerCells(combo, comboSize);
                  return (
                    <tr
                      key={i}
                      className="border-b border-border/40 hover:bg-accent/20 transition-colors"
                    >
                      <td className="py-2 pl-4 pr-2 text-muted-foreground text-xs">{i + 1}</td>
                      <td className="py-2 pr-4 font-medium">{combo.p1_name}</td>
                      <td className="py-2 pr-4 text-right tabular-nums text-muted-foreground text-xs">
                        {combo.p1_total.toLocaleString()}
                      </td>
                      {partners.map((name, j) => (
                        <td key={j} className="py-2 pr-4 text-muted-foreground">
                          {name}
                        </td>
                      ))}
                      {/* pad empty cells for shorter combos in 4-player view */}
                      {Array.from({ length: partnerCols.length - partners.length }).map((_, j) => (
                        <td key={`pad-${j}`} className="py-2 pr-4" />
                      ))}
                      <td className="py-2 pr-4 text-right tabular-nums">
                        {combo.pair_count.toLocaleString()}
                      </td>
                      <td className="py-2 pr-4">
                        <PairRateBar pct={combo.pair_rate} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {data.data.length === 0 && (
              <p className="py-10 text-center text-sm text-muted-foreground">
                No combo data for {season} ({comboSize}-player). Run precompute_combos.py to generate.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {data && <DataAsOf dataAsOf={data.data_as_of} />}
    </div>
  );
}
