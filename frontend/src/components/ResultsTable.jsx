import { Table2 } from "lucide-react";

export default function ResultsTable({ response }) {
  return (
    <section className="panel">
      <div className="panel-header flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Table2 className="h-5 w-5 text-signal-teal" />
          <h2 className="text-sm font-semibold text-graphite-900">Results Table</h2>
        </div>
        {response ? <span className="text-xs font-semibold text-graphite-500">{response.row_count} rows</span> : null}
      </div>

      {!response ? (
        <div className="p-4 text-sm text-graphite-500">Query results will appear here.</div>
      ) : response.rows.length === 0 ? (
        <div className="p-4 text-sm text-graphite-500">No rows returned.</div>
      ) : (
        <div className="max-h-[32rem] overflow-auto">
          <table className="min-w-full divide-y divide-graphite-200 text-sm">
            <thead className="sticky top-0 bg-white">
              <tr>
                {response.columns.map((column) => (
                  <th key={column} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-graphite-500">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-graphite-100">
              {response.rows.map((row, index) => (
                <tr key={index}>
                  {response.columns.map((column) => (
                    <td key={column} className="max-w-72 truncate px-3 py-2 text-graphite-700">
                      {String(row[column] ?? "")}
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

