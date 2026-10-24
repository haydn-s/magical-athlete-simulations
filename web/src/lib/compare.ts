import type { RacerStats, Summary } from "../types";
import { twoProportionZ } from "./stats";

export interface ComparedRacer {
  label: string;
  a: RacerStats;
  b: RacerStats;
  /** True when a variant is paired with its base racer. */
  paired: boolean;
  deltaPts: number;
  deltaWin: number;
  z: number;
}

export interface Comparison {
  rows: ComparedRacer[];
  onlyA: string[];
  onlyB: string[];
  /** Settings that differ between the runs, which make the comparison less direct. */
  differences: string[];
}

const COMPARED_SETTINGS = [
  ["track_name", "Track"],
  ["racers_per_game", "Racers per game"],
  ["places_to_award", "Scoring places"],
] as const;

/**
 * Line up racers from two runs. Racers match by name; a variant matches its base
 * racer (for example Scoocher -> ScoocherWeakened), the way `python -m sim compare` does.
 */
export function compareRuns(a: Summary, b: Summary): Comparison {
  const racersA = new Map(a.racers.map((r) => [r.name, r]));
  const racersB = new Map(b.racers.map((r) => [r.name, r]));
  const variants = { ...a.manifest.config.variants, ...b.manifest.config.variants };

  const rows: ComparedRacer[] = [];
  for (const rb of b.racers) {
    const ra = racersA.get(rb.name);
    if (ra) rows.push(makeRow(ra, rb, rb.name, false));
  }

  const onlyA = a.racers.map((r) => r.name).filter((n) => !racersB.has(n));
  const onlyB = b.racers.map((r) => r.name).filter((n) => !racersA.has(n));

  const paired: ComparedRacer[] = [];
  for (const nameA of [...onlyA]) {
    const nameB = onlyB.find((n) => variants[n] === nameA || variants[nameA] === n);
    if (!nameB) continue;
    paired.push(makeRow(racersA.get(nameA)!, racersB.get(nameB)!, `${nameA} → ${nameB}`, true));
    onlyA.splice(onlyA.indexOf(nameA), 1);
    onlyB.splice(onlyB.indexOf(nameB), 1);
  }

  const differences = COMPARED_SETTINGS.filter(
    ([key]) => a.manifest.config[key] !== b.manifest.config[key],
  ).map(([key, label]) => `${label}: ${a.manifest.config[key]} vs ${b.manifest.config[key]}`);

  return { rows: [...paired, ...rows], onlyA, onlyB, differences };
}

function makeRow(a: RacerStats, b: RacerStats, label: string, paired: boolean): ComparedRacer {
  return {
    label,
    a,
    b,
    paired,
    deltaPts: b.pts_per_game - a.pts_per_game,
    deltaWin: b.win_rate - a.win_rate,
    z: twoProportionZ(a.wins, a.games, b.wins, b.games),
  };
}
