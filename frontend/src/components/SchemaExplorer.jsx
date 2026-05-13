import { Braces, Columns3, Sparkles } from "lucide-react";
import StatusPill from "./StatusPill.jsx";

export default function SchemaExplorer({ dataset }) {
  if (!dataset) {
    return (
      <section className="glass-panel min-h-72 animate-fade-in">
        <div className="panel-header flex items-center gap-2">
          <Columns3 className="h-5 w-5 text-signal-cyan" />
          <h2 className="text-sm font-semibold text-white">Schema Explorer</h2>
        </div>
        <div className="flex flex-col items-center justify-center p-10 text-center">
          <div className="mb-3 rounded-full bg-glass-white p-4">
            <Columns3 className="h-8 w-8 text-graphite-600" />
          </div>
          <p className="text-sm text-graphite-500">Upload or select a parquet file to inspect its dynamic schema.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="glass-panel animate-slide-up">
      <div className="panel-header flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Columns3 className="h-5 w-5 text-signal-cyan" />
            <h2 className="text-sm font-semibold text-white">Schema Explorer</h2>
          </div>
          <p className="mt-1 max-w-2xl truncate text-xs text-graphite-500">{dataset.filename}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusPill tone="success">{dataset.row_count.toLocaleString()} rows</StatusPill>
          <StatusPill tone="neutral">{dataset.columns.length} columns</StatusPill>
          <StatusPill tone={dataset.spark_schema?.available ? "success" : "warning"}>
            Spark {dataset.spark_schema?.available ? "ready" : "fallback"}
          </StatusPill>
        </div>
      </div>

      <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        {/* Columns table */}
        <div className="overflow-hidden border border-glass-border" style={{ borderRadius: "10px" }}>
          <div className="flex items-center gap-2 border-b border-glass-border px-3 py-2.5" style={{ background: "rgba(255,255,255,0.03)" }}>
            <Sparkles className="h-4 w-4 text-signal-gold" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-graphite-400">Columns</h3>
          </div>
          <div className="max-h-96 overflow-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Semantic</th>
                  <th>Distinct</th>
                </tr>
              </thead>
              <tbody>
                {dataset.columns.map((column) => (
                  <tr key={column.name}>
                    <td className="font-semibold text-graphite-200">{column.name}</td>
                    <td>
                      <span className="badge-purple badge text-[10px]">{column.dtype}</span>
                    </td>
                    <td className="text-graphite-500">{column.normalized_name}</td>
                    <td className="text-graphite-500">{column.stats?.distinct_count ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Sample rows table */}
        <div className="overflow-hidden border border-glass-border" style={{ borderRadius: "10px" }}>
          <div className="flex items-center gap-2 border-b border-glass-border px-3 py-2.5" style={{ background: "rgba(255,255,255,0.03)" }}>
            <Braces className="h-4 w-4 text-signal-coral" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-graphite-400">Sample Rows</h3>
          </div>
          <div className="max-h-96 overflow-auto">
            <table className="data-table">
              <thead>
                <tr>
                  {dataset.columns.slice(0, 6).map((column) => (
                    <th key={column.name}>{column.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dataset.sample_rows.slice(0, 8).map((row, index) => (
                  <tr key={index}>
                    {dataset.columns.slice(0, 6).map((column) => (
                      <td key={column.name} className="max-w-48 truncate">
                        {String(row[column.name] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}
