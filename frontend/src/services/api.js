/**
 * API Service — Centralized API client for Parquet AI Analytics.
 * 
 * All requests go through the Vite dev proxy to the FastAPI backend.
 * The API layer matches the new Text-to-SQL architecture endpoints.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

// ─── Helper ──────────────────────────────────────────────────
async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof body.detail === "string"
      ? body.detail
      : body.detail?.detail || body.detail?.error || `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return body;
}

// ─── Health ──────────────────────────────────────────────────
export async function checkHealth() {
  try {
    return await request("/api/health");
  } catch {
    return { status: "unreachable", duckdb: { status: "unhealthy" }, anthropic_api: { status: "error" }, files_loaded: 0 };
  }
}

// ─── Upload ──────────────────────────────────────────────────
export async function uploadFile(file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/upload`);
    
    if (onProgress) {
      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      });
    }

    xhr.onload = () => {
      try {
        const data = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(data);
        } else {
          reject(new Error(data.detail?.detail || data.detail?.error || "Upload failed"));
        }
      } catch {
        reject(new Error("Upload failed"));
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(formData);
  });
}

// ─── Files ───────────────────────────────────────────────────
export async function listFiles() {
  return request("/api/files");
}

export async function deleteFile(filename) {
  return request(`/api/files/${encodeURIComponent(filename)}`, { method: "DELETE" });
}

export async function reindexFile(filename) {
  return request(`/api/files/${encodeURIComponent(filename)}/reindex`, { method: "POST" });
}

// ─── Schema ──────────────────────────────────────────────────
export async function getAllSchemas() {
  return request("/api/schema");
}

export async function getFileSchema(filename) {
  return request(`/api/schema/${encodeURIComponent(filename)}`);
}

// ─── Query ───────────────────────────────────────────────────
export async function runQuery(question, selectedFiles = null) {
  const t0 = performance.now();
  const body = { question };
  if (selectedFiles && selectedFiles.length > 0) {
    body.selected_files = selectedFiles;
  }
  const data = await request("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  data._client_time_ms = Math.round(performance.now() - t0);
  return data;
}

// ─── Results / History ───────────────────────────────────────
export async function getQueryHistory() {
  return request("/api/results");
}

export async function getQueryDetail(entryId) {
  return request(`/api/results/${entryId}`);
}
