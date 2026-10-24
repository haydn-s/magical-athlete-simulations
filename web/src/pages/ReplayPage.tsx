import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Board, Token } from "../components/Board";
import { Card, LoadError, Loading, Notice } from "../components/ui";
import { fetchReplay, useLoad, useRun } from "../lib/api";
import { boardLayout } from "../lib/board";
import { describeRacer, nextTurn, previousTurn, stateAt, stepCount, turnStarts } from "../lib/replay";
import { href } from "../lib/router";
import { int, ordinal, runTitle } from "../lib/stats";
import type { Replay } from "../types";

const SPEEDS = [1, 2, 4, 8];
const BASE_DELAY_MS = 400;

export function ReplayPage({ runId, game }: { runId: string; game: number }) {
  const run = useRun(runId);
  const replay = useLoad(() => fetchReplay(runId, game), [runId, game]);

  if (run.status === "error") return <LoadError message={run.error} />;
  if (replay.status === "error") return <LoadError message={replay.error} />;
  if (run.status !== "ready" || replay.status !== "ready") return <Loading what="the game" />;

  const title = runTitle({ id: runId, manifest: run.data.manifest });
  return (
    <ReplayView key={`${runId}/${game}`} runId={runId} title={title} total={run.data.manifest.config.games} replay={replay.data} />
  );
}

function ReplayView({ runId, title, total, replay }: { runId: string; title: string; total: number; replay: Replay }) {
  const layout = useMemo(() => boardLayout(replay.track.length), [replay.track.length]);
  const starts = useMemo(() => turnStarts(replay), [replay]);
  const last = stepCount(replay) - 1;
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);

  const state = stateAt(replay, step);
  const frame = step > 0 ? replay.frames[step - 1] : null;
  const actor = frame?.actor ?? null;

  useEffect(() => {
    if (!playing) return;
    if (step >= last) {
      setPlaying(false);
      return;
    }
    const timer = setTimeout(() => setStep((s) => Math.min(last, s + 1)), BASE_DELAY_MS / speed);
    return () => clearTimeout(timer);
  }, [playing, step, last, speed]);

  const go = (target: number) => setStep(Math.max(0, Math.min(last, target)));
  const pick = useCallback(
    (target: number) => {
      setPlaying(false);
      setStep(Math.max(0, Math.min(last, target)));
    },
    [last],
  );
  const goGame = (n: number) => (window.location.hash = href.game(runId, Math.max(0, Math.min(total - 1, n))));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target instanceof Element ? e.target : null;
      if (target?.closest("input, select, textarea") || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === " ") {
        if (target?.closest("button, a")) return; // Space already presses the focused control
        e.preventDefault();
        setPlaying((p) => !p);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        setPlaying(false);
        setStep((s) => (e.shiftKey ? nextTurn(starts, s, last) : Math.min(last, s + 1)));
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        setPlaying(false);
        setStep((s) => (e.shiftKey ? previousTurn(starts, s) : Math.max(0, s - 1)));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [starts, last]);

  const turnNumber = frame?.turn ?? 0;

  return (
    <>
      <div className="page-head">
        <div className="breadcrumbs">
          <a href={href.runs()}>Runs</a>
          <span>/</span>
          <a href={href.run(runId)}>{title}</a>
          <span>/</span>
          <span>Game {int(replay.game)}</span>
        </div>
        <div className="title-row">
          <h1>Game {int(replay.game)}</h1>
          <span className="subtitle">
            {replay.track.name} · {replay.racers.length} racers · {replay.turns} turns · seed {replay.seed}
          </span>
        </div>
        <GamePicker game={replay.game} total={total} onGo={goGame} />
      </div>

      {replay.code_changed && (
        <Notice tone="warning">
          <strong>The code has changed since this run.</strong> This replay uses today’s racers and engine, so it may
          not match the game as it was simulated.
        </Notice>
      )}
      {replay.error && (
        <Notice tone="critical">
          <strong>This game crashed</strong> after {int(replay.frames.length)} log lines: <code>{replay.error}</code>.
          Play to the end to see the board when it happened.
        </Notice>
      )}

      <div className="replay">
        <div className="replay-main">
          <Card>
            <Board
              layout={layout}
              track={replay.track}
              crosswalk={replay.crosswalk}
              racers={replay.racers}
              state={state}
              actor={actor}
            />
            <div className="controls" role="group" aria-label="Playback">
              <button type="button" className="button small" onClick={() => go(previousTurn(starts, step))} disabled={step === 0} title="Previous turn (Shift+←)">
                ⏮ Turn
              </button>
              <button type="button" className="button small" onClick={() => go(step - 1)} disabled={step === 0} title="Previous line (←)">
                ◀ Line
              </button>
              <button
                type="button"
                className="button primary small play"
                onClick={() => {
                  if (step >= last) setStep(0);
                  setPlaying((p) => !p);
                }}
                title="Play or pause (Space)"
              >
                {playing ? "Pause" : step >= last ? "Replay" : "Play"}
              </button>
              <button type="button" className="button small" onClick={() => go(step + 1)} disabled={step >= last} title="Next line (→)">
                Line ▶
              </button>
              <button type="button" className="button small" onClick={() => go(nextTurn(starts, step, last))} disabled={step >= last} title="Next turn (Shift+→)">
                Turn ⏭
              </button>
              <label className="speed">
                Speed
                <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
                  {SPEEDS.map((s) => (
                    <option key={s} value={s}>
                      {s}×
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <input
              className="scrubber"
              type="range"
              min={0}
              max={last}
              value={step}
              onChange={(e) => {
                setPlaying(false);
                go(Number(e.target.value));
              }}
              aria-label="Position in the game"
            />
            <div className="step-text" aria-live="polite">
              <span className="muted">
                {step === 0
                  ? "Before the race"
                  : `${frame?.actor === null ? "Setup" : `Turn ${turnNumber}`} · line ${int(step)} of ${int(last)}`}
              </span>
              {frame && <strong> {frame.text}</strong>}
            </div>
          </Card>

          <Card title="Standings" note="Where every racer is at this point in the game.">
            <ol className="standings">
              {replay.racers.map((racer, seat) => (
                <li key={seat} className={actor === seat ? "is-actor" : undefined}>
                  <Token name={racer.name} seat={seat} />
                  <span className="standings-name">
                    <span className="muted">{seat + 1}.</span> {racer.name}
                  </span>
                  <span className="standings-where">{describeRacer(state, seat, replay.track.length)}</span>
                  <span className="standings-points">{state.points[seat]} pts</span>
                </li>
              ))}
            </ol>
            {step >= last && (
              <div className="final">
                <h3>{replay.error ? "Standings when it crashed" : replay.stalled ? "Stopped at the turn limit" : "Final placings"}</h3>
                <ol>
                  {replay.results.map((r) => (
                    <li key={r.seat}>
                      {ordinal(r.place)} {replay.racers[r.seat].name} · {r.points} pts
                      {r.status === "eliminated" && " · eliminated"}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </Card>
        </div>

        <Card title="Game log" note="Click a line to jump there. ←/→ step through lines, Shift jumps a turn, Space plays.">
          <GameLog replay={replay} step={step} onPick={pick} />
        </Card>
      </div>
    </>
  );
}

function GamePicker({ game, total, onGo }: { game: number; total: number; onGo: (n: number) => void }) {
  const [value, setValue] = useState(String(game));
  const target = Number(value);
  const valid = /^\d+$/.test(value) && target < total;
  return (
    <form
      className="toolbar"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) onGo(target);
      }}
    >
      <button type="button" className="button small" onClick={() => onGo(game - 1)} disabled={game <= 0}>
        ← Game {game > 0 ? int(game - 1) : ""}
      </button>
      <label>
        Game
        <input
          type="number"
          min={0}
          max={total - 1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-label={`Game number, 0 to ${total - 1}`}
          style={{ width: 110 }}
        />
      </label>
      <span className="muted">of {int(total)}</span>
      <button type="submit" className="button small" disabled={!valid || target === game}>
        Go
      </button>
      <button type="button" className="button small" onClick={() => onGo(game + 1)} disabled={game >= total - 1}>
        Game {game < total - 1 ? int(game + 1) : ""} →
      </button>
      <button type="button" className="button small" onClick={() => onGo(Math.floor(Math.random() * total))}>
        Random game
      </button>
    </form>
  );
}

function GameLog({ replay, step, onPick }: { replay: Replay; step: number; onPick: (step: number) => void }) {
  const listRef = useRef<HTMLOListElement>(null);

  // Keep the current line in view by scrolling the log only (never the page).
  useLayoutEffect(() => {
    const list = listRef.current;
    const line = list?.querySelector<HTMLElement>(`[data-step="${step}"]`);
    if (!list || !line) return;
    const top = line.offsetTop; // the list is position: relative, so this is measured from its top
    if (top < list.scrollTop + 24 || top > list.scrollTop + list.clientHeight - 48) {
      list.scrollTop = top - list.clientHeight / 3;
    }
  }, [step]);

  return (
    <ol className="game-log" ref={listRef}>
      {replay.frames.map((frame, i) => (
        <LogLine key={i} step={i + 1} text={frame.text} active={step === i + 1} onPick={onPick} />
      ))}
    </ol>
  );
}

const LogLine = memo(function LogLine({
  step,
  text,
  active,
  onPick,
}: {
  step: number;
  text: string;
  active: boolean;
  onPick: (step: number) => void;
}) {
  const isTurn = /^Turn \d+:/.test(text);
  return (
    <li data-step={step} className={`${isTurn ? "turn-line" : ""}${active ? " active" : ""}`}>
      <button type="button" onClick={() => onPick(step)} aria-current={active ? "step" : undefined}>
        {text}
      </button>
    </li>
  );
});
