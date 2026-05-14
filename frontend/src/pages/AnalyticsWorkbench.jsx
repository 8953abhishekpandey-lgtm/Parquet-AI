import { Activity, BrainCircuit, DatabaseZap, RefreshCw, Shield, Zap } from "lucide-react";
import { useEffect, useState } from "react";

import ChatPanel from "../components/ChatPanel.jsx";
import DatasetSelector from "../components/DatasetSelector.jsx";
import DebugPanel from "../components/DebugPanel.jsx";
import ResultsTable from "../components/ResultsTable.jsx";
import SchemaExplorer from "../components/SchemaExplorer.jsx";
import Sidebar from "../components/Sidebar.jsx";
import StatusPill from "../components/StatusPill.jsx";
import UploadDropzone from "../components/UploadDropzone.jsx";
import { askAllDatasets, askQuestion, checkHealth, listDatasets, uploadParquets, deleteDataset } from "../services/api.js";

export default function AnalyticsWorkbench() {
  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [queryResponse, setQueryResponse] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [querying, setQuerying] = useState(false);
  const [queryScope, setQueryScope] = useState("selected");
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("upload");
  const [health, setHealth] = useState(null);
  const [lastUploadedDataset, setLastUploadedDataset] = useState(null);

  // Health check on mount + periodic
  useEffect(() => {
    checkHealth().then(setHealth);
    const interval = setInterval(() => checkHealth().then(setHealth), 30000);
    return () => clearInterval(interval);
  }, []);

  async function refreshDatasets() {
    try {
      const items = await listDatasets();
      setDatasets(items);
      if (!selectedDataset && items.length) {
        setSelectedDataset(items[0]);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    refreshDatasets();
  }, []);

  async function handleUpload(files) {
    setError("");
    setUploading(true);
    setQueryResponse(null);
    setLastUploadedDataset(null);
    try {
      const response = await uploadParquets(files);
      if (response.datasets.length) {
        setSelectedDataset(response.datasets[0]);
        setLastUploadedDataset(response.datasets[0]);
        setActiveTab("explorer");
      }
      if (response.errors.length) {
        const failed = response.errors.map((item) => `${item.filename}: ${item.error}`).join(" | ");
        setError(`Some files could not be processed. ${failed}`);
      }
      await refreshDatasets();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleAsk(question, exact = false) {
    if (queryScope === "selected" && !selectedDataset) return;
    if (queryScope === "all" && datasets.length === 0) return;
    setError("");
    setQuerying(true);
    try {
      if (queryScope === "all") {
        const allResponse = await askAllDatasets({
          question,
          datasetIds: datasets.map((dataset) => dataset.dataset_id),
          exact,
        });
        setQueryResponse(allResponse);
        return;
      }
      const response = await askQuestion({
        datasetId: selectedDataset.dataset_id,
        question,
        exact,
      });
      setQueryResponse(response);
    } catch (err) {
      setError(err.message);
    } finally {
      setQuerying(false);
    }
  }

  async function handleDeleteDataset(datasetId) {
    setError("");
    try {
      await deleteDataset(datasetId);
      setQueryResponse(null);
      await refreshDatasets();
      if (selectedDataset?.dataset_id === datasetId) {
        setSelectedDataset(null);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  // Determine what to show based on active tab
  function renderMainContent() {
    switch (activeTab) {
      case "upload":
        return (
          <div className="space-y-4">
            <UploadDropzone onUpload={handleUpload} loading={uploading} lastUploadedDataset={lastUploadedDataset} />
            <DatasetSelector
              datasets={datasets}
              selectedId={selectedDataset?.dataset_id}
              onSelect={(dataset) => {
                setSelectedDataset(dataset);
                setQueryResponse(null);
              }}
              onDelete={handleDeleteDataset}
            />
            {/* Pipeline status */}
            <section className="glass-panel animate-fade-in" style={{ animationDelay: "0.2s" }}>
              <div className="panel-header flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Activity className="h-5 w-5 text-signal-coral" />
                  <h2 className="text-sm font-semibold text-white">Pipeline</h2>
                </div>
                <button className="icon-button" type="button" onClick={() => refreshDatasets()} title="Refresh datasets">
                  <RefreshCw className="h-3.5 w-3.5" />
                </button>
              </div>
              <div className="space-y-1 p-4">
                <PipelineStep step={1} label="Parquet upload" active={Boolean(selectedDataset)} />
                <PipelineStep step={2} label="Schema detection" active={Boolean(selectedDataset)} />
                <PipelineStep step={3} label="BGE embeddings" active={Boolean(selectedDataset?.metadata_count)} />
                <PipelineStep step={4} label="Qdrant vectors" active={Boolean(selectedDataset?.metadata_count)} />
                <PipelineStep step={5} label="Semantic retrieval" active={Boolean(queryResponse)} />
                <PipelineStep step={6} label="Claude reasoning" active={Boolean(queryResponse?.ai_reasoning)} />
                <PipelineStep step={7} label="DuckDB execution" active={Boolean(queryResponse)} />
              </div>
            </section>
          </div>
        );
      case "explorer":
        return (
          <SchemaExplorer
            dataset={selectedDataset}
            datasets={datasets}
            onSelectDataset={(ds) => {
              setSelectedDataset(ds);
              setQueryResponse(null);
            }}
            onShowAll={() => {
              setActiveTab("chat");
              setQueryScope("all");
              handleAsk("show all data present in all files joined together");
            }}
          />
        );
      case "chat":
        return (
          <div className="space-y-4">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <ChatPanel
                dataset={selectedDataset}
                datasetCount={datasets.length}
                queryScope={queryScope}
                onScopeChange={(scope) => {
                  setQueryScope(scope);
                  setQueryResponse(null);
                }}
                onAsk={handleAsk}
                loading={querying}
                answer={queryResponse?.answer}
                aiReasoning={queryResponse?.ai_reasoning}
                queryResponse={queryResponse}
              />
              <DebugPanel response={queryResponse} />
            </div>
            <ResultsTable response={queryResponse} />
          </div>
        );
      case "debug":
        return (
          <div className="space-y-4">
            <DebugPanel response={queryResponse} />
            <ResultsTable response={queryResponse} />
          </div>
        );
      default:
        return null;
    }
  }

  return (
    <div className="app-layout">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} datasetCount={datasets.length} />

      <div className="app-main">
        {/* ── Top Navbar ──────────────────────────────────────────── */}
        <header className="top-navbar" id="top-navbar">
          <div className="flex items-center gap-4">
            <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-signal-teal to-signal-cyan text-white shadow-glow-teal">
              <DatabaseZap className="h-5 w-5" />
              <div className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-graphite-950 bg-emerald-400 animate-pulse" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white">
                Parquet AI Analytics
              </h1>
              <p className="text-[11px] text-graphite-500">
                Secure RAG · BGE Embeddings · Qdrant Vectors · Claude AI · DuckDB
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Connection status badges */}
            <StatusBadge label="Qdrant" ok={health?.services?.qdrant} />
            <StatusBadge label="DuckDB" ok={health?.services?.duckdb} />
            <StatusBadge label="Claude" ok={health?.services?.claude} />
          </div>
        </header>

        {/* ── Main content ────────────────────────────────────── */}
        <div className="app-content">
          {error ? (
            <div
              className="animate-slide-down border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300"
              style={{ borderRadius: "10px" }}
            >
              <button className="float-right ml-3 text-red-400 hover:text-red-200" onClick={() => setError("")}>✕</button>
              {error}
            </div>
          ) : null}

          {renderMainContent()}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ label, ok }) {
  return (
    <div className="status-badge" id={`status-${label.toLowerCase()}`}>
      <span className={`status-dot ${ok ? "online" : ok === false ? "offline" : "unknown"}`} />
      <span className="text-[11px] font-medium text-graphite-300">{label}</span>
    </div>
  );
}

function PipelineStep({ step, label, active }) {
  return (
    <div className="flex items-center gap-3 py-1">
      <span
        className={`flex h-6 w-6 items-center justify-center text-[10px] font-bold transition-all duration-300 ${
          active
            ? "bg-gradient-to-br from-signal-teal to-signal-cyan text-white shadow-glow"
            : "bg-glass-white text-graphite-600 border border-glass-border"
        }`}
        style={{ borderRadius: "6px" }}
      >
        {step}
      </span>
      <span className={`text-xs font-medium transition-colors ${active ? "text-graphite-200" : "text-graphite-600"}`}>
        {label}
      </span>
      {active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />}
    </div>
  );
}
