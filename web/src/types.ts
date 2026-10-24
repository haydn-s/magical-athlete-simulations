// Mirrors the summary.json written by `python -m sim run` (see sim/stats.py and sim/cli.py).

export interface RunConfig {
  games: number;
  seed: number;
  track: string;
  track_name: string;
  racers_per_game: number;
  places_to_award: number;
  focus: string[];
  pool: string[];
  replaced: string[];
  variants?: Record<string, string>; // variant name -> base racer (runs saved before this was added omit it)
}

export interface Manifest {
  label: string | null;
  created: string;
  command: string;
  duration_sec: number;
  workers: number;
  python: string;
  git: { commit: string; dirty: boolean } | null;
  code_fingerprint?: string;
  config: RunConfig;
}

export interface Totals {
  games: number;
  errors: number;
  stalled: number;
  avg_turns: number;
}

export interface RacerStats {
  name: string;
  games: number;
  wins: number;
  win_rate: number;
  win_rate_ci: [number, number];
  podium_rate: number;
  pts_per_game: number;
  pts_ci: [number, number];
  avg_place: number;
  place_counts: number[];
  avg_progress: number;
  finish_rate: number;
  elim_rate: number;
  avg_game_turns: number;
}

export interface SeatStats {
  seat: number;
  games: number;
  wins: number;
  win_rate: number;
}

export interface HeadToHead {
  names: string[];
  ahead_rate: (number | null)[][];
  together: number[][];
}

export interface Summary {
  manifest: Manifest;
  totals: Totals;
  racers: RacerStats[];
  seats: SeatStats[];
  head_to_head: HeadToHead;
}

export interface RunListItem {
  id: string;
  manifest: Manifest;
  totals: Totals;
  racer_count: number;
}

// --- run launcher (sim/serve.py: /api/roster, /api/jobs) ----------------------

export interface RosterRacer {
  name: string;
  identifier: number;
  default: boolean;
  variant_of: string | null;
}

export interface RosterInfo {
  racers: RosterRacer[];
  tracks: { key: string; name: string; length: number; marked: number }[];
  defaults: { games: number; track: string; players: number; places: number };
  limits: { max_games: number; cpu_count: number };
}

/** Body of POST /api/jobs (see parse_request in sim/jobs.py). */
export interface JobRequest {
  games: number;
  track: string;
  players: number;
  places: number;
  seed?: number;
  focus: string[];
  include: string[];
  exclude: string[];
  label?: string;
  save_games: boolean;
  from_run?: string;
}

export type JobState = "queued" | "running" | "done" | "failed" | "cancelled";

export interface Job {
  id: string;
  state: JobState;
  label: string | null;
  settings: Required<Omit<JobRequest, "label" | "from_run">> & {
    only: string[];
    label: string | null;
    from_run: string | null;
    workers: number | null;
  };
  command: string;
  replaced: string[];
  done: number;
  total: number;
  created: number;
  started: number | null;
  finished: number | null;
  elapsed_sec: number;
  rate: number;
  remaining_sec: number | null;
  run_id: string | null;
  error: string | null;
}
