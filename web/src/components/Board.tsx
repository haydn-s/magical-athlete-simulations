import { memo } from "react";
import { TOKEN_R, initials, placeTokens, type BoardLayout } from "../lib/board";
import type { ReplayState, TrackInfo } from "../types";

/** Seat colors: the eight categorical slots in order, then gray (initials still identify them). */
export function seatColor(seat: number): string {
  return seat < 8 ? `var(--series-${seat + 1})` : "var(--text-muted)";
}

export function Token({ name, seat, size = 22 }: { name: string; seat: number; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="-12 -12 24 24" aria-hidden="true" className="token-swatch">
      <circle r={11} style={{ fill: seatColor(seat) }} />
      <text className="token-text" dy="0.35em">
        {initials(name)}
      </text>
    </svg>
  );
}

export function Board({
  layout,
  track,
  crosswalk,
  racers,
  state,
  actor,
}: {
  layout: BoardLayout;
  track: TrackInfo;
  crosswalk: number | null;
  racers: { name: string }[];
  state: ReplayState;
  actor: number | null;
}) {
  const placed = placeTokens(
    layout,
    racers.map((_, i) => ({ position: state.positions[i], status: state.status[i] })),
    state.finish_order,
  );

  return (
    <svg
      className="board"
      viewBox={`0 0 ${layout.width} ${layout.height}`}
      role="img"
      aria-label={`${track.name} board. The standings list gives every racer's position as text.`}
    >
      <Spaces layout={layout} track={track} crosswalk={crosswalk} />

      {state.bombs.map((position) => {
        const cell = layout.cell(position);
        return (
          <g key={`bomb-${position}`} className="bomb" transform={`translate(${cell.x + cell.w - 12},${cell.y + 13})`}>
            <title>Bomb on space {position}</title>
            <circle r={6} />
            <path d="M3 -5 q3 -4 6 -2" />
          </g>
        );
      })}

      {racers.map((racer, seat) => {
        const { x, y, scale } = placed[seat];
        const status = state.status[seat];
        return (
          <g
            key={seat}
            className={`token${status ? ` is-${status}` : ""}${actor === seat ? " is-actor" : ""}`}
            style={{ transform: `translate(${x}px, ${y}px) scale(${scale})` }}
          >
            <title>{racer.name}</title>
            {actor === seat && <circle className="actor-ring" r={TOKEN_R + 3.5} />}
            <circle className="token-body" r={TOKEN_R} style={{ fill: seatColor(seat) }} />
            <text className="token-text" dy="0.35em">
              {initials(racer.name)}
            </text>
            {status === "tripped" && <path className="trip-mark" d="M5 -13 l4 4 -4 4" />}
            {status === "eliminated" && <path className="out-mark" d="M-7 -7 L7 7 M7 -7 L-7 7" />}
          </g>
        );
      })}
    </svg>
  );
}

// The track itself never changes during a replay, so it renders once.
const Spaces = memo(function Spaces({
  layout,
  track,
  crosswalk,
}: {
  layout: BoardLayout;
  track: TrackInfo;
  crosswalk: number | null;
}) {
  const effects = new Map(track.spaces.map((s) => [s.position, s]));
  const cells = [];
  for (let p = 1; p <= layout.length; p++) {
    const box = layout.cell(p);
    const space = effects.get(p);
    const kind = space?.trip ? "trip" : space?.move ? (space.move > 0 ? "forward" : "back") : space?.points ? "points" : "";
    const label = space
      ? [space.trip && "Trip", space.move && `${space.move > 0 ? "+" : "−"}${Math.abs(space.move)}`, space.points && `+${space.points} pt`]
          .filter(Boolean)
          .join(" ")
      : "";
    cells.push(
      <g key={p} className={`space${kind ? ` space-${kind}` : ""}`}>
        <rect x={box.x} y={box.y} width={box.w} height={box.h} rx={8} />
        <text className="space-number" x={box.x + 6} y={box.y + 13}>
          {p}
        </text>
        {label && (
          <text className="space-label" x={box.x + box.w / 2} y={box.y + box.h - 6} textAnchor="middle">
            {label}
          </text>
        )}
        {p === crosswalk && (
          <g className="crosswalk">
            {[0, 1, 2, 3, 4].map((i) => (
              <rect key={i} x={box.x + 8 + i * 9} y={box.y + box.h - 22} width={5} height={10} rx={1} />
            ))}
            <title>Crosswalk</title>
          </g>
        )}
      </g>,
    );
  }

  return (
    <g>
      <polyline className="route" points={layout.route.map(([x, y]) => `${x},${y}`).join(" ")} />
      {(["start", "finish"] as const).map((zone) => {
        const box = layout[zone];
        return (
          <g key={zone} className="zone">
            <rect x={box.x} y={box.y} width={box.w} height={box.h} rx={8} />
            <text className="zone-label" x={box.x + box.w / 2} y={box.y + 13} textAnchor="middle">
              {zone === "start" ? "Start" : "Finish"}
            </text>
          </g>
        );
      })}
      {cells}
    </g>
  );
});
