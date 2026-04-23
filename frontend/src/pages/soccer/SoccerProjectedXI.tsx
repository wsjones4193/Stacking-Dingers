import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import LoadingSpinner from "@/components/LoadingSpinner";
import { useSoccerXI, useWCTeams } from "@/hooks/useSoccerXI";
import type { XIPlayer } from "@/types/soccer";

const POSITION_COLORS: Record<string, string> = {
  GK: "bg-yellow-500/20 text-yellow-700 border-yellow-300",
  DEF: "bg-blue-500/20 text-blue-700 border-blue-300",
  MID: "bg-green-500/20 text-green-700 border-green-300",
  FWD: "bg-red-500/20 text-red-700 border-red-300",
};

function PlayerCard({ player, onClick }: { player: XIPlayer; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`
        flex flex-col items-center gap-0.5 p-2 rounded-lg border text-center
        hover:bg-accent/60 transition-colors cursor-pointer min-w-[80px]
        ${POSITION_COLORS[player.position] ?? "bg-muted/30"}
      `}
    >
      <span className="text-xs font-bold">{player.position}</span>
      <span className="text-[11px] font-medium leading-tight max-w-[80px] truncate">{player.name}</span>
      {player.current_adp && (
        <span className="text-[10px] text-muted-foreground">{player.current_adp.toFixed(1)}</span>
      )}
    </button>
  );
}

function FormationView({ starters }: { starters: XIPlayer[]; formation: string }) {
  const gk = starters.filter((p) => p.position === "GK");
  const defs = starters.filter((p) => p.position === "DEF");
  const mids = starters.filter((p) => p.position === "MID");
  const fwds = starters.filter((p) => p.position === "FWD");

  const rows = [fwds, mids, defs, gk];

  return (
    <div
      className="relative rounded-xl overflow-hidden"
      style={{
        background: "linear-gradient(to bottom, #16a34a, #15803d, #166534)",
        minHeight: 360,
        padding: "16px 8px",
      }}
    >
      {/* Pitch markings */}
      <div className="absolute inset-x-0 top-1/2 h-px bg-white/20" />
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-24 h-24 rounded-full border border-white/20" />

      <div className="relative flex flex-col gap-6 items-center justify-around h-full">
        {rows.map((row, i) => (
          <div key={i} className="flex gap-3 justify-center flex-wrap">
            {row.map((player) => (
              <PlayerCard key={player.player_id} player={player} onClick={() => {}} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function BenchList({ bench, navigate }: { bench: XIPlayer[]; navigate: (path: string) => void }) {
  if (!bench.length) return null;
  return (
    <div>
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Bench</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {bench.map((p) => (
          <button
            key={p.player_id}
            onClick={() => navigate(`/soccer/players/${p.player_id}`)}
            className="flex items-center gap-2 bg-muted/30 rounded-md px-2 py-1.5 hover:bg-accent text-sm"
          >
            <Badge variant="outline" className={`text-[10px] px-1 ${POSITION_COLORS[p.position] ?? ""}`}>
              {p.position}
            </Badge>
            <span className="flex-1 text-left truncate">{p.name}</span>
            {p.current_adp && (
              <span className="text-xs text-muted-foreground">{p.current_adp.toFixed(1)}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

function TeamXIView({ teamName }: { teamName: string }) {
  const { data, loading, error } = useSoccerXI(teamName);
  const navigate = useNavigate();

  if (loading) return <LoadingSpinner />;
  if (error) return (
    <div className="text-center py-12 text-muted-foreground">
      <p className="text-sm">No projected XI entered for {teamName} yet.</p>
    </div>
  );
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{data.formation} formation</p>
        {data.updated_at && (
          <p className="text-xs text-muted-foreground">
            Updated {new Date(data.updated_at).toLocaleDateString()}
          </p>
        )}
      </div>

      <FormationView starters={data.starters} formation={data.formation} />

      {data.bench.length > 0 && (
        <>
          <Separator />
          <BenchList bench={data.bench} navigate={navigate} />
        </>
      )}
    </div>
  );
}

export default function SoccerProjectedXI() {
  const { all, configured, loading: teamsLoading } = useWCTeams();
  const [selectedTeam, setSelectedTeam] = useState<string>("");

  return (
    <div className="p-4 max-w-2xl mx-auto space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Projected Starting XI</h1>
        <p className="text-sm text-muted-foreground">Expected lineups per national team</p>
      </div>

      {teamsLoading ? (
        <LoadingSpinner />
      ) : (
        <Select value={selectedTeam} onValueChange={setSelectedTeam}>
          <SelectTrigger>
            <SelectValue placeholder="Select a national team..." />
          </SelectTrigger>
          <SelectContent className="max-h-72 overflow-y-auto">
            {configured.length > 0 && (
              <>
                <p className="px-2 py-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  XI Available
                </p>
                {configured.map((t) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
                <Separator className="my-1" />
                <p className="px-2 py-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  All Teams
                </p>
              </>
            )}
            {all
              .filter((t) => !configured.includes(t))
              .map((t) => (
                <SelectItem key={t} value={t} className="text-muted-foreground">{t}</SelectItem>
              ))
            }
          </SelectContent>
        </Select>
      )}

      {selectedTeam && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>{selectedTeam}</CardTitle>
          </CardHeader>
          <CardContent>
            <TeamXIView teamName={selectedTeam} />
          </CardContent>
        </Card>
      )}

      {!selectedTeam && (
        <div className="text-center py-16 text-muted-foreground">
          <p className="text-sm">Select a team to view their projected starting XI</p>
        </div>
      )}
    </div>
  );
}
