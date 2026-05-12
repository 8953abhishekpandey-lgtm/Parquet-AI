import { Code2, Search } from "lucide-react";

export default function DebugPanel({ response }) {
  return (
    <section className="panel">
      <div className="panel-header flex items-center gap-2">
        <Search className="h-5 w-5 text-signal-gold" />
        <h2 className="text-sm font-semibold text-graphite-900">Semantic Debug Panel</h2>
      </div>

      {!response ? (
        <div className="p-4 text-sm text-graphite-500">Semantic matches and generated SQL will appear after a question.</div>
      ) : (
        <div className="grid gap-4 p-4 lg:grid-cols-2">
          <div className="border border-graphite-200">
            <div className="border-b border-graphite-200 bg-graphite-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-graphite-700">
              Retrieved Metadata
            </div>
            <div className="max-h-80 overflow-auto divide-y divide-graphite-100">
              {response.semantic_matches.map((match, index) => (
                <div key={`${match.kind}-${index}`} className="px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-graphite-900">{match.column_name || match.kind}</div>
                      {match.payload?.filename ? (
                        <div className="mt-0.5 truncate text-[11px] font-semibold text-graphite-500">{match.payload.filename}</div>
                      ) : null}
                    </div>
                    <div className="text-xs font-semibold text-signal-teal">{match.score.toFixed(3)}</div>
                  </div>
                  <div className="mt-2 h-1.5 bg-graphite-100">
                    <div className="h-full bg-signal-teal" style={{ width: `${Math.max(4, Math.min(100, match.score * 100))}%` }} />
                  </div>
                  <p className="mt-2 line-clamp-3 text-xs leading-5 text-graphite-600">{match.text}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="border border-graphite-200">
            <div className="flex items-center gap-2 border-b border-graphite-200 bg-graphite-50 px-3 py-2">
              <Code2 className="h-4 w-4 text-signal-coral" />
              <div className="text-xs font-semibold uppercase tracking-wide text-graphite-700">Generated SQL</div>
            </div>
            <div className="space-y-3 p-3">
              <pre className="max-h-64 overflow-auto bg-graphite-900 p-3 text-xs leading-5 text-graphite-50">
                {response.generated_sql.sql}
              </pre>
              <div className="grid gap-2 text-xs text-graphite-600 sm:grid-cols-2">
                <div>
                  <span className="font-semibold text-graphite-900">Intent:</span> {response.generated_sql.intent}
                </div>
                <div>
                  <span className="font-semibold text-graphite-900">Aggregation:</span> {response.generated_sql.aggregation || "-"}
                </div>
                <div>
                  <span className="font-semibold text-graphite-900">Metric:</span> {response.generated_sql.metric_column || "-"}
                </div>
                <div>
                  <span className="font-semibold text-graphite-900">Groups:</span>{" "}
                  {response.generated_sql.group_by_columns.length ? response.generated_sql.group_by_columns.join(", ") : "-"}
                </div>
              </div>
              <p className="text-xs leading-5 text-graphite-600">{response.generated_sql.explanation}</p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
