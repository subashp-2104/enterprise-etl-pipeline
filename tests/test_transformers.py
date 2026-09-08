import unittest
from datetime import datetime, timezone
from src.validation.cleaner import clean_email, clean_phone, parse_datetime
from src.transformers.transformer import ETLTransformer

class TestTransformers(unittest.TestCase):
    def setUp(self):
        self.transformer = ETLTransformer()

    def test_data_cleaning_helpers(self):
        """
        Verify sanitizers and datetime parsers work as expected.
        """
        # Email cleaning
        self.assertEqual(clean_email("  TEST@example.com  "), "test@example.com")
        self.assertIsNone(clean_email(None))

        # Phone cleaning
        self.assertEqual(clean_phone("+1 (555) 123-4567"), "+15551234567")
        self.assertEqual(clean_phone(" 098-765-43-21 "), "0987654321")
        self.assertIsNone(clean_phone(None))

        # DateTime parsing
        # Unix timestamp
        dt_unix = parse_datetime(1693353600)  # 2023-08-30 00:00:00 UTC
        self.assertEqual(dt_unix.year, 2023)
        self.assertEqual(dt_unix.month, 8)
        self.assertEqual(dt_unix.tzinfo, timezone.utc)

        # ISO String
        dt_iso = parse_datetime("2026-08-30T12:00:00Z")
        self.assertEqual(dt_iso.hour, 12)
        self.assertEqual(dt_iso.tzinfo, timezone.utc)

        # Date-only String
        dt_date = parse_datetime("2026-08-30")
        self.assertEqual(dt_date.day, 30)
        self.assertEqual(dt_date.hour, 0)
        self.assertEqual(dt_date.tzinfo, timezone.utc)

    def test_stripe_customer_transformation(self):
        """
        Verify Stripe customers are transformed to Unified Customers and invalid ones are quarantined.
        """
        raw_custs = [
            {
                "id": "cus_stripe_1",
                "name": "John Doe",
                "email": "JOHN@DOE.COM",
                "phone": "+1-234-567",
                "created": 1787654321,
                "currency": "usd"
            },
            {
                # Missing ID -> triggers validation error and quarantine
                "name": "Invalid Customer",
                "created": 1787654321
            }
        ]

        valid, quarantined = self.transformer.transform_stripe_customers(raw_custs)
        
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(quarantined), 1)
        
        c = valid[0]
        self.assertEqual(c["source_system"], "stripe")
        self.assertEqual(c["source_id"], "cus_stripe_1")
        self.assertEqual(c["email"], "john@doe.com")
        self.assertEqual(c["phone"], "+1234567")
        self.assertEqual(c["name"], "John Doe")

        q = quarantined[0]
        self.assertEqual(q["source_system"], "stripe")
        self.assertEqual(q["entity"], "customer")
        self.assertIn("Field required", q["error_message"])

    def test_stripe_charge_transformation(self):
        """
        Verify Stripe charges transform correctly (amount scale and status standardization).
        """
        raw_charges = [
            {
                "id": "ch_1",
                "customer": "cus_1",
                "amount": 2500,  # $25.00
                "currency": "usd",
                "status": "succeeded",
                "created": 1787654321,
                "paid": True,
                "refunded": False
            }
        ]
        
        valid, quarantined = self.transformer.transform_stripe_charges(raw_charges)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(quarantined), 0)
        
        t = valid[0]
        self.assertEqual(t["source_system"], "stripe")
        self.assertEqual(t["source_transaction_id"], "ch_1")
        self.assertEqual(t["customer_id"], "cus_1")
        self.assertEqual(t["amount"], 25.0)
        self.assertEqual(t["currency"], "USD")
        self.assertEqual(t["status"], "completed")

    def test_salesforce_account_opportunity_transformation(self):
        """
        Verify Salesforce Account and Opportunity mappings.
        """
        raw_accs = [{
            "Id": "001sf_1",
            "Name": "Salesforce Account",
            "Email__c": "billing@salesforce.com",
            "Phone": "555-1234",
            "CreatedDate": "2026-08-01T10:00:00Z",
            "SystemModstamp": "2026-08-01T10:05:00Z"
        }]

        valid_accs, _ = self.transformer.transform_salesforce_accounts(raw_accs)
        self.assertEqual(len(valid_accs), 1)
        self.assertEqual(valid_accs[0]["name"], "Salesforce Account")
        self.assertEqual(valid_accs[0]["source_system"], "salesforce")
        self.assertEqual(valid_accs[0]["phone"], "5551234")

        raw_opps = [{
            "Id": "006sf_1",
            "AccountId": "001sf_1",
            "Name": "Salesforce Opp",
            "Amount": 10000.0,
            "CurrencyIsoCode": "usd",
            "StageName": "Closed Won",
            "CloseDate": "2026-08-15",
            "CreatedDate": "2026-08-01T10:00:00Z",
            "SystemModstamp": "2026-08-01T10:05:00Z"
        }]

        valid_opps, _ = self.transformer.transform_salesforce_opportunities(raw_opps)
        self.assertEqual(len(valid_opps), 1)
        self.assertEqual(valid_opps[0]["source_transaction_id"], "006sf_1")
        self.assertEqual(valid_opps[0]["amount"], 10000.0)
        self.assertEqual(valid_opps[0]["status"], "completed")

if __name__ == '__main__':
    unittest.main()
