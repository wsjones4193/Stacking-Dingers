/**
 * Left-side navigation sidebar.
 */
import { NavLink } from "react-router-dom";
import {
  BookOpen,
  FileText,
  Home,
  LayoutDashboard,
  List,
  Mic,
  Settings,
  TrendingUp,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

const CONTENT_ITEMS = [
  { to: "/articles", icon: FileText, label: "Articles" },
  { to: "/podcasts", icon: Mic, label: "Podcasts" },
];

const DATA_ITEMS = [
  { to: "/players", icon: LayoutDashboard, label: "Player Hub" }, // label unchanged per spec
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

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-border bg-card px-3 py-4">
      {/* Logo */}
      <div className="mb-4 px-1 flex items-center gap-2">
        <img src="/logo.webp" alt="Stacking Dingers" className="h-9 w-9 shrink-0" />
        <span className="text-sm font-semibold text-muted-foreground leading-tight">
          MLB Best Ball
        </span>
      </div>

      <nav className="flex flex-1 flex-col gap-4">
        <div>
          <div className="flex flex-col gap-1">
            <NavItem to="/" icon={Home} label="Home" />
          </div>
        </div>
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
