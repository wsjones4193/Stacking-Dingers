/**
 * 2026 season calendar constants mirroring backend/constants.py.
 * Used by the frontend to compute current week, weeks remaining, and round context.
 */

export interface WeekEntry {
  week: number;
  start: string;   // ISO YYYY-MM-DD
  end: string;
  round: number;
}

export const SEASON_CALENDAR_2026: WeekEntry[] = [
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

/** Returns the current week entry based on today's date, or null if off-season. */
export function getCurrentWeek(today = new Date()): WeekEntry | null {
  const todayStr = today.toISOString().slice(0, 10);
  return SEASON_CALENDAR_2026.find(
    (w) => todayStr >= w.start && todayStr <= w.end
  ) ?? null;
}

/** Returns weeks remaining in Round 1 (weeks 1–18) from the current date. */
export function getR1WeeksRemaining(today = new Date()): number {
  const todayStr = today.toISOString().slice(0, 10);
  const r1Weeks = SEASON_CALENDAR_2026.filter((w) => w.round === 1);
  return r1Weeks.filter((w) => w.start > todayStr).length;
}

/** Returns the round label for a given week number. */
export function getRoundLabel(roundNumber: number): string {
  if (roundNumber === 4) return "Finals";
  return `Round ${roundNumber}`;
}

/** Returns weeks remaining in the current round from a given week number. */
export function getWeeksRemainingInRound(fromWeek: number): number {
  const current = SEASON_CALENDAR_2026.find((w) => w.week === fromWeek);
  if (!current) return 0;
  return SEASON_CALENDAR_2026.filter(
    (w) => w.round === current.round && w.week > fromWeek
  ).length;
}
