const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function parseResponse(response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || `Request failed with status ${response.status}`);
  }
  return body;
}

export async function uploadParquet(file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/files/upload`, {
    method: "POST",
    body: formData,
  });
  return parseResponse(response);
}

export async function uploadParquets(files) {
  const formData = new FormData();
  Array.from(files).forEach((file) => {
    formData.append("files", file);
  });
  const response = await fetch(`${API_BASE_URL}/api/files/upload-multiple`, {
    method: "POST",
    body: formData,
  });
  return parseResponse(response);
}

export async function listDatasets() {
  const response = await fetch(`${API_BASE_URL}/api/datasets`);
  return parseResponse(response);
}

export async function getDatasetSchema(datasetId) {
  const response = await fetch(`${API_BASE_URL}/api/datasets/${datasetId}/schema`);
  return parseResponse(response);
}

export async function askQuestion({ datasetId, question, limit = 100, exact = false }) {
  const response = await fetch(`${API_BASE_URL}/api/chat/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      dataset_id: datasetId,
      question,
      limit,
      exact,
    }),
  });
  return parseResponse(response);
}

export async function askAllDatasets({ question, datasetIds = null, limit = 100, exact = false }) {
  const response = await fetch(`${API_BASE_URL}/api/chat/query-all`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question,
      dataset_ids: datasetIds,
      limit,
      exact,
    }),
  });
  return parseResponse(response);
}

export async function deleteDataset(datasetId) {
  const response = await fetch(`${API_BASE_URL}/api/datasets/${datasetId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed with status ${response.status}`);
  }
  return null;
}
