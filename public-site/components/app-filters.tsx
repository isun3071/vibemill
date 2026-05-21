"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useEffect, useState } from "react";

/** Archetypes the matcher routes to. Keep in sync with vibemill/matcher.py.
 *  Sorted by deploy rail then alphabetically so the dropdown groups feel
 *  intuitive when scanning. */
const ARCHETYPES: { value: string; label: string }[] = [
  { value: "tracker", label: "tracker" },
  { value: "chatbot", label: "chatbot" },
  { value: "utility_tool", label: "utility tool" },
  { value: "search_directory", label: "search directory" },
  { value: "ai_generator", label: "ai generator" },
  { value: "ai_agent", label: "ai agent" },
  { value: "glorified_todo", label: "glorified todo" },
  { value: "parody_ui", label: "parody ui" },
  { value: "marketplace", label: "marketplace" },
  { value: "map_visualizer", label: "map visualizer" },
  { value: "recommendation_engine", label: "recommendation engine" },
  { value: "game", label: "game" },
  { value: "glorified_social", label: "glorified social" },
];

const TIERS: { value: string; label: string }[] = [
  { value: "banger", label: "banger" },
  { value: "mean_good", label: "mean good" },
  { value: "slop", label: "slop" },
];

const SINCE: { value: string; label: string }[] = [
  { value: "24h", label: "last 24 hours" },
  { value: "7d", label: "last 7 days" },
  { value: "30d", label: "last 30 days" },
];

/** Homepage search + filter controls. Updates URL search params via the
 *  app router so the server-rendered grid re-queries on change. */
export function AppFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const initial = params.get("q") ?? "";
  const [query, setQuery] = useState(initial);

  // Keep local state in sync if the URL changes from elsewhere (e.g. back
  // button), so the input does not get out of step.
  useEffect(() => {
    setQuery(params.get("q") ?? "");
  }, [params]);

  function pushParam(name: string, value: string) {
    const p = new URLSearchParams(params.toString());
    if (value && value !== "all") {
      p.set(name, value);
    } else {
      p.delete(name);
    }
    // Reset to page 1 whenever a filter changes; otherwise an empty page
    // is easy to land on.
    p.delete("page");
    const qs = p.toString();
    router.push(qs ? `${pathname}?${qs}#output` : `${pathname}#output`);
  }

  // Debounce the freeform search so each keystroke does not push a route.
  useEffect(() => {
    const current = params.get("q") ?? "";
    if (query === current) return;
    const t = setTimeout(() => pushParam("q", query.trim()), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const archetype = params.get("archetype") ?? "all";
  const tier = params.get("tier") ?? "all";
  const since = params.get("since") ?? "all";
  const anyFilter =
    !!(params.get("q") || params.get("archetype") || params.get("tier") || params.get("since"));

  const selectClass =
    "font-mono text-xs bg-paper dark:bg-night border border-ink/15 dark:border-moon/15 " +
    "text-ink dark:text-moon px-2 py-1.5 rounded-none focus:outline-none " +
    "focus:border-ink/40 dark:focus:border-moon/40 appearance-none cursor-pointer pr-7";

  return (
    <div className="mb-8 flex flex-wrap items-center gap-3">
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="search by name…"
        aria-label="search apps by name"
        className="font-mono text-xs bg-paper dark:bg-night border border-ink/15 dark:border-moon/15 text-ink dark:text-moon placeholder:text-ink-faint dark:placeholder:text-moon-faint px-2 py-1.5 rounded-none focus:outline-none focus:border-ink/40 dark:focus:border-moon/40 min-w-[180px]"
      />

      <select
        aria-label="archetype"
        value={archetype}
        onChange={(e) => pushParam("archetype", e.target.value)}
        className={selectClass}
      >
        <option value="all">all archetypes</option>
        {ARCHETYPES.map((a) => (
          <option key={a.value} value={a.value}>
            {a.label}
          </option>
        ))}
      </select>

      <select
        aria-label="tier"
        value={tier}
        onChange={(e) => pushParam("tier", e.target.value)}
        className={selectClass}
      >
        <option value="all">all tiers</option>
        {TIERS.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label}
          </option>
        ))}
      </select>

      <select
        aria-label="when shipped"
        value={since}
        onChange={(e) => pushParam("since", e.target.value)}
        className={selectClass}
      >
        <option value="all">all time</option>
        {SINCE.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>

      {anyFilter ? (
        <button
          type="button"
          onClick={() => router.push(`${pathname}#output`)}
          className="font-mono text-xs text-ink-muted dark:text-moon-muted hover:text-ink dark:hover:text-moon underline decoration-ink/30 dark:decoration-moon/30 underline-offset-4 cursor-pointer"
        >
          clear
        </button>
      ) : null}
    </div>
  );
}
