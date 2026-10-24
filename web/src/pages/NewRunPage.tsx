import { useMemo, useState, type FormEvent } from "react";
import { Badge, Card, CopyButton, LoadError, Loading, Notice } from "../components/ui";
import { fetchRoster, fetchRun, startJob, useLoad } from "../lib/api";
import { refreshJobs } from "../lib/jobs";
import { href } from "../lib/router";
import {
  defaultForm,
  effectivePool,
  equivalentCommand,
  formFromRun,
  replacedBases,
  toRequest,
  validate,
  type RunForm,
} from "../lib/runForm";
import { compact, int, runTitle } from "../lib/stats";
import type { RosterInfo, Summary } from "../types";

const GAME_PRESETS = [10_000, 50_000, 100_000, 500_000];

export function NewRunPage({ from, track }: { from: string | null; track?: string | null }) {
  const setup = useLoad(
    async () => {
      const [roster, source] = await Promise.all([fetchRoster(), from ? fetchRun(from) : Promise.resolve(null)]);
      return { roster, source };
    },
    [from],
  );

  if (setup.status === "error") return <LoadError message={setup.error} />;
  if (setup.status !== "ready") return <Loading what="racers" />;
  return (
    <NewRunForm key={`${from ?? ""}/${track ?? ""}`} roster={setup.data.roster} from={from} track={track ?? null} source={setup.data.source} />
  );
}

function NewRunForm({
  roster,
  from,
  track,
  source,
}: {
  roster: RosterInfo;
  from: string | null;
  track: string | null;
  source: Summary | null;
}) {
  const [form, setForm] = useState<RunForm>(() => {
    const base = from && source ? formFromRun(roster, from, source) : defaultForm(roster);
    return track && roster.tracks.some((t) => t.key === track) ? { ...base, track } : base;
  });
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const update = (patch: Partial<RunForm>) => {
    setServerError(null);
    setForm((f) => ({ ...f, ...patch }));
  };

  const errors = validate(form, roster);
  const pool = effectivePool(form, roster);
  const request = toRequest(form, roster);
  const sourceTitle = from && source ? runTitle({ id: from, manifest: source.manifest }) : null;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (errors.length || submitting) return;
    setSubmitting(true);
    try {
      await startJob(request);
      refreshJobs();
      window.location.hash = href.jobs();
    } catch (err) {
      setServerError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="run-form" noValidate>
      <div className="page-head">
        <h1>New run</h1>
        <p className="subtitle">
          Simulate a batch on this machine. It’s saved to <code>results/</code> like any other run, so you can open
          and compare it when it finishes.
        </p>
      </div>

      {sourceTitle && (
        <Notice tone="info">
          Settings copied from <strong>{sourceTitle}</strong>, including its seed. Keep the seed and change one thing
          (say, swap the focus racer for a variant) to compare the two runs game for game.
        </Notice>
      )}

      <Card title="Setup">
        <div className="field-grid">
          <label className="field">
            <span>Track</span>
            <select value={form.track} onChange={(e) => update({ track: e.target.value })}>
              {roster.tracks.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.name} ({t.length} spaces, {t.spaces.length ? `${t.spaces.length} marked` : "none marked"})
                </option>
              ))}
            </select>
          </label>
          <div className="field">
            <label htmlFor="games">Games</label>
            <input
              id="games"
              type="number"
              min={1}
              max={roster.limits.max_games}
              step={1000}
              value={Number.isNaN(form.games) ? "" : form.games}
              onChange={(e) => update({ games: e.target.valueAsNumber })}
            />
            <div className="presets">
              {GAME_PRESETS.map((n) => (
                <button
                  key={n}
                  type="button"
                  className="button small"
                  aria-pressed={form.games === n}
                  onClick={() => update({ games: n })}
                >
                  {compact(n)}
                </button>
              ))}
            </div>
          </div>
          <label className="field">
            <span>Racers per game</span>
            <input
              type="number"
              min={2}
              max={20}
              value={Number.isNaN(form.players) ? "" : form.players}
              onChange={(e) => update({ players: e.target.valueAsNumber })}
            />
          </label>
          <label className="field">
            <span>Scoring places</span>
            <input
              type="number"
              min={1}
              max={form.players || 20}
              value={Number.isNaN(form.places) ? "" : form.places}
              onChange={(e) => update({ places: e.target.valueAsNumber })}
            />
            <span className="hint">The race ends when this many racers finish.</span>
          </label>
          <label className="field">
            <span>Seed</span>
            <input
              type="text"
              inputMode="numeric"
              placeholder="Random"
              value={form.seed}
              onChange={(e) => update({ seed: e.target.value })}
            />
            <span className="hint">Same seed and lineup settings → same games.</span>
          </label>
          <label className="field">
            <span>Label</span>
            <input
              type="text"
              placeholder="e.g. pendulum-v2"
              maxLength={60}
              value={form.label}
              onChange={(e) => update({ label: e.target.value })}
            />
            <span className="hint">Used in the run’s name and folder.</span>
          </label>
        </div>
      </Card>

      <FocusPicker roster={roster} form={form} update={update} />
      <PoolPicker roster={roster} form={form} update={update} poolSize={pool.length} />

      <Card title="Options">
        <label className="check">
          <input type="checkbox" checked={form.saveGames} onChange={(e) => update({ saveGames: e.target.checked })} />
          <span>
            Save every game to <code>games.jsonl</code>{" "}
            <span className="muted">(about {compact(Math.max(1, Math.round(form.games * 154)))}B)</span>
          </span>
        </label>
      </Card>

      <div className="submit-bar">
        <div className="grow">
          <div className="meta">
            <span>
              <strong>{Number.isFinite(form.games) ? int(form.games) : "?"}</strong> games
            </span>
            <span>{form.players} racers per game</span>
            <span>
              {form.focus.length ? `${form.focus.length} focus + ` : ""}
              {pool.length} in the pool
            </span>
            <span>{form.seed.trim() ? `seed ${form.seed.trim()}` : "random seed"}</span>
          </div>
          {errors.length > 0 && (
            <ul className="form-errors">
              {errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
          {serverError && (
            <ul className="form-errors">
              <li>{serverError}</li>
            </ul>
          )}
        </div>
        <button type="submit" className="button primary" disabled={errors.length > 0 || submitting}>
          {submitting ? "Starting…" : "Start run"}
        </button>
      </div>

      <div className="command-preview">
        <span className="muted">Same run from the command line:</span>
        <code>{equivalentCommand(request)}</code>
        <CopyButton text={equivalentCommand(request)} />
      </div>
    </form>
  );
}

function FocusPicker({
  roster,
  form,
  update,
}: {
  roster: RosterInfo;
  form: RunForm;
  update: (patch: Partial<RunForm>) => void;
}) {
  const available = roster.racers.filter((r) => !form.focus.includes(r.name));
  const standard = available.filter((r) => r.default);
  const optIn = available.filter((r) => !r.default);

  return (
    <Card
      title="Focus racers"
      note="Seated in every game, so they get far more games than racers rotating in from the pool. Use this to test a new design or a variant."
    >
      <div className="chips">
        {form.focus.map((name) => (
          <span key={name} className="chip">
            {name}
            <button
              type="button"
              aria-label={`Remove ${name} from focus`}
              onClick={() => update({ focus: form.focus.filter((n) => n !== name) })}
            >
              ×
            </button>
          </span>
        ))}
        <select
          aria-label="Add a focus racer"
          value=""
          onChange={(e) => e.target.value && update({ focus: [...form.focus, e.target.value] })}
        >
          <option value="">{form.focus.length ? "Add another…" : "Add a focus racer…"}</option>
          {optIn.length > 0 && (
            <optgroup label="Variants and new designs">
              {optIn.map((r) => (
                <option key={r.name} value={r.name}>
                  {r.name}
                  {r.variant_of ? ` (variant of ${r.variant_of})` : ""}
                </option>
              ))}
            </optgroup>
          )}
          <optgroup label="Standard racers">
            {standard.map((r) => (
              <option key={r.name} value={r.name}>
                {r.name}
              </option>
            ))}
          </optgroup>
        </select>
      </div>
    </Card>
  );
}

function PoolPicker({
  roster,
  form,
  update,
  poolSize,
}: {
  roster: RosterInfo;
  form: RunForm;
  update: (patch: Partial<RunForm>) => void;
  poolSize: number;
}) {
  const [query, setQuery] = useState("");
  const selected = useMemo(() => new Set(form.pool), [form.pool]);
  const focus = new Set(form.focus);
  const replaced = replacedBases(form, roster);
  const variantOf = new Map(roster.racers.map((r) => [r.name, r.variant_of]));
  const needle = query.trim().toLowerCase();
  const visible = roster.racers.filter((r) => !needle || r.name.toLowerCase().includes(needle));

  // Keep the pool in roster order so the same picks always mean the same lineups.
  const setPool = (names: Set<string>) => update({ pool: roster.racers.map((r) => r.name).filter((n) => names.has(n)) });
  const toggle = (name: string) => {
    const next = new Set(selected);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    setPool(next);
  };

  const group = (title: string, racers: RosterInfo["racers"]) =>
    racers.length > 0 && (
      <div className="racer-group">
        <h3>{title}</h3>
        <div className="racer-grid">
          {racers.map((r) => {
            const isFocus = focus.has(r.name);
            const isReplaced = !isFocus && replaced.has(r.name);
            return (
              <label key={r.name} className={`racer-option${isFocus || isReplaced ? " inactive" : ""}`}>
                <input
                  type="checkbox"
                  checked={(selected.has(r.name) && !isReplaced) || isFocus}
                  disabled={isFocus || isReplaced}
                  onChange={() => toggle(r.name)}
                />
                <span className="racer-name">{r.name}</span>
                {isFocus && <Badge>focus</Badge>}
                {isReplaced && <span className="hint">replaced by variant</span>}
                {!isFocus && !isReplaced && variantOf.get(r.name) && (
                  <span className="hint">variant of {variantOf.get(r.name)}</span>
                )}
              </label>
            );
          })}
        </div>
      </div>
    );

  const standard = roster.racers.filter((r) => r.default).map((r) => r.name);
  return (
    <Card
      title={`Pool · ${poolSize} racers`}
      note="Racers that fill the remaining seats at random. A variant always sits out alongside its base racer, so the two never race together."
      actions={
        <div className="toolbar">
          <input
            type="search"
            placeholder="Filter racers"
            aria-label="Filter racers"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="button" className="button small" onClick={() => setPool(new Set(standard))}>
            Standard racers
          </button>
          <button type="button" className="button small" onClick={() => setPool(new Set())}>
            None
          </button>
        </div>
      }
    >
      {group("Variants and new designs", visible.filter((r) => !r.default))}
      {group("Standard racers", visible.filter((r) => r.default))}
      {visible.length === 0 && <p className="muted">No racers match “{query}”.</p>}
    </Card>
  );
}
