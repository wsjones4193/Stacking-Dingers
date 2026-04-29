/**
 * Home page — brand-forward landing with hero, season status, and feature overview.
 */
import { BarChart2, Mic, TrendingUp } from "lucide-react";

// 2026 season week calendar (start dates inclusive, end dates inclusive)
const WEEKS_2026 = [
  { week: 1,  start: "2026-03-25", end: "2026-03-29", round: 1 },
  { week: 2,  start: "2026-03-30", end: "2026-04-05", round: 1 },
  { week: 3,  start: "2026-04-06", end: "2026-04-12", round: 1 },
  { week: 4,  start: "2026-04-13", end: "2026-04-19", round: 1 },
  { week: 5,  start: "2026-04-20", end: "2026-04-26", round: 1 },
  { week: 6,  start: "2026-04-27", end: "2026-05-03", round: 1 },
  { week: 7,  start: "2026-05-04", end: "2026-05-10", round: 1 },
  { week: 8,  start: "2026-05-11", end: "2026-05-17", round: 1 },
  { week: 9,  start: "2026-05-18", end: "2026-05-24", round: 1 },
  { week: 10, start: "2026-05-25", end: "2026-05-31", round: 1 },
  { week: 11, start: "2026-06-01", end: "2026-06-07", round: 1 },
  { week: 12, start: "2026-06-08", end: "2026-06-14", round: 1 },
  { week: 13, start: "2026-06-15", end: "2026-06-21", round: 1 },
  { week: 14, start: "2026-06-22", end: "2026-06-28", round: 1 },
  { week: 15, start: "2026-06-29", end: "2026-07-05", round: 1 },
  { week: 16, start: "2026-07-06", end: "2026-07-12", round: 1 },
  { week: 17, start: "2026-07-13", end: "2026-07-26", round: 1 },
  { week: 18, start: "2026-07-27", end: "2026-08-02", round: 1 },
  { week: 19, start: "2026-08-03", end: "2026-08-09", round: 2 },
  { week: 20, start: "2026-08-10", end: "2026-08-16", round: 2 },
  { week: 21, start: "2026-08-17", end: "2026-08-23", round: 3 },
  { week: 22, start: "2026-08-24", end: "2026-08-30", round: 3 },
  { week: 23, start: "2026-08-31", end: "2026-09-06", round: 4 },
  { week: 24, start: "2026-09-07", end: "2026-09-13", round: 4 },
];

function getCurrentWeek(): { week: number; round: number } | null {
  const today = new Date().toISOString().slice(0, 10);
  const current = WEEKS_2026.find((w) => today >= w.start && today <= w.end);
  if (current) return { week: current.week, round: current.round };
  if (today < WEEKS_2026[0].start) return null; // pre-season
  if (today > WEEKS_2026[WEEKS_2026.length - 1].end) return null; // post-season
  // Between weeks (gap days) — show upcoming
  const next = WEEKS_2026.find((w) => today < w.start);
  return next ? { week: next.week, round: next.round } : null;
}

const ROUND_LABEL: Record<number, string> = {
  1: "Round 1",
  2: "Round 2 — Playoffs",
  3: "Round 3 — Playoffs",
  4: "Finals",
};

const FEATURES = [
  {
    icon: TrendingUp,
    title: "ADP & Ownership",
    body: "Track how average draft position moves across the draft window, spot positional scarcity cliffs, and see which player combos are being drafted together.",
  },
  {
    icon: Mic,
    title: "Strategy Content",
    body: "Articles and podcast episodes from the Stacking Dingers team — draft strategy, player analysis, and tournament breakdowns.",
  },
  {
    icon: BarChart2,
    title: "Historical Analysis",
    body: "Multi-season data on draft structure, stacking tendencies, positional composition of advancing teams, and round-by-round scoring breakdowns.",
  },
];

export default function Home() {
  const currentWeek = getCurrentWeek();
  const seasonActive = currentWeek !== null;

  return (
    <div className="flex flex-col items-center">
      {/* Hero */}
      <div className="w-full flex flex-col items-center px-6 pt-14 pb-12 text-center">
        <img
          src="/logo.webp"
          alt="Stacking Dingers"
          className="h-24 w-24 mb-6 drop-shadow-md"
        />
        <h1 className="text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl">
          Stacking Dingers
        </h1>
        <p className="mt-2 text-base font-medium text-primary tracking-wide uppercase">
          MLB Best Ball Research
        </p>
        <p className="mt-4 max-w-md text-sm text-muted-foreground leading-relaxed">
          Data tools built for Underdog Fantasy's The Dinger tournament. ADP
          trends, scoring history, draft combos, and multi-season analysis — all
          in one place.
        </p>

        {/* Season status pill */}
        <div className="mt-6">
          {seasonActive && currentWeek ? (
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-1.5">
              <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
              <span className="text-xs font-semibold text-primary">
                2026 Season · Week {currentWeek.week} · {ROUND_LABEL[currentWeek.round]}
              </span>
            </div>
          ) : (
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-4 py-1.5">
              <span className="text-xs font-semibold text-muted-foreground">
                2026 Season · The Dinger
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Divider */}
      <div className="w-full max-w-2xl border-t border-border" />

      {/* Feature descriptions */}
      <div className="w-full max-w-2xl px-6 py-10">
        <p className="text-center text-xs font-semibold uppercase tracking-widest text-muted-foreground/60 mb-8">
          What's here
        </p>
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <div key={title} className="flex flex-col items-center text-center sm:items-start sm:text-left">
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary">
                <Icon className="h-4 w-4" />
              </div>
              <p className="text-sm font-semibold text-foreground mb-1">{title}</p>
              <p className="text-xs text-muted-foreground leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Footer note */}
      <div className="w-full max-w-2xl border-t border-border px-6 py-6 text-center">
        <p className="text-xs text-muted-foreground/60">
          Data from MLB Stats API and Underdog Fantasy · Updated nightly during the season
        </p>
      </div>
    </div>
  );
}
