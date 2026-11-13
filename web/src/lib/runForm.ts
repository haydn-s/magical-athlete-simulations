import type { JobRequest, Override, RosterInfo, Summary } from "../types";

// The "New run" form, kept as plain data so the rules can be unit tested.
// The pool picker maps onto the CLI's semantics: unticked standard racers become
// --exclude, ticked opt-in racers (variants, new designs) become --include.

export interface RunForm {
  track: string;
  games: number;
  players: number;
  places: number;
  seed: string; // blank = pick a random seed when the run starts
  label: string;
  focus: string[];
  pool: string[]; // racers that may fill the open seats
  saveGames: boolean;
  fromRun: string | null;
  /** Changed power settings, "SisyphusPower.STARTING_POINTS" -> typed text; blank keeps the current value. */
  overrides: Record<string, string>;
}

export const settingKey = (o: { power: string; setting: string }) => `${o.power}.${o.setting}`;

export const MAX_SEED = Number.MAX_SAFE_INTEGER;
export const MAX_LABEL = 60;

export function defaultForm(roster: RosterInfo): RunForm {
  const { defaults } = roster;
  return {
    track: defaults.track,
    games: defaults.games,
    players: defaults.players,
    places: defaults.places,
    seed: "",
    label: "",
    focus: [],
    pool: roster.racers.filter((r) => r.default).map((r) => r.name),
    saveGames: false,
    fromRun: null,
    overrides: {},
  };
}

/** Start from an existing run's settings, keeping its seed so the two compare game for game. */
export function formFromRun(roster: RosterInfo, runId: string, summary: Summary): RunForm {
  const known = new Set(roster.racers.map((r) => r.name));
  const { config } = summary.manifest;
  return {
    ...defaultForm(roster),
    track: roster.tracks.some((t) => t.key === config.track) ? config.track : roster.defaults.track,
    games: config.games,
    players: config.racers_per_game,
    places: config.places_to_award,
    seed: String(config.seed),
    focus: config.focus.filter((n) => known.has(n)),
    pool: config.pool.filter((n) => known.has(n)),
    fromRun: runId,
    overrides: Object.fromEntries((config.overrides ?? []).map((o) => [settingKey(o), String(o.value)])),
  };
}

type SettingInfo = RosterInfo["settings"][number];

/** The typed value typed into a setting's box, or an error message. */
export function parseSettingValue(text: string, setting: SettingInfo): Override["value"] | { error: string } {
  const t = text.trim();
  const name = settingKey(setting);
  switch (setting.type) {
    case "bool":
      if (/^(true|yes|1)$/i.test(t)) return true;
      if (/^(false|no|0)$/i.test(t)) return false;
      return { error: `${name} must be true or false.` };
    case "int":
      return /^-?\d+$/.test(t) ? Number(t) : { error: `${name} must be a whole number.` };
    case "float":
      return t !== "" && Number.isFinite(Number(t)) ? Number(t) : { error: `${name} must be a number.` };
    default:
      return t;
  }
}

/** Settings whose box holds a value different from the current one. */
export function changedSettings(form: RunForm, roster: RosterInfo): Override[] {
  const changed: Override[] = [];
  for (const setting of roster.settings) {
    const text = form.overrides[settingKey(setting)];
    if (text === undefined || text.trim() === "") continue;
    const value = parseSettingValue(text, setting);
    if (typeof value === "object" || value === setting.value) continue;
    changed.push({ power: setting.power, setting: setting.setting, value });
  }
  return changed;
}

/** Base racers that sit out because one of their variants is racing. */
export function replacedBases(form: RunForm, roster: RosterInfo): Set<string> {
  const variantOf = new Map(roster.racers.map((r) => [r.name, r.variant_of]));
  const bases = new Set<string>();
  for (const name of [...form.focus, ...form.pool]) {
    const base = variantOf.get(name);
    if (base) bases.add(base);
  }
  return bases;
}

/** The racers that can actually fill open seats, in roster order. */
export function effectivePool(form: RunForm, roster: RosterInfo): string[] {
  const selected = new Set(form.pool);
  const focus = new Set(form.focus);
  const replaced = replacedBases(form, roster);
  return roster.racers
    .map((r) => r.name)
    .filter((n) => selected.has(n) && !focus.has(n) && !replaced.has(n));
}

export function toRequest(form: RunForm, roster: RosterInfo): JobRequest {
  const selected = new Set(form.pool);
  const focus = new Set(form.focus);
  const replaced = replacedBases(form, roster);
  const request: JobRequest = {
    games: form.games,
    track: form.track,
    players: form.players,
    places: form.places,
    focus: form.focus,
    include: roster.racers.filter((r) => !r.default && selected.has(r.name) && !focus.has(r.name)).map((r) => r.name),
    exclude: roster.racers
      .filter((r) => r.default && !selected.has(r.name) && !focus.has(r.name) && !replaced.has(r.name))
      .map((r) => r.name),
    save_games: form.saveGames,
  };
  if (form.seed.trim()) request.seed = Number(form.seed.trim());
  if (form.label.trim()) request.label = form.label.trim();
  if (form.fromRun) request.from_run = form.fromRun;
  const overrides = changedSettings(form, roster);
  if (overrides.length) request.overrides = overrides;
  return request;
}

/** Problems that stop the run from starting; empty when the form is ready. */
export function validate(form: RunForm, roster: RosterInfo): string[] {
  const errors: string[] = [];
  const maxGames = roster.limits.max_games;
  if (!Number.isInteger(form.games) || form.games < 1 || form.games > maxGames) {
    errors.push(`Games must be a whole number from 1 to ${maxGames.toLocaleString("en-US")}.`);
  }
  if (!Number.isInteger(form.players) || form.players < 2 || form.players > 20) {
    errors.push("Racers per game must be from 2 to 20.");
  }
  if (!Number.isInteger(form.places) || form.places < 1 || form.places > form.players) {
    errors.push(`Scoring places must be from 1 to ${form.players}.`);
  }
  const seed = form.seed.trim();
  if (seed && (!/^\d+$/.test(seed) || Number(seed) > MAX_SEED)) {
    errors.push("Seed must be a whole number (or blank for a random one).");
  }
  if (form.label.trim().length > MAX_LABEL) {
    errors.push(`Label can be at most ${MAX_LABEL} characters.`);
  }
  if (form.focus.length > form.players) {
    errors.push(`${form.focus.length} focus racers don’t fit in a ${form.players}-racer game.`);
  }
  for (const setting of roster.settings) {
    const text = form.overrides[settingKey(setting)];
    if (text === undefined || text.trim() === "") continue;
    const value = parseSettingValue(text, setting);
    if (typeof value === "object") errors.push(value.error);
  }
  const savedKeys = new Set(roster.settings.map(settingKey));
  for (const key of Object.keys(form.overrides)) {
    if (form.overrides[key].trim() && !savedKeys.has(key)) {
      errors.push(`${key} isn’t a setting any more; clear it to continue.`);
    }
  }
  const openSeats = form.players - form.focus.length;
  const available = effectivePool(form, roster).length;
  if (openSeats > available) {
    errors.push(`Each game needs ${openSeats} racers from the pool, but only ${available} are selected.`);
  }
  return errors;
}

/** Same as batch.equivalent_command() in Python: the CLI line that reproduces a request. */
export function equivalentCommand(request: JobRequest): string {
  const parts = ["python", "-m", "sim", "run", "-n", String(request.games)];
  if (request.seed !== undefined) parts.push("--seed", String(request.seed));
  if (request.track !== "wild") parts.push("--track", request.track);
  if (request.players !== 7) parts.push("--players", String(request.players));
  if (request.places !== 2) parts.push("--places", String(request.places));
  for (const [flag, names] of [
    ["--focus", request.focus],
    ["--include", request.include],
    ["--exclude", request.exclude],
  ] as const) {
    if (names.length) parts.push(flag, names.join(","));
  }
  for (const o of request.overrides ?? []) parts.push("--set", `${settingKey(o)}=${String(o.value)}`);
  if (request.label) parts.push("--label", request.label);
  if (request.save_games) parts.push("--save-games");
  return parts.map(shellQuote).join(" ");
}

/** Python's shlex.quote. */
export function shellQuote(text: string): string {
  if (text === "") return "''";
  if (/^[\w@%+=:,./-]+$/.test(text)) return text;
  return `'${text.replace(/'/g, `'"'"'`)}'`;
}
