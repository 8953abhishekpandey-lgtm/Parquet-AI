import { Check, Copy, Loader2, SendHorizonal, Sparkles, User } from "lucide-react";
import { useState, useRef, useEffect } from "react";

const SUGGESTIONS = [
  "Which category has the highest value?",
  "Count records in all uploaded datasets.",
  "Show the average values by region.",
  "Show abnormal or outlier rows.",
  "Compare monthly trends.",
];

export default function ChatPanel({ dataset, datasetCount, queryScope, onScopeChange, onAsk, loading, answer, aiReasoning, queryResponse }) {
  const [question, setQuestion] = useState("");
  const [exact, setExact] = useState(false);
  const [messages, setMessages] = useState([]);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // When a new answer arrives, add to message history
  useEffect(() => {
    if (answer && messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg.role === "user" && !messages.some((m) => m.role === "ai" && m.timestamp === lastMsg.timestamp)) {
        setMessages((prev) => [
          ...prev,
          {
            role: "ai",
            text: answer,
            timestamp: new Date().toISOString(),
            queryTime: queryResponse?.query_time_ms || queryResponse?._client_time_ms,
          },
        ]);
      }
    }
  }, [answer]);

  function submit(event) {
    event.preventDefault();
    if (!question.trim() || (!dataset && queryScope === "selected") || loading) return;
    setMessages((prev) => [
      ...prev,
      { role: "user", text: question.trim(), timestamp: new Date().toISOString() },
    ]);
    onAsk(question.trim(), exact);
    setQuestion("");
  }

  return (
    <section className="glass-panel animate-slide-up chat-panel" style={{ animationDelay: "0.15s" }} id="chat-panel">
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
            id="scope-selected-btn"
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
            id="scope-all-btn"
          >
            All uploads
          </button>
        </div>

        {/* Chat messages area */}
        <div className="chat-messages" id="chat-messages">
          {messages.length === 0 && !loading && (
            <div className="flex flex-col items-center justify-center py-6 text-center text-graphite-500">
              <Sparkles className="h-8 w-8 mb-2 text-graphite-600" />
              <p className="text-sm">Ask a question about your data</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <ChatBubble key={i} message={msg} />
          ))}

          {/* Skeleton loading */}
          {loading && (
            <div className="chat-bubble ai">
              <div className="chat-bubble-avatar ai">
                <Sparkles className="h-3.5 w-3.5" />
              </div>
              <div className="chat-bubble-content ai">
                <div className="shimmer-line w-3/4 mb-2" />
                <div className="shimmer-line w-1/2 mb-2" />
                <div className="shimmer-line w-2/3" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Question input */}
        <form onSubmit={submit} className="space-y-3">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={dataset || queryScope === "all" ? "Ask about your parquet data..." : "Upload a parquet file first"}
            className="chat-input"
            disabled={(!dataset && queryScope === "selected") || loading}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(e);
              }
            }}
            id="chat-input"
          />

          {/* Suggestions */}
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="suggestion-chip"
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
              id="chat-submit-btn"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <SendHorizonal className="h-4 w-4" />}
              Ask
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

function ChatBubble({ message }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";
  const time = new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  function handleCopy() {
    navigator.clipboard.writeText(message.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className={`chat-bubble ${isUser ? "user" : "ai"}`}>
      <div className={`chat-bubble-avatar ${isUser ? "user" : "ai"}`}>
        {isUser ? <User className="h-3.5 w-3.5" /> : <Sparkles className="h-3.5 w-3.5" />}
      </div>
      <div className={`chat-bubble-content ${isUser ? "user" : "ai"}`}>
        <p className="text-sm leading-relaxed">{message.text}</p>
        <div className="chat-bubble-meta">
          <span className="text-[10px] text-graphite-600">{time}</span>
          {!isUser && (
            <button
              type="button"
              className="chat-copy-btn"
              onClick={handleCopy}
              title="Copy response"
            >
              {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
            </button>
          )}
          {message.queryTime && (
            <span className="text-[10px] text-graphite-600">{message.queryTime}ms</span>
          )}
        </div>
      </div>
    </div>
  );
}
