/**
 * Admin page — two sections:
 *   /admin/player-mapping  → confirm/edit player ID mappings
 *   /admin/score-audit     → view score discrepancies
 */
import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { AlertCircle, Check, X } from "lucide-react";
import { confirmMapping, getPlayerMappings, getScoreAudit } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import LoadingSpinner from "@/components/LoadingSpinner";
import type { PlayerMapping, ScoreAuditEntry } from "@/types/api";

const SEASONS = [2026, 2025, 2024, 2023, 2022];

// ---------------------------------------------------------------------------
// Player Mapping
// ---------------------------------------------------------------------------

function PlayerMappingPage() {
  const [mappings, setMappings] = useState<PlayerMapping[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"unconfirmed" | "all">("unconfirmed");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editMlbId, setEditMlbId] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLoading(true);
    getPlayerMappings({ confirmed: filter === "unconfirmed" ? false : undefined })
      .then(setMappings)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filter]);

  async function handleConfirm(id: number) {
    const mlbId = parseInt(editMlbId, 10);
    if (isNaN(mlbId)) return;
    setSaving(true);
    try {
      const updated = await confirmMapping(id, mlbId);
      setMappings((prev) => prev.map((m) => (m.id === id ? updated : m)));
      setEditingId(null);
      setEditMlbId("");
    } catch (e) {
      alert(`Failed to confirm: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold">Player Mappings</h2>
          <p className="text-sm text-muted-foreground">
            Link Underdog player names to MLB Stats API IDs.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={filter === "unconfirmed" ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter("unconfirmed")}
          >
            Unconfirmed
          </Button>
          <Button
            variant={filter === "all" ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter("all")}
          >
            All
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : (
        <Card>
          <CardContent className="pt-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="pb-2">Underdog Name</th>
                  <th className="pb-2">MLB Name</th>
                  <th className="pb-2">MLB ID</th>
                  <th className="pb-2">Season</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {mappings.map((m) => (
                  <tr key={m.id} className="border-b border-border/50">
                    <td className="py-1.5 font-medium">{m.underdog_name}</td>
                    <td className="py-1.5 text-muted-foreground">{m.mlb_name ?? "—"}</td>
                    <td className="py-1.5 text-muted-foreground">
                      {editingId === m.id ? (
                        <Input
                          value={editMlbId}
                          onChange={(e) => setEditMlbId(e.target.value)}
                          className="h-7 w-28 text-xs"
                          placeholder="MLB API ID"
                          autoFocus
                        />
                      ) : (
                        m.mlb_id ?? "—"
                      )}
                    </td>
                    <td className="py-1.5">{m.season}</td>
                    <td className="py-1.5">
                      {m.confirmed ? (
                        <Badge variant="default" className="text-xs">Confirmed</Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs text-yellow-400 border-yellow-400/40">Pending</Badge>
                      )}
                    </td>
                    <td className="py-1.5">
                      {editingId === m.id ? (
                        <div className="flex gap-1">
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-6 w-6 text-primary"
                            onClick={() => handleConfirm(m.id)}
                            disabled={saving}
                          >
                            <Check className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-6 w-6 text-muted-foreground"
                            onClick={() => { setEditingId(null); setEditMlbId(""); }}
                          >
                            <X className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      ) : !m.confirmed ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 px-2 text-xs"
                          onClick={() => {
                            setEditingId(m.id);
                            setEditMlbId(m.mlb_id != null ? String(m.mlb_id) : "");
                          }}
                        >
                          Edit
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {mappings.length === 0 && (
              <p className="py-6 text-center text-sm text-muted-foreground">No mappings found.</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Score Audit
// ---------------------------------------------------------------------------

function ScoreAuditPage() {
  const [entries, setEntries] = useState<ScoreAuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [season, setSeason] = useState(2026);

  useEffect(() => {
    setLoading(true);
    getScoreAudit(season)
      .then(setEntries)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [season]);

  const sorted = [...entries].sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold">Score Audit</h2>
          <p className="text-sm text-muted-foreground">
            Discrepancies between calculated scores and Underdog's official scores (|delta| ≥ 0.5).
          </p>
        </div>
        <div className="flex gap-1">
          {SEASONS.map((s) => (
            <Button
              key={s}
              size="sm"
              variant={season === s ? "default" : "outline"}
              onClick={() => setSeason(s)}
            >
              {s}
            </Button>
          ))}
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : (
        <Card>
          <CardContent className="pt-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="pb-2">Player</th>
                  <th className="pb-2 text-right">Week</th>
                  <th className="pb-2 text-right">Calculated</th>
                  <th className="pb-2 text-right">Underdog</th>
                  <th className="pb-2 text-right">Delta</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((e) => (
                  <tr key={e.id} className="border-b border-border/50">
                    <td className="py-1.5 font-medium">{e.player_name ?? `ID ${e.player_id}`}</td>
                    <td className="py-1.5 text-right">Wk {e.week_number}</td>
                    <td className="py-1.5 text-right">{e.calculated_score.toFixed(2)}</td>
                    <td className="py-1.5 text-right">{e.underdog_score.toFixed(2)}</td>
                    <td className={`py-1.5 text-right font-medium ${e.delta > 0 ? "text-primary" : "text-destructive"}`}>
                      {e.delta > 0 ? "+" : ""}{e.delta.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {sorted.length === 0 && (
              <p className="py-6 text-center text-sm text-muted-foreground">No discrepancies found for {season}.</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Admin layout
// ---------------------------------------------------------------------------

function AdminNav() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1.5 rounded text-sm font-medium transition-colors ${
      isActive ? "bg-primary/15 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground"
    }`;

  return (
    <div className="mb-6 flex items-center gap-3 border-b border-border pb-3">
      <h1 className="text-xl font-bold mr-4">Admin</h1>
      <NavLink to="/admin/player-mapping" className={linkClass}>Player Mapping</NavLink>
      <NavLink to="/admin/score-audit" className={linkClass}>Score Audit</NavLink>
    </div>
  );
}

export default function Admin() {
  return (
    <div>
      <AdminNav />
      <Routes>
        <Route path="player-mapping" element={<PlayerMappingPage />} />
        <Route path="score-audit" element={<ScoreAuditPage />} />
        <Route index element={<PlayerMappingPage />} />
      </Routes>
    </div>
  );
}
