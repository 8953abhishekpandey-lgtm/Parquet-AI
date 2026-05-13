# Parquet AI Chat

This project lets you upload parquet files and ask questions about them in plain English.

The app keeps your files and data local. It uses:

- FastAPI for the backend API
- React for the browser UI
- DuckDB to read and query parquet files
- Qdrant to store searchable schema metadata
- Sentence Transformers for local embeddings
- Anthropic Claude only for SQL reasoning and short answers

Raw parquet files are not sent to Claude. Claude only receives small schema/context snippets and small result previews.

## Project Folders

```text
backend/       FastAPI app and data-query logic
frontend/      React UI
uploads/       uploaded parquet files, kept local
.env           your real local settings and API key, ignored by git
.env.example   safe template, no real secrets
requirements.txt
```

Do not put real API keys in `.env.example`.

## First Time Setup

Run these commands from the project root:

```powershell
cd D:\MCP-SETUP-TEST
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you see this error:

```text
No module named uvicorn
```

run this again while the `.venv` is active:

```powershell
python -m pip install -r requirements.txt
```

`uvicorn` is already listed in `requirements.txt`; the error means the packages were not installed into the active virtual environment.

## Environment File

Create or update `.env` in the project root:

```env
ANTHROPIC_API_KEY=your_real_key_here
ANTHROPIC_MODEL=claude-sonnet-4-6
ANTHROPIC_ENABLED=true

QDRANT_MODE=embedded
QDRANT_COLLECTION=parquet_semantic_metadata

EMBEDDING_MODEL=all-MiniLM-L6-v2
ENABLE_SPARK_SCHEMA=true
SAMPLE_ROWS=20
QUERY_ROW_LIMIT=100
ANTHROPIC_CONTEXT_MATCH_LIMIT=10
ANTHROPIC_RESULT_ROW_LIMIT=12
```

Use `.env` for real values. Use `.env.example` only as a template.

## Start The Backend

Run from the project root, not from inside `backend/`:

```powershell
cd D:\MCP-SETUP-TEST
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

For local embedded Qdrant, avoid `--reload`. Reload can create extra Python processes and lock Qdrant storage.

Backend URLs:

- API health: `http://127.0.0.1:8000/health`
- API docs: `http://127.0.0.1:8000/docs`

## Start The Frontend

Open a second PowerShell window:

```powershell
cd D:\MCP-SETUP-TEST\frontend
npm install
npm run dev
```

Then open:

```text
http://localhost:5173
```

## Normal Workflow

1. Start backend.
2. Start frontend.
3. Upload one or more `.parquet` files.
4. Ask a question in the chat panel.
5. Check the debug panel if the answer looks wrong.

The backend builds metadata from your parquet files, stores searchable vectors locally, asks Claude to generate safe SQL, validates the SQL, runs it in DuckDB, and returns the answer.

## Stop An Existing Backend

If port `8000` is already busy or Qdrant is locked, stop the old backend:

```powershell
$connections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
  Where-Object { $_.State -eq "Listen" }

$processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique

foreach ($processId in $processIds) {
  Stop-Process -Id $processId -Force
}
```

Then start it again:

```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

More detail is in `README-503-Troubleshooting.md`.

## Common Errors

### No module named uvicorn

Cause: dependencies are not installed in the active `.venv`.

Fix:

```powershell
cd D:\MCP-SETUP-TEST
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 503 Service Unavailable

Most likely cause: Qdrant is not reachable, embedded Qdrant is locked by another backend process, or the installed `qdrant-client` version is too old for the existing local Qdrant storage.

Fix:

1. Stop the old backend on port `8000`.
2. Start the backend again without `--reload`.
3. Check health:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health -Method Get |
  ConvertTo-Json -Depth 5
```

Expected:

```json
{
  "qdrant_mode": "embedded",
  "anthropic_configured": true
}
```

If it still fails, reinstall dependencies so the Qdrant client version matches `requirements.txt`:

```powershell
python -m pip install -r requirements.txt
```

### Anthropic is not configured

Cause: the key is missing from `.env`, or the backend was started before `.env` was updated.

Fix:

1. Put `ANTHROPIC_API_KEY=...` in `.env`.
2. Restart the backend.
3. Check `/health`.

### Hugging Face token warning

This warning is not fatal:

```text
You are sending unauthenticated requests to the HF Hub
```

The app can still work. Add `HF_TOKEN` only if downloads are rate-limited.

### Spark or Java warning

Spark schema reading is optional. If Spark or Java fails, DuckDB can still inspect and query parquet files.

To disable Spark schema checks:

```env
ENABLE_SPARK_SCHEMA=false
```

Then restart the backend.

## Qdrant Modes

Default local mode:

```env
QDRANT_MODE=embedded
```

Embedded mode is easiest. It does not need Docker, but only one backend process should use it at a time.

Server mode:

```powershell
docker compose up -d qdrant
```

Then set:

```env
QDRANT_MODE=server
QDRANT_URL=http://localhost:6333
```

Restart the backend after changing Qdrant mode.

## Clean Project Notes

Safe to delete:

- `__pycache__/`
- `.pytest_cache/`
- `*.log`
- `frontend/dist/`
- accidental nested virtual environments like `backend/.venv/`

Do not delete unless you really want to reset local data:

- `.env`
- `uploads/`
- `backend/storage/`
- root `.venv/`
- `frontend/node_modules/`

## Quick Health Test

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health -Method Get |
  ConvertTo-Json -Depth 5
```

If that works, test a query:

```powershell
$body = @{
  question = "show me the first rows"
  limit = 5
} | ConvertTo-Json

Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/chat/query-all `
  -Method Post `
  -Body $body `
  -ContentType "application/json" `
  -SkipHttpErrorCheck
```

## Security Reminder

`.env` is ignored by git and should contain the real API key. `.env.example` should never contain real keys.
