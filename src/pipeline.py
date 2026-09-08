import argparse
import sys
import uuid
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config import settings
from src.utils.logger import get_logger
from src.utils.db import init_db, SessionLocal, ETLRunLogModel
from src.extractors.stripe import StripeExtractor
from src.extractors.salesforce import SalesforceExtractor
from src.storage.storage import get_storage
from src.transformers.transformer import ETLTransformer
from src.loaders.loader import WarehouseLoader

logger = get_logger("PipelineOrchestrator")

def send_slack_alert(run_id: str, source: str, error_msg: str) -> None:
    """
    Sends a failure alert to Slack if webhook is configured, otherwise logs it.
    """
    alert_text = (
        f"🚨 *ETL Pipeline Failure Alert* 🚨\n"
        f"*Run ID:* `{run_id}`\n"
        f"*Source:* `{source}`\n"
        f"*Timestamp:* {datetime.now(timezone.utc).isoformat()}\n"
        f"*Error Message:* ```{error_msg}```"
    )
    
    if not settings.SLACK_WEBHOOK_URL or settings.SLACK_WEBHOOK_URL.startswith("your_"):
        clean_text = alert_text.replace("🚨", "[ALERT]")
        logger.info(f"[MOCK SLACK ALERT] {clean_text}")
        return

    try:
        import requests
        response = requests.post(settings.SLACK_WEBHOOK_URL, json={"text": alert_text}, timeout=10.0)
        response.raise_for_status()
        logger.info("Slack alert sent successfully.")
    except Exception as e:
        logger.error(f"Failed to deliver Slack notification: {e}")

def save_quarantine_records(source: str, entity: str, run_id: str, records: List[Dict[str, Any]]) -> None:
    """
    Saves quarantined records locally for later review and debugging.
    """
    if not records:
        return
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    quarantine_dir = os.path.join("./quarantine", source.lower(), entity.lower(), today)
    os.makedirs(quarantine_dir, exist_ok=True)
    
    file_path = os.path.join(quarantine_dir, f"run_{run_id}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        logger.warning(f"Persisted {len(records)} quarantined {entity} records from {source} to: {file_path}")
    except Exception as e:
        logger.error(f"Failed to save quarantined records to file: {e}")

def run_source_pipeline(source: str, full_load: bool = False) -> Dict[str, Any]:
    """
    Executes the ETL process for a single source (Stripe or Salesforce).
    Returns metrics on records processed.
    """
    run_id = f"run_{source.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    started_at = datetime.now(timezone.utc)
    logger.info(f"Starting ETL pipeline execution for {source}. Run ID: {run_id}")

    db_session = SessionLocal()
    
    # Track metrics
    metrics = {
        "run_id": run_id,
        "source": source,
        "records_extracted": 0,
        "records_loaded": 0,
        "records_failed": 0,
        "status": "RUNNING",
        "error_message": None
    }

    # Log initial run status in database
    run_log = ETLRunLogModel(
        run_id=run_id,
        started_at=started_at,
        status="RUNNING",
        source=source,
        records_extracted=0,
        records_loaded=0,
        records_failed=0
    )
    db_session.add(run_log)
    db_session.commit()

    try:
        # 1. Determine incremental load window
        since_time = None
        if not full_load:
            # Query latest successful execution timestamp
            latest_run = (
                db_session.query(ETLRunLogModel)
                .filter(ETLRunLogModel.source == source)
                .filter(ETLRunLogModel.status == "SUCCESS")
                .order_by(ETLRunLogModel.started_at.desc())
                .first()
            )
            if latest_run:
                since_time = latest_run.started_at
                logger.info(f"Incremental mode enabled. Pulling data updated since: {since_time.isoformat()}")
            else:
                logger.info("No prior successful run logs found. Defaulting to full load.")

        # 2. Extract Data
        if source.lower() == "stripe":
            extractor = StripeExtractor()
        elif source.lower() == "salesforce":
            extractor = SalesforceExtractor()
        else:
            raise ValueError(f"Unknown data source: {source}")

        extracted_data = extractor.extract(since=since_time)
        
        raw_customers = extracted_data.get("customers", [])
        raw_transactions = extracted_data.get("transactions", [])
        
        metrics["records_extracted"] = len(raw_customers) + len(raw_transactions)
        logger.info(f"Extraction complete: {len(raw_customers)} customer records, {len(raw_transactions)} transactions.")

        # 3. Store Raw JSON Data
        storage = get_storage()
        if raw_customers:
            storage.write(source, "customers", run_id, raw_customers)
        if raw_transactions:
            storage.write(source, "transactions", run_id, raw_transactions)

        # 4. Transform & Clean Data
        transformer = ETLTransformer()
        
        if source.lower() == "stripe":
            valid_custs, quarantined_custs = transformer.transform_stripe_customers(raw_customers)
            valid_txns, quarantined_txns = transformer.transform_stripe_charges(raw_transactions)
        else:  # salesforce
            valid_custs, quarantined_custs = transformer.transform_salesforce_accounts(raw_customers)
            valid_txns, quarantined_txns = transformer.transform_salesforce_opportunities(raw_transactions)

        metrics["records_failed"] = len(quarantined_custs) + len(quarantined_txns)
        
        # Save quarantine files
        save_quarantine_records(source, "customers", run_id, quarantined_custs)
        save_quarantine_records(source, "transactions", run_id, quarantined_txns)

        # 5. Load Data Warehouse
        loader = WarehouseLoader(db_session)
        loaded_customers = loader.upsert_customers(valid_custs)
        loaded_txns = loader.upsert_transactions(valid_txns)
        
        metrics["records_loaded"] = loaded_customers + loaded_txns
        
        # Determine status: SUCCESS, PARTIAL_SUCCESS, or FAILED
        if metrics["records_failed"] > 0:
            if metrics["records_loaded"] > 0:
                metrics["status"] = "PARTIAL_SUCCESS"
            else:
                metrics["status"] = "FAILED"
        else:
            metrics["status"] = "SUCCESS"

        logger.info(
            f"ETL Execution finished with status: {metrics['status']}. "
            f"Loaded: {metrics['records_loaded']}, Failed (quarantined): {metrics['records_failed']}"
        )

    except Exception as e:
        metrics["status"] = "FAILED"
        metrics["error_message"] = str(e)
        logger.error(f"ETL Execution FAILED: {e}", exc_info=True)
        send_slack_alert(run_id, source, str(e))

    finally:
        # Update run logs
        finished_at = datetime.now(timezone.utc)
        run_log = db_session.query(ETLRunLogModel).filter(ETLRunLogModel.run_id == run_id).first()
        if run_log:
            run_log.finished_at = finished_at
            run_log.status = metrics["status"]
            run_log.records_extracted = metrics["records_extracted"]
            run_log.records_loaded = metrics["records_loaded"]
            run_log.records_failed = metrics["records_failed"]
            run_log.error_message = metrics["error_message"]
            db_session.commit()
            
        db_session.close()
        
    return metrics

def main() -> None:
    """
    Entrypoint wrapper for running pipeline via terminal.
    """
    parser = argparse.ArgumentParser(description="Enterprise ETL Pipeline CLI")
    parser.add_argument(
        "--source", 
        type=str, 
        required=True, 
        choices=["stripe", "salesforce", "all"], 
        help="Target API source to extract."
    )
    parser.add_argument(
        "--full-load", 
        action="store_true", 
        help="Runs full extraction, ignoring last sync log."
    )
    
    args = parser.parse_args()

    # Initialize DB (creates target tables if missing)
    init_db()

    if args.source == "all":
        stripe_res = run_source_pipeline("stripe", full_load=args.full_load)
        sf_res = run_source_pipeline("salesforce", full_load=args.full_load)
        
        if stripe_res["status"] == "FAILED" or sf_res["status"] == "FAILED":
            sys.exit(1)
    else:
        res = run_source_pipeline(args.source, full_load=args.full_load)
        if res["status"] == "FAILED":
            sys.exit(1)

if __name__ == "__main__":
    main()
