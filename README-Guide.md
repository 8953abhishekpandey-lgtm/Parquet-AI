# README Guide: Chat with Dynamic Parquet Files

This guide explains how the application is structured, how each file connects to the rest of the system, how the local AI flow works, and how to debug common errors without relying on an external AI service.

## 1. Application Goal

The app lets a user upload one or many parquet files from the browser and ask natural language questions about any selected uploaded file.

The system is fully local:

- No OpenAI API
- No Ollama
- No cloud LLM
- No paid AI service
- No hardcoded parquet file
- No hardcoded schema

The local intelligence comes from:

- `sentence-transformers` for embeddings
- `all-MiniLM-L6-v2` as the embedding model
- Qdrant for vector search
- DuckDB for SQL execution
- Rule-based SQL generation for explainable analytics

## 2. High-Level Flow

```text
User uploads one or many parquet files
  -> FastAPI saves file in uploads/
  -> DuckDB reads schema, row count, samples, stats
  -> Spark tries local schema inspection if available
  -> Metadata generator creates semantic text per dataset/column/sample row
  -> sentence-transformers creates embeddings locally
  -> Qdrant stores vectors and metadata
  -> User asks a question
  -> Question is embedded locally
  -> Qdrant finds relevant metadata and columns
  -> Rule engine creates SQL dynamically
  -> DuckDB executes SQL against uploaded parquet
  -> Template response and result table are returned to React
```

## 3. Project Structure

```text
D:\MCP-SETUP-TEST
  README.md
  README-Guide.md
  requirements.txt
  docker-compose.yml
  .env.example
  .gitignore
  uploads/
  backend/
  frontend/
```

### Root Files

| File | Purpose |
|---|---|
| `README.md` | Quick setup, commands, API summary, demo flow |
| `README-Guide.md` | Detailed architecture, file explanations, troubleshooting |
| `requirements.txt` | Python backend dependencies |
| `docker-compose.yml` | Optional standalone Qdrant server |
| `.env.example` | Environment variable examples |
| `.gitignore` | Ignores uploads, storage, node modules, virtual envs, generated files |

### Important Generated Runtime Folders

| Folder | Purpose |
|---|---|
| `uploads/` | Stores user-uploaded parquet files |
| `backend/storage/datasets/` | Stores dataset schema manifests as JSON |
| `backend/storage/qdrant/` | Embedded Qdrant local vector database |
| `frontend/node_modules/` | Installed frontend packages |
| `frontend/dist/` | Production frontend build output |

These runtime folders should not be committed.

## 4. Backend Structure

```text
backend/
  main.py
  models.py
  api/
    routes/
      health.py
      files.py
      query.py
  core/
    config.py
  services/
    file_service.py
    pipeline.py
    response_builder.py
  duckdb/
    client.py
  spark/
    session.py
  metadata/
    generator.py
  embeddings/
    local_model.py
  qdrant/
    vector_store.py
  retrieval/
    semantic_retriever.py
  sql_generation/
    rules.py
```

## 5. Backend File-by-File Explanation

### `backend/main.py`

Creates the FastAPI app.

Responsibilities:

- Defines app title and description
- Enables CORS for React dev server
- Registers API route modules
- Creates required local folders on startup

Important code idea:

```python
app.include_router(health.router)
app.include_router(files.router)
app.include_router(query.router)
```

This connects all API endpoints to the FastAPI server.

### `backend/models.py`

Defines all request and response models using Pydantic.

Important models:

| Model | Meaning |
|---|---|
| `ColumnProfile` | One column's type, samples, stats, semantic text |
| `DatasetManifest` | Complete uploaded parquet metadata |
| `QueryRequest` | User question payload |
| `SemanticMatch` | One Qdrant search result |
| `GeneratedSQL` | SQL and explanation produced by rule engine |
| `QueryResponse` | Final response returned to frontend |

Why this matters:

FastAPI uses these models to validate data and generate Swagger docs at:

```text
http://127.0.0.1:8000/docs
```

### `backend/core/config.py`

Central settings file.

Important settings:

```python
qdrant_mode = "embedded"
qdrant_url = "http://localhost:6333"
qdrant_collection = "parquet_semantic_metadata"
embedding_model = "all-MiniLM-L6-v2"
sample_rows = 20
query_row_limit = 100
```

Default Qdrant mode is embedded. That means the app can use Qdrant locally without Docker.

If you want Docker Qdrant:

```powershell
$env:QDRANT_MODE="server"
docker compose up -d qdrant
```

### `backend/api/routes/health.py`

Endpoint:

```text
GET /health
```

Use it to check if the backend is alive.

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

### `backend/api/routes/files.py`

Endpoints:

```text
POST /api/files/upload
POST /api/files/upload-multiple
GET /api/datasets
GET /api/datasets/{dataset_id}/schema
```

This file connects browser upload actions to the backend pipeline.

When one parquet file is uploaded:

```python
dataset = await pipeline.ingest_upload(file)
```

When multiple parquet files are uploaded, the route loops through the files and calls the same ingestion pipeline once per file. This keeps each parquet independent while reusing the same schema detection, embedding, Qdrant, and manifest code.

That one call performs:

- File save
- Schema detection
- Metadata creation
- Embedding generation
- Qdrant indexing
- Manifest save

### `backend/api/routes/query.py`

Endpoint:

```text
POST /api/chat/query
```

This receives:

```json
{
  "dataset_id": "...",
  "question": "Which region has highest sales?",
  "limit": 100
}
```

It returns:

- Answer text
- Semantic matches
- Generated SQL
- Result table rows

### `backend/services/file_service.py`

Handles physical file and manifest storage.

Responsibilities:

- Validates `.parquet` extension
- Creates unique dataset id
- Saves upload into `uploads/`
- Saves schema manifest into `backend/storage/datasets/`
- Loads previous dataset manifests

Important behavior:

```python
stored_path = upload_dir / f"{dataset_id}_{safe_name}"
```

This avoids filename collisions when multiple files have the same name.

### `backend/duckdb/client.py`

This is the main local analytics engine.

Responsibilities:

- Reads parquet directly with DuckDB
- Creates a local view named `dataset`
- Detects schema
- Counts rows
- Extracts sample rows
- Profiles each column
- Executes generated SQL

Important idea:

```sql
CREATE OR REPLACE VIEW dataset AS
SELECT * FROM read_parquet('uploaded_file.parquet')
```

All generated SQL queries against the same logical table name:

```text
dataset
```

That is why the SQL generator does not need to know the physical parquet filename.

### `backend/spark/session.py`

Optional Spark schema reader.

Responsibilities:

- Starts local Spark if Java/Spark can run
- Reads parquet schema through Spark
- Returns Spark schema details

If Spark fails because Java is missing, the app still works because DuckDB is the primary engine.

The UI shows Spark as:

```text
Spark ready
```

or:

```text
Spark fallback
```

### `backend/metadata/generator.py`

Creates semantic metadata text from dynamic schema.

For each column it builds text like:

```text
Column Power_Consumption.
Normalized label: power consumption.
Data type: DOUBLE.
Example values: 132.5, 140.1.
Profile statistics: min_value: 10, max_value: 900.
```

This text is embedded and stored in Qdrant.

There are no hardcoded mappings like:

```text
Power_Consumption -> electricity usage
Region -> area
```

Instead, the model understands meaning from column names, split words, sample values, and stats.

### `backend/embeddings/local_model.py`

Loads the local sentence-transformers model.

Model:

```text
all-MiniLM-L6-v2
```

Embedding dimension:

```text
384
```

Important:

The first run may download the model from Hugging Face. After that, it is cached locally.

For fully offline usage, download the model once and set:

```env
EMBEDDING_MODEL=D:\models\all-MiniLM-L6-v2
```

### `backend/qdrant/vector_store.py`

Stores and searches semantic vectors.

Default mode:

```env
QDRANT_MODE=embedded
```

Embedded mode stores vectors locally at:

```text
backend/storage/qdrant/
```

Server mode uses:

```env
QDRANT_MODE=server
QDRANT_URL=http://localhost:6333
```

Each vector payload includes:

- dataset id
- filename
- metadata kind
- column name
- datatype
- sample values
- stats
- semantic text

Dataset filtering is important. It prevents one uploaded file's metadata from being mixed with another file's metadata.

### `backend/retrieval/semantic_retriever.py`

Connects question embedding to Qdrant search.

Flow:

```text
question text
  -> embedding model
  -> vector
  -> Qdrant search filtered by dataset_id
  -> semantic matches
```

### `backend/sql_generation/rules.py`

Creates SQL without an LLM.

It looks for question intent using words like:

| Question words | SQL behavior |
|---|---|
| `highest`, `top`, `maximum` | Rank descending |
| `lowest`, `minimum` | Rank ascending |
| `average`, `avg`, `mean` | `AVG()` |
| `total`, `sum` | `SUM()` |
| `count`, `how many` | `COUNT()` |
| `trend`, `monthly`, `daily` | `DATE_TRUNC()` trend query |
| `abnormal`, `outlier`, `anomaly` | z-score query |

It chooses columns dynamically:

- Metric column: usually a numeric column found by semantic retrieval
- Dimension column: usually a string/category column found by semantic retrieval
- Time column: date/timestamp column when trend questions are asked

Example:

Question:

```text
Which area has highest electricity usage?
```

Generated shape:

```sql
SELECT
  "Region" AS "Region",
  MAX("Power_Consumption") AS metric_value
FROM dataset
WHERE "Power_Consumption" IS NOT NULL AND "Region" IS NOT NULL
GROUP BY "Region"
ORDER BY metric_value DESC
LIMIT 100
```

### `backend/services/response_builder.py`

Creates human-readable template responses.

Example:

```text
Noida has the highest power consumption with a value of 42,100.
```

No LLM is used here.

### `backend/services/pipeline.py`

This is the main orchestrator.

Upload pipeline:

```python
dataset_id, filename, stored_path = await files.save_upload(upload)
duckdb_profile = duckdb.inspect_parquet(stored_path)
spark_schema = spark.inspect(stored_path)
columns = metadata.enrich_columns(duckdb_profile["columns"])
documents = metadata.build_documents(manifest)
vectors = embeddings.encode(...)
vector_store.replace_dataset_documents(...)
files.save_manifest(manifest)
```

Question pipeline:

```python
manifest = files.load_manifest(dataset_id)
matches = retriever.search(dataset_id, question)
plan = sql_generator.generate(question, manifest, matches, limit)
columns, rows = duckdb.execute_sql(path, plan.sql, plan.limit)
answer = response_builder.build(plan, rows)
```

This file is the best place to read first when learning the backend.

## 6. Frontend Structure

```text
frontend/
  index.html
  vite.config.js
  package.json
  tailwind.config.js
  postcss.config.js
  public/
    favicon.svg
  src/
    main.jsx
    App.jsx
    index.css
    services/
      api.js
    pages/
      AnalyticsWorkbench.jsx
    components/
      UploadDropzone.jsx
      DatasetSelector.jsx
      SchemaExplorer.jsx
      ChatPanel.jsx
      DebugPanel.jsx
      ResultsTable.jsx
      StatusPill.jsx
```

## 7. Frontend File-by-File Explanation

### `frontend/vite.config.js`

Very important.

This file enables React JSX transformation:

```js
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
});
```

Without this file, you may see:

```text
Uncaught ReferenceError: React is not defined
```

After adding or changing this file, restart the frontend dev server.

### `frontend/index.html`

Root HTML file loaded by Vite.

Important line:

```html
<div id="root"></div>
```

React mounts the full application into this element.

### `frontend/src/main.jsx`

React entry point.

It renders `App` into the HTML root element.

```jsx
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

### `frontend/src/App.jsx`

Small top-level component.

It renders:

```jsx
<AnalyticsWorkbench />
```

### `frontend/src/pages/AnalyticsWorkbench.jsx`

Main UI page and state manager.

Responsibilities:

- Keeps selected dataset state
- Loads dataset list
- Handles upload
- Handles question submission
- Stores latest query response
- Renders all major panels

Main frontend flow:

```text
UploadDropzone -> handleUpload -> uploadParquet API
DatasetSelector -> selectedDataset state
ChatPanel -> handleAsk -> askQuestion API
DebugPanel -> semantic matches and SQL
ResultsTable -> DuckDB result rows
```

### `frontend/src/services/api.js`

Central API client.

Backend URL:

```js
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
```

Functions:

| Function | Backend endpoint |
|---|---|
| `uploadParquet(file)` | `POST /api/files/upload` |
| `uploadParquets(files)` | `POST /api/files/upload-multiple` |
| `listDatasets()` | `GET /api/datasets` |
| `getDatasetSchema(datasetId)` | `GET /api/datasets/{id}/schema` |
| `askQuestion(...)` | `POST /api/chat/query` |

If your backend runs on another port, create:

```text
frontend/.env
```

with:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### `frontend/src/components/UploadDropzone.jsx`

Upload UI.

Supports:

- Click to browse
- Drag and drop
- Multiple file selection
- `.parquet` accept filter
- Upload loading state

Calls:

```js
onUpload(files)
```

The parent page sends the selected file list to FastAPI. Each parquet is processed as a separate dataset with its own dataset id, schema manifest, and Qdrant metadata vectors.

### `frontend/src/components/DatasetSelector.jsx`

Shows uploaded datasets.

Displays:

- filename
- row count
- column count

Selecting a dataset updates the active schema and chat target.

### `frontend/src/components/SchemaExplorer.jsx`

Shows schema and sample data.

Displays:

- column names
- datatypes
- normalized semantic labels
- distinct counts
- sample rows
- Spark status

### `frontend/src/components/ChatPanel.jsx`

Question input panel.

Sends the user question to:

```js
onAsk(question)
```

The page then calls the backend query API.

### `frontend/src/components/DebugPanel.jsx`

Shows explainability details.

Displays:

- Qdrant semantic matches
- similarity scores
- retrieved metadata text
- generated SQL
- intent
- aggregation
- metric column
- group by columns

This is the manager-demo panel because it proves how the system reasoned locally.

### `frontend/src/components/ResultsTable.jsx`

Displays query results returned by DuckDB.

It uses the dynamic column list returned by the backend, so it works with any SQL result shape.

### `frontend/src/index.css`

Tailwind imports and shared UI classes.

Important custom classes:

- `.panel`
- `.panel-header`
- `.primary-button`
- `.secondary-button`
- `.icon-button`

## 8. How Upload Works Internally

1. User drops or selects one or many parquet files in `UploadDropzone`.
2. `AnalyticsWorkbench.handleUpload()` receives the file list.
3. `uploadParquets(files)` sends `multipart/form-data` to FastAPI using the `files` field.
4. `files.py` receives the batch upload through `POST /api/files/upload-multiple`.
5. The backend loops through each file and calls `pipeline.ingest_upload(file)`.
6. `file_service.py` saves each file under `uploads/`.
7. `duckdb/client.py` reads each file schema and samples.
8. `spark/session.py` optionally reads each Spark schema.
9. `metadata/generator.py` creates semantic documents per dataset.
10. `embeddings/local_model.py` embeds each dataset's documents.
11. `qdrant/vector_store.py` stores vectors filtered by each dataset id.
12. `file_service.py` saves one manifest JSON per uploaded dataset.
13. Frontend refreshes the dataset list and selects the first successfully processed file.

## 9. How Chat Query Works Internally

1. User asks a question in `ChatPanel`.
2. `AnalyticsWorkbench.handleAsk()` calls `askQuestion()`.
3. FastAPI receives the request in `query.py`.
4. `pipeline.answer_question()` loads the dataset manifest.
5. `semantic_retriever.py` embeds the question.
6. Qdrant searches metadata for the same `dataset_id`.
7. `rules.py` chooses metric, dimension, time column, and intent.
8. `rules.py` generates SQL using quoted dynamic column names.
9. `duckdb/client.py` executes the SQL against the uploaded parquet.
10. `response_builder.py` creates a readable response.
11. React displays answer, SQL, semantic matches, and rows.

## 10. Running the App

### Backend

```powershell
cd D:\MCP-SETUP-TEST
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

Open a second PowerShell:

```powershell
cd D:\MCP-SETUP-TEST\frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## 11. Optional Qdrant Server Mode

Default embedded mode does not need Docker.

To use Docker Qdrant:

```powershell
cd D:\MCP-SETUP-TEST
$env:QDRANT_MODE="server"
docker compose up -d qdrant
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Qdrant dashboard:

```text
http://localhost:6333/dashboard
```

## 12. Common Errors and Fixes

### Error: `Uncaught ReferenceError: React is not defined`

Cause:

Vite was not using the React plugin for JSX transformation.

Fix:

Make sure this file exists:

```text
frontend/vite.config.js
```

with:

```js
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
});
```

Then restart frontend:

```powershell
cd D:\MCP-SETUP-TEST\frontend
npm run dev
```

### Message: `Download the React DevTools...`

Cause:

This is only a development suggestion from React.

Fix:

No fix required. The app can run normally without React DevTools.

### Error: `favicon.ico 404`

Cause:

Browser asked for a favicon.

Fix:

This project now includes:

```text
frontend/public/favicon.svg
```

and `frontend/index.html` links it.

Restart the frontend if the old 404 is cached.

### Error: Backend returns `{ "detail": "Not Found" }`

Common causes:

- You opened a backend API path that does not exist.
- You opened `http://127.0.0.1:8000` directly.
- The frontend is pointing to the wrong backend URL.

Correct URLs:

```text
Frontend UI: http://127.0.0.1:5173
Backend docs: http://127.0.0.1:8000/docs
Health:       http://127.0.0.1:8000/health
```

### Error: `Qdrant is not reachable`

If using embedded mode:

Check:

```env
QDRANT_MODE=embedded
```

Delete corrupted embedded storage only if you do not need old indexes:

```powershell
Remove-Item -Recurse -Force D:\MCP-SETUP-TEST\backend\storage\qdrant
```

Then restart backend.

If using server mode:

Start Qdrant:

```powershell
$env:QDRANT_MODE="server"
docker compose up -d qdrant
```

Check:

```text
http://localhost:6333/dashboard
```

### Error: Docker is not recognized

Cause:

Docker Desktop is not installed or not in PATH.

Fix:

Use embedded Qdrant mode:

```env
QDRANT_MODE=embedded
```

Docker is optional for this app.

### Error: Model download fails

Cause:

`all-MiniLM-L6-v2` is not cached and the machine cannot reach Hugging Face.

Fix:

On a machine with internet, download the model folder. Then copy it locally and set:

```env
EMBEDDING_MODEL=D:\models\all-MiniLM-L6-v2
```

Restart backend.

### Error: Spark or Java error

Cause:

Spark requires Java.

Fix:

The app still works with DuckDB. You can disable Spark schema inspection:

```env
ENABLE_SPARK_SCHEMA=false
```

Restart backend.

### Error: Upload fails with `Only .parquet files are supported`

Cause:

The uploaded file extension is not `.parquet`.

Fix:

Upload a valid parquet file.

### Error: DuckDB cannot read parquet

Possible causes:

- File is not actually parquet
- File is corrupted
- File is encrypted or unsupported
- File upload was incomplete

Quick check in Python:

```powershell
python -c "import duckdb; print(duckdb.sql(\"SELECT COUNT(*) FROM read_parquet('D:/path/file.parquet')\").fetchall())"
```

### Error: Port 8000 already in use

Find the process:

```powershell
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
```

Stop it:

```powershell
Stop-Process -Id <PID>
```

Or run backend on another port:

```powershell
uvicorn backend.main:app --reload --port 8001
```

Then update frontend:

```env
VITE_API_BASE_URL=http://127.0.0.1:8001
```

### Error: Port 5173 already in use

Run frontend on another port:

```powershell
npm run dev -- --port 5174
```

Open:

```text
http://127.0.0.1:5174
```

### Error: CORS blocked

Cause:

Frontend URL is not in backend allowed origins.

Fix:

Edit `backend/core/config.py` and add your frontend URL to:

```python
allowed_origins = [...]
```

Restart backend.

### Query returns preview instead of analytics

Cause:

The rule engine did not detect an intent such as highest, average, total, count, trend, or abnormal.

Try clearer wording:

```text
Which region has the highest sales?
What is the average consumption?
Show monthly revenue trend.
Find abnormal meter readings.
Count records by category.
```

### Wrong metric column selected

Cause:

Semantic search found a different numeric column first.

Improve the question by naming the business term closer to the column:

```text
Which region has highest power consumption?
```

instead of:

```text
Which region is highest?
```

Also inspect the Semantic Debug Panel to see which column Qdrant matched.

## 13. How to Debug Step by Step

### Step 1: Check backend health

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

If this fails, backend is not running.

### Step 2: Check frontend

Open:

```text
http://127.0.0.1:5173
```

If blank, open browser console.

### Step 3: Check API docs

Open:

```text
http://127.0.0.1:8000/docs
```

Use Swagger to test upload and query endpoints manually.

### Step 4: Check dataset manifest

After upload, check:

```text
backend/storage/datasets/
```

There should be a JSON file for the uploaded dataset.

### Step 5: Check uploaded file

After upload, check:

```text
uploads/
```

There should be a uniquely named parquet file.

### Step 6: Check Qdrant mode

Embedded:

```text
backend/storage/qdrant/
```

Server:

```text
http://localhost:6333/dashboard
```

### Step 7: Check generated SQL

Use the UI Semantic Debug Panel.

If the SQL looks wrong, inspect:

```text
backend/sql_generation/rules.py
```

### Step 8: Test SQL directly

Copy the generated SQL from the UI and test it in a small Python command after replacing the file path:

```powershell
python -c "import duckdb; con=duckdb.connect(); con.execute(\"CREATE VIEW dataset AS SELECT * FROM read_parquet('D:/path/file.parquet')\"); print(con.execute('SELECT COUNT(*) FROM dataset').fetchall())"
```

## 14. Where to Modify Future Features

| Goal | File to edit |
|---|---|
| Add new upload validation | `backend/services/file_service.py` |
| Add more column statistics | `backend/duckdb/client.py` |
| Improve semantic text | `backend/metadata/generator.py` |
| Change embedding model | `.env` or `backend/core/config.py` |
| Change vector store behavior | `backend/qdrant/vector_store.py` |
| Improve SQL generation | `backend/sql_generation/rules.py` |
| Improve answer text | `backend/services/response_builder.py` |
| Add API endpoint | `backend/api/routes/` |
| Change main UI layout | `frontend/src/pages/AnalyticsWorkbench.jsx` |
| Change upload UI | `frontend/src/components/UploadDropzone.jsx` |
| Change schema display | `frontend/src/components/SchemaExplorer.jsx` |
| Change debug panel | `frontend/src/components/DebugPanel.jsx` |
| Change result table | `frontend/src/components/ResultsTable.jsx` |

## 15. Mental Model for the Whole App

Think of the app as four layers:

### Layer 1: Data Layer

- Uploaded parquet files
- DuckDB schema and SQL execution
- Spark optional schema validation

### Layer 2: Semantic Layer

- Column metadata text
- Local embeddings
- Qdrant vectors
- Similarity search

### Layer 3: Reasoning Layer

- Rule-based intent detection
- Dynamic metric/dimension selection
- Multi-dataset join inference for all-uploads mode
- SQL generation
- Template response

### Layer 4: UI Layer

- Upload
- Schema explorer
- Chat
- Debug panel
- Results table

This separation is the reason the app can support any uploaded parquet schema dynamically.

## 16. All-Uploaded-Files Query Mode

The UI chat has two modes:

- `Selected file`: query only the dataset selected in the sidebar.
- `All uploads`: query across all uploaded parquet files at once.

The all-uploads mode calls:

```text
POST /api/chat/query-all
```

Backend flow:

```text
Question
  -> embed question locally
  -> search Qdrant across all selected dataset ids
  -> create one DuckDB view per parquet file
  -> infer join relationships from column names
  -> generate SQL using joined tables when possible
  -> execute SQL in DuckDB
```

Join inference is dynamic. It does not hardcode the sample tables, but it understands common relational patterns:

| Pattern | Example |
|---|---|
| `<Table>NameId` to target `ID` | `EquipmentId` -> `Equipment.ID` |
| underscore foreign keys | `DeviceLocationId` -> `Device_Location.ID` |
| short prefix foreign keys | `HES_ID` -> `HES_MASTER.ID` |
| master/lookup utility ids | `Material_ID` -> `Material_Master.Utility_ID` |
| same non-generic column names | matching business keys across files |

This is why uploaded files such as `Equipment`, `DevLoc_Device_Link`, `Device_Location`, `ConsumerDevLocLink`, `Consumer`, `Material_Master`, and `HES_MASTER` can be queried together when their column names expose relationships.
