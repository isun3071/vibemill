import { getRejections } from "@/lib/queries";

export const metadata = { title: "Rejected — Vibe Mill" };
export const dynamic = "force-dynamic";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

export default async function RejectedPage() {
  const rejections = await getRejections(200);

  return (
    <section className="max-w-4xl mx-auto px-6 sm:px-10 py-20">
      <h1 className="font-serif text-3xl sm:text-4xl mb-3 text-ink dark:text-moon">
        Rejected
      </h1>
      <p className="font-mono text-sm text-ink-muted dark:text-moon-muted mb-12">
        Inputs the mill refused. Guard rejections fail the safety check;
        matcher rejections score below threshold or land on a non-buildable
        archetype.
      </p>

      {rejections.length === 0 ? (
        <p className="font-mono text-sm text-ink-muted dark:text-moon-muted">
          No rejections logged.
        </p>
      ) : (
        <ul className="divide-y divide-ink/10 dark:divide-moon/10">
          {rejections.map((r) => (
            <li key={r.id} className="py-5">
              <div className="font-serif text-base text-ink dark:text-moon">
                {r.prompt}
              </div>
              <div className="font-mono text-xs text-ink-muted dark:text-moon-muted mt-2 flex flex-wrap gap-x-3 gap-y-1">
                <span>{formatDate(r.created_at)}</span>
                <span>·</span>
                <span>{r.rejection_stage}-rejected</span>
                {r.best_archetype && r.best_score !== null ? (
                  <>
                    <span>·</span>
                    <span>
                      best: {r.best_archetype} ({r.best_score})
                    </span>
                  </>
                ) : null}
                <span>·</span>
                <span>{r.source}</span>
              </div>
              {r.rejection_reason ? (
                <div className="font-serif text-sm text-ink-muted dark:text-moon-muted mt-2 italic">
                  {r.rejection_reason}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
