import { notFound } from "next/navigation";
import { getAppById, liveUrlOf } from "@/lib/queries";

export const dynamic = "force-dynamic";

export default async function AppDetailPage({
  params,
}: {
  params: { slug: string };
}) {
  const app = await getAppById(params.slug);
  if (!app) notFound();
  const liveUrl = liveUrlOf(app);

  return (
    <article className="max-w-4xl mx-auto px-6 sm:px-10 py-16">
      <a
        href="/"
        className="font-mono text-xs text-ink-muted dark:text-moon-muted hover:text-ink dark:hover:text-moon"
      >
        &larr; back to today
      </a>

      <h1 className="font-serif text-3xl sm:text-4xl mt-6 text-ink dark:text-moon">
        {app.id.slice(0, 8)}
      </h1>
      <div className="font-mono text-xs text-ink-muted dark:text-moon-muted mt-2">
        {app.archetype}
        {app.layout_archetype ? ` · ${app.layout_archetype}` : ""} ·{" "}
        {new Date(app.created_at).toISOString().slice(0, 16).replace("T", " ")} UTC
      </div>

      {app.screenshot_path ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={app.screenshot_path}
          alt={`screenshot of ${app.id}`}
          className="w-full mt-8 border border-ink/10 dark:border-moon/10"
        />
      ) : null}

      <div className="mt-8 flex flex-wrap gap-4 font-mono text-sm">
        {liveUrl ? (
          <a
            href={liveUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-ink dark:text-moon hover:text-ink-muted dark:hover:text-moon-muted underline underline-offset-4"
          >
            live &rarr;
          </a>
        ) : null}
        {app.github_url ? (
          <a
            href={app.github_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-ink dark:text-moon hover:text-ink-muted dark:hover:text-moon-muted underline underline-offset-4"
          >
            github &rarr;
          </a>
        ) : null}
      </div>

      <hr className="border-ink/15 dark:border-moon/15 my-12" />

      <h2 className="font-serif text-xl mb-4 text-ink dark:text-moon">Source</h2>
      <p className="font-serif text-base text-ink dark:text-moon italic">
        {app.prompt}
      </p>

      <hr className="border-ink/15 dark:border-moon/15 my-12" />

      <h2 className="font-serif text-xl mb-4 text-ink dark:text-moon">Operating data</h2>
      <dl className="font-mono text-sm grid grid-cols-1 sm:grid-cols-2 gap-y-2 gap-x-8 text-ink-muted dark:text-moon-muted">
        <div>
          <dt className="text-ink-faint dark:text-moon-faint">tier</dt>
          <dd>{app.tier ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-ink-faint dark:text-moon-faint">readme persona</dt>
          <dd>{app.readme_persona ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-ink-faint dark:text-moon-faint">verifier verdict</dt>
          <dd>{app.verifier_verdict ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-ink-faint dark:text-moon-faint">source</dt>
          <dd>{app.source}</dd>
        </div>
        <div>
          <dt className="text-ink-faint dark:text-moon-faint">deploy target</dt>
          <dd>{app.deploy_target ?? "vercel"}</dd>
        </div>
        {app.synthetic_track ? (
          <div>
            <dt className="text-ink-faint dark:text-moon-faint">synthetic track</dt>
            <dd>{app.synthetic_track}</dd>
          </div>
        ) : null}
        {app.blend_partner_archetype ? (
          <div>
            <dt className="text-ink-faint dark:text-moon-faint">blend partner</dt>
            <dd>{app.blend_partner_archetype}</dd>
          </div>
        ) : null}
      </dl>
    </article>
  );
}
