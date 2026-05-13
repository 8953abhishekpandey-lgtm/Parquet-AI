import { Table2 } from "lucide-react";

export default function ResultsTable({ response }) {
  return (
    <section className="glass-panel animate-slide-up" style={{ animationDelay: "0.25s" }}>
      <div className="panel-header flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Table2 className="h-5 w-5 text-signal-emerald" />
          <h2 className="text-sm font-semibold text-white">Results Table</h2>
        </div>
        {response ? (
          <span className="badge-emerald badge text-[10px]">{response.row_count} rows</span>
        ) : null}
      </div>

      {!response ? (
        <div className="flex flex-col items-center justify-center p-10 text-center">
          <div className="mb-3 rounded-full bg-glass-white p-4">
            <Table2 className="h-7 w-7 text-graphite-600" />
          </div>
          <p className="text-sm text-graphite-500">Query results will appear here.</p>
        </div>
      ) : response.rows.length === 0 ? (
        <div className="p-6 text-center text-sm text-graphite-500">No rows returned for this query.</div>
      ) : (
        <div className="max-h-[32rem] overflow-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th className="w-10 text-center">#</th>
                {response.columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {response.rows.map((row, index) => (
                <tr key={index}>
                  <td className="text-center text-graphite-600 text-xs">{index + 1}</td>
                  {response.columns.map((column) => (
                    <td key={column} className="max-w-64 truncate">
                      {formatCell(row[column])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function formatCell(value) {
  if (value == null) return <span className="text-graphite-700 italic">null</span>;
  if (typeof value === "number") {
    return <span className="tabular-nums text-signal-cyan">{Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 4 })}</span>;
  }
  return String(value);
}
