import { getRetiredApps } from "@/lib/queries";
import { AppCard } from "@/components/app-card";

export const metadata = { title: "Cemetery — Vibe Mill" };
export const dynamic = "force-dynamic";

export default async function CemeteryPage() {
  const apps = await getRetiredApps(48);

  return (
    <section className="max-w-7xl mx-auto px-6 sm:px-10 py-20">
      <h1 className="font-serif text-3xl sm:text-4xl mb-3 text-ink dark:text-moon">
        Cemetery
      </h1>
      <p className="font-mono text-sm text-ink-muted dark:text-moon-muted mb-12">
        Apps the mill has retired. Their GitHub repos remain; their Vercel
        deployments do not.
      </p>

      {apps.length === 0 ? (
        <p className="font-mono text-sm text-ink-muted dark:text-moon-muted">
          No retired apps yet.
        </p>
      ) : (
        <div className="grid gap-6 sm:gap-8 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 grayscale opacity-80">
          {apps.map((app) => (
            <AppCard key={app.id} app={app} />
          ))}
        </div>
      )}
    </section>
  );
}
