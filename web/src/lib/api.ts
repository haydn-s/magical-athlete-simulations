import { useEffect, useState } from "react";
import type { Job, JobRequest, RosterInfo, RunListItem, Summary } from "../types";

// Served by `python -m sim serve` (proxied by `npm run dev`).

const summaries = new Map<string, Promise<Summary>>();

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { cache: "no-store", ...init });
  if (!response.ok) {
    // The server explains rejected job requests as {"error": "..."}.
    const body = await response.json().catch(() => null);
    if (body && typeof body.error === "string") throw new Error(body.error);
    throw new Error(response.status === 404 ? "Not found" : `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

function postJson<T>(url: string, body: unknown): Promise<T> {
  return getJson<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function fetchRoster(): Promise<RosterInfo> {
  return getJson<RosterInfo>("api/roster");
}

export function fetchJobs(): Promise<Job[]> {
  return getJson<Job[]>("api/jobs");
}

export function startJob(request: JobRequest): Promise<Job> {
  return postJson<Job>("api/jobs", request);
}

export function cancelJob(id: string): Promise<Job> {
  return postJson<Job>(`api/jobs/${encodeURIComponent(id)}/cancel`, {});
}

export function fetchRuns(): Promise<RunListItem[]> {
  return getJson<RunListItem[]>("api/runs");
}

/** Saved runs never change, so each summary is fetched once per page load. */
export function fetchRun(runId: string): Promise<Summary> {
  let request = summaries.get(runId);
  if (!request) {
    request = getJson<Summary>(`api/runs/${encodeURIComponent(runId)}`);
    request.catch(() => summaries.delete(runId));
    summaries.set(runId, request);
  }
  return request;
}

export function downloadUrl(runId: string, file: string): string {
  return `api/runs/${encodeURIComponent(runId)}/files/${encodeURIComponent(file)}`;
}

export type Loadable<T> =
  | { status: "idle" | "loading"; data?: undefined; error?: undefined }
  | { status: "ready"; data: T; error?: undefined }
  | { status: "error"; data?: undefined; error: string };

/** Runs `load` whenever `deps` change; a null `load` means there is nothing to fetch. */
export function useLoad<T>(load: (() => Promise<T>) | null, deps: unknown[]): Loadable<T> {
  const [state, setState] = useState<Loadable<T>>({ status: load ? "loading" : "idle" });

  useEffect(() => {
    if (!load) {
      setState({ status: "idle" });
      return;
    }
    let cancelled = false;
    setState({ status: "loading" });
    load().then(
      (data) => !cancelled && setState({ status: "ready", data }),
      (err: unknown) =>
        !cancelled && setState({ status: "error", error: err instanceof Error ? err.message : String(err) }),
    );
    return () => {
      cancelled = true;
    };
  }, deps);

  return state;
}

export function useRuns() {
  return useLoad(fetchRuns, []);
}

export function useRun(runId: string | null) {
  return useLoad(runId ? () => fetchRun(runId) : null, [runId]);
}
