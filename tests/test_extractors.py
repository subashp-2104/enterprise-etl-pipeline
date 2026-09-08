import unittest
from datetime import datetime, timezone, timedelta
from src.extractors.mock_api import MockAPIGenerator
from src.extractors.stripe import StripeExtractor
from src.extractors.salesforce import SalesforceExtractor
from src.config import settings

class TestExtractors(unittest.TestCase):
    def setUp(self):
        # Force mock mode for extractor tests
        settings.MOCK_MODE = True
        self.generator = MockAPIGenerator()

    def test_mock_api_generator_stripe_customers(self):
        """
        Verify Stripe customer generation and pagination limits.
        """
        # Test basic retrieval
        records, has_more = self.generator.get_stripe_customers(limit=5)
        self.assertEqual(len(records), 5)
        self.assertTrue(has_more)
        
        # Test starting_after cursor
        last_id = records[-1]["id"]
        next_records, next_has_more = self.generator.get_stripe_customers(limit=5, starting_after=last_id)
        self.assertEqual(len(next_records), 5)
        self.assertNotEqual(records[0]["id"], next_records[0]["id"])

    def test_mock_api_generator_stripe_charges(self):
        """
        Verify Stripe charges date filter works.
        """
        # Pick a date timestamp from mid-August
        mid_august = int(datetime(2026, 8, 15, tzinfo=timezone.utc).timestamp())
        records, _ = self.generator.get_stripe_charges(created_gte=mid_august, limit=100)
        
        for r in records:
            self.assertGreaterEqual(r["created"], mid_august)

    def test_mock_api_generator_salesforce_accounts(self):
        """
        Verify Salesforce Accounts filters by SystemModstamp.
        """
        since_dt = datetime(2026, 8, 10, tzinfo=timezone.utc)
        since_iso = since_dt.isoformat()
        
        records, _ = self.generator.get_sf_accounts(modified_since_iso=since_iso, limit=10)
        
        for r in records:
            mod_dt = datetime.fromisoformat(r["SystemModstamp"].replace("Z", "+00:00"))
            self.assertGreaterEqual(mod_dt, since_dt)

    def test_stripe_extractor(self):
        """
        Verify StripeExtractor pulls data in mock mode.
        """
        extractor = StripeExtractor()
        data = extractor.extract()
        
        self.assertIn("customers", data)
        self.assertIn("transactions", data)
        self.assertGreater(len(data["customers"]), 0)
        self.assertGreater(len(data["transactions"]), 0)

    def test_salesforce_extractor(self):
        """
        Verify SalesforceExtractor pulls data in mock mode.
        """
        extractor = SalesforceExtractor()
        data = extractor.extract()
        
        self.assertIn("customers", data)
        self.assertIn("transactions", data)
        self.assertGreater(len(data["customers"]), 0)
        self.assertGreater(len(data["transactions"]), 0)
        
if __name__ == '__main__':
    unittest.main()
