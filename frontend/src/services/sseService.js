/**
 * SSE Service — Server-Sent Events handler for streaming query pipeline.
 *
 * Connects to GET /api/query/stream and emits step-by-step progress events
 * so the frontend can show real-time pipeline visualization.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

/**
 * Stream a query through the SSE pipeline endpoint.
 *
 * @param {string} question - The user's natural language question
 * @param {string[]|null} selectedFiles - Optional file filter
 * @param {object} callbacks - Event handlers:
 *   - onStep(stepData)   — called for each pipeline step
 *   - onComplete(result) — called with the final query result
 *   - onError(error)     — called on any error
 * @returns {function} abort — call to cancel the stream
 */
export function streamQuery(question, selectedFiles, { onStep, onComplete, onError }) {
  const params = new URLSearchParams({ question });
  if (selectedFiles && selectedFiles.length > 0) {
    params.set("selected_files", selectedFiles.join(","));
  }

  const url = `${API_BASE}/api/query/stream?${params.toString()}`;
  const eventSource = new EventSource(url);

  eventSource.addEventListener("step", (e) => {
    try {
      const data = JSON.parse(e.data);
      onStep?.(data);
    } catch (err) {
      console.warn("SSE step parse error:", err);
    }
  });

  eventSource.addEventListener("complete", (e) => {
    try {
      const data = JSON.parse(e.data);
      onComplete?.(data);
    } catch (err) {
      console.warn("SSE complete parse error:", err);
    }
    eventSource.close();
  });

  eventSource.addEventListener("error", (e) => {
    // EventSource native error (connection lost, etc.)
    if (eventSource.readyState === EventSource.CLOSED) return;
    try {
      if (e.data) {
        const data = JSON.parse(e.data);
        onError?.(data.error || "Stream error");
      } else {
        onError?.("Connection lost");
      }
    } catch {
      onError?.("Stream error");
    }
    eventSource.close();
  });

  // Return abort function
  return () => {
    eventSource.close();
  };
}
