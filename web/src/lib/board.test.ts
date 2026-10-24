import { describe, expect, it } from "vitest";
import type { Replay, ReplayFrame, ReplayState } from "../types";
import { CELL, GAP, PER_ROW, SIDE, TOKEN_R, boardLayout, cluster, initials, placeTokens } from "./board";
import { describeRacer, nextTurn, previousTurn, stateAt, stepCount, turnStarts } from "./replay";

describe("boardLayout", () => {
  const layout = boardLayout(30);

  it("snakes back and forth in rows of ten", () => {
    expect(layout.rows).toBe(3);
    expect(layout.cell(1).y).toBe(layout.cell(10).y);
    expect(layout.cell(2).x).toBeGreaterThan(layout.cell(1).x); // row 1 runs left to right
    expect(layout.cell(11).x).toBe(layout.cell(10).x); // turns the corner
    expect(layout.cell(12).x).toBeLessThan(layout.cell(11).x); // row 2 runs right to left
    expect(layout.cell(21).x).toBe(layout.cell(20).x);
    expect(layout.cell(11).y - layout.cell(1).y).toBe(CELL + GAP);
  });

  it("puts Start before space 1 and Finish after the last space", () => {
    expect(layout.start.x + layout.start.w).toBeLessThan(layout.cell(1).x);
    expect(layout.start.y).toBe(layout.cell(1).y);
    expect(layout.finish.x).toBeGreaterThan(layout.cell(30).x); // last row runs left to right
    expect(layout.finish.y).toBe(layout.cell(30).y);
    expect(layout.route).toHaveLength(32);
  });

  it("handles track lengths that end mid-row or on a right-to-left row", () => {
    const partial = boardLayout(35); // row 4 runs right to left and stops after 5 spaces
    expect(partial.rows).toBe(4);
    expect(partial.finish.y).toBe(partial.cell(35).y);
    expect(partial.finish.x).toBe(partial.cell(35).x - CELL - GAP);

    const even = boardLayout(PER_ROW * 2); // ends at the left edge
    expect(even.finish.x).toBeLessThan(even.cell(20).x);
    expect(even.finish.y).toBe(even.cell(20).y);
  });
});

describe("tokens", () => {
  it("never lets tokens sharing a box overlap or spill out", () => {
    const boxes = [
      { x: 0, y: 0, w: CELL, h: CELL },
      { x: 0, y: 0, w: SIDE, h: CELL },
    ];
    for (const box of boxes) {
      for (let count = 1; count <= 12; count++) {
        const { points, scale } = cluster(count, box);
        const r = TOKEN_R * scale;
        expect(points).toHaveLength(count);
        for (let i = 0; i < points.length; i++) {
          const [x, y] = points[i];
          expect(x - r).toBeGreaterThanOrEqual(box.x);
          expect(x + r).toBeLessThanOrEqual(box.x + box.w);
          expect(y + r).toBeLessThanOrEqual(box.y + box.h);
          for (let j = i + 1; j < points.length; j++) {
            expect(Math.hypot(x - points[j][0], y - points[j][1])).toBeGreaterThanOrEqual(2 * r);
          }
        }
      }
    }
    expect(cluster(2, { x: 0, y: 0, w: CELL, h: CELL }).scale).toBe(1); // only crowded spaces shrink
  });

  it("places racers by position and finishers in finishing order", () => {
    const layout = boardLayout(30);
    const racers = [
      { position: 0, status: "" },
      { position: 30, status: "finished" },
      { position: 14, status: "tripped" },
      { position: 31, status: "finished" },
    ];
    const placed = placeTokens(layout, racers, [3, 1]);
    const inBox = ({ x, y }: { x: number; y: number }, b: { x: number; y: number; w: number; h: number }) =>
      x > b.x && x < b.x + b.w && y > b.y && y < b.y + b.h;
    expect(inBox(placed[0], layout.start)).toBe(true);
    expect(inBox(placed[2], layout.cell(14))).toBe(true);
    expect(inBox(placed[1], layout.finish)).toBe(true);
    expect(placed[3].x).toBeLessThan(placed[1].x); // the winner comes first
  });

  it("makes two-letter initials", () => {
    expect(["BabaYaga", "M.O.U.T.H.", "Oddball", "HighFive"].map(initials)).toEqual(["BY", "MO", "Od", "HF"]);
  });
});

function state(overrides: Partial<ReplayState> = {}): ReplayState {
  return { positions: [0, 0], status: ["", ""], points: [0, 0], finish_order: [], bombs: [], ...overrides };
}

function frame(text: string, overrides: Partial<ReplayFrame> = {}): ReplayFrame {
  return { ...state(), text, turn: 1, actor: 0, ...overrides };
}

describe("replay steps", () => {
  const replay = {
    initial: state(),
    frames: [
      frame("MadBomber places bombs on spaces [8, 20, 29].", { actor: null }),
      frame("Turn 1: A's turn."),
      frame("A rolls 3."),
      frame("Turn 2: B's turn.", { actor: 1 }),
      frame("B rolls 6.", { actor: 1 }),
    ],
  } as unknown as Replay;

  it("counts the starting board as step 0", () => {
    expect(stepCount(replay)).toBe(6);
    expect(stateAt(replay, 0)).toBe(replay.initial);
    expect(stateAt(replay, 1)).toBe(replay.frames[0]);
    expect(stateAt(replay, 99)).toBe(replay.frames[4]);
  });

  it("jumps between turns", () => {
    const starts = turnStarts(replay);
    expect(starts).toEqual([2, 4]);
    expect(nextTurn(starts, 0, 5)).toBe(2);
    expect(nextTurn(starts, 2, 5)).toBe(4);
    expect(nextTurn(starts, 4, 5)).toBe(5);
    expect(previousTurn(starts, 5)).toBe(4);
    expect(previousTurn(starts, 4)).toBe(2);
    expect(previousTurn(starts, 2)).toBe(0);
  });

  it("describes where each racer is", () => {
    const s = state({ positions: [14, 31], status: ["tripped", "finished"], finish_order: [1] });
    expect(describeRacer(s, 0, 30)).toBe("tripped on 14");
    expect(describeRacer(s, 1, 30)).toBe("finished 1st");
    expect(describeRacer(state(), 0, 30)).toBe("at the start");
  });
});
