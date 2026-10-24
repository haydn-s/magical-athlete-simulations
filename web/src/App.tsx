import { useEffect, useState } from "react";
import { href, useRoute, type Route } from "./lib/router";
import { ComparePage } from "./pages/ComparePage";
import { RacerPage } from "./pages/RacerPage";
import { RunPage } from "./pages/RunPage";
import { RunsPage } from "./pages/RunsPage";

export function App() {
  const route = useRoute();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [route.page, "runId" in route ? route.runId : null, "racer" in route ? route.racer : null]);

  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          <a className="brand" href={href.runs()}>
            <BrandMark />
            <span className="brand-text">Magical Athlete Results</span>
          </a>
          <nav className="nav" aria-label="Main">
            <a href={href.runs()} aria-current={route.page === "runs" || route.page === "run" || route.page === "racer" ? "page" : undefined}>
              Runs
            </a>
            <a href={href.compare()} aria-current={route.page === "compare" ? "page" : undefined}>
              Compare
            </a>
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
    case "compare":
      return <ComparePage a={route.a} b={route.b} />;
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
      {theme === "system" ? "Auto" : theme === "light" ? "Light" : "Dark"} theme
    </button>
  );
}
