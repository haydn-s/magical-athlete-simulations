import { useEffect, useState } from "react";
import type { Job } from "../types";
import { fetchJobs } from "./api";

// One shared poller for /api/jobs: every component that shows jobs subscribes,
// and polling stops when none are mounted. Fast while a job is active.

const ACTIVE_MS = 1000;
const IDLE_MS = 5000;

interface JobsState {
  jobs: Job[] | null;
  error: string | null;
}

let state: JobsState = { jobs: null, error: null };
const listeners = new Set<(s: JobsState) => void>();
let timer: ReturnType<typeof setTimeout> | undefined;
let generation = 0;

export function isActive(job: Job): boolean {
  return job.state === "queued" || job.state === "running";
}

async function poll() {
  const current = ++generation;
  clearTimeout(timer);
  timer = undefined;
  try {
    state = { jobs: await fetchJobs(), error: null };
  } catch (err) {
    state = { jobs: state.jobs, error: err instanceof Error ? err.message : String(err) };
  }
  if (current !== generation) return; // a newer poll superseded this one
  listeners.forEach((listener) => listener(state));
  if (listeners.size) {
    timer = setTimeout(poll, state.jobs?.some(isActive) ? ACTIVE_MS : IDLE_MS);
  }
}

/** Fetch now (after starting or cancelling a job) instead of waiting for the next tick. */
export function refreshJobs(): void {
  void poll();
}

export function useJobs(): JobsState {
  const [current, setCurrent] = useState(state);
  useEffect(() => {
    listeners.add(setCurrent);
    if (listeners.size === 1) refreshJobs();
    else setCurrent(state);
    return () => {
      listeners.delete(setCurrent);
      if (!listeners.size) {
        clearTimeout(timer);
        timer = undefined;
      }
    };
  }, []);
  return current;
}
