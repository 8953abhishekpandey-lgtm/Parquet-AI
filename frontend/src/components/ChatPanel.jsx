import { Loader2, SendHorizonal, Sparkles } from "lucide-react";
import { useState } from "react";

const SUGGESTIONS = [
  "Which category has the highest value?",
  "Count records in all uploaded datasets.",
  "Show the average values by region.",
  "Show abnormal or outlier rows.",
  "Compare monthly trends.",
];

export default function ChatPanel({ dataset, datasetCount, queryScope, onScopeChange, onAsk, loading, answer, aiReasoning }) {
  const [question, setQuestion] = useState("");
  const [exact, setExact] = useState(false);

  function submit(event) {
    event.preventDefault();
    if (!question.trim() || (!dataset && queryScope === "selected") || loading) return;
    onAsk(question.trim(), exact);
  }

  return (
    <section className="glass-panel animate-slide-up" style={{ animationDelay: "0.15s" }}>
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-signal-gold" />
          <h2 className="text-sm font-semibold text-white">AI Query Chat</h2>
        </div>
        <p className="mt-1 text-xs text-graphite-500">
          Natural language → local Qdrant retrieval → Claude reasoning → DuckDB execution
        </p>
      </div>

      <div className="space-y-4 p-4">
        {/* Scope toggle */}
        <div className="flex gap-1 rounded-lg bg-glass-white p-1">
          <button
            type="button"
            className={`flex-1 px-3 py-2 text-xs font-semibold transition-all duration-200 ${
              queryScope === "selected"
                ? "bg-signal-teal/20 text-teal-300 shadow-sm"
                : "text-graphite-500 hover:text-graphite-300"
            }`}
            style={{ borderRadius: "6px" }}
            onClick={() => onScopeChange("selected")}
            disabled={loading}
          >
            Selected file
          </button>
          <button
            type="button"
            className={`flex-1 px-3 py-2 text-xs font-semibold transition-all duration-200 ${
              queryScope === "all"
                ? "bg-signal-teal/20 text-teal-300 shadow-sm"
                : "text-graphite-500 hover:text-graphite-300"
            }`}
            style={{ borderRadius: "6px" }}
            onClick={() => onScopeChange("all")}
            disabled={loading || datasetCount === 0}
          >
            All uploads
          </button>
        </div>

        {/* Question input */}
        <form onSubmit={submit} className="space-y-3">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={dataset || queryScope === "all" ? "Ask about your parquet data..." : "Upload a parquet file first"}
            className="min-h-24 w-full resize-y border border-glass-border bg-glass-white px-4 py-3 text-sm text-graphite-200 outline-none transition-all duration-200 placeholder:text-graphite-600 focus:border-signal-teal/50 focus:shadow-glow-teal"
            style={{ borderRadius: "10px", backdropFilter: "blur(8px)" }}
            disabled={(!dataset && queryScope === "selected") || loading}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(e);
              }
            }}
          />

          {/* Suggestions */}
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="border border-glass-border bg-glass-white px-2.5 py-1.5 text-[11px] font-medium text-graphite-400 transition-all duration-200 hover:border-graphite-400 hover:text-graphite-200"
                style={{ borderRadius: "6px" }}
                onClick={() => setQuestion(suggestion)}
                disabled={(!dataset && queryScope === "selected") || loading}
              >
                {suggestion}
              </button>
            ))}
          </div>

          {/* Submit row */}
          <div className="flex items-center justify-between gap-3">
            <label className="inline-flex items-center gap-2 text-xs text-graphite-500 cursor-pointer select-none">
              <input
                type="checkbox"
                className="accent-signal-teal"
                checked={exact}
                onChange={(e) => setExact(e.target.checked)}
                disabled={loading}
              />
              Exact rows
            </label>
            <button
              type="submit"
              className="primary-button"
              disabled={(!dataset && queryScope === "selected") || loading || !question.trim()}
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <SendHorizonal className="h-4 w-4" />}
              Ask
            </button>
          </div>
        </form>

        {/* Answer display */}
        {answer ? (
          <div className="answer-card animate-slide-up px-5 py-4">
            <div className="mb-2 flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5 text-teal-400" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-teal-400">
                AI Answer
              </span>
            </div>
            <p className="text-sm leading-relaxed text-graphite-200">{answer}</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
