import { Link } from "react-router-dom";
import { TrendingUp, Users, Trophy, BarChart2, Star } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import LoadingSpinner from "@/components/LoadingSpinner";
import { useSoccerAdpMovement } from "@/hooks/useSoccerAdp";
import { useSoccerTeamOdds } from "@/hooks/useSoccerOdds";

const NAV_CARDS = [
  {
    to: "/soccer/players",
    icon: Users,
    title: "Player Hub",
    description: "Search players, view club stats and ADP trends",
  },
  {
    to: "/soccer/adp",
    icon: TrendingUp,
    title: "ADP Explorer",
    description: "Value scatter, movement chart, positional scarcity",
  },
  {
    to: "/soccer/odds",
    icon: Trophy,
    title: "Team Odds",
    description: "Advancement probabilities per World Cup stage",
  },
  {
    to: "/soccer/rankings",
    icon: Star,
    title: "Rankings Builder",
    description: "Create and manage tiered player rankings",
  },
  {
    to: "/soccer/xi",
    icon: BarChart2,
    title: "Projected XI",
    description: "Expected starting lineups per national team",
  },
];

const POSITION_COLORS: Record<string, string> = {
  GK: "bg-yellow-500/20 text-yellow-600",
  DEF: "bg-blue-500/20 text-blue-600",
  MID: "bg-green-500/20 text-green-600",
  FWD: "bg-red-500/20 text-red-600",
};

function AdpMovers() {
  const { data, loading } = useSoccerAdpMovement(3);

  const risers = data.filter((d) => (d.movement ?? 0) > 0).slice(0, 5);
  const fallers = data.filter((d) => (d.movement ?? 0) < 0).slice(-5).reverse();

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">ADP Movers (3d)</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && <LoadingSpinner className="py-4" />}
        {!loading && !data.length && (
          <p className="text-xs text-muted-foreground">No data yet.</p>
        )}
        {!loading && data.length > 0 && (
          <div className="space-y-1">
            {risers.map((p) => (
              <div key={p.player_id} className="flex items-center gap-2 text-sm">
                <Badge variant="outline" className={`text-[10px] px-1 ${POSITION_COLORS[p.position] ?? ""}`}>
                  {p.position}
                </Badge>
                <Link to={`/soccer/players/${p.player_id}`} className="flex-1 truncate hover:underline">
                  {p.name}
                </Link>
                <span className="text-green-600 text-xs font-medium">+{p.movement?.toFixed(1)}</span>
              </div>
            ))}
            {fallers.length > 0 && <div className="border-t border-border/50 my-1" />}
            {fallers.map((p) => (
              <div key={p.player_id} className="flex items-center gap-2 text-sm">
                <Badge variant="outline" className={`text-[10px] px-1 ${POSITION_COLORS[p.position] ?? ""}`}>
                  {p.position}
                </Badge>
                <Link to={`/soccer/players/${p.player_id}`} className="flex-1 truncate hover:underline">
                  {p.name}
                </Link>
                <span className="text-red-500 text-xs font-medium">{p.movement?.toFixed(1)}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TopContenders() {
  const { data, loading } = useSoccerTeamOdds();

  const top = data
    .filter((t) => t.winner_prob != null)
    .sort((a, b) => (b.winner_prob ?? 0) - (a.winner_prob ?? 0))
    .slice(0, 6);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Top Contenders</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && <LoadingSpinner className="py-4" />}
        {!loading && !top.length && (
          <p className="text-xs text-muted-foreground">No odds data yet.</p>
        )}
        {!loading && top.length > 0 && (
          <div className="space-y-1.5">
            {top.map((t) => (
              <div key={t.team_name} className="flex items-center gap-2 text-sm">
                <span className="flex-1">{t.team_name}</span>
                <div className="w-16 h-1.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${Math.round((t.winner_prob ?? 0) * 100)}%` }}
                  />
                </div>
                <span className="text-xs text-muted-foreground w-10 text-right">
                  {((t.winner_prob ?? 0) * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        )}
        <Link to="/soccer/odds" className="text-xs text-primary hover:underline block mt-3">
          View all teams →
        </Link>
      </CardContent>
    </Card>
  );
}

export default function SoccerHome() {
  return (
    <div className="p-4 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <h1 className="text-3xl font-bold">The World Pup</h1>
          <Badge className="bg-green-500/20 text-green-700 border-green-300">2026</Badge>
        </div>
        <p className="text-muted-foreground">
          Underdog Fantasy · 2026 FIFA World Cup Best Ball · $10 entry · 12-player roster
        </p>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Entry Fee", value: "$10" },
          { label: "Roster Size", value: "12" },
          { label: "Rounds", value: "4" },
          { label: "Grand Prize", value: "$30K" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-muted/40 rounded-lg px-4 py-3 text-center">
            <p className="text-xl font-bold">{value}</p>
            <p className="text-xs text-muted-foreground">{label}</p>
          </div>
        ))}
      </div>

      {/* Roster breakdown */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Roster Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2 text-sm">
            {[
              { slot: "GK", count: 1 },
              { slot: "DEF", count: 1 },
              { slot: "MID", count: 1 },
              { slot: "FWD", count: 2 },
              { slot: "FLEX", count: 1 },
              { slot: "BENCH", count: 6 },
            ].map(({ slot, count }) => (
              <div key={slot} className="flex items-center gap-1.5 bg-muted/30 rounded-md px-2 py-1">
                <Badge variant="outline" className={`text-[10px] px-1 ${POSITION_COLORS[slot] ?? "bg-muted text-muted-foreground"}`}>
                  {slot}
                </Badge>
                <span className="text-muted-foreground">×{count}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Underdog auto-selects your best starters each week — no lineup setting required
          </p>
        </CardContent>
      </Card>

      {/* Nav cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {NAV_CARDS.map(({ to, icon: Icon, title, description }) => (
          <Link
            key={to}
            to={to}
            className="block rounded-lg border border-border bg-card p-4 hover:bg-accent/40 transition-colors"
          >
            <div className="flex items-center gap-2 mb-1.5">
              <Icon className="h-4 w-4 text-green-600" />
              <span className="font-semibold text-sm">{title}</span>
            </div>
            <p className="text-xs text-muted-foreground">{description}</p>
          </Link>
        ))}
      </div>

      {/* Live data widgets */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <AdpMovers />
        <TopContenders />
      </div>
    </div>
  );
}
