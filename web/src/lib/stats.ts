import type { RacerStats, RunListItem, Summary } from "../types";

export const Z_95 = 1.96;

/** Wilson score interval for k successes in n trials (matches sim/stats.py). */
export function wilson(k: number, n: number, z = Z_95): [number, number] {
  if (n === 0) return [0, 0];
  const p = k / n;
  const denom = 1 + (z * z) / n;
  const centre = (p + (z * z) / (2 * n)) / denom;
  const half = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / denom;
  return [Math.max(0, centre - half), Math.min(1, centre + half)];
}

/** z for the change from proportion k1/n1 to k2/n2 (matches sim/stats.py). */
export function twoProportionZ(k1: number, n1: number, k2: number, n2: number): number {
  if (n1 === 0 || n2 === 0) return 0;
  const pooled = (k1 + k2) / (n1 + n2);
  const se = Math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2));
  if (se === 0) return 0;
  return (k2 / n2 - k1 / n1) / se;
}

export function isSignificant(z: number): boolean {
  return Math.abs(z) >= Z_95;
}

/** Points per game across every racer appearance in the run. */
export function fieldMeanPoints(racers: RacerStats[]): number {
  const games = racers.reduce((sum, r) => sum + r.games, 0);
  if (games === 0) return 0;
  return racers.reduce((sum, r) => sum + r.pts_per_game * r.games, 0) / games;
}

/** Win rate every racer would have if the field were perfectly balanced. */
export function parityWinRate(summary: Summary): number {
  return 1 / summary.manifest.config.racers_per_game;
}

export function runTitle(run: Pick<RunListItem, "id" | "manifest">): string {
  return run.manifest.label || run.id;
}

const pctFormat = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const intFormat = new Intl.NumberFormat("en-US");

export function pct(value: number): string {
  return `${pctFormat.format(value * 100)}%`;
}

export function signedPct(value: number): string {
  const text = pctFormat.format(Math.abs(value * 100));
  return `${value > 0 ? "+" : value < 0 ? "−" : "±"}${text}`;
}

export function num(value: number, digits = 2): string {
  return value.toFixed(digits);
}

export function signedNum(value: number, digits = 2): string {
  const text = Math.abs(value).toFixed(digits);
  return `${value > 0 ? "+" : value < 0 ? "−" : "±"}${text}`;
}

export function int(value: number): string {
  return intFormat.format(value);
}

/** 1,284 / 12.9K / 1.2M */
export function compact(value: number): string {
  if (value >= 1e6) return `${trim(value / 1e6)}M`;
  if (value >= 1e4) return `${trim(value / 1e3)}K`;
  return int(value);
}

function trim(value: number): string {
  return value >= 100 ? value.toFixed(0) : value.toFixed(1).replace(/\.0$/, "");
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function ordinal(n: number): string {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  return `${n}${{ 1: "st", 2: "nd", 3: "rd" }[n % 10] ?? "th"}`;
}
