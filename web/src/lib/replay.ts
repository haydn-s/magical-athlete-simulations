import type { Replay, ReplayState } from "../types";

// A replay has frames.length + 1 steps: step 0 is the board before anything
// happens, and step k is the board right after log line k - 1.

export function stepCount(replay: Replay): number {
  return replay.frames.length + 1;
}

export function stateAt(replay: Replay, step: number): ReplayState {
  return step <= 0 ? replay.initial : replay.frames[Math.min(step, replay.frames.length) - 1];
}

const TURN_LINE = /^Turn \d+:/;

/** Steps where a racer's turn begins (the "Turn N: …'s turn." line). */
export function turnStarts(replay: Replay): number[] {
  const starts: number[] = [];
  replay.frames.forEach((frame, i) => {
    if (TURN_LINE.test(frame.text)) starts.push(i + 1);
  });
  return starts;
}

export function nextTurn(starts: number[], step: number, last: number): number {
  return starts.find((s) => s > step) ?? last;
}

export function previousTurn(starts: number[], step: number): number {
  let previous = 0;
  for (const s of starts) {
    if (s >= step) break;
    previous = s;
  }
  return previous;
}

/** "space 14", "tripped on 14", "finished 1st" … for the standings list. */
export function describeRacer(state: ReplayState, seat: number, length: number): string {
  const position = state.positions[seat];
  switch (state.status[seat]) {
    case "finished": {
      const place = state.finish_order.indexOf(seat) + 1;
      return place > 0 ? `finished ${ordinalPlace(place)}` : "finished";
    }
    case "eliminated":
      return `eliminated on ${position}`;
    case "tripped":
      return position <= 0 ? "tripped at the start" : `tripped on ${position}`;
    default:
      return position <= 0 ? "at the start" : position >= length ? "at the finish" : `space ${position}`;
  }
}

function ordinalPlace(n: number): string {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  return `${n}${{ 1: "st", 2: "nd", 3: "rd" }[n % 10] ?? "th"}`;
}
