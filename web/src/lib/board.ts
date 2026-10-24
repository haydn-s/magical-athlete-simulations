// Geometry for the replay board, in SVG viewBox units. The track snakes back and
// forth in rows of PER_ROW spaces, with Start before space 1 and Finish after the
// last space, so any track length lays out the same way.

export const PER_ROW = 10;
export const CELL = 60;
export const GAP = 8;
export const SIDE = 84;
export const PAD = 12;
export const TOKEN_R = 10;

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface BoardLayout {
  length: number;
  rows: number;
  width: number;
  height: number;
  start: Box;
  finish: Box;
  cell: (position: number) => Box;
  /** Centers from Start through every space to Finish, for drawing the route. */
  route: [number, number][];
}

const center = (b: Box): [number, number] => [b.x + b.w / 2, b.y + b.h / 2];

export function boardLayout(length: number): BoardLayout {
  const rows = Math.max(1, Math.ceil(length / PER_ROW));
  const left = PAD + SIDE + GAP;
  const colX = (c: number) => left + c * (CELL + GAP);
  const rowY = (r: number) => PAD + r * (CELL + GAP);
  const slot = (index: number): Box => {
    const r = Math.floor(index / PER_ROW);
    const i = index % PER_ROW;
    const c = r % 2 === 0 ? i : PER_ROW - 1 - i;
    return { x: colX(c), y: rowY(r), w: CELL, h: CELL };
  };

  const cell = (position: number) => slot(position - 1);
  const start: Box = { x: PAD, y: rowY(0), w: SIDE, h: CELL };

  // Finish takes the next slot along the route, or the side zone when the last row is full.
  const lastRow = rows - 1;
  let finish: Box;
  if (length % PER_ROW !== 0) {
    finish = slot(length);
  } else if (lastRow % 2 === 0) {
    finish = { x: colX(PER_ROW - 1) + CELL + GAP, y: rowY(lastRow), w: SIDE, h: CELL };
  } else {
    finish = { x: PAD, y: rowY(lastRow), w: SIDE, h: CELL };
  }

  const route: [number, number][] = [center(start)];
  for (let p = 1; p <= length; p++) route.push(center(cell(p)));
  route.push(center(finish));

  return {
    length,
    rows,
    width: PAD * 2 + SIDE * 2 + GAP * 2 + PER_ROW * CELL + (PER_ROW - 1) * GAP,
    height: PAD * 2 + rows * CELL + (rows - 1) * GAP,
    start,
    finish,
    cell,
    route,
  };
}

export interface Cluster {
  points: [number, number][];
  /** Token scale (at most 1) so tokens sharing the box don't overlap. */
  scale: number;
}

/**
 * Where `count` tokens sit inside a box: the grid shape that leaves the most room
 * for this box's proportions, shrinking tokens only when they wouldn't fit.
 */
export function cluster(count: number, box: Box): Cluster {
  if (count === 0) return { points: [], scale: 1 };
  const width = box.w - 6;
  const height = box.h - 16; // leave the top strip for the space number
  let best = { cols: 1, rows: count, step: 0 };
  for (let cols = 1; cols <= count; cols++) {
    const rows = Math.ceil(count / cols);
    const step = Math.min(TOKEN_R * 2 + 4, width / cols, height / rows);
    if (step > best.step) best = { cols, rows, step };
  }
  const { cols, rows, step } = best;
  const cx = box.x + box.w / 2;
  const cy = box.y + 16 + height / 2;
  const points = Array.from({ length: count }, (_, i): [number, number] => {
    const r = Math.floor(i / cols);
    const inRow = r === rows - 1 ? count - r * cols : cols;
    const c = i % cols;
    return [cx + (c - (inRow - 1) / 2) * step, cy + (r - (rows - 1) / 2) * step];
  });
  return { points, scale: Math.min(1, (step - 1) / (TOKEN_R * 2)) };
}

export interface TokenState {
  position: number;
  status: string;
}

/**
 * Board coordinates for every racer (by seat index). Racers sharing a spot are
 * spread out in seat order; finishers line up in finishing order.
 */
export interface PlacedToken {
  x: number;
  y: number;
  scale: number;
}

export function placeTokens(layout: BoardLayout, racers: TokenState[], finishOrder: number[]): PlacedToken[] {
  const groups = new Map<string, number[]>();
  const add = (key: string, seat: number) => groups.set(key, [...(groups.get(key) ?? []), seat]);

  const finishers = [...finishOrder, ...racers.map((_, i) => i).filter((i) => racers[i].status === "finished" && !finishOrder.includes(i))];
  finishers.forEach((seat) => add("finish", seat));
  racers.forEach((r, seat) => {
    if (r.status === "finished") return;
    if (r.position <= 0) add("start", seat);
    else if (r.position > layout.length) add("finish", seat);
    else add(String(r.position), seat);
  });

  const placed: PlacedToken[] = racers.map(() => ({ x: 0, y: 0, scale: 1 }));
  for (const [key, seats] of groups) {
    const box = key === "start" ? layout.start : key === "finish" ? layout.finish : layout.cell(Number(key));
    const { points, scale } = cluster(seats.length, box);
    points.forEach(([x, y], i) => (placed[seats[i]] = { x, y, scale }));
  }
  return placed;
}

/** Two letters for a token: the first two capitals (BabaYaga → BY), else the first two letters. */
export function initials(name: string): string {
  const caps = name.match(/[A-Z]/g) ?? [];
  return caps.length >= 2 ? caps[0] + caps[1] : name.replace(/[^A-Za-z]/g, "").slice(0, 2);
}
