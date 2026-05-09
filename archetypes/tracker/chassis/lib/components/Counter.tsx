type Props = {
  label: string;
  value: number | string;
  sublabel?: string;
};

export function Counter({ label, value, sublabel }: Props) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold text-gray-900">{value}</div>
      {sublabel ? (
        <div className="mt-1 text-sm text-gray-500">{sublabel}</div>
      ) : null}
    </div>
  );
}
