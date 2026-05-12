import { Activity, BrainCircuit, DatabaseZap, RefreshCw } from "lucide-react";
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
    <main className="min-h-screen bg-graphite-50">
      <header className="border-b border-graphite-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-5">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center bg-graphite-900 text-white">
                <DatabaseZap className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-normal text-graphite-900">Chat with Dynamic Parquet Files</h1>
                <p className="mt-1 text-sm text-graphite-500">Local semantic retrieval, Qdrant vectors, rule-based SQL, DuckDB execution.</p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusPill tone="success">No cloud LLM</StatusPill>
            <StatusPill>Local embeddings</StatusPill>
            <StatusPill>Dynamic schema</StatusPill>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-4 px-4 py-4">
        {error ? (
          <div className="border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
          <aside className="space-y-4">
            <UploadDropzone onUpload={handleUpload} loading={uploading} error="" />
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
            <section className="panel">
              <div className="panel-header flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Activity className="h-5 w-5 text-signal-coral" />
                  <h2 className="text-sm font-semibold text-graphite-900">Pipeline</h2>
                </div>
                <button className="icon-button" type="button" onClick={() => refreshDatasets()} title="Refresh datasets">
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>
              <div className="space-y-2 p-4 text-sm text-graphite-700">
                <PipelineStep label="Parquet upload" active={Boolean(selectedDataset)} />
                <PipelineStep label="Schema detection" active={Boolean(selectedDataset)} />
                <PipelineStep label="Semantic metadata" active={Boolean(selectedDataset?.metadata_count)} />
                <PipelineStep label="Qdrant retrieval" active={Boolean(queryResponse)} />
                <PipelineStep label="DuckDB SQL" active={Boolean(queryResponse)} />
              </div>
            </section>
          </aside>

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

function PipelineStep({ label, active }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`flex h-6 w-6 items-center justify-center ${active ? "bg-signal-teal text-white" : "bg-graphite-100 text-graphite-500"}`}>
        <BrainCircuit className="h-3.5 w-3.5" />
      </span>
      <span className={active ? "font-semibold text-graphite-900" : "text-graphite-500"}>{label}</span>
    </div>
  );
}
