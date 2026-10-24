import { useState } from "react";
import { useRuns } from "../lib/api";
import { href } from "../lib/router";
import { compact, formatDate, int, runTitle } from "../lib/stats";
import type { RunListItem } from "../types";
import { Badge, Card, LoadError, Loading, SortHeader, sortRows, useSort } from "../components/ui";

type SortKey = "created" | "title" | "track" | "games" | "players";

const SORT_VALUE: Record<SortKey, (r: RunListItem) => number | string> = {
  created: (r) => r.manifest.created,
  title: (r) => runTitle(r),
  track: (r) => r.manifest.config.track_name,
  games: (r) => r.totals.games,
  players: (r) => r.manifest.config.racers_per_game,
};

export function RunsPage() {
  const runs = useRuns();
  const [selected, setSelected] = useState<string[]>([]);
  const [sort, onSort] = useSort<SortKey>("created");

  if (runs.status === "error") return <LoadError message={runs.error} />;
  if (runs.status !== "ready") return <Loading what="runs" />;

  if (runs.data.length === 0) {
    return (
      <div className="empty">
        <h2>No saved runs yet</h2>
        <p>Run a batch from the repo root and it will show up here.</p>
        <pre>
          <code>python -m sim run -n 50000 --seed 1</code>
        </pre>
      </div>
    );
  }

  // Comparing in selection order: the first run picked is the baseline.
  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id].slice(-2)));
  const rows = sortRows(runs.data, SORT_VALUE[sort.key], sort.dir);

  return (
    <>
      <div className="page-head">
        <h1>Simulation runs</h1>
        <p className="subtitle">
          {runs.data.length} saved {runs.data.length === 1 ? "run" : "runs"} in <code>results/</code>. Pick two to compare
          them.
        </p>
      </div>

      <div className="toolbar">
        <button
          type="button"
          className="button"
          disabled={selected.length !== 2}
          onClick={() => (window.location.hash = href.compare(selected[0], selected[1]))}
        >
          Compare selected ({selected.length}/2)
        </button>
        {selected.length > 0 && (
          <button type="button" className="button" onClick={() => setSelected([])}>
            Clear
          </button>
        )}
      </div>

      <Card flush>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th aria-label="Select" />
                <SortHeader label="Run" sortKey="title" sort={sort} onSort={onSort} defaultDir="asc" />
                <SortHeader label="Created" sortKey="created" sort={sort} onSort={onSort} />
                <SortHeader label="Track" sortKey="track" sort={sort} onSort={onSort} defaultDir="asc" />
                <SortHeader label="Games" sortKey="games" sort={sort} onSort={onSort} numeric />
                <SortHeader label="Racers" sortKey="players" sort={sort} onSort={onSort} numeric />
                <th>Focus</th>
                <th className="num">Seed</th>
                <th className="num">Took</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((run) => {
                const { config } = run.manifest;
                const order = selected.indexOf(run.id);
                return (
                  <tr key={run.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={order >= 0}
                        onChange={() => toggle(run.id)}
                        aria-label={`Select ${runTitle(run)} for comparison`}
                      />
                      {order >= 0 && <span className="muted"> {order === 0 ? "A" : "B"}</span>}
                    </td>
                    <td>
                      <a href={href.run(run.id)}>{runTitle(run)}</a>
                      {run.manifest.label && <div className="muted mono">{run.id}</div>}
                    </td>
                    <td>{formatDate(run.manifest.created)}</td>
                    <td>{config.track_name}</td>
                    <td className="num" title={int(run.totals.games)}>
                      {compact(run.totals.games)}
                    </td>
                    <td className="num">{config.racers_per_game}</td>
                    <td>
                      {config.focus.length ? config.focus.join(", ") : <span className="muted">—</span>}
                      {run.totals.errors > 0 && <> <Badge>{int(run.totals.errors)} errors</Badge></>}
                    </td>
                    <td className="num mono">{config.seed}</td>
                    <td className="num">{run.manifest.duration_sec.toFixed(1)}s</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
