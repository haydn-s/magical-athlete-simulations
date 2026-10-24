import { useEffect, useState } from "react";
import type { RunListItem, Summary } from "../types";

// Served by `python -m sim serve` (proxied by `npm run dev`).

const summaries = new Map<string, Promise<Summary>>();

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(response.status === 404 ? "Not found" : `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
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
