import { useEffect, useState } from "react";

// Hash routes, so the built app works from any static path:
//   #/                         runs
//   #/run/<id>[/h2h|/seats]    one run
//   #/run/<id>/racer/<name>    one racer in a run
//   #/compare?a=<id>&b=<id>    two runs side by side

export type Route =
  | { page: "runs" }
  | { page: "run"; runId: string; tab: "leaderboard" | "h2h" | "seats" }
  | { page: "racer"; runId: string; racer: string }
  | { page: "compare"; a: string | null; b: string | null }
  | { page: "not-found" };

export function parseRoute(hash: string): Route {
  const [path, query = ""] = hash.replace(/^#/, "").split("?");
  const parts = path.split("/").filter(Boolean).map(safeDecode);
  const params = new URLSearchParams(query);

  if (parts.length === 0) return { page: "runs" };
  if (parts[0] === "compare" && parts.length === 1) {
    return { page: "compare", a: params.get("a"), b: params.get("b") };
  }
  if (parts[0] === "run" && parts.length >= 2) {
    const runId = parts[1];
    if (parts.length === 2) return { page: "run", runId, tab: "leaderboard" };
    if (parts.length === 3 && (parts[2] === "h2h" || parts[2] === "seats")) {
      return { page: "run", runId, tab: parts[2] };
    }
    if (parts.length === 4 && parts[2] === "racer") return { page: "racer", runId, racer: parts[3] };
  }
  return { page: "not-found" };
}

export const href = {
  runs: () => "#/",
  run: (runId: string, tab: "leaderboard" | "h2h" | "seats" = "leaderboard") =>
    `#/run/${encodeURIComponent(runId)}${tab === "leaderboard" ? "" : `/${tab}`}`,
  racer: (runId: string, racer: string) =>
    `#/run/${encodeURIComponent(runId)}/racer/${encodeURIComponent(racer)}`,
  compare: (a?: string | null, b?: string | null) => {
    const params = new URLSearchParams();
    if (a) params.set("a", a);
    if (b) params.set("b", b);
    const query = params.toString();
    return `#/compare${query ? `?${query}` : ""}`;
  },
};

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

function safeDecode(part: string): string {
  try {
    return decodeURIComponent(part);
  } catch {
    return part;
  }
}
