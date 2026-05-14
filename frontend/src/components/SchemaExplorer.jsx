import { Braces, Columns3, Search, Sparkles, ChevronDown, ChevronRight } from "lucide-react";
import { useState, useMemo } from "react";
import StatusPill from "./StatusPill.jsx";

const TYPE_BADGE_MAP = {
  integer: "badge-blue",
  bigint: "badge-blue",
  smallint: "badge-blue",
  tinyint: "badge-blue",
  hugeint: "badge-blue",
  utinyint: "badge-blue",
  usmallint: "badge-blue",
  uinteger: "badge-blue",
  ubigint: "badge-blue",
  varchar: "badge-green",
  string: "badge-green",
  float: "badge-yellow",
  double: "badge-yellow",
  decimal: "badge-yellow",
  real: "badge-yellow",
  date: "badge-purple",
  time: "badge-purple",
  timestamp: "badge-purple",
  boolean: "badge-cyan",
  bool: "badge-cyan",
};

function getTypeBadge(dtype) {
  const lower = dtype.toLowerCase();
  for (const [key, cls] of Object.entries(TYPE_BADGE_MAP)) {
    if (lower.includes(key)) return cls;
  }
  return "badge-cyan";
}

export default function SchemaExplorer({ dataset, datasets, onSelectDataset, onShowAll }) {
  const [searchTerm, setSearchTerm] = useState("");
  const [expandedCol, setExpandedCol] = useState(null);

  const filteredColumns = useMemo(() => {
    if (!dataset) return [];
    if (!searchTerm.trim()) return dataset.columns;
    const term = searchTerm.toLowerCase();
    return dataset.columns.filter(
      (col) => col.name.toLowerCase().includes(term) || col.dtype.toLowerCase().includes(term)
    );
  }, [dataset, searchTerm]);

  if (!dataset) {
    return (
      <section className="glass-panel min-h-72 animate-fade-in" id="schema-explorer">
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
    <section className="glass-panel animate-slide-up" id="schema-explorer">
      <div className="panel-header flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Columns3 className="h-5 w-5 text-signal-cyan" />
            <h2 className="text-sm font-semibold text-white">Schema Explorer</h2>
          </div>

          {/* File switcher tabs */}
          {datasets && datasets.length > 1 && (
            <div className="mt-2 flex flex-wrap gap-1 items-center">
              <button
                type="button"
                className="file-tab bg-signal-teal/20 text-signal-cyan border border-signal-teal shadow-glow-teal hover:bg-signal-teal/40 transition-all font-bold"
                onClick={() => onShowAll && onShowAll()}
                title="Join and view all data across these datasets"
              >
                ALL (Join & Show)
              </button>
              {datasets.map((ds) => (
                <button
                  key={ds.dataset_id}
                  type="button"
                  className={`file-tab ${ds.dataset_id === dataset.dataset_id ? "active" : ""}`}
                  onClick={() => onSelectDataset && onSelectDataset(ds)}
                >
                  {ds.filename}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusPill tone="success">{dataset.row_count.toLocaleString()} rows</StatusPill>
          <StatusPill tone="neutral">{dataset.columns.length} columns</StatusPill>
        </div>
      </div>

      <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        {/* Columns table */}
        <div className="overflow-hidden border border-glass-border" style={{ borderRadius: "10px" }}>
          <div className="flex items-center gap-2 border-b border-glass-border px-3 py-2.5" style={{ background: "rgba(255,255,255,0.03)" }}>
            <Sparkles className="h-4 w-4 text-signal-gold" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-graphite-400">Columns</h3>
            <div className="ml-auto relative">
              <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-graphite-600" />
              <input
                type="text"
                placeholder="Search columns..."
                className="schema-search"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                id="schema-search-input"
              />
            </div>
          </div>
          <div className="max-h-96 overflow-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: "24px" }}></th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Distinct</th>
                  <th>Nulls</th>
                </tr>
              </thead>
              <tbody>
                {filteredColumns.map((column) => {
                  const isExpanded = expandedCol === column.name;
                  const nullCount = column.stats?.null_count ?? 0;
                  const distinctCount = column.stats?.distinct_count ?? 0;
                  const total = nullCount + distinctCount || 1;
                  const nullPct = ((nullCount / total) * 100).toFixed(1);

                  return (
                    <ColumnRow
                      key={column.name}
                      column={column}
                      isExpanded={isExpanded}
                      nullPct={nullPct}
                      onToggle={() => setExpandedCol(isExpanded ? null : column.name)}
                    />
                  );
                })}
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
          <div className="max-h-96 overflow-auto w-full">
            <table className="data-table whitespace-nowrap">
              <thead>
                <tr>
                  {dataset.columns.map((column) => (
                    <th key={column.name}>{column.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dataset.sample_rows.map((row, index) => (
                  <tr key={index}>
                    {dataset.columns.map((column) => (
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

function ColumnRow({ column, isExpanded, nullPct, onToggle }) {
  const badgeClass = getTypeBadge(column.dtype);
  return (
    <>
      <tr className="cursor-pointer" onClick={onToggle}>
        <td className="text-center text-graphite-600" style={{ width: "24px" }}>
          {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        </td>
        <td className="font-semibold text-graphite-200">{column.name}</td>
        <td>
          <span className={`badge ${badgeClass} text-[10px]`}>{column.dtype}</span>
        </td>
        <td className="text-graphite-500">{column.stats?.distinct_count ?? "—"}</td>
        <td className="text-graphite-500">{nullPct}%</td>
      </tr>
      {isExpanded && (
        <tr className="expanded-row">
          <td colSpan="5" className="!p-0">
            <div className="expanded-row-content">
              <div className="expanded-row-section">
                <span className="expanded-row-label">Sample Values:</span>
                <span className="expanded-row-value">
                  {column.sample_values?.slice(0, 8).map((v, i) => (
                    <span key={i} className="sample-value-chip">{String(v)}</span>
                  ))}
                  {(!column.sample_values || column.sample_values.length === 0) && (
                    <span className="text-graphite-600 italic">none</span>
                  )}
                </span>
              </div>
              {column.stats?.min_value != null && (
                <div className="expanded-row-section">
                  <span className="expanded-row-label">Range:</span>
                  <span className="expanded-row-value">
                    {column.stats.min_value} → {column.stats.max_value}
                    {column.stats.avg_value != null && ` (avg: ${Number(column.stats.avg_value).toFixed(2)})`}
                  </span>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
