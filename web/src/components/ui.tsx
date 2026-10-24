import { useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";

export function Card({
  title,
  note,
  actions,
  flush,
  children,
}: {
  title?: ReactNode;
  note?: ReactNode;
  actions?: ReactNode;
  flush?: boolean;
  children: ReactNode;
}) {
  return (
    <section className={`card${flush ? " flush" : ""}`}>
      {(title || actions) && (
        <div className="card-head">
          <div className="grow">
            {title && <h2>{title}</h2>}
            {note && <p className="card-note">{note}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatTile({ label, value, detail }: { label: string; value: ReactNode; detail?: ReactNode }) {
  return (
    <div className="tile">
      <span className="tile-label">{label}</span>
      <span className="tile-value">{value}</span>
      {detail && <span className="tile-detail">{detail}</span>}
    </div>
  );
}

export function Badge({ children }: { children: ReactNode }) {
  return <span className="badge">{children}</span>;
}

export function Notice({ tone, children }: { tone: "warning" | "critical" | "info"; children: ReactNode }) {
  return (
    <div className="notice" role={tone === "info" ? undefined : "status"}>
      <NoticeIcon tone={tone} />
      <div>{children}</div>
    </div>
  );
}

function NoticeIcon({ tone }: { tone: "warning" | "critical" | "info" }) {
  if (tone === "info") {
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
        <circle cx="8" cy="8" r="7" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" />
        <path d="M8 7v4M8 4.6v.1" stroke="var(--text-muted)" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    );
  }
  const color = tone === "warning" ? "var(--status-warning)" : "var(--status-critical)";
  const ink = tone === "warning" ? "#0b0b0b" : "#ffffff";
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-label={tone === "warning" ? "Warning" : "Problem"}>
      <path d="M8 1.5 15 14H1L8 1.5Z" fill={color} />
      <path d="M8 6v4M8 11.8v.1" stroke={ink} strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function Loading({ what = "results" }: { what?: string }) {
  return <div className="loading">Loading {what}…</div>;
}

export function LoadError({ message }: { message: string }) {
  return (
    <div className="empty">
      <h2>Couldn’t load this</h2>
      <p>{message}. Is <code>python -m sim serve</code> running?</p>
    </div>
  );
}

// --- sorting -----------------------------------------------------------------

export type SortDir = "asc" | "desc";
export interface SortState<K extends string> {
  key: K;
  dir: SortDir;
}

export function useSort<K extends string>(key: K, dir: SortDir = "desc") {
  const [sort, setSort] = useState<SortState<K>>({ key, dir });
  const toggle = (next: K, defaultDir: SortDir = "desc") =>
    setSort((s) => (s.key === next ? { key: next, dir: s.dir === "asc" ? "desc" : "asc" } : { key: next, dir: defaultDir }));
  return [sort, toggle] as const;
}

export function sortRows<T>(rows: T[], value: (row: T) => number | string, dir: SortDir): T[] {
  const sign = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const va = value(a);
    const vb = value(b);
    if (typeof va === "string" || typeof vb === "string") {
      return sign * String(va).localeCompare(String(vb), undefined, { sensitivity: "base" });
    }
    return sign * (va - vb);
  });
}

export function SortHeader<K extends string>({
  label,
  sortKey,
  sort,
  onSort,
  defaultDir = "desc",
  numeric,
  sub,
}: {
  label: ReactNode;
  sortKey: K;
  sort: SortState<K>;
  onSort: (key: K, defaultDir: SortDir) => void;
  defaultDir?: SortDir;
  numeric?: boolean;
  sub?: ReactNode;
}) {
  const active = sort.key === sortKey;
  return (
    <th
      className={numeric ? "num" : undefined}
      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
    >
      <button type="button" className="sort-button" data-active={active} onClick={() => onSort(sortKey, defaultDir)}>
        {label}
        <span className="sort-arrow" aria-hidden="true">
          {active ? (sort.dir === "asc" ? "▲" : "▼") : ""}
        </span>
      </button>
      {sub && <span className="th-sub">{sub}</span>}
    </th>
  );
}

// --- layout helpers ----------------------------------------------------------

export function useElementWidth<T extends HTMLElement>(): [RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(el.clientWidth);
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

export interface TooltipState {
  x: number;
  y: number;
  content: ReactNode;
}

/** Follows the pointer (client coordinates) and flips to stay inside the viewport. */
export function Tooltip({ state }: { state: TooltipState | null }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: -9999, top: -9999 });

  useLayoutEffect(() => {
    if (!state || !ref.current) return;
    const { width, height } = ref.current.getBoundingClientRect();
    let left = state.x + 14;
    let top = state.y + 14;
    if (left + width > window.innerWidth - 8) left = state.x - width - 14;
    if (top + height > window.innerHeight - 8) top = state.y - height - 14;
    setPos({ left: Math.max(8, left), top: Math.max(8, top) });
  }, [state]);

  if (!state) return null;
  return createPortal(
    <div className="tooltip" ref={ref} style={pos} role="tooltip">
      {state.content}
    </div>,
    document.body,
  );
}

/** Tooltip anchor for keyboard focus: the top-right corner of the focused element. */
export function anchorOf(el: Element): { x: number; y: number } {
  const rect = el.getBoundingClientRect();
  return { x: rect.right - 6, y: rect.top };
}
