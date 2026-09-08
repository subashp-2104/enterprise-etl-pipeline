# Enterprise ETL Pipeline & Data Warehouse Synchronizer

A production-grade, modular ETL pipeline designed to extract business data from multiple APIs (Stripe and Salesforce), validate and clean it via Pydantic, transform the schemas into a unified reporting format, and load it into PostgreSQL using idempotent Upsert logic. 

Features include rate-limiting, tenacity retry mechanisms, S3/local file raw data archiving, audit logging, a FastAPI-based monitoring dashboard, and Docker/Airflow orchestration.

---

## Project Architecture

```
enterprise-etl-pipeline/
├── dags/
│   └── etl_dag.py             # Airflow DAG orchestrating the pipeline tasks
├── src/
│   ├── extractors/
│   │   ├── base.py            # Base Extractor implementing tenacity retry & rate-limits
│   │   ├── mock_api.py        # Generates realistic mock data (Date filters, offset & cursors)
│   │   ├── salesforce.py      # Salesforce Accounts & Opportunities extractor
│   │   └── stripe.py          # Stripe Customers & Charges cursor extractor
│   ├── loaders/
│   │   └── loader.py          # Idempotent bulk upsert loader (PostgreSQL & SQLite support)
│   ├── storage/
│   │   └── storage.py         # Handles raw JSON storage (Local filesystem or AWS S3 fallback)
│   ├── transformers/
│   │   └── transformer.py     # Validates, sanitizes, and maps inputs to unified DW schemas
│   ├── utils/
│   │   ├── db.py              # SQLAlchemy schemas and warehouse connections
│   │   └── logger.py          # Structured stdout log formatter
│   ├── config.py              # Configuration manager using Pydantic Settings
│   ├── dashboard.py           # Monitoring web dashboard backend (FastAPI)
│   └── pipeline.py            # Main CLI runner orchestrating pipeline tasks
├── tests/
│   ├── test_extractors.py     # Unit tests for mock API and pagination
│   ├── test_loaders.py        # Unit tests for SQLite DB connection and upserting
│   ├── test_pipeline.py       # End-to-end integration tests
│   └── test_transformers.py   # Unit tests for standard sanitizers and schemas
├── Dockerfile                 # Docker container specification
├── docker-compose.yml         # Container configuration (Postgres, Airflow, Web Dashboard)
├── requirements.txt           # Python application dependencies
└── README.md                  # This setup documentation
```

---

## Getting Started

### 1. Requirements
- Python 3.11+
- (Optional) Docker & Docker Compose (for Postgres and Airflow)

### 2. Installation
Clone or navigate to the directory and run:
```bash
# Create virtual environment
python -m venv venv
source venv/Scripts/activate # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
By default, the `.env` configuration is pre-set with:
* `MOCK_MODE=True` (no real API keys required; generates realistic, time-aligned mockup data)
* `DATABASE_URL=sqlite:///./warehouse.db` (local SQLite database fallback)

---

## Local Development Execution

### Launch Web Dashboard
Start the monitoring dashboard locally (FastAPI + HTML/CSS UI with Chart.js):
```bash
python src/dashboard.py
```
Open **[http://localhost:5000](http://localhost:5000)** in your browser. From here you can:
- View database storage status (SQLite or PostgreSQL).
- View KPI stats (customers by source, total revenue synced, runs).
- Monitor raw logs and browse unified database tables (Customers, Transactions, Logs).
- **Trigger Stripe/Salesforce ETL pipeline runs manually** by clicking the header buttons!

### Run Pipeline via CLI
You can also execute the ETL pipeline manually via the console:
```bash
# Run Stripe Pipeline (Incremental Load)
python src/pipeline.py --source stripe

# Run Salesforce Pipeline (Incremental Load)
python src/pipeline.py --source salesforce

# Run All Pipelines (Full Load - ignores history)
python src/pipeline.py --source all --full-load
```

---

## Docker & Airflow Orchestration

To boot the production database, Airflow scheduler/webserver, and the web dashboard simultaneously:
```bash
docker-compose up -d --build
```

- **ETL Monitoring Dashboard**: `http://localhost:5000`
- **Airflow Webserver**: `http://localhost:8080` (monitoring workflows and triggers)
- **Postgres Warehouse**: Host: `localhost`, Port: `5432`, DB: `warehouse`, User: `postgres`, Password: `postgres`

To terminate containers and clean up:
```bash
docker-compose down -v
```

---

## Testing

Execute the automated tests using `pytest` to verify reliability:
```bash
# Run entire test suite
python -m pytest tests/
```
Tests check mock pagination, email/phone standardizers, in-memory SQLite schema upserts, and end-to-end orchestration workflows.
