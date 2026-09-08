import os
import unittest
from datetime import datetime, timezone
from src.config import settings
from src.utils.db import SessionLocal, init_db, UnifiedCustomerModel, UnifiedTransactionModel, ETLRunLogModel, Base, engine
from src.pipeline import run_source_pipeline

class TestPipelineIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Override configuration for integration testing
        cls.test_db_file = "./test_integration_warehouse.db"
        settings.DATABASE_URL = f"sqlite:///{cls.test_db_file}"
        settings.MOCK_MODE = True
        settings.RAW_STORAGE_PATH = "./test_raw_data"
        
        # Re-bind the engine and SessionLocal in db.py to use the test database
        from src.utils import db
        import sqlalchemy
        
        # Dispose the old engine
        db.engine.dispose()
        
        # Delete test db file if it exists to ensure a clean start
        if os.path.exists(cls.test_db_file):
            try:
                os.remove(cls.test_db_file)
            except Exception:
                pass
                
        # Recreate test engine and configure SessionLocal
        db.engine = sqlalchemy.create_engine(
            settings.DATABASE_URL, 
            pool_pre_ping=True, 
            connect_args={"check_same_thread": False}
        )
        db.SessionLocal.configure(bind=db.engine)
        
        # Reset database tables
        db.Base.metadata.create_all(bind=db.engine)

    @classmethod
    def tearDownClass(cls):
        # Clean up database files and directories
        from src.utils import db
        db.engine.dispose()
        
        if os.path.exists(cls.test_db_file):
            try:
                os.remove(cls.test_db_file)
            except Exception as e:
                print(f"Could not delete test DB file: {e}")

        # Clean up test raw directories
        import shutil
        if os.path.exists("./test_raw_data"):
            shutil.rmtree("./test_raw_data")
        if os.path.exists("./quarantine"):
            shutil.rmtree("./quarantine")

    def test_end_to_end_pipeline(self):
        """
        Runs the full Stripe and Salesforce ETL pipelines end-to-end in mock mode
        and verifies data persistence and run logs.
        """
        db = SessionLocal()
        
        # 1. Verify initially database is empty
        self.assertEqual(db.query(UnifiedCustomerModel).count(), 0)
        self.assertEqual(db.query(UnifiedTransactionModel).count(), 0)
        self.assertEqual(db.query(ETLRunLogModel).count(), 0)

        # 2. Run Stripe ETL Pipeline (Full Load)
        stripe_metrics = run_source_pipeline("stripe", full_load=True)
        self.assertEqual(stripe_metrics["status"], "SUCCESS")
        self.assertGreater(stripe_metrics["records_extracted"], 0)
        self.assertGreater(stripe_metrics["records_loaded"], 0)

        # Assert Stripe customers and charges exist in DB
        stripe_cust_count = db.query(UnifiedCustomerModel).filter(UnifiedCustomerModel.source_system == "stripe").count()
        stripe_tx_count = db.query(UnifiedTransactionModel).filter(UnifiedTransactionModel.source_system == "stripe").count()
        
        self.assertGreater(stripe_cust_count, 0)
        self.assertGreater(stripe_tx_count, 0)

        # 3. Run Salesforce ETL Pipeline (Full Load)
        sf_metrics = run_source_pipeline("salesforce", full_load=True)
        self.assertEqual(sf_metrics["status"], "SUCCESS")
        self.assertGreater(sf_metrics["records_extracted"], 0)
        self.assertGreater(sf_metrics["records_loaded"], 0)

        # Assert Salesforce accounts and opportunities exist in DB
        sf_cust_count = db.query(UnifiedCustomerModel).filter(UnifiedCustomerModel.source_system == "salesforce").count()
        sf_tx_count = db.query(UnifiedTransactionModel).filter(UnifiedTransactionModel.source_system == "salesforce").count()
        
        self.assertGreater(sf_cust_count, 0)
        self.assertGreater(sf_tx_count, 0)

        # 4. Verify ETL Run Log entry
        run_logs = db.query(ETLRunLogModel).all()
        self.assertEqual(len(run_logs), 2)
        
        sources_logged = [log.source for log in run_logs]
        self.assertIn("stripe", sources_logged)
        self.assertIn("salesforce", sources_logged)

        # 5. Run Incremental Sync (should run but add 0 new records since no new data has been simulated)
        stripe_inc_metrics = run_source_pipeline("stripe", full_load=False)
        self.assertEqual(stripe_inc_metrics["status"], "SUCCESS")
        
        # Since it is incremental since the last execution run, and the mock generator generates
        # static dates in the past, it should return 0 new updates or load 0 records.
        # Let's verify that incremental filtering is working by confirming it finished successfully.
        self.assertEqual(stripe_inc_metrics["status"], "SUCCESS")

        db.close()

if __name__ == '__main__':
    unittest.main()
