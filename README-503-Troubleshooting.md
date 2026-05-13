# 503 Service Unavailable Troubleshooting

This app can return `503 Service Unavailable` from `/api/chat/query-all` when the backend cannot reach Qdrant.

For local development, the most common cause is embedded Qdrant being locked by an older backend process. Embedded Qdrant is file-backed and should be used by one backend process at a time.

## Quick Fix

Run these commands from the project root in PowerShell:

```powershell
$connections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
  Where-Object { $_.State -eq "Listen" }

$processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique

foreach ($processId in $processIds) {
  Stop-Process -Id $processId -Force
}
```

Then start the backend again:

```powershell
cd D:\MCP-SETUP-TEST
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

For embedded Qdrant, prefer starting without `--reload`. Reload mode can create extra Python processes and may keep the Qdrant storage lock open.

If PowerShell shows `No module named uvicorn`, install the backend packages into the active virtual environment:

```powershell
cd D:\MCP-SETUP-TEST
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Check Runtime Config

Verify the backend loaded the expected `.env`:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health -Method Get |
  ConvertTo-Json -Depth 5
```

Expected local values:

```json
{
  "qdrant_mode": "embedded",
  "anthropic_enabled": true,
  "anthropic_configured": true
}
```

## Correct Local `.env`

Use `.env`, not `.env.example`, for real runtime secrets.

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

## If You Want Qdrant Server Mode

Start Qdrant first:

```powershell
docker compose up -d qdrant
```

Then set:

```env
QDRANT_MODE=server
QDRANT_URL=http://localhost:6333
```

Restart the backend after changing `.env`.

## Test The Query Endpoint

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

If it still returns `503`, read the response body. A message mentioning Qdrant usually means either an old backend process still holds the embedded Qdrant lock, or server mode is enabled while the Qdrant Docker service is not running.

## Qdrant Version Mismatch

If the backend says Qdrant is not reachable even when `QDRANT_MODE=embedded`, the local Qdrant storage may have been written by a newer Qdrant client than the one installed in `.venv`.

Check the installed version:

```powershell
python -m pip show qdrant-client
```

This project expects:

```text
qdrant-client==1.18.0
```

Fix:

```powershell
python -m pip install -r requirements.txt
```

Then restart the backend without `--reload`.
