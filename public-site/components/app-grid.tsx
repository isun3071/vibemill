import Link from "next/link";
import { getLiveApps, getLiveAppsCount, getTodayCounts, type AppFilters } from "@/lib/queries";
import { AppCard } from "./app-card";
import { TodayCounts } from "./today-counts";
import { AppFilters as AppFiltersBar } from "./app-filters";

const PER_PAGE = 12; // 4 cols x 3 rows at lg breakpoint

export async function AppGrid({
  page = 1,
  filters,
}: {
  page?: number;
  filters?: AppFilters;
}) {
  const safePage = Math.max(1, Math.floor(page));
  const offset = (safePage - 1) * PER_PAGE;
  const [apps, total, counts] = await Promise.all([
    getLiveApps(PER_PAGE, offset, filters),
    getLiveAppsCount(filters),
    getTodayCounts(),
  ]);

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));
  const clampedPage = Math.min(safePage, totalPages);
  const hasPrev = clampedPage > 1;
  const hasNext = clampedPage < totalPages;

  // Build page-link hrefs. Page 1 drops the page param so the canonical
  // home URL matches the first page; current filter params are preserved
  // across pagination.
  const filterQS = new URLSearchParams();
  if (filters?.q) filterQS.set("q", filters.q);
  if (filters?.archetype) filterQS.set("archetype", filters.archetype);
  if (filters?.tier) filterQS.set("tier", filters.tier);
  if (filters?.since) filterQS.set("since", filters.since);
  const hrefFor = (p: number) => {
    const qs = new URLSearchParams(filterQS);
    if (p > 1) qs.set("page", String(p));
    const s = qs.toString();
    return s ? `/?${s}#output` : "/#output";
  };

  return (
    <section
      id="output"
      className="w-full px-6 sm:px-10 py-16 max-w-7xl mx-auto"
      aria-label="recent output"
    >
      <h2 className="font-serif text-xl sm:text-2xl mb-6 text-ink dark:text-moon">
        {filters && Object.values(filters).some(Boolean)
          ? "Filtered output:"
          : clampedPage === 1
            ? "Today’s output:"
            : "Output, continued:"}
      </h2>

      <AppFiltersBar />

      {apps.length === 0 ? (
        <p className="font-mono text-sm text-ink-muted dark:text-moon-muted">
          No live apps. The mill may be between cron ticks.
        </p>
      ) : (
        <div className="grid gap-6 sm:gap-8 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
          {apps.map((app) => (
            <AppCard key={app.id} app={app} />
          ))}
        </div>
      )}

      {totalPages > 1 ? (
        <nav
          aria-label="output pagination"
          className="mt-10 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 font-mono text-xs"
        >
          {hasPrev ? (
            <Link
              href={hrefFor(1)}
              className="text-ink-muted dark:text-moon-muted hover:text-ink dark:hover:text-moon transition-colors"
              aria-label="first page"
            >
              &laquo; First
            </Link>
          ) : (
            <span className="text-ink-faint dark:text-moon-faint select-none">&laquo; First</span>
          )}

          {hasPrev ? (
            <Link
              href={hrefFor(clampedPage - 1)}
              className="text-ink-muted dark:text-moon-muted hover:text-ink dark:hover:text-moon transition-colors"
              aria-label="previous page"
            >
              &larr; Prev
            </Link>
          ) : (
            <span className="text-ink-faint dark:text-moon-faint select-none">&larr; Prev</span>
          )}

          <span className="text-ink-muted dark:text-moon-muted select-none">
            Page {clampedPage} of {totalPages}
          </span>

          {hasNext ? (
            <Link
              href={hrefFor(clampedPage + 1)}
              className="text-ink-muted dark:text-moon-muted hover:text-ink dark:hover:text-moon transition-colors"
              aria-label="next page"
            >
              Next &rarr;
            </Link>
          ) : (
            <span className="text-ink-faint dark:text-moon-faint select-none">Next &rarr;</span>
          )}

          {hasNext ? (
            <Link
              href={hrefFor(totalPages)}
              className="text-ink-muted dark:text-moon-muted hover:text-ink dark:hover:text-moon transition-colors"
              aria-label="last page"
            >
              Last &raquo;
            </Link>
          ) : (
            <span className="text-ink-faint dark:text-moon-faint select-none">Last &raquo;</span>
          )}
        </nav>
      ) : null}

      <TodayCounts initial={counts} />
    </section>
  );
}
