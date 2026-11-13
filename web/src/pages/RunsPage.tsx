import { useState } from "react";
import { fetchSweeps, useLoad, useRuns } from "../lib/api";
import { href } from "../lib/router";
import { compact, formatDate, int, runTitle } from "../lib/stats";
import type { RunListItem, SweepListItem } from "../types";
import { sweepTitle } from "./SweepPage";
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
  const sweeps = useLoad(fetchSweeps, []);
  const [selected, setSelected] = useState<string[]>([]);
  const [showSweepRuns, setShowSweepRuns] = useState(false);
  const [sort, onSort] = useSort<SortKey>("created");

  if (runs.status === "error") return <LoadError message={runs.error} />;
  if (runs.status !== "ready") return <Loading what="runs" />;

  if (runs.data.length === 0) {
    return (
      <div className="empty">
        <h2>No saved runs yet</h2>
        <p>
          <a href={href.newRun()}>Start a run here</a>, or run a batch from the repo root and it will show up.
        </p>
        <pre>
          <code>python -m sim run -n 50000 --seed 1</code>
        </pre>
      </div>
    );
  }

  // Comparing in selection order: the first run picked is the baseline.
  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id].slice(-2)));
  const sweepRuns = runs.data.filter((r) => r.manifest.sweep).length;
  const visible = showSweepRuns ? runs.data : runs.data.filter((r) => !r.manifest.sweep);
  const rows = sortRows(visible, SORT_VALUE[sort.key], sort.dir);

  return (
    <>
      <div className="page-head">
        <h1>Simulation runs</h1>
        <p className="subtitle">
          {runs.data.length} saved {runs.data.length === 1 ? "run" : "runs"} in <code>results/</code>. Pick two to compare
          them.
        </p>
      </div>

      {sweeps.status === "ready" && sweeps.data.length > 0 && <SweepList sweeps={sweeps.data} />}

      <div className="toolbar">
        <a className="button primary" href={href.newRun()}>
          New run
        </a>
        <button
          type="button"
          className="button"
          disabled={selected.length !== 2}
          onClick={() => (window.location.hash = href.compare(selected[0], selected[1]))}
        >
          Compare selected ({selected.length}/2)
        </button>
        {sweepRuns > 0 && (
          <label className="check">
            <input type="checkbox" checked={showSweepRuns} onChange={(e) => setShowSweepRuns(e.target.checked)} />
            Show runs from sweeps ({sweepRuns})
          </label>
        )}
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
                      {run.manifest.sweep && <> <Badge>sweep</Badge></>}
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

function SweepList({ sweeps }: { sweeps: SweepListItem[] }) {
  return (
    <Card
      flush
      title="Sweeps"
      note="Each sweep ran the same games at several values of a power setting. Make one with python -m sim sweep."
    >
      <div className="table-scroll">
        <table className="data">
          <thead>
            <tr>
              <th>Sweep</th>
              <th>Values</th>
              <th>Created</th>
              <th className="num">Games per value</th>
              <th>Racers</th>
            </tr>
          </thead>
          <tbody>
            {sweeps.map((sweep) => (
              <tr key={sweep.id}>
                <td>
                  <a href={href.sweep(sweep.id)}>{sweepTitle(sweep)}</a>{" "}
                  {!sweep.complete && <Badge>incomplete</Badge>}
                  {sweep.no_effect && <Badge>no effect</Badge>}
                </td>
                <td>{sweep.settings.map((s) => `${s.setting} = ${s.values.join(", ")}`).join("; ")}</td>
                <td>{formatDate(sweep.created)}</td>
                <td className="num">{compact(sweep.config.games)}</td>
                <td>{sweep.subjects.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
