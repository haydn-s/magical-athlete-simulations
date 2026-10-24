import { useState, type ReactNode } from "react";
import { linearScale, niceTicks } from "../lib/scale";
import { Tooltip, anchorOf, useElementWidth, type TooltipState } from "./ui";

// Inline marks sit in table cells, so every row in a column shares one scale.
export const MARK_WIDTH = 150;
const MARK_HEIGHT = 22;
const MARK_PAD = 7;

function markScale(max: number) {
  return linearScale([0, max], [MARK_PAD, MARK_WIDTH - MARK_PAD]);
}

/** Tick labels for an inline-mark column, drawn in the column header. Pass `max` from niceMax(). */
export function MarkAxis({ max, format }: { max: number; format: (v: number) => string }) {
  const x = markScale(max);
  const ticks = niceTicks(max, 4).filter((t) => t <= max + 1e-9);
  return (
    <svg className="chart" width={MARK_WIDTH} height={14} aria-hidden="true">
      {ticks.map((t, i) => (
        <text key={t} x={x(t)} y={10} textAnchor={i === 0 ? "start" : i === ticks.length - 1 ? "end" : "middle"}>
          {format(t)}
        </text>
      ))}
    </svg>
  );
}

/** Estimate (dot) and 95% interval (line), with an optional reference rule. */
export function CiMark({
  value,
  lo,
  hi,
  max,
  reference,
}: {
  value: number;
  lo: number;
  hi: number;
  max: number;
  reference?: number;
}) {
  const x = markScale(max);
  const cy = MARK_HEIGHT / 2;
  return (
    <svg className="chart" width={MARK_WIDTH} height={MARK_HEIGHT} aria-hidden="true">
      {reference !== undefined && (
        <line className="reference" x1={Math.round(x(reference)) + 0.5} x2={Math.round(x(reference)) + 0.5} y1={2} y2={MARK_HEIGHT - 2} />
      )}
      <line className="ci stroke-1" strokeOpacity={0.45} x1={x(lo)} x2={x(hi)} y1={cy} y2={cy} />
      <circle className="series-1 ring" cx={x(value)} cy={cy} r={4.5} />
    </svg>
  );
}

/** Baseline (slot 1) and candidate (slot 2) values joined by a connector. */
export function DumbbellMark({ a, b, max }: { a: number; b: number; max: number }) {
  const x = markScale(max);
  const cy = MARK_HEIGHT / 2;
  return (
    <svg className="chart" width={MARK_WIDTH} height={MARK_HEIGHT} aria-hidden="true">
      <line className="connector" x1={x(a)} x2={x(b)} y1={cy} y2={cy} />
      <circle className="series-1 ring" cx={x(a)} cy={cy} r={4.5} />
      <circle className="series-2 ring" cx={x(b)} cy={cy} r={4.5} />
    </svg>
  );
}

export interface ColumnDatum {
  key: string;
  label: string;
  value: number;
  lo?: number;
  hi?: number;
  tooltip: ReactNode;
}

function columnPath(x: number, w: number, top: number, base: number) {
  const r = Math.min(4, w / 2, Math.max(0, base - top));
  return `M${x},${base}V${top + r}A${r},${r} 0 0 1 ${x + r},${top}H${x + w - r}A${r},${r} 0 0 1 ${x + w},${top + r}V${base}Z`;
}

/** Single-series column chart with optional 95% whiskers and a reference rule. */
export function ColumnChart({
  data,
  format,
  reference,
  height = 220,
  label,
}: {
  data: ColumnDatum[];
  format: (v: number) => string;
  reference?: { value: number; label: string };
  height?: number;
  label: string;
}) {
  const [ref, width] = useElementWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const margin = { top: 18, right: 8, bottom: 26, left: 40 };
  const max = Math.max(...data.map((d) => d.hi ?? d.value), reference?.value ?? 0);
  const ticks = niceTicks(max, 4);
  const yMax = ticks[ticks.length - 1] || 1;
  const plotW = Math.max(0, width - margin.left - margin.right);
  const base = height - margin.bottom;
  const y = linearScale([0, yMax], [base, margin.top]);
  const band = data.length ? plotW / data.length : 0;
  const barW = Math.min(24, band * 0.6);

  const show = (index: number, at: { x: number; y: number }) => {
    setHover(index);
    setTooltip({ ...at, content: data[index].tooltip });
  };
  const hide = () => {
    setHover(null);
    setTooltip(null);
  };

  return (
    <div ref={ref}>
      {width > 0 && (
        <svg className="chart" width={width} height={height} role="img" aria-label={label}>
          {ticks.map((t) => (
            <g key={t}>
              <line className={t === 0 ? "baseline" : "grid"} x1={margin.left} x2={width - margin.right} y1={Math.round(y(t)) + 0.5} y2={Math.round(y(t)) + 0.5} />
              <text x={margin.left - 8} y={y(t) + 4} textAnchor="end">
                {format(t)}
              </text>
            </g>
          ))}

          {hover !== null && (
            <rect className="hover-band" x={margin.left + hover * band} y={margin.top} width={band} height={base - margin.top} />
          )}

          {data.map((d, i) => {
            const cx = margin.left + band * (i + 0.5);
            return (
              <g key={d.key}>
                <path className="series-1" d={columnPath(cx - barW / 2, barW, y(d.value), base)} />
                {d.lo !== undefined && d.hi !== undefined && (
                  <g>
                    <line className="whisker" x1={cx} x2={cx} y1={y(d.lo)} y2={y(d.hi)} />
                    <line className="whisker" x1={cx - 4} x2={cx + 4} y1={y(d.hi)} y2={y(d.hi)} />
                    <line className="whisker" x1={cx - 4} x2={cx + 4} y1={y(d.lo)} y2={y(d.lo)} />
                  </g>
                )}
                <text x={cx} y={base + 17} textAnchor="middle" className="label-secondary">
                  {d.label}
                </text>
              </g>
            );
          })}

          {reference && (
            <g>
              <line className="reference" x1={margin.left} x2={width - margin.right} y1={Math.round(y(reference.value)) + 0.5} y2={Math.round(y(reference.value)) + 0.5} />
              <text x={width - margin.right} y={y(reference.value) - 5} textAnchor="end" className="label-secondary">
                {reference.label}
              </text>
            </g>
          )}

          {data.map((d, i) => (
            <rect
              key={d.key}
              className="hit"
              x={margin.left + band * i}
              y={margin.top}
              width={band}
              height={base - margin.top}
              tabIndex={0}
              aria-label={`${d.label}: ${format(d.value)}`}
              onPointerMove={(e) => show(i, { x: e.clientX, y: e.clientY })}
              onPointerLeave={hide}
              onFocus={(e) => show(i, anchorOf(e.currentTarget))}
              onBlur={hide}
            />
          ))}
        </svg>
      )}
      <Tooltip state={tooltip} />
    </div>
  );
}
