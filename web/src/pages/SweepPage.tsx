import { useState } from "react";
import { PointChart } from "../components/charts";
import { Badge, Card, CopyButton, LoadError, Loading, Notice, StatTile } from "../components/ui";
import { fetchSweep, useLoad } from "../lib/api";
import { href } from "../lib/router";
import { formatDate, int, num, pct } from "../lib/stats";
import type { PairedDelta, Sweep, SweepPoint } from "../types";

export function sweepTitle(sweep: { id: string; label: string | null; settings: Sweep["settings"] }): string {
  return sweep.label || sweep.settings.map((s) => `${s.power.replace(/Power$/, "")}.${s.setting}`).join(" × ") || sweep.id;
}

export function SweepPage({ sweepId }: { sweepId: string }) {
  const sweep = useLoad(() => fetchSweep(sweepId), [sweepId]);
  if (sweep.status === "error") return <LoadError message={sweep.error} />;
  if (sweep.status !== "ready") return <Loading what="the sweep" />;
  return <SweepView sweep={sweep.data} />;
}

function SweepView({ sweep }: { sweep: Sweep }) {
  const points = sweep.points.filter((p): p is SweepPoint => p !== null);
  const everyone = Array.from(new Set(points.flatMap((p) => p.racers.map((r) => r.name))));
  const options = [...sweep.subjects, ...everyone.filter((n) => !sweep.subjects.includes(n)).sort()];
  const [racer, setRacer] = useState(options[0] ?? "");

  const { config } = sweep;
  const single = sweep.settings.length === 1;
  const baseline = sweep.points[sweep.baseline];
  const isSubject = sweep.subjects.includes(racer);
  const valueLabel = (p: SweepPoint) => (single ? String(p.overrides[0].value) : p.label);
  const rows = points.map((p) => ({ point: p, stats: p.racers.find((r) => r.name === racer) })).filter((r) => r.stats);
  const best = sweep.best[racer];
  const statsAt = (index: number) => sweep.points[index]?.racers.find((r) => r.name === racer);
  const pointLabel = (index: number | null | undefined) => {
    const point = index === null || index === undefined ? null : sweep.points[index];
    return point ? (single ? `${sweep.settings[0].setting} = ${point.overrides[0].value}` : point.label) : null;
  };

  return (
    <>
      <div className="page-head">
        <div className="breadcrumbs">
          <a href={href.runs()}>Runs</a>
          <span>/</span>
          <span>Sweep</span>
        </div>
        <div className="title-row">
          <h1>{sweepTitle(sweep)}</h1>
          {!sweep.complete && <Badge>incomplete</Badge>}
        </div>
        <div className="meta">
          {sweep.settings.map((s) => (
            <span key={s.setting} style={{ whiteSpace: "normal" }}>
              <strong>
                {s.power}.{s.setting}
              </strong>{" "}
              = {s.values.join(", ")} (now {String(s.current)})
            </span>
          ))}
          <span>{int(config.games)} games per value</span>
          <span>{config.track_name}</span>
          <span>{config.racers_per_game} racers per game</span>
          <span>
            seed <span className="mono">{config.seed}</span>
          </span>
          <span>{formatDate(sweep.created)}</span>
        </div>
      </div>

      {!sweep.complete && (
        <Notice tone="warning">
          <strong>
            {points.length} of {sweep.points.length} values finished.
          </strong>{" "}
          The sweep is still running or was stopped; reload to see more.
        </Notice>
      )}
      {sweep.no_effect && (
        <Notice tone="warning">
          <strong>This setting had no effect:</strong> every value gave identical results. Check that the power reads it
          as <code>self.{sweep.settings[0]?.setting}</code>.
        </Notice>
      )}
      {sweep.auto_focus.length > 0 && (
        <Notice tone="info">
          {sweep.auto_focus.join(", ")} {sweep.auto_focus.length === 1 ? "was" : "were"} added as a focus racer, so{" "}
          {sweep.auto_focus.length === 1 ? "it’s" : "they’re"} in every game. Every value used the same seed, so each
          game number had the same lineup at every value.
        </Notice>
      )}

      <div className="toolbar">
        <label>
          Racer
          <select value={racer} onChange={(e) => setRacer(e.target.value)}>
            <optgroup label="Swept racers">
              {sweep.subjects.map((n) => (
                <option key={n}>{n}</option>
              ))}
            </optgroup>
            <optgroup label="Everyone else">
              {options.slice(sweep.subjects.length).map((n) => (
                <option key={n}>{n}</option>
              ))}
            </optgroup>
          </select>
        </label>
      </div>

      {best && (
        <div className="verdict">
          <StatTile
            label="Win rate closest to parity"
            value={pointLabel(best.parity) ?? "No change"}
            detail={
              best.parity === null
                ? "this setting doesn’t change who wins"
                : `${pct(statsAt(best.parity)?.win_rate ?? 0)} there, vs parity ${pct(sweep.parity)}`
            }
          />
          <StatTile
            label="Points closest to the field average"
            value={pointLabel(best.points) ?? "No change"}
            detail={
              best.points === null
                ? "this setting doesn’t change points"
                : `${num(statsAt(best.points)?.pts_per_game ?? 0)} per game there, vs ${num(sweep.points[best.points]?.field_pts ?? 0)} for the field`
            }
          />
        </div>
      )}

      <div className="two-col">
        <Card title={`${racer}: win rate`} note="Dots are estimates, whiskers 95% intervals; the gray rule is parity.">
          <PointChart
            label={`${racer} win rate at each value`}
            format={(v) => `${Math.round(v * 100)}%`}
            reference={{ value: sweep.parity, label: `parity ${pct(sweep.parity)}` }}
            data={rows.map(({ point, stats }) => ({
              key: String(point.index),
              label: valueLabel(point),
              value: stats!.win_rate,
              lo: stats!.win_rate_ci[0],
              hi: stats!.win_rate_ci[1],
              highlight: point.current,
              tooltip: (
                <>
                  <div className="tooltip-value">{pct(stats!.win_rate)}</div>
                  <div>{point.label}</div>
                  <div className="muted">
                    95% interval {pct(stats!.win_rate_ci[0])} – {pct(stats!.win_rate_ci[1])}
                  </div>
                </>
              ),
            }))}
          />
        </Card>
        <Card title={`${racer}: points per game`} note="The gray rule is the field average at the current value.">
          <PointChart
            label={`${racer} points per game at each value`}
            format={(v) => num(v, v < 10 ? 1 : 0)}
            reference={baseline ? { value: baseline.field_pts, label: `field average ${num(baseline.field_pts)}` } : undefined}
            data={rows.map(({ point, stats }) => ({
              key: String(point.index),
              label: valueLabel(point),
              value: stats!.pts_per_game,
              lo: stats!.pts_ci[0],
              hi: stats!.pts_ci[1],
              highlight: point.current,
              tooltip: (
                <>
                  <div className="tooltip-value">{num(stats!.pts_per_game)} points</div>
                  <div>{point.label}</div>
                  <div className="muted">
                    95% interval {num(stats!.pts_ci[0])} – {num(stats!.pts_ci[1])}
                  </div>
                </>
              ),
            }))}
          />
        </Card>
      </div>

      <Card
        flush
        title="Every value"
        note={
          isSubject
            ? "“vs current” compares each game with the same game at the current value, which is far more precise than comparing two separate runs."
            : "Game-by-game comparisons are worked out for the swept racers; pick one above to see them."
        }
      >
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>{single ? sweep.settings[0].setting : "Settings"}</th>
                <th className="num">Games</th>
                <th className="num">Win rate</th>
                <th className="num">vs current</th>
                <th className="num">Points / game</th>
                <th className="num">vs current</th>
                <th className="num">Games changed</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map(({ point, stats }) => {
                const paired = isSubject ? point.paired[racer] : undefined;
                return (
                  <tr key={point.index} className={point.current ? "highlight" : undefined}>
                    <td>
                      {valueLabel(point)} {point.current && <Badge>current</Badge>}
                    </td>
                    <td className="num">{int(stats!.games)}</td>
                    <td className="num">
                      {pct(stats!.win_rate)}{" "}
                      <span className="muted">
                        {(stats!.win_rate_ci[0] * 100).toFixed(1)}–{(stats!.win_rate_ci[1] * 100).toFixed(1)}
                      </span>
                    </td>
                    <td className="num">{point.current ? "—" : <Delta d={paired?.win} scale={100} digits={1} unit=" pts" />}</td>
                    <td className="num">{num(stats!.pts_per_game)}</td>
                    <td className="num">{point.current ? "—" : <Delta d={paired?.pts} scale={1} digits={2} />}</td>
                    <td className="num muted">{point.current || !paired?.pts ? "—" : int(paired.pts.changed)}</td>
                    <td>
                      <a href={href.run(point.run_id)}>Results</a>
                      {!point.current && baseline && (
                        <>
                          {" · "}
                          <a href={href.compare(baseline.run_id, point.run_id)}>Compare</a>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {sweep.command && (
        <div className="command-preview">
          <span className="muted">Run again with:</span>
          <code>{sweep.command}</code>
          <CopyButton text={sweep.command} />
        </div>
      )}
    </>
  );
}

function Delta({ d, scale, digits, unit = "" }: { d: PairedDelta | null | undefined; scale: number; digits: number; unit?: string }) {
  if (!d) return <span className="muted">—</span>;
  const fmt = (v: number) => {
    const text = Math.abs(v * scale).toFixed(digits);
    return `${Number(text) === 0 ? "±" : v > 0 ? "+" : "−"}${text}`;
  };
  const text = `${fmt(d.delta)}${unit}`;
  return (
    <>
      {d.significant ? <strong>{text}</strong> : text}{" "}
      <span className="muted">
        [{fmt(d.ci[0])}, {fmt(d.ci[1])}]
      </span>
      {d.significant && (
        <>
          {" "}
          <Badge>significant</Badge>
        </>
      )}
    </>
  );
}
