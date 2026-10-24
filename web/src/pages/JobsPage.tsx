import { useState } from "react";
import { Badge, CopyButton, LoadError, Loading, Notice } from "../components/ui";
import { cancelJob, clearFinishedJobs } from "../lib/api";
import { isActive, refreshJobs, useJobs } from "../lib/jobs";
import { href } from "../lib/router";
import { compact, int } from "../lib/stats";
import type { Job } from "../types";

const STATE_LABEL: Record<Job["state"], string> = {
  queued: "Queued",
  running: "Running",
  done: "Done",
  failed: "Failed",
  cancelled: "Cancelled",
  interrupted: "Interrupted",
};

export function JobsPage() {
  const { jobs, error } = useJobs();
  const [clearing, setClearing] = useState(false);

  if (!jobs && error) return <LoadError message={error} />;
  if (!jobs) return <Loading what="jobs" />;
  const finished = jobs.filter((job) => !isActive(job)).length;

  const clear = async () => {
    setClearing(true);
    try {
      await clearFinishedJobs();
      refreshJobs();
    } finally {
      setClearing(false);
    }
  };

  return (
    <>
      <div className="page-head">
        <div className="title-row">
          <h1>Started here</h1>
        </div>
        <p className="subtitle">
          Runs you start from the viewer. They run one at a time on this machine, using every core, and save to{" "}
          <code>results/</code> like any other run. This list is kept in <code>results/.jobs.json</code>, so it
          survives restarting the server.
        </p>
        <div className="head-actions">
          <a className="button primary small" href={href.newRun()}>
            New run
          </a>
          {finished > 0 && (
            <button type="button" className="button small" onClick={clear} disabled={clearing}>
              Clear finished ({finished})
            </button>
          )}
        </div>
      </div>

      {error && <Notice tone="warning">Lost contact with the server ({error}). Retrying…</Notice>}

      {jobs.length === 0 ? (
        <div className="empty">
          <h2>Nothing started yet</h2>
          <p>
            <a href={href.newRun()}>Start a run</a>, or open a saved run and choose “New run from this”.
          </p>
        </div>
      ) : (
        <div className="job-list">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </div>
      )}
    </>
  );
}

function JobCard({ job }: { job: Job }) {
  const [cancelError, setCancelError] = useState<string | null>(null);
  const { settings } = job;
  const title = job.label ?? `${compact(job.total)} games · seed ${settings.seed}`;
  const share = job.total ? job.done / job.total : 0;

  const cancel = async () => {
    try {
      await cancelJob(job.id);
      refreshJobs();
    } catch (err) {
      setCancelError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <section className="card job" aria-label={title}>
      <div className="card-head">
        <div className="grow">
          <div className="title-row">
            <h2>{title}</h2>
            <span className={`state state-${job.state}`}>
              <span className="state-dot" aria-hidden="true" />
              {STATE_LABEL[job.state]}
            </span>
          </div>
          <div className="meta">
            <span>{settings.track === "mild" ? "Mild Mile" : settings.track === "wild" ? "Wild Wilds" : settings.track}</span>
            <span>{int(job.total)} games</span>
            <span>{settings.players} racers per game</span>
            <span>seed {settings.seed}</span>
            {settings.focus.length > 0 && <span>focus: {settings.focus.join(", ")}</span>}
            <span>started {new Date(job.created * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>
          </div>
        </div>
        <div className="head-actions">
          {isActive(job) && (
            <button type="button" className="button small" onClick={cancel}>
              Cancel
            </button>
          )}
          {job.state === "done" && job.run_id && (
            <>
              <a className="button primary small" href={href.run(job.run_id)}>
                View results
              </a>
              {settings.from_run && (
                <a className="button small" href={href.compare(settings.from_run, job.run_id)}>
                  Compare with the original
                </a>
              )}
              <a className="button small" href={href.newRun(job.run_id)}>
                New run from this
              </a>
            </>
          )}
        </div>
      </div>

      {job.state !== "failed" && job.state !== "cancelled" && job.state !== "interrupted" && (
        <div className="progress">
          <div
            className="meter"
            role="progressbar"
            aria-label="Games simulated"
            aria-valuemin={0}
            aria-valuemax={job.total}
            aria-valuenow={job.done}
          >
            <div className="meter-fill" style={{ width: `${Math.min(100, share * 100)}%` }} />
          </div>
          <div className="progress-text">
            <strong>{int(job.done)}</strong> of {int(job.total)} games
            {job.state === "running" && job.rate > 0 && <> · {int(Math.round(job.rate))} games/s</>}
            {job.state === "running" && job.remaining_sec !== null && <> · about {duration(job.remaining_sec)} left</>}
            {job.state === "done" && <> · took {duration(job.elapsed_sec)}</>}
            {job.state === "queued" && <> · waiting for the current run to finish</>}
          </div>
        </div>
      )}

      {job.state === "cancelled" && (
        <p className="card-note">
          Stopped after {int(job.done)} of {int(job.total)} games. Nothing was saved.
        </p>
      )}
      {job.state === "interrupted" && (
        <Notice tone="warning">
          <strong>Interrupted</strong> after about {int(job.done)} of {int(job.total)} games. {job.error}
        </Notice>
      )}
      {job.state === "failed" && (
        <Notice tone="critical">
          <strong>The run failed:</strong> <code>{job.error}</code>
        </Notice>
      )}
      {cancelError && <Notice tone="warning">Couldn’t cancel: {cancelError}</Notice>}

      <div className="command-preview">
        <code>{job.command}</code>
        <CopyButton text={job.command} />
        {job.replaced.length > 0 && <Badge>variant replaces {job.replaced.join(", ")}</Badge>}
      </div>
    </section>
  );
}

/** 8s, 4m 12s, 1h 3m */
export function duration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}
