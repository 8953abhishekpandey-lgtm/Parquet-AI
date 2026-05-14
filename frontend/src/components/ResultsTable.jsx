import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Download, Table2, Clock } from "lucide-react";
import { useState, useMemo } from "react";

const PAGE_SIZE = 25;

export default function ResultsTable({ response }) {
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState("asc");
  const [page, setPage] = useState(0);

  // Reset pagination when response changes
  const responseId = response ? `${response.question}-${response.row_count}` : null;
  useMemo(() => setPage(0), [responseId]);

  const sortedRows = useMemo(() => {
    if (!response?.rows?.length || !sortCol) return response?.rows || [];
    return [...response.rows].sort((a, b) => {
      const va = a[sortCol];
      const vb = b[sortCol];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === "number" && typeof vb === "number") {
        return sortDir === "asc" ? va - vb : vb - va;
      }
      const sa = String(va);
      const sb = String(vb);
      return sortDir === "asc" ? sa.localeCompare(sb) : sb.localeCompare(sa);
    });
  }, [response?.rows, sortCol, sortDir]);

  const totalPages = Math.ceil(sortedRows.length / PAGE_SIZE);
  const pagedRows = sortedRows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  function handleSort(col) {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
    setPage(0);
  }

  function exportCSV() {
    if (!response) return;
    const header = response.columns.join(",");
    const rows = response.rows.map((row) =>
      response.columns.map((col) => {
        const val = row[col];
        if (val == null) return "";
        const str = String(val);
        return str.includes(",") || str.includes('"') || str.includes("\n")
          ? `"${str.replace(/"/g, '""')}"`
          : str;
      }).join(",")
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `query_results_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="glass-panel animate-slide-up" style={{ animationDelay: "0.25s" }} id="results-table">
      <div className="panel-header flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Table2 className="h-5 w-5 text-signal-emerald" />
          <h2 className="text-sm font-semibold text-white">Results Table</h2>
        </div>
        <div className="flex items-center gap-2">
          {response && response.rows.length > 0 && (
            <button
              type="button"
              className="secondary-button text-[11px] py-1.5 px-3"
              onClick={exportCSV}
              id="export-csv-btn"
            >
              <Download className="h-3 w-3" />
              Export CSV
            </button>
          )}
          {response ? (
            <span className="badge-emerald badge text-[10px]">{response.row_count} rows</span>
          ) : null}
        </div>
      </div>

      {/* Summary stat bar */}
      {response && response.rows.length > 0 && (
        <div className="results-stat-bar">
          <div className="results-stat">
            <Table2 className="h-3 w-3 text-signal-cyan" />
            <span>{response.row_count} rows returned</span>
          </div>
          <div className="results-stat">
            <Clock className="h-3 w-3 text-signal-gold" />
            <span>{response.query_time_ms || response._client_time_ms || "—"}ms</span>
          </div>
          {totalPages > 1 && (
            <div className="results-stat">
              <span>Page {page + 1} of {totalPages}</span>
            </div>
          )}
        </div>
      )}

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
        <>
          <div className="max-h-[32rem] overflow-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="w-10 text-center">#</th>
                  {response.columns.map((column) => (
                    <th
                      key={column}
                      className="cursor-pointer hover:text-graphite-200 select-none"
                      onClick={() => handleSort(column)}
                    >
                      <span className="inline-flex items-center gap-1">
                        {column}
                        {sortCol === column ? (
                          sortDir === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
                        ) : (
                          <ArrowUpDown className="h-2.5 w-2.5 opacity-30" />
                        )}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pagedRows.map((row, index) => (
                  <tr key={index} className={index % 2 === 1 ? "alt-row" : ""}>
                    <td className="text-center text-graphite-600 text-xs">{page * PAGE_SIZE + index + 1}</td>
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

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="pagination-bar">
              <button
                type="button"
                className="icon-button"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                id="page-prev-btn"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-xs text-graphite-400">
                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, sortedRows.length)} of {sortedRows.length}
              </span>
              <button
                type="button"
                className="icon-button"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                id="page-next-btn"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </>
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
