import { DumbbellMark, MarkAxis } from "../components/charts";
import { Badge, Card, LoadError, Loading, Notice, SortHeader, sortRows, useSort } from "../components/ui";
import { useRun, useRuns } from "../lib/api";
import { compareRuns, type ComparedRacer } from "../lib/compare";
import { href } from "../lib/router";
import { niceMax } from "../lib/scale";
import { formatDate, int, isSignificant, num, pct, runTitle, signedNum, signedPct } from "../lib/stats";
import type { RunListItem, Summary } from "../types";

type CompareKey = "label" | "change" | "winA" | "winB" | "deltaWin" | "ptsA" | "ptsB" | "deltaPts";

const COMPARE_VALUE: Record<CompareKey, (r: ComparedRacer) => number | string> = {
  label: (r) => r.label,
  // Biggest, most certain changes first; a variant paired with its base always leads.
  change: (r) => Math.abs(r.z) + (r.paired ? 1e6 : 0),
  winA: (r) => r.a.win_rate,
  winB: (r) => r.b.win_rate,
  deltaWin: (r) => r.deltaWin,
  ptsA: (r) => r.a.pts_per_game,
  ptsB: (r) => r.b.pts_per_game,
  deltaPts: (r) => r.deltaPts,
};

export function ComparePage({ a, b }: { a: string | null; b: string | null }) {
  const runs = useRuns();
  const runA = useRun(a);
  const runB = useRun(b);

  if (runs.status === "error") return <LoadError message={runs.error} />;
  if (runs.status !== "ready") return <Loading what="runs" />;

  const go = (nextA: string | null, nextB: string | null) => (window.location.hash = href.compare(nextA, nextB));

  return (
    <>
      <div className="page-head">
        <h1>Compare runs</h1>
        <p className="subtitle">
          Racer by racer, how the candidate run differs from the baseline. To test a design change, run the original and
          the variant as focus racers with the same seed.
        </p>
      </div>

      <div className="toolbar">
        <RunSelect label="Baseline (A)" runs={runs.data} value={a} onChange={(id) => go(id, b)} />
        <RunSelect label="Candidate (B)" runs={runs.data} value={b} onChange={(id) => go(a, id)} />
        <button type="button" className="button" onClick={() => go(b, a)} disabled={!a && !b}>
          Swap
        </button>
      </div>

      {!a || !b ? (
        <div className="empty">
          <h2>Pick two runs</h2>
          <p>Choose a baseline and a candidate above.</p>
        </div>
      ) : runA.status === "error" || runB.status === "error" ? (
        <LoadError message={runA.error ?? runB.error ?? "Unknown error"} />
      ) : runA.status !== "ready" || runB.status !== "ready" ? (
        <Loading />
      ) : (
        <Comparison idA={a} idB={b} a={runA.data} b={runB.data} />
      )}
    </>
  );
}

function RunSelect({
  label,
  runs,
  value,
  onChange,
}: {
  label: string;
  runs: RunListItem[];
  value: string | null;
  onChange: (id: string | null) => void;
}) {
  return (
    <label>
      {label}
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value || null)}>
        <option value="">Choose a run…</option>
        {runs.map((run) => (
          <option key={run.id} value={run.id}>
            {runTitle(run)} · {formatDate(run.manifest.created)}
          </option>
        ))}
      </select>
    </label>
  );
}

function Comparison({ idA, idB, a, b }: { idA: string; idB: string; a: Summary; b: Summary }) {
  const [sort, onSort] = useSort<CompareKey>("change");
  const { rows, onlyA, onlyB, differences } = compareRuns(a, b);
  const sorted = sortRows(rows, COMPARE_VALUE[sort.key], sort.dir);

  const cfgA = a.manifest.config;
  const cfgB = b.manifest.config;
  const sameSeed = cfgA.seed === cfgB.seed;
  const samePool = cfgA.pool.length === cfgB.pool.length && cfgA.pool.every((n, i) => n === cfgB.pool[i]);
  const winMax = niceMax(Math.max(0.01, ...rows.flatMap((r) => [r.a.win_rate, r.b.win_rate])));
  const significant = rows.filter((r) => isSignificant(r.z)).length;

  return (
    <>
      {idA === idB && <Notice tone="info">Both sides are the same run, so every difference is zero.</Notice>}
      {differences.length > 0 && (
        <Notice tone="warning">
          <strong>These runs use different settings</strong> ({differences.join("; ")}), so differences mix the design
          change with the setup change.
        </Notice>
      )}
      {idA !== idB && sameSeed && samePool && (
        <Notice tone="info">
          Both runs use seed <span className="mono">{cfgA.seed}</span> and the same opponent pool, so each game number
          had the same opponents, seats and starting dice in both runs.
        </Notice>
      )}

      <Card
        flush
        title={`${rows.length} racers in both runs · ${significant} with a significant win-rate change`}
        note="Significant means the change in win rate is unlikely to be noise (95% level, two-proportion z-test)."
        actions={
          <div className="legend">
            <span className="legend-item">
              <span className="swatch-dot" style={{ background: "var(--series-1)" }} /> A: {runTitle({ id: idA, manifest: a.manifest })}
            </span>
            <span className="legend-item">
              <span className="swatch-dot" style={{ background: "var(--series-2)" }} /> B: {runTitle({ id: idB, manifest: b.manifest })}
            </span>
          </div>
        }
      >
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <SortHeader label="Racer" sortKey="label" sort={sort} onSort={onSort} defaultDir="asc" />
                <th>
                  Win rate
                  <MarkAxis max={winMax} format={(v) => `${Math.round(v * 100)}%`} />
                </th>
                <SortHeader label="A" sortKey="winA" sort={sort} onSort={onSort} numeric />
                <SortHeader label="B" sortKey="winB" sort={sort} onSort={onSort} numeric />
                <SortHeader label="Change" sortKey="deltaWin" sort={sort} onSort={onSort} numeric sub="pct. points" />
                <SortHeader label="z" sortKey="change" sort={sort} onSort={onSort} numeric />
                <SortHeader label="Points A" sortKey="ptsA" sort={sort} onSort={onSort} numeric />
                <SortHeader label="Points B" sortKey="ptsB" sort={sort} onSort={onSort} numeric />
                <SortHeader label="Change" sortKey="deltaPts" sort={sort} onSort={onSort} numeric sub="per game" />
                <th className="num">Games A / B</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.label} className={r.paired ? "highlight" : undefined}>
                  <td>
                    <a href={href.racer(idB, r.b.name)}>{r.label}</a> {r.paired && <Badge>variant</Badge>}
                  </td>
                  <td className="chart-cell">
                    <DumbbellMark a={r.a.win_rate} b={r.b.win_rate} max={winMax} />
                  </td>
                  <td className="num">{pct(r.a.win_rate)}</td>
                  <td className="num">{pct(r.b.win_rate)}</td>
                  <td className="num">
                    {isSignificant(r.z) ? <strong>{signedPct(r.deltaWin)}</strong> : signedPct(r.deltaWin)}
                  </td>
                  <td className="num">
                    {signedNum(r.z)} {isSignificant(r.z) ? <Badge>significant</Badge> : null}
                  </td>
                  <td className="num">{num(r.a.pts_per_game)}</td>
                  <td className="num">{num(r.b.pts_per_game)}</td>
                  <td className="num">{signedNum(r.deltaPts)}</td>
                  <td className="num muted">
                    {int(r.a.games)} / {int(r.b.games)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {onlyA.length > 0 && <p className="card-note">Only in A: {onlyA.join(", ")}</p>}
      {onlyB.length > 0 && <p className="card-note">Only in B: {onlyB.join(", ")}</p>}
    </>
  );
}
