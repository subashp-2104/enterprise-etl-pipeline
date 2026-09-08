import unittest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.utils.db import Base, UnifiedCustomerModel, UnifiedTransactionModel
from src.loaders.loader import WarehouseLoader

class TestWarehouseLoader(unittest.TestCase):
    def setUp(self):
        # Set up an in-memory SQLite database for testing the loader
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        self.loader = WarehouseLoader(self.session)

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_upsert_customers(self):
        """
        Verify that upserting customers creates records and updates them on conflict.
        """
        records = [
            {
                "source_system": "stripe",
                "source_id": "cus_1",
                "email": "customer1@example.com",
                "name": "Customer One",
                "phone": "+15550001",
                "created_at": datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
                "synced_at": datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
            }
        ]

        # 1. First insert
        loaded = self.loader.upsert_customers(records)
        self.assertEqual(loaded, 1)

        # Query database
        custs = self.session.query(UnifiedCustomerModel).all()
        self.assertEqual(len(custs), 1)
        self.assertEqual(custs[0].name, "Customer One")
        self.assertEqual(custs[0].email, "customer1@example.com")

        # 2. Update record details and upsert again
        updated_records = [
            {
                "source_system": "stripe",
                "source_id": "cus_1",
                "email": "updated_customer1@example.com",
                "name": "Customer One Updated",
                "phone": "+15559999",
                "created_at": datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 8, 2, 14, 0, 0, tzinfo=timezone.utc), # newer update date
                "synced_at": datetime(2026, 8, 2, 14, 0, 0, tzinfo=timezone.utc),
            }
        ]

        self.loader.upsert_customers(updated_records)

        # Query database again - count must still be 1, values must be updated
        custs_after = self.session.query(UnifiedCustomerModel).all()
        self.assertEqual(len(custs_after), 1)
        self.assertEqual(custs_after[0].name, "Customer One Updated")
        self.assertEqual(custs_after[0].email, "updated_customer1@example.com")
        self.assertEqual(custs_after[0].phone, "+15559999")

    def test_upsert_transactions(self):
        """
        Verify that upserting transactions is idempotent.
        """
        records = [
            {
                "source_system": "salesforce",
                "source_transaction_id": "opp_1",
                "customer_id": "acc_1",
                "amount": 5000.0,
                "currency": "USD",
                "status": "pending",
                "transaction_date": datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
                "synced_at": datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
            }
        ]

        # First insert
        loaded = self.loader.upsert_transactions(records)
        self.assertEqual(loaded, 1)

        # Verify initial record
        tx = self.session.query(UnifiedTransactionModel).first()
        self.assertEqual(tx.status, "pending")

        # Second insert with updated status (Stage Close Won)
        records[0]["status"] = "completed"
        records[0]["updated_at"] = datetime(2026, 8, 15, 18, 0, 0, tzinfo=timezone.utc)
        
        self.loader.upsert_transactions(records)

        # Verify record updated and did not duplicate
        tx_count = self.session.query(UnifiedTransactionModel).count()
        self.assertEqual(tx_count, 1)
        
        tx_updated = self.session.query(UnifiedTransactionModel).first()
        self.assertEqual(tx_updated.status, "completed")
        self.assertEqual(float(tx_updated.amount), 5000.0)

if __name__ == '__main__':
    unittest.main()
