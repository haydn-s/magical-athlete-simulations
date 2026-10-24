import { memo, useMemo, useState, type MouseEvent, type PointerEvent } from "react";
import type { HeadToHead } from "../types";
import { int, pct } from "../lib/stats";
import { Tooltip, useElementWidth, type TooltipState } from "./ui";

const LABEL_WIDTH = 116;
export const MIN_RACES = 20;

/**
 * Symmetric distance from 50% that the color scale spans, rounded up to 5 points.
 * Uses the 95th percentile so one lopsided racer doesn't wash every other cell out
 * to gray; anything beyond it is drawn at full color (the legend says so).
 */
export function divergingExtent(matrix: (number | null)[][]): number {
  const deviations = matrix
    .flat()
    .filter((v): v is number => v !== null)
    .map((v) => Math.abs(v - 0.5))
    .sort((a, b) => a - b);
  if (deviations.length === 0) return 0.1;
  const p95 = deviations[Math.min(deviations.length - 1, Math.floor(deviations.length * 0.95))];
  return Math.min(0.5, Math.max(0.1, Math.ceil(p95 * 20 - 1e-9) / 20));
}

/** Fill for an "ahead" rate: blue above 50%, red below, neutral gray at 50%. */
export function divergingFill(value: number, extent: number): string {
  const t = Math.max(-1, Math.min(1, (value - 0.5) / extent));
  const pole = t >= 0 ? "var(--div-pos)" : "var(--div-neg)";
  return `color-mix(in oklab, ${pole} ${Math.round(Math.abs(t) * 100)}%, var(--div-mid))`;
}

export function DivergingLegend({ extent }: { extent: number }) {
  const clamped = extent < 0.5;
  return (
    <div className="diverging-legend" aria-hidden="true">
      <span>Row behind more often</span>
      <span className="bar" />
      <span>Row ahead more often</span>
      <span className="ticks">
        <span>
          {clamped && "≤ "}
          {pct(0.5 - extent)}
        </span>
        <span>50%</span>
        <span>
          {clamped && "≥ "}
          {pct(0.5 + extent)}
        </span>
      </span>
    </div>
  );
}

interface Hover {
  row: number;
  col: number;
}

export function Heatmap({ data, onSelect }: { data: HeadToHead; onSelect: (name: string) => void }) {
  const [ref, width] = useElementWidth<HTMLDivElement>();
  const [hover, setHover] = useState<Hover | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const n = data.names.length;
  const extent = useMemo(() => divergingExtent(data.ahead_rate), [data]);
  const cell = Math.max(10, Math.min(22, Math.floor((width - LABEL_WIDTH - 4) / Math.max(n, 1))));
  const gap = cell >= 12 ? 2 : 1;
  const top = Math.min(118, cell * 6 + 10);
  const svgWidth = LABEL_WIDTH + n * cell + 4;
  const svgHeight = top + n * cell;
  const fontSize = Math.min(11.5, cell - 1);

  const cellAt = (e: MouseEvent<SVGSVGElement>): Hover | null => {
    const rect = e.currentTarget.getBoundingClientRect();
    const col = Math.floor((e.clientX - rect.left - LABEL_WIDTH) / cell);
    const row = Math.floor((e.clientY - rect.top - top) / cell);
    if (row < 0 || col < 0 || row >= n || col >= n) return null;
    return { row, col };
  };

  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const at = cellAt(e);
    setHover(at);
    if (!at || at.row === at.col) {
      setTooltip(null);
      return;
    }
    const rowName = data.names[at.row];
    const colName = data.names[at.col];
    const races = data.together[at.row][at.col];
    const rate = data.ahead_rate[at.row][at.col];
    setTooltip({
      x: e.clientX,
      y: e.clientY,
      content:
        rate === null || races < MIN_RACES ? (
          <>
            <div className="tooltip-value">Too few races</div>
            <div>
              {rowName} and {colName} raced together {int(races)} times
            </div>
          </>
        ) : (
          <>
            <div className="tooltip-value">{pct(rate)}</div>
            <div>
              {rowName} placed ahead of {colName}
            </div>
            <div className="muted">in {int(races)} races together</div>
          </>
        ),
    });
  };

  const onClick = (e: MouseEvent<SVGSVGElement>) => {
    const at = cellAt(e);
    if (at) onSelect(data.names[at.row]);
  };

  return (
    <div ref={ref} className="heatmap-scroll">
      {width > 0 && (
        <svg
          className="chart"
          width={svgWidth}
          height={svgHeight}
          role="img"
          aria-label="Head-to-head heatmap: how often each row racer placed ahead of each column racer"
          onPointerMove={onMove}
          onPointerLeave={() => {
            setHover(null);
            setTooltip(null);
          }}
          onClick={onClick}
          style={{ cursor: "pointer" }}
        >
          {cell >= 11 &&
            data.names.map((name, i) => (
              <text
                key={name}
                className={`row-label${hover?.col === i ? " active" : ""}`}
                transform={`translate(${LABEL_WIDTH + i * cell + cell / 2 + fontSize / 3},${top - 6}) rotate(-90)`}
                style={{ fontSize }}
              >
                {name}
              </text>
            ))}
          {data.names.map((name, i) => (
            <text
              key={name}
              className={`row-label${hover?.row === i ? " active" : ""}`}
              x={LABEL_WIDTH - 8}
              y={top + i * cell + cell / 2 + fontSize / 3}
              textAnchor="end"
              style={{ fontSize }}
            >
              {name}
            </text>
          ))}
          <Cells data={data} extent={extent} cell={cell} gap={gap} top={top} />
          {hover && hover.row !== hover.col && (
            <rect
              className="cell-outline"
              x={LABEL_WIDTH + hover.col * cell}
              y={top + hover.row * cell}
              width={cell - gap}
              height={cell - gap}
              rx={2}
            />
          )}
        </svg>
      )}
      <Tooltip state={tooltip} />
    </div>
  );
}

// The grid is the expensive part (n x n rects), so it only re-renders when the data or size changes.
const Cells = memo(function Cells({
  data,
  extent,
  cell,
  gap,
  top,
}: {
  data: HeadToHead;
  extent: number;
  cell: number;
  gap: number;
  top: number;
}) {
  const rects = [];
  for (let r = 0; r < data.names.length; r++) {
    for (let c = 0; c < data.names.length; c++) {
      const rate = data.ahead_rate[r][c];
      if (r === c || rate === null || data.together[r][c] < MIN_RACES) continue;
      rects.push(
        <rect
          key={`${r}:${c}`}
          x={LABEL_WIDTH + c * cell}
          y={top + r * cell}
          width={cell - gap}
          height={cell - gap}
          rx={2}
          style={{ fill: divergingFill(rate, extent) }}
        />,
      );
    }
  }
  return <g>{rects}</g>;
});
