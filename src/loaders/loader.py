from typing import Any, Dict, List, Type
from sqlalchemy.orm import Session
from sqlalchemy import Table
from src.utils.db import UnifiedCustomerModel, UnifiedTransactionModel
from src.utils.logger import get_logger

class WarehouseLoader:
    """
    Handles bulk, idempotent loading of unified schemas into the Data Warehouse.
    Utilizes engine-native UPSERT logic to handle conflict scenarios.
    """
    def __init__(self, session: Session):
        self.session = session
        self.logger = get_logger(self.__class__.__name__)
        self.dialect = session.bind.dialect.name

    def upsert_customers(self, records: List[Dict[str, Any]]) -> int:
        """
        Upserts a batch of customer records.
        """
        if not records:
            return 0
        return self._upsert(UnifiedCustomerModel, records, ["source_system", "source_id"])

    def upsert_transactions(self, records: List[Dict[str, Any]]) -> int:
        """
        Upserts a batch of transaction records.
        """
        if not records:
            return 0
        return self._upsert(UnifiedTransactionModel, records, ["source_system", "source_transaction_id"])

    def _upsert(self, model_class: Type, records: List[Dict[str, Any]], conflict_keys: List[str]) -> int:
        table: Table = model_class.__table__
        
        # Route to appropriate dialect implementation
        if self.dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt_fn = pg_insert
        elif self.dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            stmt_fn = sqlite_insert
        else:
            # Sequential fallback for other database dialects (e.g. MySQL, Oracle)
            self.logger.warning(
                f"Dialect '{self.dialect}' does not support standardized bulk UPSERT. "
                f"Falling back to iterative merge."
            )
            count = 0
            for rec in records:
                try:
                    # Look up by conflict keys
                    query = self.session.query(model_class)
                    for key in conflict_keys:
                        query = query.filter(getattr(model_class, key) == rec[key])
                    existing = query.first()
                    
                    if existing:
                        for k, v in rec.items():
                            setattr(existing, k, v)
                    else:
                        self.session.add(model_class(**rec))
                    count += 1
                except Exception as e:
                    self.logger.error(f"Iterative merge failed for record {rec}: {e}")
                    raise
            self.session.commit()
            return count

        # SQLite & PostgreSQL native bulk upsert path
        stmt = stmt_fn(table).values(records)
        
        # Build update fields excluding conflict columns and surrogate IDs
        update_cols = {
            col.name: stmt.excluded[col.name]
            for col in table.columns
            if col.name not in conflict_keys and col.name != "id"
        }
        
        conflict_elements = [table.c[key] for key in conflict_keys]
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=conflict_elements,
            set_=update_cols
        )

        try:
            result = self.session.execute(upsert_stmt)
            self.session.commit()
            rows_affected = len(records)
            self.logger.info(f"Upserted {rows_affected} records into table: {table.name}")
            return rows_affected
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Failed bulk upsert into {table.name}: {e}")
            raise
