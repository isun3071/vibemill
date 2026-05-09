type Region = {
  name: string;
  status: "active" | "monitoring" | "resolved" | "unknown";
  value?: number;
};

type Props = { regions: Region[] };

const STATUS_STYLES: Record<Region["status"], string> = {
  active: "bg-red-100 text-red-700",
  monitoring: "bg-amber-100 text-amber-700",
  resolved: "bg-emerald-100 text-emerald-700",
  unknown: "bg-gray-100 text-gray-700",
};

export function MapPanel({ regions }: Props) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <ul className="divide-y divide-gray-100">
        {regions.map((r) => (
          <li
            key={r.name}
            className="flex items-center justify-between py-3"
          >
            <span className="font-medium text-gray-900">{r.name}</span>
            <div className="flex items-center gap-3">
              {typeof r.value === "number" ? (
                <span className="text-sm tabular-nums text-gray-500">
                  {r.value}
                </span>
              ) : null}
              <span
                className={`text-xs uppercase tracking-wide px-2 py-1 rounded ${STATUS_STYLES[r.status]}`}
              >
                {r.status}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
