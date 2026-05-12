import { Braces, Columns3, Sparkles } from "lucide-react";
import StatusPill from "./StatusPill.jsx";

export default function SchemaExplorer({ dataset }) {
  if (!dataset) {
    return (
      <section className="panel min-h-80">
        <div className="panel-header flex items-center gap-2">
          <Columns3 className="h-5 w-5 text-signal-teal" />
          <h2 className="text-sm font-semibold text-graphite-900">Schema Explorer</h2>
        </div>
        <div className="p-6 text-sm text-graphite-500">Upload or select a parquet file to inspect its dynamic schema.</div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-header flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Columns3 className="h-5 w-5 text-signal-teal" />
            <h2 className="text-sm font-semibold text-graphite-900">Schema Explorer</h2>
          </div>
          <p className="mt-1 max-w-2xl truncate text-xs text-graphite-500">{dataset.filename}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusPill tone="success">{dataset.row_count.toLocaleString()} rows</StatusPill>
          <StatusPill>{dataset.columns.length} columns</StatusPill>
          <StatusPill tone={dataset.spark_schema?.available ? "success" : "warning"}>
            Spark {dataset.spark_schema?.available ? "ready" : "fallback"}
          </StatusPill>
        </div>
      </div>

      <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        <div className="overflow-hidden border border-graphite-200">
          <div className="flex items-center gap-2 border-b border-graphite-200 bg-graphite-50 px-3 py-2">
            <Sparkles className="h-4 w-4 text-signal-gold" />
            <h3 className="text-xs font-semibold uppercase tracking-wide text-graphite-700">Columns</h3>
          </div>
          <div className="max-h-96 overflow-auto">
            <table className="min-w-full divide-y divide-graphite-200 text-sm">
              <thead className="sticky top-0 bg-white">
                <tr className="text-left text-xs uppercase tracking-wide text-graphite-500">
                  <th className="px-3 py-2 font-semibold">Name</th>
                  <th className="px-3 py-2 font-semibold">Type</th>
                  <th className="px-3 py-2 font-semibold">Semantic label</th>
                  <th className="px-3 py-2 font-semibold">Distinct</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-graphite-100">
                {dataset.columns.map((column) => (
                  <tr key={column.name} className="align-top">
                    <td className="px-3 py-2 font-semibold text-graphite-900">{column.name}</td>
                    <td className="px-3 py-2 text-graphite-600">{column.dtype}</td>
                    <td className="px-3 py-2 text-graphite-600">{column.normalized_name}</td>
                    <td className="px-3 py-2 text-graphite-600">{column.stats?.distinct_count ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="overflow-hidden border border-graphite-200">
          <div className="flex items-center gap-2 border-b border-graphite-200 bg-graphite-50 px-3 py-2">
            <Braces className="h-4 w-4 text-signal-coral" />
            <h3 className="text-xs font-semibold uppercase tracking-wide text-graphite-700">Sample Rows</h3>
          </div>
          <div className="max-h-96 overflow-auto">
            <table className="min-w-full divide-y divide-graphite-200 text-sm">
              <thead className="sticky top-0 bg-white">
                <tr>
                  {dataset.columns.slice(0, 6).map((column) => (
                    <th key={column.name} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-graphite-500">
                      {column.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-graphite-100">
                {dataset.sample_rows.slice(0, 8).map((row, index) => (
                  <tr key={index}>
                    {dataset.columns.slice(0, 6).map((column) => (
                      <td key={column.name} className="max-w-56 truncate px-3 py-2 text-graphite-700">
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

      <div className="border-t border-graphite-100 px-4 py-3 flex items-center justify-between text-sm text-graphite-600">
        <div className="truncate">{dataset.filename}</div>
        <div className="flex gap-2">
          <span className="px-2 py-1 bg-graphite-50 border border-graphite-100 text-xs rounded">Sample Rows</span>
          <span className="px-2 py-1 bg-graphite-50 border border-graphite-100 text-xs rounded">Columns</span>
        </div>
      </div>
    </section>
  );
}

