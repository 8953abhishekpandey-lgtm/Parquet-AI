import { FileUp, Loader2, UploadCloud, Check, Database, Columns3, Cpu, Server } from "lucide-react";
import { useRef, useState, useEffect } from "react";

const STEPS = [
  { id: 1, label: "Upload", icon: UploadCloud },
  { id: 2, label: "Schema", icon: Columns3 },
  { id: 3, label: "Embed", icon: Cpu },
  { id: 4, label: "Index", icon: Server },
  { id: 5, label: "Ready", icon: Check },
];

export default function UploadDropzone({ onUpload, loading, lastUploadedDataset }) {
  const inputRef = useRef(null);
  const [isDragging, setDragging] = useState(false);
  const [selectedSummary, setSelectedSummary] = useState("");
  const [pipelineStep, setPipelineStep] = useState(0);

  // Animate pipeline steps during upload
  useEffect(() => {
    if (!loading) {
      if (lastUploadedDataset) setPipelineStep(5);
      return;
    }
    setPipelineStep(1);
    const timers = [
      setTimeout(() => setPipelineStep(2), 800),
      setTimeout(() => setPipelineStep(3), 2000),
      setTimeout(() => setPipelineStep(4), 4000),
    ];
    return () => timers.forEach(clearTimeout);
  }, [loading, lastUploadedDataset]);

  function handleFiles(files) {
    const selectedFiles = Array.from(files || []);
    if (!selectedFiles.length) return;
    const totalSize = selectedFiles.reduce((sum, f) => sum + f.size, 0);
    setSelectedSummary(
      selectedFiles.length === 1
        ? `${selectedFiles[0].name} (${formatBytes(totalSize)})`
        : `${selectedFiles.length} files (${formatBytes(totalSize)})`,
    );
    setPipelineStep(0);
    onUpload(selectedFiles);
  }

  return (
    <section className="glass-panel animate-fade-in" id="upload-section">
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
        className={`upload-dropzone ${isDragging ? "dragging" : ""}`}
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
        id="upload-dropzone-btn"
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

      {/* Processing Stepper */}
      {(loading || pipelineStep === 5) && (
        <div className="px-4 pb-4">
          <div className="pipeline-stepper">
            {STEPS.map((step) => {
              const Icon = step.icon;
              const done = pipelineStep >= step.id;
              const active = pipelineStep === step.id && loading;
              return (
                <div key={step.id} className={`pipeline-step ${done ? "done" : ""} ${active ? "active" : ""}`}>
                  <div className="pipeline-step-icon">
                    {done && !active ? <Check className="h-3 w-3" /> : <Icon className="h-3 w-3" />}
                  </div>
                  <span className="pipeline-step-label">{step.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Stat cards after upload */}
      {lastUploadedDataset && !loading && (
        <div className="grid grid-cols-3 gap-2 px-4 pb-4">
          <StatCard label="Rows" value={lastUploadedDataset.row_count?.toLocaleString()} icon={Database} />
          <StatCard label="Columns" value={lastUploadedDataset.columns?.length} icon={Columns3} />
          <StatCard label="Vectors" value={lastUploadedDataset.metadata_count} icon={Cpu} />
        </div>
      )}

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

function StatCard({ label, value, icon: Icon }) {
  return (
    <div className="stat-card">
      <Icon className="h-3.5 w-3.5 text-signal-cyan" />
      <span className="stat-card-value">{value ?? "—"}</span>
      <span className="stat-card-label">{label}</span>
    </div>
  );
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
