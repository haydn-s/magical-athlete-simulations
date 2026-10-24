import { useMemo, useState } from "react";
import { CiMark, ColumnChart, MarkAxis } from "../components/charts";
import { DivergingLegend, Heatmap, divergingExtent } from "../components/Heatmap";
import {
  Badge,
  Card,
  LoadError,
  Loading,
  Notice,
  SortHeader,
  StatTile,
  sortRows,
  useSort,
} from "../components/ui";
import { downloadUrl, useRun } from "../lib/api";
import { href } from "../lib/router";
import { niceMax } from "../lib/scale";
import {
  compact,
  fieldMeanPoints,
  formatDate,
  int,
  num,
  parityWinRate,
  pct,
  runTitle,
  wilson,
} from "../lib/stats";
import type { RacerStats, Summary } from "../types";

type Tab = "leaderboard" | "h2h" | "seats";

export function RunPage({ runId, tab }: { runId: string; tab: Tab }) {
  const run = useRun(runId);
  if (run.status === "error") return <LoadError message={run.error} />;
  if (run.status !== "ready") return <Loading />;
  const summary = run.data;

  return (
    <>
      <RunHeader runId={runId} summary={summary} />
      <nav className="tabs" aria-label="Run views">
        <a href={href.run(runId)} aria-current={tab === "leaderboard" ? "page" : undefined}>
          Leaderboard
        </a>
        <a href={href.run(runId, "h2h")} aria-current={tab === "h2h" ? "page" : undefined}>
          Head-to-head
        </a>
        <a href={href.run(runId, "seats")} aria-current={tab === "seats" ? "page" : undefined}>
          Turn order
        </a>
      </nav>
      {tab === "leaderboard" && <Leaderboard runId={runId} summary={summary} />}
      {tab === "h2h" && <HeadToHeadView runId={runId} summary={summary} />}
      {tab === "seats" && <SeatsView summary={summary} />}
    </>
  );
}

function RunHeader({ runId, summary }: { runId: string; summary: Summary }) {
  const { manifest, totals, seats, racers } = summary;
  const { config } = manifest;
  const title = runTitle({ id: runId, manifest });
  const topRacer = racers.reduce<RacerStats | null>((best, r) => (!best || r.pts_per_game > best.pts_per_game ? r : best), null);
  const firstSeat = seats[0];
  const lastSeat = seats[seats.length - 1];

  return (
    <>
      <div className="page-head">
        <div className="breadcrumbs">
          <a href={href.runs()}>Runs</a>
          <span>/</span>
          <span>{title}</span>
        </div>
        <div className="title-row">
          <h1>{title}</h1>
          {config.focus.map((name) => (
            <Badge key={name}>focus: {name}</Badge>
          ))}
        </div>
        <div className="meta">
          <span>
            <strong>{config.track_name}</strong>
          </span>
          <span>{int(totals.games)} games</span>
          <span>{config.racers_per_game} racers per game</span>
          <span>top {config.places_to_award} score</span>
          <span>
            seed <span className="mono">{config.seed}</span>
          </span>
          <span>{formatDate(manifest.created)}</span>
          <span>
            {manifest.duration_sec.toFixed(1)}s on {manifest.workers} workers
          </span>
          {manifest.git && (
            <span>
              code <span className="mono">{manifest.git.commit.slice(0, 7)}</span>
              {manifest.git.dirty && " + uncommitted changes"}
            </span>
          )}
        </div>
        <div className="head-actions">
          <a className="button small" href={href.compare(runId)}>
            Compare with another run
          </a>
          <a className="button small" href={href.newRun(runId)}>
            New run from this
          </a>
          <a className="button small" href={downloadUrl(runId, "racers.csv")}>
            racers.csv
          </a>
          <a className="button small" href={downloadUrl(runId, "head_to_head.csv")}>
            head_to_head.csv
          </a>
          <a className="button small" href={downloadUrl(runId, "summary.json")}>
            summary.json
          </a>
        </div>
      </div>

      {totals.errors > 0 && (
        <Notice tone="critical">
          <strong>{int(totals.errors)} games raised an error</strong> and are left out of these numbers. They’re listed in{" "}
          <code>errors.jsonl</code>; replay one with <code>python -m sim replay --from results/{runId} --game N</code>.
        </Notice>
      )}
      {totals.stalled > 0 && (
        <Notice tone="warning">
          <strong>{int(totals.stalled)} games hit the 1,000-turn cap</strong> before enough racers finished. They’re
          included, scored by position.
        </Notice>
      )}
      {config.replaced.length > 0 && (
        <Notice tone="info">
          Variants raced in place of <strong>{config.replaced.join(", ")}</strong>.
        </Notice>
      )}

      <div className="tiles">
        <StatTile label="Games simulated" value={compact(totals.games)} detail={`${int(totals.games)} games`} />
        <StatTile label="Average game length" value={`${totals.avg_turns.toFixed(1)} turns`} />
        {topRacer && (
          <StatTile label="Most points per game" value={topRacer.name} detail={`${num(topRacer.pts_per_game)} points per game`} />
        )}
        {firstSeat && lastSeat && firstSeat !== lastSeat && (
          <StatTile
            label="Turn-order effect"
            value={`${pct(firstSeat.win_rate)} vs ${pct(lastSeat.win_rate)}`}
            detail={`win rate, seat 1 vs seat ${lastSeat.seat}`}
          />
        )}
      </div>
    </>
  );
}

// --- leaderboard ---------------------------------------------------------------

type LeaderKey = "name" | "games" | "pts" | "win" | "podium" | "place" | "elim" | "turns";

const LEADER_VALUE: Record<LeaderKey, (r: RacerStats) => number | string> = {
  name: (r) => r.name,
  games: (r) => r.games,
  pts: (r) => r.pts_per_game,
  win: (r) => r.win_rate,
  podium: (r) => r.podium_rate,
  place: (r) => r.avg_place,
  elim: (r) => r.elim_rate,
  turns: (r) => r.avg_game_turns,
};

function Leaderboard({ runId, summary }: { runId: string; summary: Summary }) {
  const [sort, onSort] = useSort<LeaderKey>("pts");
  const [query, setQuery] = useState("");
  const { racers, manifest } = summary;
  const focus = new Set(manifest.config.focus);

  const ptsMax = niceMax(Math.max(...racers.map((r) => r.pts_ci[1])));
  const winMax = niceMax(Math.max(...racers.map((r) => r.win_rate_ci[1])));
  const fieldPts = fieldMeanPoints(racers);
  const parity = parityWinRate(summary);

  const needle = query.trim().toLowerCase();
  const rows = sortRows(
    racers.filter((r) => !needle || r.name.toLowerCase().includes(needle)),
    LEADER_VALUE[sort.key],
    sort.dir,
  );

  return (
    <>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Filter racers"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Filter racers"
        />
        <span className="spacer" />
        <div className="legend">
          <span className="legend-item">
            <span className="swatch-dot" style={{ background: "var(--series-1)" }} /> estimate
          </span>
          <span className="legend-item">
            <span className="swatch-line" style={{ background: "var(--series-1)", opacity: 0.45 }} /> 95% interval
          </span>
          <span className="legend-item">
            <span className="swatch-line" style={{ background: "var(--text-secondary)", width: 1, height: 12 }} /> field
            average · parity ({pct(parity)})
          </span>
        </div>
      </div>

      <Card flush>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th className="num">#</th>
                <SortHeader label="Racer" sortKey="name" sort={sort} onSort={onSort} defaultDir="asc" />
                <SortHeader label="Games" sortKey="games" sort={sort} onSort={onSort} numeric />
                <SortHeader label="Points / game" sortKey="pts" sort={sort} onSort={onSort} numeric />
                <th>
                  <MarkAxis max={ptsMax} format={(v) => String(v)} />
                </th>
                <SortHeader label="Win rate" sortKey="win" sort={sort} onSort={onSort} numeric sub="95% interval" />
                <th>
                  <MarkAxis max={winMax} format={(v) => `${Math.round(v * 100)}%`} />
                </th>
                <SortHeader
                  label={`Top ${manifest.config.places_to_award}`}
                  sortKey="podium"
                  sort={sort}
                  onSort={onSort}
                  numeric
                />
                <SortHeader label="Avg place" sortKey="place" sort={sort} onSort={onSort} numeric defaultDir="asc" />
                <SortHeader label="Eliminated" sortKey="elim" sort={sort} onSort={onSort} numeric />
                <SortHeader label="Game length" sortKey="turns" sort={sort} onSort={onSort} numeric sub="turns" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.name} className={focus.has(r.name) ? "highlight" : undefined}>
                  <td className="num muted">{i + 1}</td>
                  <td>
                    <a href={href.racer(runId, r.name)}>{r.name}</a> {focus.has(r.name) && <Badge>focus</Badge>}
                  </td>
                  <td className="num">{int(r.games)}</td>
                  <td className="num">
                    {num(r.pts_per_game)} <span className="muted">±{num((r.pts_ci[1] - r.pts_ci[0]) / 2)}</span>
                  </td>
                  <td className="chart-cell">
                    <CiMark value={r.pts_per_game} lo={r.pts_ci[0]} hi={r.pts_ci[1]} max={ptsMax} reference={fieldPts} />
                  </td>
                  <td className="num">
                    {pct(r.win_rate)}{" "}
                    <span className="muted">
                      {(r.win_rate_ci[0] * 100).toFixed(1)}–{(r.win_rate_ci[1] * 100).toFixed(1)}
                    </span>
                  </td>
                  <td className="chart-cell">
                    <CiMark value={r.win_rate} lo={r.win_rate_ci[0]} hi={r.win_rate_ci[1]} max={winMax} reference={parity} />
                  </td>
                  <td className="num">{pct(r.podium_rate)}</td>
                  <td className="num">{r.avg_place.toFixed(2)}</td>
                  <td className="num">{pct(r.elim_rate)}</td>
                  <td className="num">{r.avg_game_turns.toFixed(1)}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={11} className="muted">
                    No racers match “{query}”.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
      <p className="card-note">
        Gray rules mark the field average ({num(fieldPts)} points per game) and parity, the win rate every racer would
        have in a perfectly balanced field. Game length is the average number of turns in games this racer was in.
      </p>
    </>
  );
}

// --- head-to-head --------------------------------------------------------------

function HeadToHeadView({ runId, summary }: { runId: string; summary: Summary }) {
  const extent = useMemo(() => divergingExtent(summary.head_to_head.ahead_rate), [summary]);
  const focusRun = summary.manifest.config.focus.length > 0;

  return (
    <Card
      title="Head-to-head"
      note={
        <>
          How often the row racer finished ahead of the column racer when both were in the race. Racers are ordered by
          points per game. Click a cell to open the row racer.
          {focusRun && " In a focus run, most racers rarely meet each other, so pairs with fewer than 20 races are left blank."}
        </>
      }
      actions={
        <a className="button small" href={downloadUrl(runId, "head_to_head.csv")}>
          Download as CSV
        </a>
      }
    >
      <div style={{ marginBottom: 12 }}>
        <DivergingLegend extent={extent} />
      </div>
      <Heatmap data={summary.head_to_head} onSelect={(name) => (window.location.hash = href.racer(runId, name))} />
    </Card>
  );
}

// --- turn order ----------------------------------------------------------------

function SeatsView({ summary }: { summary: Summary }) {
  const [asTable, setAsTable] = useState(false);
  const parity = parityWinRate(summary);
  const seats = summary.seats.map((s) => ({ ...s, ci: wilson(s.wins, s.games) }));

  return (
    <Card
      title="Win rate by turn order"
      note="Seat 1 takes the first turn. Whiskers show the 95% interval; the gray rule is parity."
      actions={
        <button type="button" className="button small" aria-pressed={asTable} onClick={() => setAsTable((v) => !v)}>
          {asTable ? "Show chart" : "Show table"}
        </button>
      }
    >
      {asTable ? (
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>Seat</th>
                <th className="num">Games</th>
                <th className="num">Wins</th>
                <th className="num">Win rate</th>
                <th className="num">95% interval</th>
              </tr>
            </thead>
            <tbody>
              {seats.map((s) => (
                <tr key={s.seat}>
                  <td>{s.seat}</td>
                  <td className="num">{int(s.games)}</td>
                  <td className="num">{int(s.wins)}</td>
                  <td className="num">{pct(s.win_rate)}</td>
                  <td className="num">
                    {pct(s.ci[0])} – {pct(s.ci[1])}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <ColumnChart
          label="Win rate by seat"
          format={(v) => `${Math.round(v * 100)}%`}
          reference={{ value: parity, label: `parity ${pct(parity)}` }}
          data={seats.map((s) => ({
            key: String(s.seat),
            label: `Seat ${s.seat}`,
            value: s.win_rate,
            lo: s.ci[0],
            hi: s.ci[1],
            tooltip: (
              <>
                <div className="tooltip-value">{pct(s.win_rate)}</div>
                <div>Seat {s.seat} win rate</div>
                <div className="muted">
                  95% interval {pct(s.ci[0])} – {pct(s.ci[1])} · {int(s.games)} games
                </div>
              </>
            ),
          }))}
        />
      )}
    </Card>
  );
}
