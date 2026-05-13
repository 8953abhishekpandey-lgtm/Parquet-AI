export default function StatusPill({ tone = "neutral", children }) {
  const tones = {
    neutral: "badge-cyan",
    success: "badge-emerald",
    warning: "badge-amber",
    danger: "badge-red",
    purple: "badge-purple",
    teal: "badge-teal",
  };

  return (
    <span className={`badge ${tones[tone] || tones.neutral}`}>
      {children}
    </span>
  );
}
