import Link from "next/link";
import { getLiveApps, getLiveAppsCount, getTodayCounts } from "@/lib/queries";
import { AppCard } from "./app-card";

const PER_PAGE = 12; // 4 cols x 3 rows at lg breakpoint

export async function AppGrid({ page = 1 }: { page?: number }) {
  const safePage = Math.max(1, Math.floor(page));
  const offset = (safePage - 1) * PER_PAGE;
  const [apps, total, counts] = await Promise.all([
    getLiveApps(PER_PAGE, offset),
    getLiveAppsCount(),
    getTodayCounts(),
  ]);

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));
  const clampedPage = Math.min(safePage, totalPages);
  const hasPrev = clampedPage > 1;
  const hasNext = clampedPage < totalPages;

  // Build page-link hrefs. Page 1 drops the query param entirely so the
  // canonical home URL matches the first page.
  const hrefFor = (p: number) => (p <= 1 ? "/#output" : `/?page=${p}#output`);

  return (
    <section
      id="output"
      className="w-full px-6 sm:px-10 py-16 max-w-7xl mx-auto"
      aria-label="recent output"
    >
      <h2 className="font-serif text-xl sm:text-2xl mb-8 text-ink dark:text-moon">
        {clampedPage === 1 ? "Today’s output:" : "Output, continued:"}
      </h2>

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
          className="mt-10 flex items-center justify-center gap-6 font-mono text-xs"
        >
          {hasPrev ? (
            <Link
              href={hrefFor(clampedPage - 1)}
              className="text-ink-muted dark:text-moon-muted hover:text-ink dark:hover:text-moon transition-colors"
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
            >
              Next &rarr;
            </Link>
          ) : (
            <span className="text-ink-faint dark:text-moon-faint select-none">Next &rarr;</span>
          )}
        </nav>
      ) : null}

      <p className="font-mono text-xs text-ink-faint dark:text-moon-faint mt-10 text-center">
        Today: {counts.shipped} shipped &middot; {counts.guardRejected} guard-rejected &middot;{" "}
        {counts.matcherRejected} matcher-rejected
      </p>
    </section>
  );
}
