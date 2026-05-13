import { Activity, BrainCircuit, DatabaseZap, RefreshCw, Shield, Zap } from "lucide-react";
import { useEffect, useState } from "react";

import ChatPanel from "../components/ChatPanel.jsx";
import DatasetSelector from "../components/DatasetSelector.jsx";
import DebugPanel from "../components/DebugPanel.jsx";
import ResultsTable from "../components/ResultsTable.jsx";
import SchemaExplorer from "../components/SchemaExplorer.jsx";
import StatusPill from "../components/StatusPill.jsx";
import UploadDropzone from "../components/UploadDropzone.jsx";
import { askAllDatasets, askQuestion, listDatasets, uploadParquets, deleteDataset } from "../services/api.js";

export default function AnalyticsWorkbench() {
  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [queryResponse, setQueryResponse] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [querying, setQuerying] = useState(false);
  const [queryScope, setQueryScope] = useState("selected");
  const [error, setError] = useState("");

  async function refreshDatasets() {
    const items = await listDatasets();
    setDatasets(items);
    if (!selectedDataset && items.length) {
      setSelectedDataset(items[0]);
    }
  }

  useEffect(() => {
    refreshDatasets().catch((err) => setError(err.message));
  }, []);

  async function handleUpload(files) {
    setError("");
    setUploading(true);
    setQueryResponse(null);
    try {
      const response = await uploadParquets(files);
      if (response.datasets.length) {
        setSelectedDataset(response.datasets[0]);
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
          limit: 100,
          exact,
        });
        setQueryResponse(allResponse);
        return;
      }
      const response = await askQuestion({
        datasetId: selectedDataset.dataset_id,
        question,
        limit: 100,
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

  return (
    <main className="min-h-screen">
      {/* ── Header ──────────────────────────────────────────── */}
      <header className="border-b border-glass-border" style={{ background: "rgba(255,255,255,0.02)" }}>
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-5">
          <div className="flex items-center gap-4">
            <div className="relative flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-signal-teal to-signal-cyan text-white shadow-glow-teal">
              <DatabaseZap className="h-6 w-6" />
              <div className="absolute -right-1 -top-1 h-3 w-3 rounded-full border-2 border-graphite-950 bg-emerald-400 animate-pulse" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white">
                Parquet AI Analytics
              </h1>
              <p className="mt-0.5 text-xs text-graphite-500">
                Secure RAG · Local Embeddings · Qdrant Vectors · Claude Reasoning · DuckDB Execution
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusPill tone="success">
              <Shield className="h-3 w-3" /> Enterprise Secure
            </StatusPill>
            <StatusPill tone="purple">
              <Zap className="h-3 w-3" /> Claude AI
            </StatusPill>
            <StatusPill tone="neutral">
              <BrainCircuit className="h-3 w-3" /> Local RAG
            </StatusPill>
          </div>
        </div>
      </header>

      {/* ── Main content ────────────────────────────────────── */}
      <div className="mx-auto max-w-7xl space-y-4 px-4 py-5">
        {error ? (
          <div
            className="animate-slide-down border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300"
            style={{ borderRadius: "10px" }}
          >
            <button className="float-right ml-3 text-red-400 hover:text-red-200" onClick={() => setError("")}>✕</button>
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
          {/* ── Sidebar ──────────────────────────────────── */}
          <aside className="space-y-4">
            <UploadDropzone onUpload={handleUpload} loading={uploading} />
            <DatasetSelector
              datasets={datasets}
              selectedId={selectedDataset?.dataset_id}
              onSelect={(dataset) => {
                setSelectedDataset(dataset);
                setQueryResponse(null);
              }}
              onDelete={async (id) => {
                await handleDeleteDataset(id);
              }}
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
                <PipelineStep step={3} label="Local embeddings" active={Boolean(selectedDataset?.metadata_count)} />
                <PipelineStep step={4} label="Qdrant vectors" active={Boolean(selectedDataset?.metadata_count)} />
                <PipelineStep step={5} label="Semantic retrieval" active={Boolean(queryResponse)} />
                <PipelineStep step={6} label="Claude reasoning" active={Boolean(queryResponse?.ai_reasoning)} />
                <PipelineStep step={7} label="DuckDB execution" active={Boolean(queryResponse)} />
              </div>
            </section>
          </aside>

          {/* ── Main panels ──────────────────────────────── */}
          <section className="space-y-4">
            <SchemaExplorer dataset={selectedDataset} />
            <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
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
              />
              <DebugPanel response={queryResponse} />
            </div>
            <ResultsTable response={queryResponse} />
          </section>
        </div>
      </div>
    </main>
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
