Build a full-stack secure enterprise AI analytics platform that allows users to upload dynamic parquet files and query them using natural language.

The system must use a secure Retrieval-Augmented Generation (RAG) architecture where:

* raw parquet files NEVER leave the local system
* embeddings are generated LOCALLY
* vector database runs LOCALLY
* semantic retrieval happens LOCALLY
* DuckDB query execution happens LOCALLY
* ONLY minimal retrieved context is sent to Anthropic API for reasoning and final response generation

The architecture should prioritize:

* enterprise data privacy
* semantic retrieval
* vector database workflows
* dynamic schema understanding
* scalable RAG architecture
* production-style modular backend
* manager demo readiness

====================================================
CRITICAL SECURITY REQUIREMENTS
==============================

1. NEVER send full parquet files to Anthropic API
2. NEVER send entire datasets externally
3. NEVER upload raw parquet content to AI APIs
4. ONLY send minimal retrieved context after local retrieval
5. ALL embeddings must be generated locally
6. ALL vector storage must remain local
7. ALL semantic retrieval must remain local
8. ALL SQL execution must remain local

Anthropic API should ONLY be used for:

* reasoning
* summarization
* SQL generation assistance
* natural language explanations

====================================================
HIGH LEVEL ARCHITECTURE
=======================

PARQUET FILES (LOCAL)
↓
SPARK / DUCKDB (LOCAL)
↓
SCHEMA EXTRACTION (LOCAL)
↓
LOCAL EMBEDDINGS
(sentence-transformers)
↓
QDRANT VECTOR DB (LOCAL)
↓
LOCAL SEMANTIC RETRIEVAL
↓
MINIMAL CONTEXT RETRIEVAL
↓
ANTHROPIC API
(reasoning only)
↓
FINAL ANSWER

====================================================
TECH STACK
==========

Backend:

* Python
* FastAPI

Data Processing:

* Apache Spark
* DuckDB
* Pandas
* PyArrow

Vector Database:

* Qdrant (local Docker)

Embeddings:

* sentence-transformers
* all-MiniLM-L6-v2

Frontend:

* React.js
* Tailwind CSS

AI API:

* Anthropic Claude API

Environment Variables:

* python-dotenv
* .env support

====================================================
IMPORTANT IMPLEMENTATION REQUIREMENTS
=====================================

1. User uploads parquet manually from UI
2. No sample parquet generation
3. No hardcoded schemas
4. No hardcoded parquet filenames
5. Dynamic schema handling required
6. Dynamic column detection required
7. Dynamic semantic matching required
8. Dynamic SQL generation required

====================================================
STEP 1 — FILE UPLOAD SYSTEM
===========================

Frontend must include:

* parquet upload button
* drag-and-drop upload
* upload progress
* upload success/error handling

Backend must:

* receive parquet file
* save locally in uploads/ folder
* support multiple parquet uploads
* validate parquet extension

====================================================
STEP 2 — LOCAL PARQUET PROCESSING
=================================

Use Spark + DuckDB locally.

Requirements:

* dynamically read parquet
* detect schema
* detect columns
* detect datatypes
* detect row counts
* preview sample rows

Support:

* changing schemas
* new columns
* multiple parquet files

====================================================
STEP 3 — SCHEMA EXTRACTION
==========================

Automatically extract:

* column names
* data types
* parquet metadata
* sample values

Store metadata locally.

====================================================
STEP 4 — LOCAL EMBEDDING GENERATION
===================================

Use ONLY local embeddings.

Use:
sentence-transformers
model:
all-MiniLM-L6-v2

Generate embeddings for:

* column names
* schema descriptions
* parquet metadata
* sample rows
* semantic descriptions

NO embedding APIs allowed.

====================================================
STEP 5 — LOCAL QDRANT VECTOR STORAGE
====================================

Use local Qdrant Docker container.

Store:

* embeddings
* semantic metadata
* schema information
* parquet references

Metadata should include:

* parquet filename
* column name
* datatype
* semantic meaning
* sample values

Implement:

* create collection
* upsert vectors
* semantic similarity search
* metadata filtering

====================================================
STEP 6 — SEMANTIC RETRIEVAL
===========================

When user asks question:

* create embedding locally
* search Qdrant locally
* identify semantically similar columns
* identify relevant parquet files
* identify relevant metadata

Examples:
“electricity usage”
≈
“Power_Consumption”

“area”
≈
“Region”

This matching must happen locally.

====================================================
STEP 7 — LOCAL SQL GENERATION CONTEXT
=====================================

Use retrieved metadata to build SQL generation context.

Example retrieved metadata:

* relevant columns
* parquet file names
* schema details
* sample values

DO NOT send entire parquet content.

====================================================
STEP 8 — ANTHROPIC API INTEGRATION
==================================

Use Anthropic Claude API ONLY after retrieval.

API usage should ONLY receive:

* minimal schema context
* relevant metadata
* retrieved semantic matches
* limited sample rows if needed

Example prompt sent to Claude:

Relevant Schema:
Region
Power_Consumption

Relevant Context:
Noida → 900

User Question:
Which area has highest electricity usage?

Generate:

* SQL query
* reasoning
* human-readable answer

====================================================
IMPORTANT SECURITY RULE
=======================

The application MUST NEVER:

* send full parquet
* send entire database
* send full tables
* send all rows
* send sensitive datasets externally

Only send:

* retrieved semantic snippets
* relevant metadata
* minimal required context

====================================================
STEP 9 — DYNAMIC SQL GENERATION
===============================

Claude API should:

* generate SQL dynamically
* adapt to changing schemas
* adapt to new columns
* generate DuckDB-compatible SQL

Examples:

* aggregations
* filtering
* grouping
* averages
* comparisons

Implement:

* SQL validation
* SQL retry correction
* fallback handling

====================================================
STEP 10 — DUCKDB EXECUTION
==========================

Execute generated SQL locally using DuckDB.

Requirements:

* direct parquet querying
* dynamic parquet references
* safe query execution
* return JSON responses

====================================================
STEP 11 — FINAL RESPONSE GENERATION
===================================

Claude API should generate:

* intelligent summaries
* analytics explanations
* natural language insights

Example:
“Noida has the highest electricity usage.”

====================================================
FRONTEND REQUIREMENTS
=====================

Frontend must include:

1. Upload Section

* parquet upload
* upload status

2. Schema Explorer

* columns
* datatypes
* row counts
* sample rows

3. AI Chat Interface

* natural language querying

4. Semantic Debug Panel

* matched columns
* semantic similarity scores
* retrieved metadata
* retrieved vectors
* generated SQL

5. Results Section

* tables
* formatted analytics
* loading states
* error handling

====================================================
ENVIRONMENT VARIABLES
=====================

Use .env file.

Required:
ANTHROPIC_API_KEY

Use python-dotenv.

NEVER hardcode API keys.

====================================================
PROJECT STRUCTURE
=================

backend/
api/
services/
spark/
duckdb/
embeddings/
qdrant/
retrieval/
sql_generation/
anthropic/
metadata/

frontend/
components/
pages/
services/

uploads/

====================================================
DOCKER REQUIREMENTS
===================

Provide Docker setup for:

* Qdrant
* backend
* frontend

Provide docker-compose.yml.

====================================================
README REQUIREMENTS
===================

Provide:

* setup instructions
* PowerShell commands
* Docker instructions
* Qdrant setup
* .env setup
* Anthropic API setup
* architecture explanation
* RAG explanation
* semantic search explanation

====================================================
EXPECTED FINAL DEMO FLOW
========================

1. User uploads parquet
2. Schema detected dynamically
3. Embeddings generated locally
4. Qdrant stores vectors locally
5. User asks natural language question
6. Qdrant performs local semantic retrieval
7. Minimal context prepared
8. Claude API generates SQL + reasoning
9. DuckDB executes SQL locally
10. Final intelligent answer shown

====================================================
IMPORTANT GOAL
==============

The project should clearly demonstrate:

* secure enterprise RAG architecture
* local vector retrieval
* semantic search
* Qdrant usage
* embeddings
* dynamic schema handling
* secure AI integration
* hybrid local + API reasoning architecture

The code should be:

* modular
* enterprise-style
* production-oriented
* scalable
* easy to understand
* suitable for manager demo
* suitable for future expansion
Key Should Be .env and the program should take from here 