import { getLiveApps, getTodayCounts } from "@/lib/queries";
import { AppCard } from "./app-card";

export async function AppGrid() {
  const [apps, counts] = await Promise.all([getLiveApps(24), getTodayCounts()]);

  return (
    <section
      id="output"
      className="w-full px-6 sm:px-10 py-16 max-w-7xl mx-auto"
      aria-label="recent output"
    >
      <h2 className="font-serif text-xl sm:text-2xl mb-8 text-ink dark:text-moon">
        Today&rsquo;s output:
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

      <p className="font-mono text-xs text-ink-faint dark:text-moon-faint mt-10 text-center">
        Today: {counts.shipped} shipped · {counts.guardRejected} guard-rejected ·{" "}
        {counts.matcherRejected} matcher-rejected
      </p>
    </section>
  );
}
