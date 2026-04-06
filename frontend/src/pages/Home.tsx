/**
 * Home page — landing page with section-grouped cards matching the sidebar nav.
 */
import { useNavigate } from "react-router-dom";
import {
  BookOpen,
  FileText,
  LayoutDashboard,
  List,
  Mic,
  TrendingUp,
  Users,
} from "lucide-react";

const SECTIONS = [
  {
    heading: "Content",
    items: [
      {
        to: "/articles",
        icon: FileText,
        label: "Articles",
        description: "Strategy breakdowns and analysis from the Stacking Dingers team.",
      },
      {
        to: "/podcasts",
        icon: Mic,
        label: "Podcasts",
        description: "Watch and listen to the latest episodes of The Stacking Dingers Show.",
      },
    ],
  },
  {
    heading: "Data Hub",
    items: [
      {
        to: "/players",
        icon: LayoutDashboard,
        label: "Player Hub",
        description: "Research individual players — ADP trends, scoring trajectory, BPCOR, and ownership.",
      },
      {
        to: "/teams",
        icon: Users,
        label: "Team Analyzer",
        description: "Look up any Underdog username to view their rosters, group standings, and advancement odds.",
      },
      {
        to: "/adp",
        icon: TrendingUp,
        label: "ADP Explorer",
        description: "Explore ADP movement, positional scarcity curves, and value vs. actual production.",
      },
      {
        to: "/history",
        icon: BookOpen,
        label: "History Browser",
        description: "Dig into multi-season data — stacking, draft structure, combos, and ceiling analysis.",
      },
    ],
  },
  {
    heading: "Live Leaderboard",
    items: [
      {
        to: "/leaderboard",
        icon: List,
        label: "Leaderboard",
        description: "Browse all teams by total points, rank, and advancement probability.",
      },
    ],
  },
];

export default function Home() {
  const navigate = useNavigate();

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-foreground">MLB Best Ball</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Research tools for Underdog Fantasy MLB best ball — The Dinger tournament.
        </p>
      </div>

      <div className="flex flex-col gap-8">
        {SECTIONS.map(({ heading, items }) => (
          <div key={heading}>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
              {heading}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {items.map(({ to, icon: Icon, label, description }) => (
                <button
                  key={to}
                  onClick={() => navigate(to)}
                  className="flex items-start gap-4 rounded-lg border border-border bg-card p-4 text-left transition-colors hover:bg-accent hover:border-primary/30"
                >
                  <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">{label}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">{description}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
