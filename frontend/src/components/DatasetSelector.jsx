import { Database, Trash2 } from "lucide-react";

export default function DatasetSelector({ datasets, selectedId, onSelect, onDelete }) {
  return (
    <section className="glass-panel animate-fade-in" style={{ animationDelay: "0.1s" }}>
      <div className="panel-header flex items-center gap-2">
        <Database className="h-5 w-5 text-signal-purple" />
        <h2 className="text-sm font-semibold text-white">Datasets</h2>
        {datasets.length > 0 && (
          <span className="ml-auto badge-cyan badge text-[10px]">{datasets.length}</span>
        )}
      </div>

      <div className="max-h-64 overflow-auto p-2">
        {datasets.length === 0 ? (
          <p className="px-3 py-4 text-sm text-graphite-500">Uploaded files will appear here.</p>
        ) : (
          <div className="space-y-1.5">
            {datasets.map((dataset) => (
              <div
                key={dataset.dataset_id}
                className={`group flex w-full items-center justify-between px-3 py-3 transition-all duration-200 ${
                  selectedId === dataset.dataset_id
                    ? "bg-signal-teal/15 border border-signal-teal/30 shadow-glow-teal"
                    : "bg-glass-white border border-transparent hover:bg-glass-hover hover:border-glass-border"
                }`}
                style={{ borderRadius: "8px" }}
              >
                <button type="button" className="w-full text-left" onClick={() => onSelect(dataset)}>
                  <div className="truncate text-sm font-semibold text-graphite-200">{dataset.filename}</div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-graphite-500">
                    <span>{dataset.row_count.toLocaleString()} rows</span>
                    <span className="h-1 w-1 rounded-full bg-graphite-600" />
                    <span>{dataset.columns.length} cols</span>
                  </div>
                </button>
                <button
                  type="button"
                  title="Delete dataset"
                  className="ml-2 flex-shrink-0 p-1.5 text-graphite-600 opacity-0 transition-all duration-200 hover:text-red-400 group-hover:opacity-100"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onDelete && window.confirm(`Delete ${dataset.filename}? This removes the file, manifest, and vectors.`)) {
                      onDelete(dataset.dataset_id);
                    }
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
