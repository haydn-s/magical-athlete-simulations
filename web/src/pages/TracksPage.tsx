import { useMemo } from "react";
import { Board } from "../components/Board";
import { Card, CopyButton, LoadError, Loading, Notice } from "../components/ui";
import { fetchRoster, useLoad } from "../lib/api";
import { boardLayout } from "../lib/board";
import { href } from "../lib/router";
import type { ReplayState, TrackInfo } from "../types";

const EMPTY_BOARD: ReplayState = { positions: [], status: [], points: [], finish_order: [], bombs: [] };

const TEMPLATE = `{
  "name": "My Track",
  "length": 30,
  "spaces": {
    "4": { "points": 1 },
    "9": { "trip": true },
    "12": { "move": 3 },
    "21": { "move": -2 }
  }
}`;

export function TracksPage() {
  // Read fresh on every visit, so edits to track files show up on reload.
  const roster = useLoad(fetchRoster, []);
  if (roster.status === "error") return <LoadError message={roster.error} />;
  if (roster.status !== "ready") return <Loading what="tracks" />;
  const { tracks, track_errors: broken } = roster.data;

  return (
    <>
      <div className="page-head">
        <h1>Tracks</h1>
        <p className="subtitle">
          Every <code>tracks/*.json</code> file. Edit a file and reload this page to see the change.
        </p>
      </div>

      {broken.length > 0 && (
        <Notice tone="critical">
          <strong>
            {broken.length === 1 ? "One track file can’t be raced" : `${broken.length} track files can’t be raced`}:
          </strong>
          <ul className="error-list">
            {broken.map((b) => (
              <li key={b.key}>
                <code>{b.error}</code>
              </li>
            ))}
          </ul>
        </Notice>
      )}

      {tracks.map((track) => (
        <TrackCard key={track.key} trackKey={track.key} track={track} />
      ))}

      <Card
        title="Design a track"
        note="Save a file like this in the tracks folder (its file name becomes the track’s key), then reload. Spaces run from 1 to length − 1; arrows can’t point off the track."
        actions={<CopyButton text={TEMPLATE} label="Copy template" />}
      >
        <pre className="template">
          <code>{TEMPLATE}</code>
        </pre>
      </Card>
    </>
  );
}

function TrackCard({ trackKey, track }: { trackKey: string; track: TrackInfo }) {
  const layout = useMemo(() => boardLayout(track.length), [track.length]);
  const counts = {
    trip: track.spaces.filter((s) => s.trip).length,
    forward: track.spaces.filter((s) => s.move > 0).length,
    back: track.spaces.filter((s) => s.move < 0).length,
    points: track.spaces.filter((s) => s.points).length,
  };

  return (
    <Card
      title={track.name}
      note={
        <>
          <code>{trackKey}</code> · {track.length} spaces · {counts.trip} trip, {counts.forward} forward arrows,{" "}
          {counts.back} back arrows, {counts.points} point spaces
        </>
      }
      actions={
        <a className="button small" href={href.newRun(null, trackKey)}>
          Race on this track
        </a>
      }
    >
      <Board layout={layout} track={track} crosswalk={null} racers={[]} state={EMPTY_BOARD} actor={null} />
    </Card>
  );
}
