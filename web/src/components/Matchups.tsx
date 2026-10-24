import { href } from "../lib/router";
import { int, pct } from "../lib/stats";
import type { HeadToHead } from "../types";
import { MIN_RACES, divergingExtent } from "./Heatmap";

export interface Matchup {
  opponent: string;
  rate: number;
  races: number;
}

export function matchupsFor(data: HeadToHead, racer: string): Matchup[] {
  const row = data.names.indexOf(racer);
  if (row < 0) return [];
  return data.names
    .map((opponent, col) => ({ opponent, rate: data.ahead_rate[row][col], races: data.together[row][col] }))
    .filter((m): m is Matchup => m.opponent !== racer && m.rate !== null && m.races > 0)
    .sort((a, b) => b.rate - a.rate);
}

/** One row per opponent: a bar out from 50% toward "ahead" (blue) or "behind" (red). */
export function Matchups({ runId, racer, matchups }: { runId: string; racer: string; matchups: Matchup[] }) {
  const extent = divergingExtent([matchups.map((m) => m.rate)]);

  return (
    <div className="matchups" role="table" aria-label={`How often ${racer} placed ahead of each opponent`}>
      <div className="head" role="columnheader">
        Opponent
      </div>
      <div className="head" role="columnheader">
        <span className="matchup-axis">
          <span>
            {extent < 0.5 && "≤ "}
            {pct(0.5 - extent)}
          </span>
          <span>50%</span>
          <span>
            {extent < 0.5 && "≥ "}
            {pct(0.5 + extent)}
          </span>
        </span>
      </div>
      <div className="head num" role="columnheader">
        Ahead
      </div>
      <div className="head num races" role="columnheader">
        Races
      </div>
      {matchups.map((m) => {
        const low = m.races < MIN_RACES ? " low" : "";
        const share = (Math.min(Math.abs(m.rate - 0.5), extent) / extent) * 50;
        const ahead = m.rate >= 0.5;
        return (
          <div key={m.opponent} role="row" style={{ display: "contents" }}>
            <div className={`cell${low}`} role="cell">
              <a href={href.racer(runId, m.opponent)}>{m.opponent}</a>
            </div>
            <div className={`cell${low}`} role="cell" aria-hidden="true">
              <div className="mbar-track">
                <div
                  className={`mbar ${ahead ? "pos" : "neg"}`}
                  style={ahead ? { left: "50%", width: `${share}%` } : { right: "50%", width: `${share}%` }}
                />
              </div>
            </div>
            <div className={`cell num${low}`} role="cell">
              {pct(m.rate)}
            </div>
            <div className={`cell num races muted${low}`} role="cell">
              {int(m.races)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
