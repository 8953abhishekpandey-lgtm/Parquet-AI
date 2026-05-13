import { FileUp, Loader2, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

export default function UploadDropzone({ onUpload, loading }) {
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
    <section className="glass-panel animate-fade-in">
      <div className="panel-header flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Upload</h2>
          <p className="mt-1 text-xs text-graphite-400">
            Parquet files are indexed locally after upload.
          </p>
        </div>
        {loading ? (
          <Loader2 className="h-5 w-5 animate-spin text-signal-cyan" />
        ) : (
          <FileUp className="h-5 w-5 text-signal-cyan" />
        )}
      </div>

      <button
        type="button"
        className={`m-4 flex min-h-36 w-[calc(100%-2rem)] flex-col items-center justify-center border-2 border-dashed px-5 py-8 text-center transition-all duration-300 ${
          isDragging
            ? "border-signal-cyan bg-signal-cyan/10 shadow-glow"
            : "border-glass-border bg-glass-white hover:border-graphite-400 hover:bg-glass-hover"
        }`}
        style={{ borderRadius: "10px" }}
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
        <div className={`mb-3 rounded-full p-3 ${isDragging ? "bg-signal-cyan/20" : "bg-glass-white"}`}>
          <UploadCloud className={`h-7 w-7 ${isDragging ? "text-signal-cyan animate-float" : "text-graphite-400"}`} />
        </div>
        <span className="text-sm font-semibold text-graphite-200">
          {loading
            ? "Processing..."
            : selectedSummary || "Drop .parquet files or browse"}
        </span>
        <span className="mt-2 text-xs text-graphite-500">
          Multiple files are indexed as separate dynamic datasets.
        </span>
      </button>

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
    </section>
  );
}
