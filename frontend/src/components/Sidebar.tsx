/**
 * Left-side navigation sidebar.
 */
import { NavLink } from "react-router-dom";
import {
  BarChart2,
  BarChart,
  FileText,
  Home,
  LayoutDashboard,
  Layers,
  List,
  Mic,
  PieChart,
  Settings,
  Shuffle,
  Star,
  Target,
  TrendingUp,
  Users,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

const CONTENT_ITEMS = [
  { to: "/articles", icon: FileText, label: "Articles" },
  { to: "/podcasts", icon: Mic, label: "Podcasts" },
];

const DATA_ITEMS = [
  { to: "/adp", icon: TrendingUp, label: "ADP Explorer" },
  { to: "/combos", icon: Shuffle, label: "Combos" },
  { to: "/history/stacking", icon: Layers, label: "Stacking" },
  { to: "/history/positional-scarcity", icon: PieChart, label: "Positional Scarcity" },
  { to: "/history/round-composition", icon: BarChart, label: "Round Composition" },
];

const COMING_SOON_ITEMS = [
  { to: "/players", icon: LayoutDashboard, label: "Player Hub" },
  { to: "/teams", icon: Users, label: "Team Analyzer" },
  { to: "/history/ceiling", icon: Star, label: "Ceiling Analysis" },
  { to: "/history/draft-structure", icon: BarChart2, label: "Draft Structure" },
  { to: "/history/adp-accuracy", icon: Target, label: "ADP Accuracy" },
];

function NavItem({ to, icon: Icon, label, onClick }: { to: string; icon: React.ElementType; label: string; onClick?: () => void }) {
  return (
    <NavLink
      to={to}
      onClick={onClick}
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

interface SidebarProps {
  onClose?: () => void;
}

export default function Sidebar({ onClose }: SidebarProps) {
  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-border bg-card px-3 py-4">
      {/* Logo + mobile close button */}
      <div className="mb-4 px-1 flex items-center gap-2">
        <img src="/logo.webp" alt="Stacking Dingers" className="h-9 w-9 shrink-0" />
        <span className="text-sm font-semibold text-muted-foreground leading-tight flex-1">
          MLB Best Ball
        </span>
        {onClose && (
          <button
            onClick={onClose}
            className="md:hidden rounded-md p-1 text-muted-foreground hover:bg-accent"
            aria-label="Close menu"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <nav className="flex flex-1 flex-col gap-4">
        <div>
          <div className="flex flex-col gap-1">
            <NavItem to="/" icon={Home} label="Home" onClick={onClose} />
          </div>
        </div>
        <div>
          <p className="px-3 mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">Content</p>
          <div className="flex flex-col gap-1">
            {CONTENT_ITEMS.map((item) => (
              <NavItem key={item.to} {...item} onClick={onClose} />
            ))}
          </div>
        </div>
        <div>
          <p className="px-3 mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">Data Hub</p>
          <div className="flex flex-col gap-1">
            {DATA_ITEMS.map((item) => (
              <NavItem key={item.to} {...item} onClick={onClose} />
            ))}
          </div>
        </div>
        <div>
          <p className="px-3 mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">Under Construction</p>
          <div className="flex flex-col gap-1">
            {COMING_SOON_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary/15 text-primary"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground"
                  )
                }
              >
                <item.icon className="h-4 w-4 shrink-0 opacity-50" />
                <span className="flex-1">{item.label}</span>
                <span className="text-[10px] text-muted-foreground/60 font-normal">🚧</span>
              </NavLink>
            ))}
          </div>
        </div>
        <div>
          <p className="px-3 mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">Leaderboard</p>
          <div className="flex flex-col gap-1">
            <NavItem to="/leaderboard" icon={List} label="Leaderboard" onClick={onClose} />
          </div>
        </div>
      </nav>

      <div className="mt-auto border-t border-border pt-3">
        <NavLink
          to="/admin"
          onClick={onClose}
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
