# Enterprise ETL Pipeline & Data Warehouse Synchronizer

A production-grade, modular ETL (Extract, Transform, Load) pipeline and data warehouse synchronizer built using Python, PostgreSQL, Pydantic, Pandas, SQLAlchemy, FastAPI, and Apache Airflow.

---

## Internship Context

- **Internship Role**: Python Development Intern
- **Company**: Zaalima Development Pvt. Ltd.
- **Internship Duration**: 2 Months
- **Project Scope**: Month 1 Project

*This project was developed as part of my 2-month Python Development Internship at Zaalima Development Pvt. Ltd. to demonstrate practical skills in building automated data engineering pipelines, API integrations, data validation, database warehousing, and monitoring.*

---

## Project Overview

In modern software architectures, enterprise data is frequently fragmented across specialized third-party SaaS platforms. Payment transactions live inside payment gateways like **Stripe**, while customer relationship records reside in CRM platforms like **Salesforce**. 

Analyzing business performance across these isolated systems creates data silos, making unified financial and customer reporting difficult.

The **Enterprise ETL Pipeline & Data Warehouse Synchronizer** solves this problem by automating the end-to-end data integration workflow:

1. **Extraction**: Ingests raw customer and transaction records from third-party REST APIs (Stripe and Salesforce) handling pagination, rate limits, and network retries.
2. **Raw Storage & Auditing**: Persists raw JSON payloads to local storage or AWS S3 before processing to preserve audit compliance.
3. **Validation & Data Cleaning**: Enforces strict data types, email/phone format sanitization, and timestamp normalization using Pydantic. Malformed records are quarantined without crashing the pipeline.
4. **Transformation**: Harmonizes different source schemas into standardized relational data models using Pandas.
5. **Warehouse Sync**: Performs idempotent bulk upserts into a centralized **PostgreSQL Data Warehouse** using SQLAlchemy, avoiding duplicate records and supporting timestamp-based incremental loading.
6. **Observability**: Exposes real-time sync metrics, run logs, and manual pipeline triggers through an interactive **FastAPI Web Dashboard**.

---

## Problem Statement

Businesses using multiple SaaS platforms face several challenges when building unified data repositories:

- **Incompatible API Payload Structures**: Stripe represents payments as `charges` with amounts in cents, whereas Salesforce represents deals as `opportunities` with monetary amounts in dollars and custom stage names (`Closed Won`, `Negotiation`).
- **Data Quality & Schema Drift**: Missing fields, unformatted phone numbers, or invalid email strings can corrupt database tables if inserted directly.
- **Network Instability & API Rate Limits**: External APIs often enforce rate limits (HTTP 429 Too Many Requests) or experience transient connection drops.
- **Duplicate Records on Re-execution**: Simple database insertions create duplicate records if the pipeline is executed multiple times for the same time window.
- **Full Refresh Inefficiencies**: Reloading historical datasets on every run consumes excessive API bandwidth and database I/O.

---

## Project Objectives

- **Multi-Source Extraction**: Extract customer and transaction data from Stripe and Salesforce REST APIs.
- **API Pagination Handling**: Implement cursor-based pagination (`starting_after`) for Stripe and offset-based pagination (`OFFSET`) for Salesforce.
- **Fault-Tolerant Network Retries**: Use exponential backoff strategies to retry failed HTTP requests and handle HTTP 429 rate limits.
- **Data Archiving**: Archive raw JSON responses before transformation for compliance and auditing.
- **Schema Validation & Quarantine**: Use Pydantic models to validate incoming records and isolate invalid data into a `./quarantine/` folder without breaking execution.
- **Unified Schema Transformation**: Convert cents to dollars, standardize dates, and map source fields into `UnifiedCustomer` and `UnifiedTransaction` models.
- **PostgreSQL Warehousing & Upserts**: Load transformed data into PostgreSQL using native `ON CONFLICT DO UPDATE` upsert logic to guarantee idempotency.
- **Incremental Synchronization**: Watermark pipeline runs using execution timestamps in `etl_run_log` to fetch only new or updated records on subsequent runs.
- **Pipeline Observability**: Build a live monitoring dashboard to visualize execution logs, revenue metrics, and database connection statuses.
- **Automated Testing**: Maintain automated unit and integration tests using Pytest.

---

## Architecture & Data Flow

```text
               +-----------------------+      +--------------------------+
               |  Stripe REST API      |      |  Salesforce REST/SOQL    |
               |  (Customers/Charges)  |      |  (Accounts/Opportunities)|
               +-----------+-----------+      +------------+-------------+
                           |                               |
                           +---------------+---------------+
                                           |
                                           v
                        +-------------------------------------+
                        |     Extraction Layer (`src/`)       |
                        | - Cursor & SOQL Pagination          |
                        | - Tenacity Exponential Retries      |
                        | - Rate Limit Handling (HTTP 429)    |
                        +------------------+------------------+
                                           |
                                           v
                        +-------------------------------------+
                        |    Raw Storage Layer (`storage/`)   |
                        | - Local JSON / AWS S3 Archiving     |
                        +------------------+------------------+
                                           |
                                           v
                        +-------------------------------------+
                        |  Validation & Quarantine (`cleaner`)|
                        | - Pydantic Model Schema Checks      |
                        | - Quarantine Corrupted Records      |
                        +------------------+------------------+
                                           |
                                           v
                        +-------------------------------------+
                        |    Transformation Layer (`pandas`)  |
                        | - Currency & Stage Normalization    |
                        | - Unified Customer & Txn Schemas    |
                        +------------------+------------------+
                                           |
                                           v
                        +-------------------------------------+
                        |     PostgreSQL Data Warehouse       |
                        | - SQLAlchemy ORM Models             |
                        | - Idempotent Bulk Upsert            |
                        | - Incremental Watermarking Logs     |
                        +------------------+------------------+
                                           |
                           +---------------+---------------+
                           |                               |
                           v                               v
            +------------------------------+  +----------------------------+
            |  FastAPI Web Dashboard       |  |  Apache Airflow DAG        |
            |  (Live KPIs & Trigger Controls)|  |  (Parallel Workflow Sync)  |
            +------------------------------+  +----------------------------+
```

---

## Main Features

1. **Dual-Source Ingestion**: Pulls customer and financial records from both payment gateways and CRM systems.
2. **Cursor & SOQL Pagination**: Seamlessly traverses large datasets using pagination tokens (`starting_after`) and query locators.
3. **Resilient Retry Logic**: Uses `tenacity` retry decorators with exponential backoff and `Retry-After` header parsing.
4. **Data Quarantine**: Isolates invalid records to `./quarantine/` with diagnostic logs, maintaining partial pipeline success.
5. **Raw Data Lineage**: Automatically saves un-transformed JSON payloads to `raw_data/{source}/{entity}/{date}/`.
6. **Unified Schema Mapping**: Standardizes distinct vendor models into common reporting structures (`UnifiedCustomerModel` & `UnifiedTransactionModel`).
7. **Idempotent PostgreSQL Bulk Upserts**: Prevents duplicate entries upon re-execution using PostgreSQL native `ON CONFLICT DO UPDATE`.
8. **Incremental Processing**: Tracks historical executions in `etl_run_log` to sync only newly updated records.
9. **Automatic Local Fallback**: Attempts PostgreSQL connection first; gracefully falls back to local `SQLite` if PostgreSQL is offline during local testing.
10. **Interactive Monitoring UI**: Built with FastAPI and glassmorphic UI, allowing developers to view live database statistics, search customers, inspect logs, and trigger manual ETL runs.
11. **Airflow Orchestration**: Includes an Airflow DAG (`dags/etl_dag.py`) for parallel daily sync tasks (`init_db_task >> [stripe_etl_task, salesforce_etl_task]`).

---

## Technology Stack

| Technology | Role / Purpose |
| :--- | :--- |
| **Python 3.11+** | Primary programming language |
| **Requests** | HTTP client for third-party REST API extraction |
| **Tenacity** | Exponential backoff retry decorators for resilient network requests |
| **Pydantic** | Strict schema validation, type enforcement, and settings management |
| **Pandas** | Data transformation, currency scaling, and schema standardization |
| **SQLAlchemy** | Database ORM, connection pooling, and dialect-safe upsert queries |
| **PostgreSQL** | Primary centralized Enterprise Data Warehouse |
| **SQLite** | Local development database fallback |
| **FastAPI & Uvicorn** | Backend web server powering the monitoring dashboard and trigger APIs |
| **Apache Airflow** | Workflow orchestration DAG for parallel execution scheduling |
| **Pytest** | Automated unit and integration testing framework |
| **Docker & Docker Compose** | Multi-container orchestration (Postgres, Airflow, Dashboard) |

---

## Repository Structure

```text
enterprise-etl-pipeline/
│
├── dags/
│   └── etl_dag.py             # Airflow DAG for parallel ETL task scheduling
│
├── src/
│   ├── extractors/
│   │   ├── base.py            # Base Extractor implementing tenacity retries & rate-limits
│   │   ├── mock_api.py        # Mock data generator (Cursor & offset pagination)
│   │   ├── salesforce.py      # Salesforce Accounts & Opportunities extractor
│   │   └── stripe.py          # Stripe Customers & Charges cursor extractor
│   │
│   ├── loaders/
│   │   └── loader.py          # Idempotent bulk upsert loader (PostgreSQL & SQLite)
│   │
│   ├── storage/
│   │   └── storage.py         # Raw JSON data storage (Local filesystem / S3 fallback)
│   │
│   ├── transformers/
│   │   └── transformer.py     # Schema mapping, currency scaling, and sanitization
│   │
│   ├── utils/
│   │   ├── db.py              # SQLAlchemy models and connection manager with fallback
│   │   └── logger.py          # Standardized logging configuration
│   │
│   ├── validation/
│   │   ├── cleaner.py         # Phone, email, and timestamp sanitizers
│   │   └── models.py          # Pydantic raw payload models
│   │
│   ├── config.py              # Application settings loader via Pydantic BaseSettings
│   ├── dashboard.py           # FastAPI Web Dashboard backend & API endpoints
│   └── pipeline.py            # CLI pipeline orchestrator
│
├── tests/
│   ├── test_extractors.py     # Unit tests for API pagination and mock extraction
│   ├── test_loaders.py        # Unit tests for database connection and upserts
│   ├── test_pipeline.py       # End-to-end integration tests
│   └── test_transformers.py   # Unit tests for data sanitization and schema mapping
│
├── .env.example               # Template for environment configuration
├── .gitignore                 # Excludes cache, database files, and secrets
├── Dockerfile                 # Container definition for application services
├── docker-compose.yml         # Services setup (PostgreSQL, Airflow, Web Dashboard)
├── pyproject.toml             # Pytest and linter tool configuration
├── requirements.txt           # Python package dependencies
└── README.md                  # Project documentation
```

---

## Setup & Local Execution Guide

### Prerequisites
- Python 3.11 or higher
- (Optional) PostgreSQL server installed locally or running via Docker

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/enterprise-etl-pipeline.git
cd enterprise-etl-pipeline

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default `.env` settings are pre-configured for local testing:
```env
MOCK_MODE=True
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/warehouse
```
*(Note: If PostgreSQL is offline, the application will print a warning log and automatically fall back to local `sqlite:///./warehouse.db`).*

---

### 3. Execution Options

#### Option A: Run via CLI

```bash
# Run full sync for all sources (Stripe & Salesforce)
python -m src.pipeline --source all --full-load

# Run incremental sync for Stripe only
python -m src.pipeline --source stripe

# Run incremental sync for Salesforce only
python -m src.pipeline --source salesforce
```

#### Option B: Run Web Dashboard

Start the FastAPI dashboard server:
```bash
python -m src.dashboard
```
Open **[http://localhost:5000](http://localhost:5000)** in your browser to:
- Monitor live database connection status and storage statistics.
- View total customers, transactions, and revenue timelines.
- Click **Trigger Stripe ETL** or **Trigger Salesforce ETL** header buttons to run pipelines directly from the UI.

#### Option C: Run in VS Code

This repository includes predefined debug configurations in `.vscode/launch.json`:
1. Press **`Ctrl + Shift + D`** (Run & Debug).
2. Select **`Python: Web Dashboard`** or **`Python: ETL Pipeline (All Sources)`**.
3. Press **`F5`**.

#### Option D: Run via Docker Compose

To boot PostgreSQL, Airflow, and the Dashboard simultaneously:
```bash
docker-compose up -d --build
```
- **Web Dashboard**: `http://localhost:5000`
- **Airflow UI**: `http://localhost:8080`
- **PostgreSQL Warehouse**: `localhost:5432`

---

## Verification & Test Results

### Automated Test Suite
The codebase includes 12 automated unit and integration tests covering extraction, cleaning, schema transformation, upsert loading, and full pipeline execution.

Execute the test suite using `pytest`:
```bash
python -m pytest tests/
```

**Actual Test Result**:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\mukes\OneDrive\Desktop\SUBASH_PROJECT\enterprise-etl-pipeline
configfile: pyproject.toml
collected 12 items

tests\test_extractors.py .....                                           [ 41%]
tests\test_loaders.py ..                                                 [ 58%]
tests\test_pipeline.py .                                                 [ 66%]
tests\test_transformers.py ....                                          [100%]

============================= 12 passed in 1.04s ==============================
```

### Verified Dataset Metrics (PostgreSQL Warehouse)
- **Unified Customers**: 100 records (50 Stripe, 50 Salesforce)
- **Unified Transactions**: 200 records (120 Stripe Charges, 80 Salesforce Opportunities)
- **Total Synced Revenue**: $1,297,920.00
- **Execution Log Audit**: All runs recorded with start/finish timestamps and `SUCCESS` / `PARTIAL_SUCCESS` / `FAILED` status flags.

---

## Limitations & Future Scope

### Current Limitations
1. **Local S3 Archiving Default**: AWS S3 archiving requires real AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET_NAME`) in `.env`; otherwise, raw data archives to the local disk.
2. **Mock Mode Default**: Real API extraction requires replacing mock credentials with live Stripe API keys and Salesforce OAuth tokens.

### Future Improvements
- **Real-Time Webhook Streaming**: Add FastAPI webhook receivers for instant event-driven ingestion alongside scheduled batch syncs.
- **dbt Integration**: Integrate dbt (data build tool) for SQL modeling and data freshness assertions inside the warehouse.
- **Additional Data Connectors**: Expand extractors to support HubSpot CRM, Shopify Payments, and Zendesk Support tickets.
