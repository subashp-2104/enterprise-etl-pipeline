import os
import uvicorn
from datetime import datetime, timedelta
from typing import Dict, List, Any
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.config import settings
from src.utils.logger import get_logger
from src.utils.db import (
    init_db, 
    SessionLocal, 
    UnifiedCustomerModel, 
    UnifiedTransactionModel, 
    ETLRunLogModel
)
from src.pipeline import run_source_pipeline

logger = get_logger("DashboardServer")

app = FastAPI(title="Enterprise ETL Synchronizer Dashboard")

# Resolve directories relative to this file
base_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(base_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)

# Mount static folder for CSS
app.mount("/static", StaticFiles(directory=os.path.join(base_dir, "static")), name="static")

# Database Session Dependency
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    """
    Ensure the database and tables are initialized when the server starts.
    """
    init_db()

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """
    Serves the dashboard user interface page.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db_session)) -> Dict[str, Any]:
    """
    Returns aggregated KPIs, timeline logs, and chart metrics.
    """
    try:
        # Customers breakdown
        cust_counts = (
            db.query(UnifiedCustomerModel.source_system, func.count(UnifiedCustomerModel.id))
            .group_by(UnifiedCustomerModel.source_system)
            .all()
        )
        customers_by_source = {source: count for source, count in cust_counts}
        
        # Default empty counts
        for source in ["stripe", "salesforce"]:
            if source not in customers_by_source:
                customers_by_source[source] = 0

        # Total revenue of completed transactions
        total_rev = (
            db.query(func.sum(UnifiedTransactionModel.amount))
            .filter(UnifiedTransactionModel.status == "completed")
            .scalar()
        ) or 0.0

        # Total pipeline executions log count
        total_runs = db.query(ETLRunLogModel).count()

        # Build timeline revenue data for Chart.js
        # Group transaction amounts by date (YYYY-MM-DD) and source system
        txns = (
            db.query(
                UnifiedTransactionModel.source_system,
                UnifiedTransactionModel.transaction_date,
                UnifiedTransactionModel.amount
            )
            .filter(UnifiedTransactionModel.status == "completed")
            .all()
        )

        timeline: Dict[str, Dict[str, float]] = {}
        for source, tx_date, amount in txns:
            # Convert date to string format YYYY-MM-DD
            date_str = tx_date.strftime("%Y-%m-%d")
            if date_str not in timeline:
                timeline[date_str] = {"stripe": 0.0, "salesforce": 0.0}
            timeline[date_str][source] = timeline[date_str].get(source, 0.0) + float(amount)

        # Fill missing dates to keep charts smooth
        # Sort and return timeline stats
        sorted_timeline = {d: timeline[d] for d in sorted(timeline.keys())[-15:]} # Limit to last 15 days of revenue

        return {
            "db_url": db.bind.url.render_as_string(hide_password=True),
            "customers_by_source": customers_by_source,
            "total_revenue": float(total_rev),
            "total_runs": total_runs,
            "revenue_timeline": sorted_timeline
        }
    except Exception as e:
        logger.error(f"Failed to fetch stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/customers", response_model=List[Dict[str, Any]])
def get_customers(db: Session = Depends(get_db_session)):
    """
    Returns lists of all consolidated customer records.
    """
    try:
        custs = db.query(UnifiedCustomerModel).order_by(UnifiedCustomerModel.created_at.desc()).all()
        return [
            {
                "source_system": c.source_system,
                "source_id": c.source_id,
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "created_at": c.created_at.isoformat()
            }
            for c in custs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/transactions", response_model=List[Dict[str, Any]])
def get_transactions(db: Session = Depends(get_db_session)):
    """
    Returns list of all consolidated transaction records.
    """
    try:
        txns = db.query(UnifiedTransactionModel).order_by(UnifiedTransactionModel.transaction_date.desc()).all()
        return [
            {
                "source_system": t.source_system,
                "source_transaction_id": t.source_transaction_id,
                "customer_id": t.customer_id,
                "amount": float(t.amount),
                "currency": t.currency,
                "status": t.status,
                "transaction_date": t.transaction_date.isoformat()
            }
            for t in txns
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs", response_model=List[Dict[str, Any]])
def get_logs(db: Session = Depends(get_db_session)):
    """
    Returns details of past pipeline execution audits.
    """
    try:
        logs = db.query(ETLRunLogModel).order_by(ETLRunLogModel.started_at.desc()).limit(50).all()
        return [
            {
                "run_id": l.run_id,
                "source": l.source,
                "status": l.status,
                "records_extracted": l.records_extracted,
                "records_loaded": l.records_loaded,
                "records_failed": l.records_failed,
                "started_at": l.started_at.isoformat(),
                "finished_at": l.finished_at.isoformat() if l.finished_at else None,
                "error_message": l.error_message
            }
            for l in logs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trigger/{source}")
def trigger_pipeline(source: str):
    """
    Synchronously triggers the specified source ETL pipeline.
    """
    if source.lower() not in ["stripe", "salesforce"]:
        raise HTTPException(status_code=400, detail="Invalid source parameter.")
        
    try:
        # We run it synchronously here so the UI receives the execution metrics response immediately
        metrics = run_source_pipeline(source, full_load=False)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {e}")

if __name__ == "__main__":
    # Start web server on port 5000
    uvicorn.run(app, host="0.0.0.0", port=5000)
