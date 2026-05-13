import { FileUp, Loader2, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

export default function UploadDropzone({ onUpload, loading, progress = 0, error }) {
  const inputRef = useRef(null);
  const [isDragging, setDragging] = useState(false);
  const [selectedSummary, setSelectedSummary] = useState("");

  function handleFiles(files) {
    const selectedFiles = Array.from(files || []);
    if (!selectedFiles.length) return;
    setSelectedSummary(
      selectedFiles.length === 1
        ? selectedFiles[0].name
        : `${selectedFiles.length} parquet files selected`,
    );
    onUpload(selectedFiles);
  }

  return (
    <section className="panel">
      <div className="panel-header flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-graphite-900">Upload</h2>
          <p className="mt-1 text-xs text-graphite-500">Parquet files are indexed dynamically after upload.</p>
        </div>
        {loading ? <Loader2 className="h-5 w-5 animate-spin text-signal-teal" /> : <FileUp className="h-5 w-5 text-signal-teal" />}
      </div>

      <button
        type="button"
        className={`m-4 flex min-h-40 w-[calc(100%-2rem)] flex-col items-center justify-center border border-dashed px-5 py-8 text-center transition ${
          isDragging ? "border-signal-teal bg-teal-50" : "border-graphite-200 bg-graphite-50 hover:border-graphite-500"
        }`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          handleFiles(event.dataTransfer.files);
        }}
        disabled={loading}
      >
        <UploadCloud className="mb-3 h-8 w-8 text-signal-teal" />
        <span className="text-sm font-semibold text-graphite-900">
          {selectedSummary || "Drop .parquet files or browse"}
        </span>
        <span className="mt-2 text-xs text-graphite-500">Multiple files are indexed as separate dynamic datasets.</span>
      </button>

      {loading ? (
        <div className="mx-4 mb-4">
          <div className="flex items-center justify-between text-xs font-semibold text-graphite-600">
            <span>Uploading and indexing locally</span>
            <span>{progress}%</span>
          </div>
          <div className="mt-2 h-2 bg-graphite-100">
            <div className="h-full bg-signal-teal transition-all" style={{ width: `${Math.max(8, progress)}%` }} />
          </div>
        </div>
      ) : selectedSummary ? (
        <div className="mx-4 mb-4 border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800">
          Upload accepted. Schema, embeddings, and Qdrant indexing run on the backend.
        </div>
      ) : null}

      <input
        ref={inputRef}
        type="file"
        accept=".parquet"
        multiple
        className="hidden"
        onChange={(event) => {
          handleFiles(event.target.files);
          event.target.value = "";
        }}
      />

      {error ? <div className="mx-4 mb-4 border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
    </section>
  );
}
