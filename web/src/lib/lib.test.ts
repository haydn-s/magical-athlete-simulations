import { describe, expect, it } from "vitest";
import type { RacerStats, Summary } from "../types";
import { compareRuns } from "./compare";
import { parseRoute, href } from "./router";
import { niceTicks } from "./scale";
import { compact, fieldMeanPoints, ordinal, signedPct, twoProportionZ, wilson } from "./stats";

function racer(name: string, overrides: Partial<RacerStats> = {}): RacerStats {
  return {
    name,
    games: 1000,
    wins: 150,
    win_rate: 0.15,
    win_rate_ci: [0.13, 0.17],
    podium_rate: 0.3,
    pts_per_game: 1.5,
    pts_ci: [1.4, 1.6],
    avg_place: 4,
    place_counts: [150, 150, 140, 140, 140, 140, 140],
    avg_progress: 25,
    finish_rate: 0.3,
    elim_rate: 0,
    avg_game_turns: 50,
    ...overrides,
  };
}

function summary(racers: RacerStats[], config: Partial<Summary["manifest"]["config"]> = {}): Summary {
  return {
    manifest: {
      label: null,
      created: "2026-10-24T12:00:00",
      command: "",
      duration_sec: 1,
      workers: 1,
      python: "3.14",
      git: null,
      config: {
        games: 1000,
        seed: 1,
        track: "wild",
        track_name: "Wild Wilds",
        racers_per_game: 7,
        places_to_award: 2,
        focus: [],
        pool: [],
        replaced: [],
        variants: {},
        ...config,
      },
    },
    totals: { games: 1000, errors: 0, stalled: 0, avg_turns: 50 },
    racers,
    seats: [],
    head_to_head: { names: [], ahead_rate: [], together: [] },
  };
}

describe("stats", () => {
  it("matches the Wilson interval the Python side computes", () => {
    // sim.stats.wilson_interval(480, 1000) == (0.4491702320581413, 0.5109828438853143)
    const [lo, hi] = wilson(480, 1000);
    expect(lo).toBeCloseTo(0.4491702320581413, 12);
    expect(hi).toBeCloseTo(0.5109828438853143, 12);
    expect(wilson(0, 0)).toEqual([0, 0]);
  });

  it("signs the two-proportion z by the direction of change", () => {
    expect(twoProportionZ(100, 1000, 150, 1000)).toBeGreaterThan(1.96);
    expect(twoProportionZ(150, 1000, 100, 1000)).toBeLessThan(-1.96);
    expect(twoProportionZ(0, 0, 1, 1)).toBe(0);
  });

  it("weights the field mean by games", () => {
    expect(fieldMeanPoints([racer("A", { pts_per_game: 1, games: 100 }), racer("B", { pts_per_game: 4, games: 300 })]))
      .toBeCloseTo(3.25);
  });

  it("formats numbers", () => {
    expect(signedPct(0.025)).toBe("+2.5");
    expect(signedPct(-0.1)).toBe("−10.0");
    expect(compact(950)).toBe("950");
    expect(compact(50000)).toBe("50K");
    expect(compact(1_250_000)).toBe("1.3M");
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22].map(ordinal)).toEqual([
      "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd",
    ]);
  });
});

describe("niceTicks", () => {
  it("covers the maximum with round steps", () => {
    expect(niceTicks(0.57, 4)).toEqual([0, 0.2, 0.4, 0.6]);
    expect(niceTicks(7.9, 4)).toEqual([0, 2, 4, 6, 8]);
    expect(niceTicks(10, 4)).toEqual([0, 2.5, 5, 7.5, 10]);
  });
});

describe("compareRuns", () => {
  it("pairs racers by name and computes deltas", () => {
    const a = summary([racer("Hare", { wins: 100, win_rate: 0.1 }), racer("Banana")]);
    const b = summary([racer("Hare", { wins: 200, win_rate: 0.2 }), racer("Banana")]);
    const { rows, onlyA, onlyB } = compareRuns(a, b);
    expect(rows.map((r) => r.label)).toEqual(["Hare", "Banana"]);
    expect(rows[0].deltaWin).toBeCloseTo(0.1);
    expect(rows[0].z).toBeGreaterThan(1.96);
    expect(onlyA).toEqual([]);
    expect(onlyB).toEqual([]);
  });

  it("pairs a variant with its base racer and lists it first", () => {
    const a = summary([racer("Hare"), racer("Scoocher"), racer("Banana")], { focus: ["Scoocher"] });
    const b = summary([racer("Hare"), racer("ScoocherWeakened")], {
      focus: ["ScoocherWeakened"],
      variants: { ScoocherWeakened: "Scoocher" },
    });
    const { rows, onlyA, onlyB } = compareRuns(a, b);
    expect(rows[0]).toMatchObject({ label: "Scoocher → ScoocherWeakened", paired: true });
    expect(rows.map((r) => r.label)).toEqual(["Scoocher → ScoocherWeakened", "Hare"]);
    expect(onlyA).toEqual(["Banana"]);
    expect(onlyB).toEqual([]);
  });

  it("reports settings that differ", () => {
    const a = summary([racer("Hare")]);
    const b = summary([racer("Hare")], { track_name: "Mild Mile", racers_per_game: 5 });
    expect(compareRuns(a, b).differences).toEqual(["Track: Wild Wilds vs Mild Mile", "Racers per game: 7 vs 5"]);
  });
});

describe("router", () => {
  it("round-trips every route", () => {
    expect(parseRoute(href.runs())).toEqual({ page: "runs" });
    expect(parseRoute(href.run("20261024_baseline"))).toEqual({ page: "run", runId: "20261024_baseline", tab: "leaderboard" });
    expect(parseRoute(href.run("x", "h2h"))).toEqual({ page: "run", runId: "x", tab: "h2h" });
    expect(parseRoute(href.racer("x", "M.O.U.T.H."))).toEqual({ page: "racer", runId: "x", racer: "M.O.U.T.H." });
    expect(parseRoute(href.compare("a b", "c"))).toEqual({ page: "compare", a: "a b", b: "c" });
    expect(parseRoute(href.compare())).toEqual({ page: "compare", a: null, b: null });
    expect(parseRoute(href.newRun())).toEqual({ page: "new", from: null, track: null });
    expect(parseRoute(href.newRun("20261024_a b"))).toEqual({ page: "new", from: "20261024_a b", track: null });
    expect(parseRoute(href.newRun(null, "sprint"))).toEqual({ page: "new", from: null, track: "sprint" });
    expect(parseRoute(href.tracks())).toEqual({ page: "tracks" });
    expect(parseRoute(href.sweep("20261024_sweep_chips"))).toEqual({ page: "sweep", sweepId: "20261024_sweep_chips" });
    expect(parseRoute(href.jobs())).toEqual({ page: "jobs" });
    expect(parseRoute("#/nope")).toEqual({ page: "not-found" });
    expect(parseRoute("#/run/x/racer")).toEqual({ page: "not-found" });
  });
});
