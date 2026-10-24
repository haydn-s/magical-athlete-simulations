import { useState } from "react";
import { ColumnChart } from "../components/charts";
import { Matchups, matchupsFor } from "../components/Matchups";
import { Badge, Card, LoadError, Loading, StatTile } from "../components/ui";
import { fetchGames, useLoad, useRun } from "../lib/api";
import { href } from "../lib/router";
import { int, num, ordinal, pct, runTitle } from "../lib/stats";
import type { GameList, RacerStats, Summary } from "../types";

export function RacerPage({ runId, racer }: { runId: string; racer: string }) {
  const run = useRun(runId);
  if (run.status === "error") return <LoadError message={run.error} />;
  if (run.status !== "ready") return <Loading />;

  const summary = run.data;
  const stats = summary.racers.find((r) => r.name === racer);
  const title = runTitle({ id: runId, manifest: summary.manifest });

  if (!stats) {
    return (
      <div className="empty">
        <h2>{racer} didn’t race in this run</h2>
        <p>
          <a href={href.run(runId)}>Back to {title}</a>
        </p>
      </div>
    );
  }

  return <RacerView runId={runId} title={title} summary={summary} stats={stats} />;
}

function RacerView({ runId, title, summary, stats }: { runId: string; title: string; summary: Summary; stats: RacerStats }) {
  const { config } = summary.manifest;
  const byPoints = [...summary.racers].sort((a, b) => b.pts_per_game - a.pts_per_game);
  const rank = byPoints.findIndex((r) => r.name === stats.name) + 1;
  const matchups = matchupsFor(summary.head_to_head, stats.name);
  const isFocus = config.focus.includes(stats.name);

  return (
    <>
      <div className="page-head">
        <div className="breadcrumbs">
          <a href={href.runs()}>Runs</a>
          <span>/</span>
          <a href={href.run(runId)}>{title}</a>
          <span>/</span>
          <span>{stats.name}</span>
        </div>
        <div className="title-row">
          <h1>{stats.name}</h1>
          {isFocus && <Badge>focus</Badge>}
        </div>
        <div className="toolbar">
          <p className="subtitle">
            {ordinal(rank)} of {summary.racers.length} by points per game · {int(stats.games)} games on{" "}
            {config.track_name}
          </p>
          <span className="spacer" />
          <label>
            Racer
            <select value={stats.name} onChange={(e) => (window.location.hash = href.racer(runId, e.target.value))}>
              {byPoints.map((r) => (
                <option key={r.name} value={r.name}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="tiles">
        <StatTile
          label="Points per game"
          value={num(stats.pts_per_game)}
          detail={`95% interval ${num(stats.pts_ci[0])} – ${num(stats.pts_ci[1])}`}
        />
        <StatTile
          label="Win rate"
          value={pct(stats.win_rate)}
          detail={`95% interval ${pct(stats.win_rate_ci[0])} – ${pct(stats.win_rate_ci[1])}`}
        />
        <StatTile label={`Finished top ${config.places_to_award}`} value={pct(stats.podium_rate)} />
        <StatTile label="Average place" value={stats.avg_place.toFixed(2)} detail={`of ${config.racers_per_game} racers`} />
        <StatTile label="Eliminated" value={pct(stats.elim_rate)} />
        <StatTile
          label="Game length"
          value={`${stats.avg_game_turns.toFixed(1)} turns`}
          detail={`field average ${summary.totals.avg_turns.toFixed(1)}`}
        />
      </div>

      <PlaceDistribution stats={stats} scoring={config.places_to_award} />

      <RacerGames runId={runId} racer={stats.name} />

      <Card
        title="Matchups"
        note={`How often ${stats.name} finished ahead of each opponent when both raced. Faded rows have fewer than 20 races together.`}
      >
        {matchups.length ? (
          <Matchups runId={runId} racer={stats.name} matchups={matchups} />
        ) : (
          <p className="muted">No head-to-head data for this racer.</p>
        )}
      </Card>
    </>
  );
}

function PlaceDistribution({ stats, scoring }: { stats: RacerStats; scoring: number }) {
  const [asTable, setAsTable] = useState(false);
  const places = stats.place_counts.map((count, i) => ({ place: i + 1, count, share: count / stats.games }));

  return (
    <Card
      title="Finishing place"
      note={`Places 1–${scoring} are the racers who crossed the line; the rest are ordered by track position when the race ended, with eliminated racers last.`}
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
                <th>Place</th>
                <th className="num">Games</th>
                <th className="num">Share</th>
              </tr>
            </thead>
            <tbody>
              {places.map((p) => (
                <tr key={p.place}>
                  <td>{ordinal(p.place)}</td>
                  <td className="num">{int(p.count)}</td>
                  <td className="num">{pct(p.share)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <ColumnChart
          label={`${stats.name} finishing place distribution`}
          format={(v) => `${Math.round(v * 100)}%`}
          data={places.map((p) => ({
            key: String(p.place),
            label: ordinal(p.place),
            value: p.share,
            tooltip: (
              <>
                <div className="tooltip-value">{pct(p.share)}</div>
                <div>Finished {ordinal(p.place)}</div>
                <div className="muted">
                  {int(p.count)} of {int(stats.games)} games
                </div>
              </>
            ),
          }))}
        />
      )}
    </Card>
  );
}

/** The first games this racer was in, each linking to its replay. */
function RacerGames({ runId, racer }: { runId: string; racer: string }) {
  const first = useLoad(() => fetchGames(runId, { racer, limit: 12 }), [runId, racer]);
  const [more, setMore] = useState<GameList[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);

  const pages = first.status === "ready" ? [first.data, ...more] : [];
  const games = pages.flatMap((p) => p.games);
  const next = pages.length ? pages[pages.length - 1].next : null;

  const loadMore = async () => {
    if (next === null) return;
    setLoadingMore(true);
    try {
      const page = await fetchGames(runId, { racer, start: next, limit: 12 });
      setMore((m) => [...m, page]);
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <Card title={`Watch ${racer} race`} note="Replay any game turn by turn. Opponents are listed in turn order.">
      {first.status === "error" && <p className="muted">Couldn’t list games: {first.error}</p>}
      <div className="game-chips">
        {games.map((g) => (
          <a key={g.game} className="game-chip" href={href.game(runId, g.game)}>
            <strong>Game {int(g.game)}</strong>
            <span className="muted">{g.lineup.filter((n) => n !== racer).join(", ")}</span>
          </a>
        ))}
      </div>
      {first.status === "ready" && games.length === 0 && next === null && <p className="muted">No games found.</p>}
      {next !== null && (
        <button type="button" className="button small" onClick={loadMore} disabled={loadingMore} style={{ marginTop: 10 }}>
          {games.length ? "More games" : "Keep looking"}
        </button>
      )}
    </Card>
  );
}
