import { describe, expect, it } from "vitest";
import type { RosterInfo, Summary } from "../types";
import {
  defaultForm,
  effectivePool,
  equivalentCommand,
  formFromRun,
  shellQuote,
  toRequest,
  validate,
  type RunForm,
} from "./runForm";

const STANDARD = ["Hare", "Banana", "Scoocher", "M.O.U.T.H.", "Coach", "Gunk", "Lackey", "Skipper", "Legs"];

const roster: RosterInfo = {
  racers: [
    ...STANDARD.map((name, i) => ({ name, identifier: i + 1, default: true, variant_of: null })),
    { name: "ScoocherWeakened", identifier: 55, default: false, variant_of: "Scoocher" },
    { name: "Comet", identifier: 56, default: false, variant_of: null },
  ],
  tracks: [
    { key: "mild", name: "Mild Mile", length: 30, marked: 0 },
    { key: "wild", name: "Wild Wilds", length: 30, marked: 10 },
  ],
  defaults: { games: 10000, track: "wild", players: 7, places: 2 },
  limits: { max_games: 2_000_000, cpu_count: 8 },
};

function form(overrides: Partial<RunForm> = {}): RunForm {
  return { ...defaultForm(roster), ...overrides };
}

describe("defaultForm", () => {
  it("starts from the standard pool and server defaults", () => {
    const f = defaultForm(roster);
    expect(f.pool).toEqual(STANDARD);
    expect([f.games, f.track, f.players, f.places, f.seed]).toEqual([10000, "wild", 7, 2, ""]);
    expect(toRequest(f, roster)).toEqual({
      games: 10000, track: "wild", players: 7, places: 2, focus: [], include: [], exclude: [], save_games: false,
    });
  });
});

describe("toRequest", () => {
  it("turns unticked standard racers into exclusions and ticked opt-ins into inclusions", () => {
    const f = form({ pool: [...STANDARD.filter((n) => n !== "Hare"), "Comet"], seed: " 42 ", label: " my run " });
    expect(toRequest(f, roster)).toMatchObject({ seed: 42, label: "my run", include: ["Comet"], exclude: ["Hare"] });
  });

  it("doesn't exclude focus racers or bases a variant replaces", () => {
    // Copied from a Scoocher focus run, then switched to the variant: Scoocher was never in the pool.
    const f = form({ focus: ["ScoocherWeakened"], pool: STANDARD.filter((n) => n !== "Scoocher") });
    expect(toRequest(f, roster)).toMatchObject({ focus: ["ScoocherWeakened"], include: [], exclude: [] });
    expect(effectivePool(f, roster)).toEqual(STANDARD.filter((n) => n !== "Scoocher"));
  });

  it("drops a base racer when its variant is in the pool", () => {
    const f = form({ pool: [...STANDARD, "ScoocherWeakened"] });
    expect(effectivePool(f, roster)).toEqual([...STANDARD.filter((n) => n !== "Scoocher"), "ScoocherWeakened"]);
    expect(toRequest(f, roster)).toMatchObject({ include: ["ScoocherWeakened"], exclude: [] });
  });
});

describe("formFromRun", () => {
  it("copies a run's settings and seed", () => {
    const summary = {
      manifest: {
        config: {
          games: 30000, seed: 7, track: "mild", track_name: "Mild Mile", racers_per_game: 6, places_to_award: 3,
          focus: ["Scoocher"], pool: STANDARD.filter((n) => n !== "Scoocher").concat("Retired"), replaced: [],
        },
      },
    } as unknown as Summary;
    const f = formFromRun(roster, "run-1", summary);
    expect(f).toMatchObject({ games: 30000, seed: "7", track: "mild", players: 6, places: 3, focus: ["Scoocher"], fromRun: "run-1" });
    expect(f.pool).not.toContain("Retired"); // no longer in the roster
    expect(toRequest(f, roster)).toMatchObject({ seed: 7, focus: ["Scoocher"], exclude: [], from_run: "run-1" });
  });
});

describe("validate", () => {
  it("accepts the defaults", () => {
    expect(validate(defaultForm(roster), roster)).toEqual([]);
  });

  it("explains each problem", () => {
    expect(validate(form({ games: 0 }), roster)[0]).toMatch(/Games must be/);
    expect(validate(form({ games: 2.5 }), roster)[0]).toMatch(/Games must be/);
    expect(validate(form({ places: 8 }), roster)[0]).toMatch(/Scoring places must be from 1 to 7/);
    expect(validate(form({ seed: "-1" }), roster)[0]).toMatch(/Seed/);
    expect(validate(form({ seed: "99999999999999999999" }), roster)[0]).toMatch(/Seed/);
    expect(validate(form({ label: "x".repeat(61) }), roster)[0]).toMatch(/Label/);
    expect(validate(form({ pool: ["Hare", "Banana"] }), roster)[0]).toMatch(/needs 7 racers from the pool, but only 2/);
    // A focus racer takes a seat, so the pool only has to fill the other six.
    expect(validate(form({ focus: ["Hare"], pool: STANDARD.slice(0, 7) }), roster)).toEqual([]);
    expect(validate(form({ players: 2, focus: ["Hare", "Banana", "Coach"] }), roster)).toContain(
      "3 focus racers don’t fit in a 2-racer game.",
    );
  });
});

describe("equivalentCommand", () => {
  it("matches the Python side", () => {
    // Expected strings come from sim.batch.equivalent_command.
    expect(
      equivalentCommand({ games: 50000, seed: 7, track: "wild", players: 7, places: 2, focus: ["ScoocherWeakened"], include: [], exclude: [], save_games: false }),
    ).toBe("python -m sim run -n 50000 --seed 7 --focus ScoocherWeakened");
    expect(
      equivalentCommand({
        games: 1000, track: "mild", players: 5, places: 3, focus: ["M.O.U.T.H."], include: ["ScoocherWeakened"],
        exclude: ["Hare", "Banana"], label: "it's a test", save_games: true,
      }),
    ).toBe(
      `python -m sim run -n 1000 --track mild --players 5 --places 3 --focus M.O.U.T.H. --include ScoocherWeakened --exclude Hare,Banana --label 'it'"'"'s a test' --save-games`,
    );
  });

  it("quotes like shlex.quote", () => {
    expect(shellQuote("")).toBe("''");
    expect(shellQuote("plain-name_1.0")).toBe("plain-name_1.0");
    expect(shellQuote("two words")).toBe("'two words'");
  });
});
