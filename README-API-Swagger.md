# README API Swagger Guide

This guide explains every API available in FastAPI Swagger, where each endpoint is implemented, where it is used in the frontend, how to test each API locally, and how to run an end-to-end parquet upload and question flow from Swagger.

## 1. What Swagger Is Used For

FastAPI automatically generates Swagger documentation from the backend route files and Pydantic models.

When the backend is running, open:

```text
http://127.0.0.1:8000/docs
```

Swagger lets you:

- Check backend health
- Upload one or many parquet files
- View uploaded datasets
- Inspect one dataset schema
- Ask a natural language question
- See exact request and response JSON
- Debug the backend without using the React UI

FastAPI also provides:

```text
OpenAPI JSON: http://127.0.0.1:8000/openapi.json
ReDoc:        http://127.0.0.1:8000/redoc
```

## 2. Start and Stop Commands

### Start Backend

Run from the project root:

```powershell
cd D:\MCP-SETUP-TEST
.\.venv\Scripts\Activate.ps1
$env:QDRANT_MODE="embedded"
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

If `.venv` does not exist yet:

```powershell
cd D:\MCP-SETUP-TEST
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### Start Frontend

Open a second PowerShell window:

```powershell
cd D:\MCP-SETUP-TEST\frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open the UI:

```text
http://127.0.0.1:5173
```

### Stop Backend and Frontend

Find running processes:

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess
```

Stop them:

```powershell
Stop-Process -Id <BACKEND_PID> -Force
Stop-Process -Id <FRONTEND_PID> -Force
```

Example:

```powershell
Stop-Process -Id 11140,20868 -Force
```

Verify ports are closed:

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
```

If there is no output, the servers are stopped.

## 3. Swagger API List

These are the app APIs shown in Swagger:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Check backend health and local AI settings |
| `POST` | `/api/files/upload` | Upload and index a parquet file |
| `POST` | `/api/files/upload-multiple` | Upload and index multiple parquet files |
| `GET` | `/api/datasets` | List uploaded parquet datasets |
| `GET` | `/api/datasets/{dataset_id}/schema` | Get schema details for one dataset |
| `POST` | `/api/chat/query` | Ask a natural language question about one dataset |
| `POST` | `/api/chat/query-all` | Ask a natural language question across uploaded datasets |

## 4. API Implementation Map

| API | Backend file | Main backend function | Frontend usage |
|---|---|---|---|
| `GET /health` | `backend/api/routes/health.py` | `health_check()` | Manual health check, not currently called by UI |
| `POST /api/files/upload` | `backend/api/routes/files.py` | `upload_parquet()` | `uploadParquet()` in `frontend/src/services/api.js` |
| `POST /api/files/upload-multiple` | `backend/api/routes/files.py` | `upload_multiple_parquet()` | `uploadParquets()` in `frontend/src/services/api.js` |
| `GET /api/datasets` | `backend/api/routes/files.py` | `list_datasets()` | `listDatasets()` in `frontend/src/services/api.js` |
| `GET /api/datasets/{dataset_id}/schema` | `backend/api/routes/files.py` | `get_dataset_schema()` | `getDatasetSchema()` exists in API service for refresh/debug |
| `POST /api/chat/query` | `backend/api/routes/query.py` | `query_dataset()` | `askQuestion()` in `frontend/src/services/api.js` |
| `POST /api/chat/query-all` | `backend/api/routes/query.py` | `query_all_datasets()` | `askAllDatasets()` in `frontend/src/services/api.js` |

## 5. API Details

## `GET /health`

### Purpose

Checks whether the backend is running and shows the active local AI/vector settings.

### Backend Code

File:

```text
backend/api/routes/health.py
```

Function:

```python
@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "embedding_model": settings.embedding_model,
        "qdrant_mode": settings.qdrant_mode,
        "qdrant_url": settings.qdrant_url,
    }
```

### PowerShell Test

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "app": "Chat with Dynamic Parquet Files",
  "embedding_model": "all-MiniLM-L6-v2",
  "qdrant_mode": "embedded",
  "qdrant_url": "http://localhost:6333"
}
```

### Swagger Test

1. Open `http://127.0.0.1:8000/docs`
2. Expand `GET /health`
3. Click `Try it out`
4. Click `Execute`
5. Confirm response code is `200`

## `POST /api/files/upload`

### Purpose

Uploads one parquet file, saves it locally, detects schema dynamically, generates semantic metadata, creates local embeddings, and stores vectors in Qdrant.

### Backend Code

Route file:

```text
backend/api/routes/files.py
```

Pipeline file:

```text
backend/services/pipeline.py
```

Important flow:

```python
dataset = await pipeline.ingest_upload(file)
```

`ingest_upload()` then calls:

| Step | File |
|---|---|
| Save file | `backend/services/file_service.py` |
| Profile parquet | `backend/duckdb/client.py` |
| Optional Spark schema | `backend/spark/session.py` |
| Build semantic metadata | `backend/metadata/generator.py` |
| Generate local embeddings | `backend/embeddings/local_model.py` |
| Store Qdrant vectors | `backend/qdrant/vector_store.py` |
| Save manifest JSON | `backend/services/file_service.py` |

### Frontend Usage

Frontend API function:

```text
frontend/src/services/api.js
```

```js
export async function uploadParquet(file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/files/upload`, {
    method: "POST",
    body: formData,
  });
  return parseResponse(response);
}
```

Called from:

```text
frontend/src/pages/AnalyticsWorkbench.jsx
frontend/src/components/UploadDropzone.jsx
```

### Swagger Test

1. Open `http://127.0.0.1:8000/docs`
2. Expand `POST /api/files/upload`
3. Click `Try it out`
4. Click `Choose File`
5. Select any real `.parquet` file from your machine
6. Click `Execute`
7. Confirm response code is `200`
8. Copy `dataset.dataset_id` from the response

Example response shape:

```json
{
  "dataset": {
    "dataset_id": "a_unique_id",
    "filename": "your_file.parquet",
    "stored_path": "D:\\MCP-SETUP-TEST\\uploads\\a_unique_id_your_file.parquet",
    "uploaded_at": "2026-05-12T...",
    "row_count": 1000,
    "columns": [
      {
        "name": "Region",
        "dtype": "VARCHAR",
        "nullable": true,
        "normalized_name": "region",
        "sample_values": ["North", "South"],
        "stats": {
          "null_count": 0,
          "distinct_count": 4
        },
        "semantic_text": "Column Region..."
      }
    ],
    "sample_rows": [],
    "spark_schema": {},
    "metadata_count": 10
  }
}
```

### PowerShell Upload Test

Use your own parquet path:

```powershell
$PARQUET_PATH = "D:\path\to\your-file.parquet"
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/files/upload" `
  -Method Post `
  -Form @{ file = Get-Item $PARQUET_PATH }
```

## `POST /api/files/upload-multiple`

### Purpose

Uploads one or many parquet files in a single request. Each file is processed as an independent dataset with its own:

- dataset id
- saved parquet path
- schema manifest
- semantic metadata documents
- Qdrant vectors

If one file fails, the other files can still succeed. The response contains both `datasets` and `errors`.

### Backend Code

Route file:

```text
backend/api/routes/files.py
```

Function:

```python
@router.post("/files/upload-multiple", response_model=MultiUploadResponse)
async def upload_multiple_parquet(files: list[UploadFile] = File(...)) -> MultiUploadResponse:
    ...
```

Response models:

```text
backend/models.py
```

```python
class UploadFailure(BaseModel):
    filename: str
    error: str

class MultiUploadResponse(BaseModel):
    datasets: list[DatasetManifest] = Field(default_factory=list)
    errors: list[UploadFailure] = Field(default_factory=list)
```

### Frontend Usage

Frontend API function:

```text
frontend/src/services/api.js
```

```js
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
```

Called from:

```text
frontend/src/pages/AnalyticsWorkbench.jsx
frontend/src/components/UploadDropzone.jsx
```

### Swagger Test

1. Open `http://127.0.0.1:8000/docs`
2. Expand `POST /api/files/upload-multiple`
3. Click `Try it out`
4. Under `files`, click `Choose Files`
5. Select multiple `.parquet` files
6. Click `Execute`
7. Confirm response code is `200`
8. Review `datasets` for successful files
9. Review `errors` for failed files

Example response shape:

```json
{
  "datasets": [
    {
      "dataset_id": "first_dataset_id",
      "filename": "first.parquet",
      "row_count": 1000,
      "columns": [],
      "sample_rows": [],
      "spark_schema": {},
      "metadata_count": 8
    },
    {
      "dataset_id": "second_dataset_id",
      "filename": "second.parquet",
      "row_count": 2500,
      "columns": [],
      "sample_rows": [],
      "spark_schema": {},
      "metadata_count": 12
    }
  ],
  "errors": []
}
```

### PowerShell Multi-Upload Test

Use `curl.exe` because it handles repeated multipart field names clearly:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/files/upload-multiple" `
  -F "files=@D:\path\to\first.parquet" `
  -F "files=@D:\path\to\second.parquet"
```

## `GET /api/datasets`

### Purpose

Lists all uploaded dataset manifests saved under:

```text
backend/storage/datasets/
```

### Backend Code

File:

```text
backend/api/routes/files.py
```

Function:

```python
@router.get("/datasets", response_model=list[DatasetManifest])
def list_datasets() -> list[DatasetManifest]:
    return pipeline.list_datasets()
```

### Frontend Usage

Function:

```text
frontend/src/services/api.js
```

```js
export async function listDatasets() {
  const response = await fetch(`${API_BASE_URL}/api/datasets`);
  return parseResponse(response);
}
```

Used by:

```text
frontend/src/pages/AnalyticsWorkbench.jsx
frontend/src/components/DatasetSelector.jsx
```

### Swagger Test

1. Open `http://127.0.0.1:8000/docs`
2. Expand `GET /api/datasets`
3. Click `Try it out`
4. Click `Execute`
5. Confirm uploaded datasets are returned

### PowerShell Test

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/datasets
```

## `GET /api/datasets/{dataset_id}/schema`

### Purpose

Returns full schema and metadata for one uploaded dataset.

Use this when:

- You want to inspect one dataset by id
- You want to confirm schema detection worked
- You want to debug a frontend dataset selection problem
- You want to verify column profiles and sample rows

### Backend Code

File:

```text
backend/api/routes/files.py
```

Function:

```python
@router.get("/datasets/{dataset_id}/schema", response_model=DatasetManifest)
def get_dataset_schema(dataset_id: str) -> DatasetManifest:
    return pipeline.get_dataset(dataset_id)
```

### Frontend Usage

Function exists in:

```text
frontend/src/services/api.js
```

```js
export async function getDatasetSchema(datasetId) {
  const response = await fetch(`${API_BASE_URL}/api/datasets/${datasetId}/schema`);
  return parseResponse(response);
}
```

The current UI usually already has the manifest from upload/list calls, but this function is available for refresh and debugging.

### Swagger Test

1. Upload a parquet file first
2. Copy the `dataset_id`
3. Expand `GET /api/datasets/{dataset_id}/schema`
4. Click `Try it out`
5. Paste the dataset id
6. Click `Execute`
7. Confirm response code is `200`

### PowerShell Test

```powershell
$DATASET_ID = "paste_dataset_id_here"
Invoke-RestMethod "http://127.0.0.1:8000/api/datasets/$DATASET_ID/schema"
```

## `POST /api/chat/query`

### Purpose

Asks a natural language question about one uploaded parquet dataset.

The backend will:

1. Load the dataset manifest
2. Embed the question locally
3. Search Qdrant for relevant metadata
4. Pick metric and grouping columns dynamically
5. Generate SQL with rules
6. Execute SQL in DuckDB
7. Return answer, debug metadata, SQL, and result rows

### Backend Code

Route file:

```text
backend/api/routes/query.py
```

Main pipeline:

```text
backend/services/pipeline.py
```

SQL rules:

```text
backend/sql_generation/rules.py
```

### Frontend Usage

Function:

```text
frontend/src/services/api.js
```

```js
export async function askQuestion({ datasetId, question, limit = 100 }) {
  const response = await fetch(`${API_BASE_URL}/api/chat/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      dataset_id: datasetId,
      question,
      limit,
    }),
  });
  return parseResponse(response);
}
```

Used by:

```text
frontend/src/pages/AnalyticsWorkbench.jsx
frontend/src/components/ChatPanel.jsx
frontend/src/components/DebugPanel.jsx
frontend/src/components/ResultsTable.jsx
```

### Request Body

```json
{
  "dataset_id": "paste_dataset_id_here",
  "question": "How many records are in this file?",
  "limit": 100
}
```

### Safe First Question

This works for any uploaded parquet file because it does not depend on a specific column:

```text
How many records are in this file?
```

### Analytics Questions

These depend on your file having matching numeric/category/date columns:

```text
Which region has the highest sales?
What is the average consumption?
Show monthly revenue trend.
Find abnormal meter readings.
Count records by category.
```

### Swagger Test

1. Upload a parquet file first
2. Copy `dataset_id`
3. Expand `POST /api/chat/query`
4. Click `Try it out`
5. Paste this body:

```json
{
  "dataset_id": "paste_dataset_id_here",
  "question": "How many records are in this file?",
  "limit": 100
}
```

6. Click `Execute`
7. Confirm response code is `200`
8. Review:
   - `answer`
   - `semantic_matches`
   - `generated_sql.sql`
   - `rows`

### Example Response Shape

```json
{
  "dataset_id": "a_unique_id",
  "question": "How many records are in this file?",
  "answer": "The uploaded parquet contains 1,000 records.",
  "semantic_matches": [
    {
      "score": 0.52,
      "kind": "dataset",
      "column_name": null,
      "text": "Parquet file your_file.parquet...",
      "payload": {}
    }
  ],
  "generated_sql": {
    "sql": "SELECT COUNT(*) AS record_count FROM dataset",
    "intent": "count",
    "aggregation": "COUNT",
    "metric_column": null,
    "group_by_columns": [],
    "selected_columns": [],
    "limit": 100,
    "explanation": "Counts all records in the uploaded parquet file."
  },
  "columns": ["record_count"],
  "rows": [
    {
      "record_count": 1000
    }
  ],
  "row_count": 1
}
```

### PowerShell Test

```powershell
$DATASET_ID = "paste_dataset_id_here"
$BODY = @{
  dataset_id = $DATASET_ID
  question = "How many records are in this file?"
  limit = 100
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/chat/query" `
  -Method Post `
  -ContentType "application/json" `
  -Body $BODY
```

## `POST /api/chat/query-all`

### Purpose

Asks a natural language question across all uploaded parquet datasets, or across a supplied subset of dataset ids.

Use this when your answer may require more than one parquet file, such as:

```text
Show joined meter, consumer, material, location, and HES details.
Which meter type has the highest usage?
Compare monthly trends by region across uploaded files.
Count rows in all uploaded datasets.
```

The backend does not hardcode table names. It dynamically:

- searches Qdrant metadata across uploaded datasets
- creates one DuckDB view per parquet
- infers joins from column relationships
- generates SQL with joins, grouping, ordering, trends, or outlier logic
- executes the SQL locally in DuckDB

### Backend Code

Route file:

```text
backend/api/routes/query.py
```

Main pipeline:

```text
backend/services/pipeline.py
```

Multi-table SQL rules:

```text
backend/sql_generation/multi_table_rules.py
```

DuckDB multi-view execution:

```text
backend/duckdb/client.py
```

### Request Body

Query all uploaded datasets:

```json
{
  "question": "Show joined meter consumer location details from all uploaded files",
  "dataset_ids": null,
  "limit": 100
}
```

Query only selected datasets:

```json
{
  "question": "Show joined meter consumer location details",
  "dataset_ids": [
    "first_dataset_id",
    "second_dataset_id"
  ],
  "limit": 100
}
```

### Swagger Test

1. Upload multiple parquet files first with `POST /api/files/upload-multiple`
2. Expand `POST /api/chat/query-all`
3. Click `Try it out`
4. Use this safe test:

```json
{
  "question": "Count records in all uploaded datasets",
  "dataset_ids": null,
  "limit": 100
}
```

5. Click `Execute`
6. Confirm `generated_sql.sql` contains `UNION ALL`
7. Confirm result rows show one count per uploaded parquet

### Joined Query Test

After uploading related files, try:

```json
{
  "question": "Show joined meter consumer material location and HES details from all uploaded files",
  "dataset_ids": null,
  "limit": 100
}
```

Review:

- `semantic_matches`: which files and columns Qdrant selected
- `generated_sql.sql`: inferred joins
- `rows`: joined result rows

### Join Inference Patterns

The rule engine looks for relationship patterns like:

| Pattern | Example |
|---|---|
| foreign key name to table id | `EquipmentId` -> `Equipment.ID` |
| location link id | `DeviceLocationId` -> `Device_Location.ID` |
| consumer link id | `ConsumerID` -> `Consumer.ID` |
| short prefix id | `HES_ID` -> `HES_MASTER.ID` |
| lookup/master utility id | `Material_ID` -> `Material_Master.Utility_ID` |
| same non-generic column | matching business keys across files |

### PowerShell Test

```powershell
$BODY = @{
  question = "Count records in all uploaded datasets"
  dataset_ids = $null
  limit = 100
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/chat/query-all" `
  -Method Post `
  -ContentType "application/json" `
  -Body $BODY
```

## 6. End-to-End Swagger Test

This is the recommended local test flow.

### Step 1: Start Backend

```powershell
cd D:\MCP-SETUP-TEST
.\.venv\Scripts\Activate.ps1
$env:QDRANT_MODE="embedded"
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### Step 2: Open Swagger

```text
http://127.0.0.1:8000/docs
```

### Step 3: Check Health

Use:

```text
GET /health
```

Expected:

```text
200 OK
```

and:

```json
{
  "status": "ok"
}
```

### Step 4: Upload Parquet Files

For one file, use:

```text
POST /api/files/upload
```

For multiple files, use:

```text
POST /api/files/upload-multiple
```

Select one or more real `.parquet` files from your machine.

After execution:

- Confirm `200 OK`
- Copy `dataset.dataset_id` from single upload, or `datasets[0].dataset_id` from multi-upload
- Confirm columns are present
- Confirm row count is present

### Step 5: List Datasets

Use:

```text
GET /api/datasets
```

Confirm the uploaded file appears.

### Step 6: Inspect Schema

Use:

```text
GET /api/datasets/{dataset_id}/schema
```

Paste the copied dataset id.

Confirm:

- `columns`
- `dtype`
- `sample_values`
- `stats`
- `sample_rows`
- `metadata_count`

### Step 7: Ask a Question

Use:

```text
POST /api/chat/query
```

Paste:

```json
{
  "dataset_id": "paste_dataset_id_here",
  "question": "How many records are in this file?",
  "limit": 100
}
```

Confirm:

- `answer` is returned
- `generated_sql.sql` is visible
- `rows` contains a result
- `semantic_matches` contains Qdrant matches

### Step 8: Try a Data-Specific Question

Look at your schema response and identify:

- A numeric column, such as amount, sales, usage, consumption, revenue
- A category column, such as region, city, type, category

Then ask:

```json
{
  "dataset_id": "paste_dataset_id_here",
  "question": "Which category has the highest amount?",
  "limit": 100
}
```

Change `category` and `amount` to words that match your file.

### Step 9: Try All-Datasets Query

Use:

```text
POST /api/chat/query-all
```

Paste:

```json
{
  "question": "Count records in all uploaded datasets",
  "dataset_ids": null,
  "limit": 100
}
```

For related parquet files, try:

```json
{
  "question": "Show joined meter consumer material location and HES details from all uploaded files",
  "dataset_ids": null,
  "limit": 100
}
```

## 7. End-to-End PowerShell Test

This tests the same API flow without Swagger UI.

### Step 1: Health

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

### Step 2: Upload One File

```powershell
$PARQUET_PATH = "D:\path\to\your-file.parquet"
$UPLOAD = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/files/upload" `
  -Method Post `
  -Form @{ file = Get-Item $PARQUET_PATH }

$UPLOAD.dataset.dataset_id
```

### Optional: Upload Multiple Files

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/files/upload-multiple" `
  -F "files=@D:\path\to\first.parquet" `
  -F "files=@D:\path\to\second.parquet"
```

If using the multi-upload response in PowerShell, save the first successful dataset id:

```powershell
$UPLOAD = curl.exe -s -X POST "http://127.0.0.1:8000/api/files/upload-multiple" `
  -F "files=@D:\path\to\first.parquet" `
  -F "files=@D:\path\to\second.parquet" | ConvertFrom-Json

$DATASET_ID = $UPLOAD.datasets[0].dataset_id
```

### Step 3: Save Dataset Id

For the single-upload response:

```powershell
$DATASET_ID = $UPLOAD.dataset.dataset_id
```

For the multi-upload response:

```powershell
$DATASET_ID = $UPLOAD.datasets[0].dataset_id
```

### Step 4: List Datasets

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/datasets
```

### Step 5: Inspect Schema

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/datasets/$DATASET_ID/schema"
```

### Step 6: Query

```powershell
$BODY = @{
  dataset_id = $DATASET_ID
  question = "How many records are in this file?"
  limit = 100
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/chat/query" `
  -Method Post `
  -ContentType "application/json" `
  -Body $BODY
```

## 8. How API Responses Connect to the UI

### Upload Responses

`POST /api/files/upload` returns a dataset manifest.

`POST /api/files/upload-multiple` returns:

- `datasets`: successful dataset manifests
- `errors`: files that failed validation or processing

The UI uses it to populate:

- Dataset selector
- Schema explorer
- Sample rows
- Pipeline status

Frontend path:

```text
AnalyticsWorkbench.jsx
  -> handleUpload()
  -> uploadParquets()
  -> setSelectedDataset(response.datasets[0])
```

### Dataset List Response

`GET /api/datasets` returns all manifests.

The UI uses it in:

```text
DatasetSelector.jsx
```

### Query Response

`POST /api/chat/query` returns:

- `answer`
- `semantic_matches`
- `generated_sql`
- `columns`
- `rows`

The UI maps them to:

| Response field | UI component |
|---|---|
| `answer` | `ChatPanel.jsx` |
| `semantic_matches` | `DebugPanel.jsx` |
| `generated_sql` | `DebugPanel.jsx` |
| `columns` | `ResultsTable.jsx` |
| `rows` | `ResultsTable.jsx` |

## 9. Health Checks

### Backend Health

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Success means:

- FastAPI is running
- settings loaded
- backend app imported correctly

It does not upload a file or test embeddings by itself.

### Swagger Health

Open:

```text
http://127.0.0.1:8000/docs
```

If Swagger loads, FastAPI docs are active.

### Frontend Health

```powershell
Invoke-WebRequest http://127.0.0.1:5173 -UseBasicParsing
```

Success code:

```text
200 OK
```

### Qdrant Embedded Health

Embedded Qdrant does not expose a browser dashboard.

Check local storage exists after upload:

```text
backend/storage/qdrant/
```

Also check that upload response has:

```json
"metadata_count": 1
```

or higher.

### Qdrant Server Health

Only if using Docker/server mode:

```text
http://localhost:6333/dashboard
```

or:

```powershell
Invoke-RestMethod http://localhost:6333/collections
```

## 10. Common Swagger/API Errors

### `404 Not Found`

Cause:

- Wrong URL
- Wrong method
- Opened backend root `/`

Correct URLs:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/health
http://127.0.0.1:8000/api/datasets
```

### `422 Validation Error`

Cause:

- Missing required request field
- Wrong JSON key
- Wrong type

For query, use exactly:

```json
{
  "dataset_id": "id_here",
  "question": "How many records are in this file?",
  "limit": 100
}
```

Do not use camelCase in Swagger:

```json
{
  "datasetId": "wrong"
}
```

Use:

```json
{
  "dataset_id": "correct"
}
```

### `400 Only .parquet files are supported`

Cause:

The uploaded file is not named with `.parquet`.

Fix:

Upload a valid parquet file.

### `404 Dataset not found`

Cause:

The dataset id is wrong or the manifest JSON does not exist.

Fix:

Call:

```text
GET /api/datasets
```

Copy the correct `dataset_id`.

### `503 Qdrant is not reachable`

Cause:

Qdrant server mode is selected but Qdrant is not running, or embedded storage has a problem.

Fix for embedded:

```powershell
$env:QDRANT_MODE="embedded"
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Fix for server mode:

```powershell
$env:QDRANT_MODE="server"
docker compose up -d qdrant
```

### `500 Upload failed`

Common causes:

- Corrupt parquet file
- DuckDB cannot read the file
- Model loading failed
- Storage folder permission issue

Check backend terminal logs first. Then test the file directly:

```powershell
python -c "import duckdb; print(duckdb.sql(\"SELECT COUNT(*) FROM read_parquet('D:/path/to/file.parquet')\").fetchall())"
```

### `500 Query failed`

Common causes:

- Generated SQL is invalid for the uploaded schema
- Dataset file was deleted from `uploads/`
- Column type cannot be aggregated

Debug steps:

1. Check `generated_sql.sql` in response if available
2. Check `backend/sql_generation/rules.py`
3. Confirm the parquet file still exists in `uploads/`
4. Use `GET /api/datasets/{dataset_id}/schema`
5. Ask a simpler question:

```text
How many records are in this file?
```

## 11. Recommended API Testing Order

Always test in this order:

```text
1. GET /health
2. POST /api/files/upload or POST /api/files/upload-multiple
3. GET /api/datasets
4. GET /api/datasets/{dataset_id}/schema
5. POST /api/chat/query
6. POST /api/chat/query-all
```

This order makes debugging easier because each API depends on the previous one.

## 12. Quick Command Checklist

Backend:

```powershell
cd D:\MCP-SETUP-TEST
.\.venv\Scripts\Activate.ps1
$env:QDRANT_MODE="embedded"
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd D:\MCP-SETUP-TEST\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

Health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Stop servers:

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object OwningProcess
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object OwningProcess
Stop-Process -Id <PID1>,<PID2> -Force
```
