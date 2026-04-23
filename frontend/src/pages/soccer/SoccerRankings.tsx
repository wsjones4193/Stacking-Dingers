import { useState } from "react";
import { Plus, Trash2, GripVertical, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import LoadingSpinner from "@/components/LoadingSpinner";
import { useSoccerRanking, useSoccerRankingsList } from "@/hooks/useSoccerRankings";
import { useSoccerPlayerSearch } from "@/hooks/useSoccerPlayers";
import {
  createSoccerRanking,
  deleteSoccerRanking,
  updateSoccerRanking,
} from "@/lib/api";
import type { RankingEntry } from "@/types/soccer";

const POSITION_COLORS: Record<string, string> = {
  GK: "bg-yellow-500/20 text-yellow-600",
  DEF: "bg-blue-500/20 text-blue-600",
  MID: "bg-green-500/20 text-green-600",
  FWD: "bg-red-500/20 text-red-600",
};

const TIERS = [1, 2, 3, 4, 5];

// Simple player search for adding to a ranking
function PlayerAdder({ onAdd, existingIds }: { onAdd: (entry: { player_id: number; name: string; position: string; nationality: string | null; current_adp: number | null }) => void; existingIds: Set<number> }) {
  const [query, setQuery] = useState("");
  const { results, loading } = useSoccerPlayerSearch(query);

  return (
    <div className="relative">
      <Input
        placeholder="Add player..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="text-sm"
      />
      {query.length >= 2 && (
        <div className="absolute top-full mt-1 left-0 right-0 z-10 bg-card border border-border rounded-md shadow-lg max-h-48 overflow-y-auto">
          {loading && <p className="px-3 py-2 text-xs text-muted-foreground">Searching...</p>}
          {results.filter((r) => !existingIds.has(r.player_id)).map((p) => (
            <button
              key={p.player_id}
              className="w-full text-left flex items-center gap-2 px-3 py-2 hover:bg-accent text-sm"
              onClick={() => {
                onAdd({ player_id: p.player_id, name: p.name, position: p.position, nationality: p.nationality, current_adp: p.current_adp });
                setQuery("");
              }}
            >
              <Badge variant="outline" className={`text-[10px] px-1 ${POSITION_COLORS[p.position] ?? ""}`}>{p.position}</Badge>
              <span className="flex-1">{p.name}</span>
              {p.current_adp && <span className="text-xs text-muted-foreground">ADP {p.current_adp.toFixed(1)}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function RankingEditor({ rankingId, onClose }: { rankingId: number; onClose: () => void }) {
  const { data, loading, refresh } = useSoccerRanking(rankingId);
  const [entries, setEntries] = useState<RankingEntry[]>([]);
  const [initialized, setInitialized] = useState(false);
  const [saving, setSaving] = useState(false);

  if (data && !initialized) {
    setEntries(data.entries);
    setInitialized(true);
  }

  if (loading) return <LoadingSpinner />;
  if (!data) return null;

  const existingIds = new Set(entries.map((e) => e.player_id));

  const addPlayer = (p: { player_id: number; name: string; position: string; nationality: string | null; current_adp: number | null }) => {
    setEntries((prev) => [...prev, { ...p, tier: null, notes: null }]);
  };

  const removePlayer = (playerId: number) => {
    setEntries((prev) => prev.filter((e) => e.player_id !== playerId));
  };

  const setTier = (playerId: number, tier: number | null) => {
    setEntries((prev) => prev.map((e) => e.player_id === playerId ? { ...e, tier } : e));
  };

  const save = async () => {
    setSaving(true);
    try {
      await updateSoccerRanking(rankingId, {
        entries: entries.map((e) => ({ player_id: e.player_id, tier: e.tier ?? undefined, notes: e.notes ?? undefined })),
      });
      refresh();
    } finally {
      setSaving(false);
    }
  };

  const grouped: Record<number | string, RankingEntry[]> = {};
  for (const e of entries) {
    const key = e.tier ?? "Untiered";
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(e);
  }
  const tierKeys = [1, 2, 3, 4, 5, "Untiered"].filter((k) => grouped[k]?.length);

  return (
    <div className="space-y-4">
      <PlayerAdder onAdd={addPlayer} existingIds={existingIds} />

      <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1">
        {tierKeys.map((tier) => (
          <div key={tier}>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
              {tier === "Untiered" ? "Untiered" : `Tier ${tier}`}
            </p>
            <div className="space-y-1">
              {grouped[tier].map((entry) => (
                <div key={entry.player_id} className="flex items-center gap-2 bg-muted/30 rounded-md px-2 py-1.5">
                  <GripVertical className="h-3 w-3 text-muted-foreground/40 shrink-0" />
                  <Badge variant="outline" className={`text-[10px] px-1 shrink-0 ${POSITION_COLORS[entry.position] ?? ""}`}>
                    {entry.position}
                  </Badge>
                  <span className="flex-1 text-sm truncate">{entry.name}</span>
                  {entry.current_adp && (
                    <span className="text-xs text-muted-foreground">{entry.current_adp.toFixed(1)}</span>
                  )}
                  <Select
                    value={entry.tier?.toString() ?? "none"}
                    onValueChange={(v) => setTier(entry.player_id, v === "none" ? null : parseInt(v))}
                  >
                    <SelectTrigger className="h-6 w-20 text-xs">
                      <SelectValue placeholder="Tier" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">—</SelectItem>
                      {TIERS.map((t) => (
                        <SelectItem key={t} value={t.toString()}>T{t}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <button onClick={() => removePlayer(entry.player_id)} className="text-muted-foreground hover:text-destructive">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end gap-2 border-t border-border pt-3">
        <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
        <Button size="sm" onClick={save} disabled={saving}>
          <Save className="h-3.5 w-3.5 mr-1" />
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>
    </div>
  );
}

function CreateRankingForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [posFilter, setPosFilter] = useState("ALL");
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState(false);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await createSoccerRanking({ name, position_filter: posFilter });
      setOpen(false);
      setName("");
      onCreated();
    } finally {
      setCreating(false);
    }
  };

  if (!open) {
    return (
      <Button size="sm" onClick={() => setOpen(true)}>
        <Plus className="h-4 w-4 mr-1" /> New Ranking
      </Button>
    );
  }

  return (
    <Card className="border-primary/30">
      <CardContent className="pt-4 space-y-3">
        <p className="text-sm font-medium">Create Ranking List</p>
        <Input placeholder="Ranking name..." value={name} onChange={(e) => setName(e.target.value)} />
        <Select value={posFilter} onValueChange={setPosFilter}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {["ALL", "GK", "DEF", "MID", "FWD"].map((p) => (
              <SelectItem key={p} value={p}>{p}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
          <Button size="sm" onClick={handleCreate} disabled={creating || !name.trim()}>
            {creating ? "Creating..." : "Create"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function SoccerRankings() {
  const { data: lists, loading, refresh } = useSoccerRankingsList();
  const [editingId, setEditingId] = useState<number | null>(null);

  const handleDelete = async (id: number) => {
    await deleteSoccerRanking(id);
    refresh();
    if (editingId === id) setEditingId(null);
  };

  return (
    <div className="p-4 max-w-3xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Rankings Builder</h1>
          <p className="text-sm text-muted-foreground">The World Pup · 2026 World Cup</p>
        </div>
        <CreateRankingForm onCreated={refresh} />
      </div>

      {loading && <LoadingSpinner />}

      {!loading && lists.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          <p className="text-sm">No rankings yet. Create one to get started.</p>
        </div>
      )}

      <div className="space-y-3">
        {lists.map((list) => (
          <Card key={list.ranking_id}>
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base">{list.name}</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {list.position_filter !== "ALL" && list.position_filter && (
                    <Badge variant="outline" className="mr-2 text-[10px]">{list.position_filter}</Badge>
                  )}
                  {list.entry_count} players · updated {new Date(list.updated_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditingId(editingId === list.ranking_id ? null : list.ranking_id)}
                >
                  {editingId === list.ranking_id ? "Close" : "Edit"}
                </Button>
                <button
                  className="text-muted-foreground hover:text-destructive"
                  onClick={() => handleDelete(list.ranking_id)}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </CardHeader>
            {editingId === list.ranking_id && (
              <CardContent>
                <RankingEditor rankingId={list.ranking_id} onClose={() => setEditingId(null)} />
              </CardContent>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
