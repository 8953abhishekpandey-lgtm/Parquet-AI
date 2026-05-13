import { Loader2, SendHorizonal } from "lucide-react";
import { useState } from "react";

const SUGGESTIONS = [
  "Count records in all uploaded datasets.",
  "Show joined meter consumer location details.",
  "Which category has the highest value?",
  "Show abnormal consumption rows.",
  "Compare monthly trends by region.",
];

export default function ChatPanel({ dataset, datasetCount, queryScope, onScopeChange, onAsk, loading, answer }) {
  const [question, setQuestion] = useState("");
  const [exact, setExact] = useState(false);

  function submit(event) {
    event.preventDefault();
    if (!question.trim() || (!dataset && queryScope === "selected") || loading) return;
    onAsk(question.trim(), exact);
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2 className="text-sm font-semibold text-graphite-900">AI Query Chat</h2>
        <p className="mt-1 text-xs text-graphite-500">Questions are retrieved locally, then Claude receives only the minimal matched context.</p>
      </div>

      <div className="space-y-4 p-4">
        <div className="grid grid-cols-2 border border-graphite-200 bg-graphite-50 p-1 text-xs font-semibold">
          <button
            type="button"
            className={`px-3 py-2 transition ${queryScope === "selected" ? "bg-white text-graphite-900 shadow-sm" : "text-graphite-500 hover:text-graphite-900"}`}
            onClick={() => onScopeChange("selected")}
            disabled={loading}
          >
            Selected file
          </button>
          <button
            type="button"
            className={`px-3 py-2 transition ${queryScope === "all" ? "bg-white text-graphite-900 shadow-sm" : "text-graphite-500 hover:text-graphite-900"}`}
            onClick={() => onScopeChange("all")}
            disabled={loading || datasetCount === 0}
          >
            All uploads
          </button>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={dataset || queryScope === "all" ? "Ask about parquet data..." : "Upload a parquet file first"}
            className="min-h-28 w-full resize-y border border-graphite-200 bg-white px-3 py-3 text-sm text-graphite-900 outline-none transition placeholder:text-graphite-400 focus:border-signal-teal"
            disabled={(!dataset && queryScope === "selected") || loading}
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="border border-graphite-200 bg-graphite-50 px-2.5 py-1.5 text-xs font-semibold text-graphite-700 transition hover:border-graphite-500"
                  onClick={() => setQuestion(suggestion)}
                  disabled={(!dataset && queryScope === "selected") || loading}
                >
                  {suggestion}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-3">
              <label className="inline-flex items-center text-xs text-graphite-700">
                <input
                  type="checkbox"
                  className="mr-2"
                  checked={exact}
                  onChange={(e) => setExact(e.target.checked)}
                  disabled={loading}
                />
                Exact rows
              </label>
              <button type="submit" className="primary-button" disabled={(!dataset && queryScope === "selected") || loading || !question.trim()}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <SendHorizonal className="h-4 w-4" />}
                Ask
              </button>
            </div>
          </div>
        </form>

        {answer ? (
          <div className="border border-emerald-200 bg-emerald-50 px-4 py-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Answer</div>
            <p className="mt-1 text-sm text-graphite-900">{answer}</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
