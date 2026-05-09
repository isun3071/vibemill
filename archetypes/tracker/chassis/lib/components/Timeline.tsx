type TimelineEvent = {
  date: string;
  title: string;
  description: string;
};

type Props = { events: TimelineEvent[] };

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function Timeline({ events }: Props) {
  return (
    <ol className="rounded-lg border border-gray-200 bg-white p-5 space-y-4">
      {events.map((e, i) => (
        <li key={i} className="border-l-2 border-gray-200 pl-4">
          <div className="text-xs uppercase tracking-wide text-gray-500">
            {formatDate(e.date)}
          </div>
          <div className="font-medium text-gray-900">{e.title}</div>
          <div className="text-sm text-gray-600 mt-1">{e.description}</div>
        </li>
      ))}
    </ol>
  );
}
