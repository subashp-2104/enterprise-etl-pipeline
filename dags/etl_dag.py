import os
import sys
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Ensure the DAGs folder is on PYTHONPATH so we can import our custom ETL code
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import run_source_pipeline
from src.utils.db import init_db

default_args = {
    'owner': 'data_engineering',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=1),
}

def init_tables():
    """
    Ensures that target tables exist before running extraction tasks.
    """
    init_db()

def run_stripe():
    """
    Python task wrapper to run Stripe ETL.
    """
    metrics = run_source_pipeline("stripe", full_load=False)
    if metrics["status"] == "FAILED":
        raise Exception(f"Stripe ETL sub-pipeline failed: {metrics['error_message']}")

def run_salesforce():
    """
    Python task wrapper to run Salesforce ETL.
    """
    metrics = run_source_pipeline("salesforce", full_load=False)
    if metrics["status"] == "FAILED":
        raise Exception(f"Salesforce ETL sub-pipeline failed: {metrics['error_message']}")

with DAG(
    'enterprise_warehouse_sync',
    default_args=default_args,
    description='Extracts Stripe and Salesforce data, standardizes it, and syncs to warehouse.',
    schedule_interval=timedelta(days=1),  # Daily schedule
    start_date=datetime(2026, 8, 1),
    catchup=False,
    max_active_runs=1,
) as dag:

    init_db_task = PythonOperator(
        task_id='init_warehouse_tables',
        python_callable=init_tables
    )

    stripe_etl_task = PythonOperator(
        task_id='stripe_etl',
        python_callable=run_stripe
    )

    salesforce_etl_task = PythonOperator(
        task_id='salesforce_etl',
        python_callable=run_salesforce
    )

    # Execution flow: Initialize database tables, then run extractors in parallel
    init_db_task >> [stripe_etl_task, salesforce_etl_task]
