import { Database, Trash2 } from "lucide-react";

export default function DatasetSelector({ datasets, selectedId, onSelect, onDelete }) {
  return (
    <section className="panel">
      <div className="panel-header flex items-center gap-2">
        <Database className="h-5 w-5 text-signal-teal" />
        <h2 className="text-sm font-semibold text-graphite-900">Datasets</h2>
      </div>

      <div className="max-h-64 overflow-auto p-2">
        {datasets.length === 0 ? (
          <p className="px-2 py-4 text-sm text-graphite-500">Uploaded files will appear here.</p>
        ) : (
          <div className="space-y-2">
            {datasets.map((dataset) => (
              <div
                key={dataset.dataset_id}
                className={`w-full flex items-center justify-between border px-3 py-3 transition ${
                  selectedId === dataset.dataset_id ? "border-signal-teal bg-teal-50" : "border-graphite-200 bg-white hover:border-graphite-500"
                }`}
              >
                <button type="button" className="text-left w-full" onClick={() => onSelect(dataset)}>
                  <div className="truncate text-sm font-semibold text-graphite-900">{dataset.filename}</div>
                  <div className="mt-1 flex items-center gap-2 text-xs text-graphite-500">
                    <span>{dataset.row_count.toLocaleString()} rows</span>
                    <span>{dataset.columns.length} columns</span>
                  </div>
                </button>
                <div className="ml-3 flex-shrink-0">
                  <button
                    type="button"
                    title="Delete dataset"
                    className="icon-button text-red-600"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onDelete && window.confirm(`Delete uploaded dataset ${dataset.filename}? This will remove file, manifest and vectors.`)) {
                        onDelete(dataset.dataset_id);
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

