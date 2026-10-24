import { useEffect, useState } from "react";
import { isActive, useJobs } from "./lib/jobs";
import { href, useRoute, type Route } from "./lib/router";
import { ComparePage } from "./pages/ComparePage";
import { JobsPage } from "./pages/JobsPage";
import { NewRunPage } from "./pages/NewRunPage";
import { RacerPage } from "./pages/RacerPage";
import { ReplayPage } from "./pages/ReplayPage";
import { RunPage } from "./pages/RunPage";
import { RunsPage } from "./pages/RunsPage";

export function App() {
  const route = useRoute();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [route.page, "runId" in route ? route.runId : null, "racer" in route ? route.racer : null, "game" in route ? route.game : null]);

  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          <a className="brand" href={href.runs()}>
            <BrandMark />
            <span className="brand-text">Magical Athlete Results</span>
          </a>
          <nav className="nav" aria-label="Main">
            <a href={href.runs()} aria-current={["runs", "run", "racer", "game"].includes(route.page) ? "page" : undefined}>
              Runs
            </a>
            <a href={href.compare()} aria-current={route.page === "compare" ? "page" : undefined}>
              Compare
            </a>
            <a href={href.newRun()} aria-current={route.page === "new" ? "page" : undefined}>
              New run
            </a>
            <JobsLink current={route.page === "jobs"} />
          </nav>
          <ThemeToggle />
        </div>
      </header>
      <main className="page">
        <Page route={route} />
      </main>
    </>
  );
}

function Page({ route }: { route: Route }) {
  switch (route.page) {
    case "runs":
      return <RunsPage />;
    case "run":
      return <RunPage key={route.runId} runId={route.runId} tab={route.tab} />;
    case "racer":
      return <RacerPage key={`${route.runId}/${route.racer}`} runId={route.runId} racer={route.racer} />;
    case "game":
      return <ReplayPage key={`${route.runId}/${route.game}`} runId={route.runId} game={route.game} />;
    case "compare":
      return <ComparePage a={route.a} b={route.b} />;
    case "new":
      return <NewRunPage from={route.from} />;
    case "jobs":
      return <JobsPage />;
    case "not-found":
      return (
        <div className="empty">
          <h2>Page not found</h2>
          <p>
            <a href={href.runs()}>See all runs</a>
          </p>
        </div>
      );
  }
}

function JobsLink({ current }: { current: boolean }) {
  const { jobs } = useJobs();
  const active = jobs?.filter(isActive).length ?? 0;
  return (
    <a href={href.jobs()} aria-current={current ? "page" : undefined}>
      Jobs
      {active > 0 && (
        <span className="nav-count" aria-label={`${active} running or queued`}>
          {active}
        </span>
      )}
    </a>
  );
}

function BrandMark() {
  // A finish-line flag.
  return (
    <svg className="brand-mark" viewBox="0 0 20 20" aria-hidden="true">
      <rect x="3" y="2" width="1.8" height="16" rx="0.9" fill="var(--text-secondary)" />
      <rect x="5" y="3" width="12" height="9" rx="1.5" fill="var(--surface-2)" stroke="var(--text-secondary)" strokeWidth="1" />
      <rect x="5" y="3" width="3" height="3" fill="var(--text-primary)" />
      <rect x="11" y="3" width="3" height="3" fill="var(--text-primary)" />
      <rect x="8" y="6" width="3" height="3" fill="var(--text-primary)" />
      <rect x="14" y="6" width="3" height="3" fill="var(--text-primary)" />
      <rect x="5" y="9" width="3" height="3" fill="var(--text-primary)" />
      <rect x="11" y="9" width="3" height="3" fill="var(--text-primary)" />
    </svg>
  );
}

type Theme = "system" | "light" | "dark";
const THEMES: Theme[] = ["system", "light", "dark"];
const THEME_KEY = "ma-results-theme";

function readTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    return THEMES.includes(saved as Theme) ? (saved as Theme) : "system";
  } catch {
    return "system";
  }
}

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(readTheme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // Storage can be unavailable (private windows); the theme still applies for this visit.
    }
  }, [theme]);

  const next = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
  return (
    <button
      type="button"
      className="button small"
      onClick={() => setTheme(next)}
      aria-label={`Theme: ${theme}. Switch to ${next}.`}
      title={`Theme: ${theme}`}
    >
      {theme === "system" ? "Auto" : theme === "light" ? "Light" : "Dark"}
      <span className="hide-sm"> theme</span>
    </button>
  );
}
