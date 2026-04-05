import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatScore(score: number | null | undefined): string {
  if (score == null) return "—";
  return score.toFixed(1);
}

export function formatPct(pct: number | null | undefined): string {
  if (pct == null) return "—";
  return `${(pct * 100).toFixed(1)}%`;
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Returns a CSS class based on flag type. */
export function flagColor(flagType: string): string {
  switch (flagType) {
    case "position_wiped":
      return "text-red-400 border-red-400/40 bg-red-400/10";
    case "ghost_player":
      return "text-orange-400 border-orange-400/40 bg-orange-400/10";
    case "below_replacement":
    case "pitcher_trending_wrong":
    case "hitter_usage_decline":
      return "text-yellow-400 border-yellow-400/40 bg-yellow-400/10";
    default:
      return "text-muted-foreground border-border bg-muted/50";
  }
}

export function flagLabel(flagType: string): string {
  switch (flagType) {
    case "position_wiped":
      return "Position Wiped";
    case "ghost_player":
      return "Ghost Player";
    case "below_replacement":
      return "Below Replacement";
    case "pitcher_trending_wrong":
      return "Pitcher Trending Wrong";
    case "hitter_usage_decline":
      return "Hitter Usage Decline";
    default:
      return flagType;
  }
}
