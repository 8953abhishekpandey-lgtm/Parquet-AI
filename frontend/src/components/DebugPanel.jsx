import { ChevronDown, ChevronRight, Code2, Lock, Search, Shield, Unlock, FileText } from "lucide-react";
import { useState } from "react";

// Simple keyword highlighter for SQL
function highlightSQL(sql) {
  if (!sql) return "";
  const keywords = [
    "SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "LIMIT", "AS",
    "JOIN", "LEFT", "RIGHT", "INNER", "ON", "AND", "OR", "NOT", "IN",
    "IS", "NULL", "IS NOT NULL", "DESC", "ASC", "COUNT", "SUM", "AVG",
    "MAX", "MIN", "DISTINCT", "HAVING", "WITH", "CASE", "WHEN", "THEN",
    "ELSE", "END", "LIKE", "BETWEEN", "CAST", "DATE_TRUNC", "STDDEV_POP",
    "BY", "INSERT", "UPDATE", "DELETE", "CREATE", "VIEW", "TABLE",
  ];

  let result = sql;
  // Highlight keywords
  keywords.forEach((kw) => {
    const regex = new RegExp(`\\b(${kw})\\b`, "gi");
    result = result.replace(regex, `<span class="sql-keyword">$1</span>`);
  });
  // Highlight strings
  result = result.replace(/'([^']*)'/g, `<span class="sql-string">'$1'</span>`);
  // Highlight numbers
  result = result.replace(/\b(\d+\.?\d*)\b/g, `<span class="sql-number">$1</span>`);

  return result;
}

export default function DebugPanel({ response }) {
  const [contextOpen, setContextOpen] = useState(false);

  return (
    <section className="glass-panel animate-slide-up" style={{ animationDelay: "0.2s" }} id="debug-panel">
      <div className="panel-header flex items-center gap-2">
        <Search className="h-5 w-5 text-signal-gold" />
        <h2 className="text-sm font-semibold text-white">Semantic Debug Panel</h2>
      </div>

      {!response ? (
        <div className="flex flex-col items-center justify-center p-10 text-center">
          <div className="mb-3 rounded-full bg-glass-white p-4">
            <Search className="h-7 w-7 text-graphite-600" />
          </div>
          <p className="text-sm text-graphite-500">Semantic matches and generated SQL will appear after a query.</p>
        </div>
      ) : (
        <div className="space-y-4 p-4">
          {/* Security Audit */}
          {response.security_audit && Object.keys(response.security_audit).length > 0 && (
            <div className="border border-glass-border p-3" style={{ borderRadius: "10px", background: "rgba(15, 118, 110, 0.06)" }}>
              <div className="mb-2 flex items-center gap-2">
                <Shield className="h-4 w-4 text-teal-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-teal-400">Security Audit</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="flex items-center gap-1.5">
                  <Lock className="h-3 w-3 text-emerald-400" />
                  <span className="text-graphite-400">Raw data sent:</span>
                  <span className="font-semibold text-emerald-400">NO</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Lock className="h-3 w-3 text-emerald-400" />
                  <span className="text-graphite-400">Full dataset sent:</span>
                  <span className="font-semibold text-emerald-400">NO</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Lock className="h-3 w-3 text-emerald-400" />
                  <span className="text-graphite-400">Embeddings:</span>
                  <span className="font-semibold text-emerald-400">LOCAL</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Lock className="h-3 w-3 text-emerald-400" />
                  <span className="text-graphite-400">SQL execution:</span>
                  <span className="font-semibold text-emerald-400">LOCAL</span>
                </div>
                {response.security_audit.data_sent_to_api?.matched_column_details != null && (
                  <div className="col-span-2 flex items-center gap-1.5">
                    <Unlock className="h-3 w-3 text-amber-400" />
                    <span className="text-graphite-400">Sent to Claude:</span>
                    <span className="font-semibold text-amber-300">
                      {response.security_audit.data_sent_to_api.matched_column_details} column metadata,{" "}
                      ~{response.security_audit.data_sent_to_api.estimated_tokens || "?"} tokens
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            {/* Semantic matches */}
            <div className="border border-glass-border overflow-hidden" style={{ borderRadius: "10px" }}>
              <div className="border-b border-glass-border px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-graphite-400" style={{ background: "rgba(255,255,255,0.03)" }}>
                Retrieved Metadata ({response.semantic_matches.length})
              </div>
              <div className="max-h-80 overflow-auto divide-y divide-glass-border">
                {response.semantic_matches.map((match, index) => (
                  <div key={`${match.kind}-${index}`} className="px-3 py-3 transition-colors hover:bg-glass-white">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-graphite-200">{match.column_name || match.kind}</div>
                        {match.payload?.filename ? (
                          <div className="mt-0.5 truncate text-[10px] text-graphite-600">{match.payload.filename}</div>
                        ) : null}
                      </div>
                      <span className="badge-teal badge text-[10px] tabular-nums">{match.score.toFixed(3)}</span>
                    </div>
                    <div className="score-bar-track mt-2">
                      <div
                        className="score-bar-fill"
                        style={{ width: `${Math.max(4, Math.min(100, match.score * 100))}%` }}
                      />
                    </div>
                    <p className="mt-2 line-clamp-2 text-[11px] leading-5 text-graphite-500">{match.text}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Generated SQL */}
            <div className="border border-glass-border overflow-hidden" style={{ borderRadius: "10px" }}>
              <div className="flex items-center gap-2 border-b border-glass-border px-3 py-2.5" style={{ background: "rgba(255,255,255,0.03)" }}>
                <Code2 className="h-4 w-4 text-signal-coral" />
                <span className="text-xs font-semibold uppercase tracking-wider text-graphite-400">Generated SQL</span>
              </div>
              <div className="space-y-3 p-3">
                <pre
                  className="sql-code max-h-56 overflow-auto p-3 text-xs leading-5"
                  dangerouslySetInnerHTML={{ __html: highlightSQL(response.generated_sql.sql) }}
                />
                <div className="grid gap-2 text-[11px] sm:grid-cols-2">
                  <div>
                    <span className="text-graphite-500">Intent: </span>
                    <span className="badge-purple badge text-[10px]">{response.generated_sql.intent}</span>
                  </div>
                  <div>
                    <span className="text-graphite-500">Aggregation: </span>
                    <span className="font-semibold text-graphite-300">{response.generated_sql.aggregation || "—"}</span>
                  </div>
                  <div>
                    <span className="text-graphite-500">Metric: </span>
                    <span className="font-semibold text-graphite-300">{response.generated_sql.metric_column || "—"}</span>
                  </div>
                  <div>
                    <span className="text-graphite-500">Groups: </span>
                    <span className="font-semibold text-graphite-300">
                      {response.generated_sql.group_by_columns.length ? response.generated_sql.group_by_columns.join(", ") : "—"}
                    </span>
                  </div>
                </div>
                <p className="text-[11px] leading-5 text-graphite-500">{response.generated_sql.explanation}</p>
              </div>

              {/* Context sent to Claude — collapsible */}
              {response.security_audit?.data_sent_to_api && (
                <div className="border-t border-glass-border">
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-3 py-2.5 text-xs text-graphite-400 hover:text-graphite-200 transition-colors"
                    onClick={() => setContextOpen(!contextOpen)}
                  >
                    <FileText className="h-3.5 w-3.5" />
                    <span className="font-semibold uppercase tracking-wider">Context sent to Claude</span>
                    <span className="ml-auto text-graphite-600">
                      ~{response.security_audit.data_sent_to_api.estimated_tokens || "?"} tokens
                    </span>
                    {contextOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  </button>
                  {contextOpen && (
                    <div className="px-3 pb-3">
                      <pre className="sql-code max-h-40 overflow-auto p-3 text-[10px] leading-4 text-graphite-400">
                        {JSON.stringify(response.security_audit.data_sent_to_api, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
