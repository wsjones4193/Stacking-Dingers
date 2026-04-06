/**
 * Left-side navigation sidebar with player name autocomplete search and
 * username search for the Team Analyzer.
 */
import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  BookOpen,
  FileText,
  LayoutDashboard,
  List,
  Mic,
  Settings,
  TrendingUp,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { usePlayerSearch } from "@/hooks/usePlayerSearch";
import type { PlayerSearchResult } from "@/types/api";

const CONTENT_ITEMS = [
  { to: "/articles", icon: FileText, label: "Articles" },
  { to: "/podcasts", icon: Mic, label: "Podcasts" },
];

const DATA_ITEMS = [
  { to: "/players", icon: LayoutDashboard, label: "Player Hub" },
  { to: "/teams", icon: Users, label: "Team Analyzer" },
  { to: "/adp", icon: TrendingUp, label: "ADP Explorer" },
  { to: "/history", icon: BookOpen, label: "History Browser" },
];

function NavItem({ to, icon: Icon, label }: { to: string; icon: React.ElementType; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-primary/15 text-primary"
            : "text-muted-foreground hover:bg-accent hover:text-foreground"
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span>{label}</span>
    </NavLink>
  );
}

/** Player name autocomplete. */
function PlayerSearch() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const { results, loading } = usePlayerSearch(query);

  function select(player: PlayerSearchResult) {
    setQuery("");
    setOpen(false);
    navigate(`/players/${player.player_id}`);
  }

  return (
    <div className="relative mb-2">
      <input
        className="w-full rounded-md border border-input bg-muted px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        placeholder="Search players…"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && query.length >= 2 && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-md border bg-popover shadow-lg">
          {loading && (
            <div className="px-3 py-2 text-xs text-muted-foreground">Searching…</div>
          )}
          {!loading && results.length === 0 && (
            <div className="px-3 py-2 text-xs text-muted-foreground">No results</div>
          )}
          {results.map((p) => (
            <button
              key={p.player_id}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent"
              onMouseDown={() => select(p)}
            >
              <span className="font-medium">{p.name}</span>
              <span className="text-xs text-muted-foreground">{p.position}</span>
              {p.mlb_team && (
                <span className="ml-auto text-xs text-muted-foreground">{p.mlb_team}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Username search → navigates to Team Analyzer pre-filled. */
function UsernameSearch() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = username.trim();
    if (!trimmed) return;
    setUsername("");
    navigate(`/teams?username=${encodeURIComponent(trimmed)}`);
  }

  return (
    <form onSubmit={handleSubmit} className="relative mb-4">
      <input
        className="w-full rounded-md border border-input bg-muted px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        placeholder="Username → teams…"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
      />
    </form>
  );
}

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-border bg-card px-3 py-4">
      {/* Logo */}
      <div className="mb-4 px-1 flex items-center gap-2">
        <img src="/logo.webp" alt="Stacking Dingers" className="h-9 w-9 shrink-0" />
        <span className="text-sm font-semibold text-muted-foreground leading-tight">
          MLB Best Ball Hub
        </span>
      </div>

      <PlayerSearch />
      <UsernameSearch />

      <nav className="flex flex-1 flex-col gap-4">
        <div>
          <p className="px-3 mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">Content</p>
          <div className="flex flex-col gap-1">
            {CONTENT_ITEMS.map((item) => (
              <NavItem key={item.to} {...item} />
            ))}
          </div>
        </div>
        <div>
          <p className="px-3 mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">Data Hub</p>
          <div className="flex flex-col gap-1">
            {DATA_ITEMS.map((item) => (
              <NavItem key={item.to} {...item} />
            ))}
          </div>
        </div>
        <div>
          <p className="px-3 mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">Leaderboard</p>
          <div className="flex flex-col gap-1">
            <NavItem to="/leaderboard" icon={List} label="Leaderboard" />
          </div>
        </div>
      </nav>

      <div className="mt-auto border-t border-border pt-3">
        <NavLink
          to="/admin"
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-primary/15 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground"
            )
          }
        >
          <Settings className="h-4 w-4 shrink-0" />
          <span>Admin</span>
        </NavLink>
      </div>
    </aside>
  );
}
