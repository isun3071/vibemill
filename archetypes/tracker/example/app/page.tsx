import { Counter, MapPanel, Timeline, NewsList } from "@/lib/components";
import {
  title,
  tagline,
  counters,
  regions,
  timelineEvents,
  newsItems,
} from "@/lib/data";

export default function Page() {
  return (
    <div className="flex flex-col gap-10">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold text-gray-900">{title}</h1>
        <p className="text-lg text-gray-600">{tagline}</p>
      </header>

      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {counters.map((c, i) => (
          <Counter key={i} {...c} />
        ))}
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900">Regions</h2>
        <MapPanel regions={regions} />
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900">Timeline</h2>
        <Timeline events={timelineEvents} />
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900">News</h2>
        <NewsList items={newsItems} />
      </section>
    </div>
  );
}
