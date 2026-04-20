/**
 * Combos Explorer — association rule mining on player co-ownership.
 * Metrics: support, confidence, lift, conviction.
 */
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronDown, ChevronUp, ChevronsUpDown, X } from "lucide-react";
import { useCombosLeaderboard } from "@/hooks/useCombos";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import LoadingSpinner from "@/components/LoadingSpinner";
import DataAsOf from "@/components/DataAsOf";
import type { ComboPair } from "@/types/api";

const SEASONS = [2026, 2025, 2024];

// ---------------------------------------------------------------------------
// Metric definitions shown in the legend
// ---------------------------------------------------------------------------
const METRIC_DEFS = [
  {
    key: "support",
    label: "Support",
    desc: "% of all rosters that drafted this combo",
  },
  {
    key: "confidence",
    label: "Confidence",
    desc: "Given Player A, how often the rest also appear",
  },
  {
    key: "lift",
    label: "Lift",
    desc: "How much more often than random chance (>1 = positive correlation)",
  },
];

type SortCol = "pair_count" | "support" | "confidence" | "lift";

function SortIcon({ col, sortCol, sortDir }: { col: SortCol; sortCol: SortCol; sortDir: "asc" | "desc" }) {
  if (col !== sortCol) return <ChevronsUpDown className="inline h-3 w-3 ml-1 opacity-30" />;
  return sortDir === "asc"
    ? <ChevronUp className="inline h-3 w-3 ml-1" />
    : <ChevronDown className="inline h-3 w-3 ml-1" />;
}

function SortTh({ col, label, sortCol, sortDir, onSort, className = "" }: {
  col: SortCol; label: string; sortCol: SortCol; sortDir: "asc" | "desc";
  onSort: (c: SortCol) => void; className?: string;
}) {
  return (
    <th
      className={`pb-2 pr-4 cursor-pointer select-none hover:text-foreground ${className}`}
      onClick={() => onSort(col)}
    >
      {label} <SortIcon col={col} sortCol={sortCol} sortDir={sortDir} />
    </th>
  );
}

function MetricCell({ value, format }: { value: number | null | undefined; format: "pct" | "num" }) {
  if (value == null) return <td className="py-2 pr-4 text-right text-muted-foreground text-xs">—</td>;
  const display = format === "pct" ? `${value.toFixed(2)}%` : value.toFixed(2);
  return <td className="py-2 pr-4 text-right tabular-nums text-xs">{display}</td>;
}

export default function CombosExplorer() {
  const [searchParams, setSearchParams] = useSearchParams();
  const season = Number(searchParams.get("season")) || 2026;
  const comboSize = Number(searchParams.get("combo_size")) || 2;
  const [sortCol, setSortCol] = useState<SortCol>("pair_count");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [filterA, setFilterA] = useState("");
  const [filterB, setFilterB] = useState("");

  function handleSort(col: SortCol) {
    if (col === sortCol) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("desc");
    }
  }

  function setSeason(s: number) {
    setSearchParams({ season: String(s), combo_size: String(comboSize) }, { replace: true });
  }
  function setComboSize(k: number) {
    setSortCol("pair_count");
    setSortDir("desc");
    setFilterA("");
    setFilterB("");
    setSearchParams({ season: String(season), combo_size: String(k) }, { replace: true });
  }

  const { data, loading, error } = useCombosLeaderboard(season, comboSize, filterA, filterB);

  const sorted = [...(data?.data ?? [])].sort((a, b) => {
    const va = (a[sortCol] as number | null) ?? -Infinity;
    const vb = (b[sortCol] as number | null) ?? -Infinity;
    return sortDir === "asc" ? va - vb : vb - va;
  });

  const partnerCols = comboSize === 2
    ? ["Player B"]
    : comboSize === 3
    ? ["Player B", "Player C"]
    : ["Player B", "Player C", "Player D"];

  function getPartners(combo: ComboPair) {
    const names = [combo.p2_name];
    if (comboSize >= 3 && combo.p3_name) names.push(combo.p3_name);
    if (comboSize === 4 && combo.p4_name) names.push(combo.p4_name);
    return names;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold">Combos</h1>
          <p className="text-sm text-muted-foreground">
            Association rule mining on player co-ownership.
          </p>
        </div>
        <div className="flex items-center gap-2">
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

      {/* Player filters */}
      <div className="flex gap-3 flex-wrap">
        {(["A", "B"] as const).map((slot) => {
          const val = slot === "A" ? filterA : filterB;
          const set = slot === "A" ? setFilterA : setFilterB;
          return (
            <div key={slot} className="relative w-56">
              <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs font-semibold text-muted-foreground pointer-events-none">
                {slot}:
              </span>
              <Input
                placeholder={`Player ${slot}...`}
                value={val}
                onChange={(e) => set(e.target.value)}
                className="pl-7 pr-7 text-sm"
              />
              {val && (
                <button
                  onClick={() => set("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Metric legend */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {METRIC_DEFS.map((m) => (
          <div key={m.key} className="rounded-md border border-border bg-card px-3 py-2">
            <p className="text-xs font-semibold text-primary">{m.label}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{m.desc}</p>
          </div>
        ))}
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
                  {partnerCols.map((col) => (
                    <th key={col} className="pb-2 pr-4">{col}</th>
                  ))}
                  <SortTh col="pair_count" label="Count"   sortCol={sortCol} sortDir={sortDir} onSort={handleSort} className="text-right" />
                  <SortTh col="support"    label="Support"    sortCol={sortCol} sortDir={sortDir} onSort={handleSort} className="text-right" />
                  <SortTh col="confidence" label="Confidence" sortCol={sortCol} sortDir={sortDir} onSort={handleSort} className="text-right" />
                  <SortTh col="lift"       label="Lift"       sortCol={sortCol} sortDir={sortDir} onSort={handleSort} className="text-right" />
                </tr>
              </thead>
              <tbody>
                {sorted.map((combo, i) => {
                  const partners = getPartners(combo);
                  return (
                    <tr key={i} className="border-b border-border/40 hover:bg-accent/20 transition-colors">
                      <td className="py-2 pl-4 pr-2 text-muted-foreground text-xs">{i + 1}</td>
                      <td className="py-2 pr-4 font-medium">{combo.p1_name}</td>
                      {partners.map((name, j) => (
                        <td key={j} className="py-2 pr-4 text-muted-foreground">{name}</td>
                      ))}
                      {Array.from({ length: partnerCols.length - partners.length }).map((_, j) => (
                        <td key={`pad-${j}`} className="py-2 pr-4" />
                      ))}
                      <td className="py-2 pr-4 text-right tabular-nums text-xs">{combo.pair_count.toLocaleString()}</td>
                      <MetricCell value={combo.support}    format="pct" />
                      <MetricCell value={combo.confidence} format="pct" />
                      <MetricCell value={combo.lift}       format="num" />
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!loading && sorted.length === 0 && (
              <p className="py-10 text-center text-sm text-muted-foreground">
                No results{filterA || filterB ? " for that filter" : ""}.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {data && <DataAsOf dataAsOf={data.data_as_of} />}
    </div>
  );
}
