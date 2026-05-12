export default function StatusPill({ tone = "neutral", children }) {
  const tones = {
    neutral: "border-graphite-200 bg-graphite-50 text-graphite-700",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    danger: "border-red-200 bg-red-50 text-red-700",
  };

  return (
    <span className={`inline-flex items-center border px-2.5 py-1 text-xs font-semibold ${tones[tone]}`}>
      {children}
    </span>
  );
}

