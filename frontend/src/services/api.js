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

export async function uploadParquets(files, onProgress) {
  const formData = new FormData();
  Array.from(files).forEach((file) => {
    formData.append("files", file);
  });

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/files/upload-multiple`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      let body = {};
      try {
        body = JSON.parse(xhr.responseText || "{}");
      } catch {
        body = {};
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body);
        return;
      }
      reject(new Error(body.detail || `Request failed with status ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error("Upload failed because the backend could not be reached."));
    xhr.send(formData);
  });
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
