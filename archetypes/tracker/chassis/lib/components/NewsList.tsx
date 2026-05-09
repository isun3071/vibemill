type NewsItem = {
  source: string;
  headline: string;
  url: string;
  publishedAt: string;
};

type Props = { items: NewsItem[] };

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function NewsList({ items }: Props) {
  return (
    <ul className="rounded-lg border border-gray-200 bg-white p-5 divide-y divide-gray-100">
      {items.map((n, i) => (
        <li key={i} className="py-3">
          <a
            href={n.url}
            target="_blank"
            rel="noreferrer"
            className="text-gray-900 hover:underline"
          >
            {n.headline}
          </a>
          <div className="mt-1 text-xs text-gray-500 flex items-center gap-2">
            <span className="uppercase tracking-wide">{n.source}</span>
            <span>·</span>
            <span>{formatDate(n.publishedAt)}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}
