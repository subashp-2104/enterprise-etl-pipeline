from datetime import datetime, timezone
from typing import Generator
from sqlalchemy import (
    create_engine, 
    Column, 
    Integer, 
    String, 
    Float, 
    DateTime, 
    Text, 
    UniqueConstraint, 
    Numeric
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger("DB")

Base = declarative_base()

class UnifiedCustomerModel(Base):
    """
    Unified Customer Dimension Table
    """
    __tablename__ = "unified_customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_system = Column(String(50), nullable=False)
    source_id = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    synced_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("source_system", "source_id", name="uq_source_customer"),
    )

class UnifiedTransactionModel(Base):
    """
    Unified Transaction Fact Table
    """
    __tablename__ = "unified_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_system = Column(String(50), nullable=False)
    source_transaction_id = Column(String(100), nullable=False)
    customer_id = Column(String(100), nullable=False)  # Map to customer's source_id
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(10), nullable=False)
    status = Column(String(50), nullable=False)
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    synced_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("source_system", "source_transaction_id", name="uq_source_transaction"),
    )

class ETLRunLogModel(Base):
    """
    Pipeline Audit & Execution Tracking Table
    """
    __tablename__ = "etl_run_log"

    run_id = Column(String(100), primary_key=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False)  # RUNNING, SUCCESS, FAILED
    source = Column(String(50), nullable=False)    # stripe, salesforce, all
    records_extracted = Column(Integer, default=0, nullable=False)
    records_loaded = Column(Integer, default=0, nullable=False)
    records_failed = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)

# Determine engine and session factory with connection fallback
db_url = settings.DATABASE_URL
connect_args = {}

try:
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        engine = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
    else:
        # PostgreSQL or other database connection test
        engine = create_engine(db_url, pool_pre_ping=True)
        # Verify connection by executing a dummy check
        with engine.connect() as conn:
            pass
        logger.info(f"Database connection verified: {db_url}")
except Exception as e:
    logger.warning(
        f"Failed to connect to primary database ({db_url}): {e}. "
        f"Falling back to local SQLite database: sqlite:///./warehouse.db"
    )
    db_url = "sqlite:///./warehouse.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db() -> None:
    """
    Initializes tables in the target database if they do not exist.
    """
    logger.info("Initializing database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}")
        raise

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to yield database sessions safely.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
