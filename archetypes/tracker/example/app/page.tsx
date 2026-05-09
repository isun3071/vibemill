import { snapshot } from "@/lib/data";

export default function Page() {
  return (
    <>
      <header className="bg-indigo-700 text-white">
        <div className="max-w-6xl mx-auto px-6 py-12">
          <h1 className="text-4xl font-bold tracking-tight">
            {snapshot.title}
          </h1>
          <p className="mt-3 text-lg text-indigo-100 max-w-3xl">
            {snapshot.tagline}
          </p>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-10 grid grid-cols-1 lg:grid-cols-3 gap-8">
        <section className="lg:col-span-2 space-y-6">
          <div className="grid grid-cols-2 gap-4">
            {snapshot.stats.map((s) => (
              <div
                key={s.label}
                className="rounded-lg border border-gray-200 bg-white p-5"
              >
                <div className="text-xs uppercase tracking-wide text-gray-500">
                  {s.label}
                </div>
                <div className="mt-2 text-3xl font-semibold text-gray-900">
                  {s.value}
                </div>
                {s.note ? (
                  <div className="mt-1 text-sm text-gray-500">{s.note}</div>
                ) : null}
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">
              Timeline
            </h2>
            <ol className="space-y-3 text-sm">
              {snapshot.events.map((e, i) => (
                <li key={i} className="flex gap-3">
                  <span className="text-gray-500 w-24 shrink-0 tabular-nums">
                    {e.date}
                  </span>
                  <span className="text-gray-900">{e.text}</span>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <aside className="space-y-6">
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">
              Regions
            </h2>
            <ul className="space-y-2 text-sm">
              {snapshot.regions.map((r) => (
                <li
                  key={r.name}
                  className="flex items-center justify-between"
                >
                  <span className="text-gray-900">{r.name}</span>
                  <span className="text-gray-500 tabular-nums">{r.value}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">News</h2>
            <ul className="space-y-3 text-sm">
              {snapshot.news.map((n, i) => (
                <li key={i}>
                  <a
                    href={n.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-gray-900 hover:underline"
                  >
                    {n.headline}
                  </a>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {n.source}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </>
  );
}
