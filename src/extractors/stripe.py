from typing import Any, Dict, List, Optional
from datetime import datetime
from src.extractors.base import BaseExtractor
from src.extractors.mock_api import MockAPIGenerator
from src.config import settings

class StripeExtractor(BaseExtractor):
    """
    Extractor class for pulling Stripe Customers and Charges.
    """
    def __init__(self):
        super().__init__(source_name="Stripe")
        self.mock_generator = MockAPIGenerator() if settings.MOCK_MODE else None

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.STRIPE_API_KEY}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

    def _extract_customers(self, since_unix: Optional[int] = None) -> List[Dict[str, Any]]:
        self.logger.info("Extracting Stripe customers...")
        customers: List[Dict[str, Any]] = []
        limit = 100
        starting_after: Optional[str] = None
        has_more = True

        while has_more:
            if settings.MOCK_MODE:
                # Retrieve from local mock generator
                batch, has_more = self.mock_generator.get_stripe_customers(
                    created_gte=since_unix,
                    limit=limit,
                    starting_after=starting_after
                )
            else:
                # Real API HTTP call
                url = "https://api.stripe.com/v1/customers"
                params: Dict[str, Any] = {"limit": limit}
                if since_unix:
                    params["created[gte]"] = since_unix
                if starting_after:
                    params["starting_after"] = starting_after

                response = self._make_request("GET", url, headers=self._get_headers(), params=params)
                res_data = response.json()
                batch = res_data.get("data", [])
                has_more = res_data.get("has_more", False)

            customers.extend(batch)
            if batch:
                starting_after = batch[-1]["id"]
                self.logger.info(f"Retrieved {len(batch)} customer records. Cursor: {starting_after}")
            else:
                has_more = False

        self.logger.info(f"Finished customer extraction. Total records: {len(customers)}")
        return customers

    def _extract_charges(self, since_unix: Optional[int] = None) -> List[Dict[str, Any]]:
        self.logger.info("Extracting Stripe charges...")
        charges: List[Dict[str, Any]] = []
        limit = 100
        starting_after: Optional[str] = None
        has_more = True

        while has_more:
            if settings.MOCK_MODE:
                # Retrieve from local mock generator
                batch, has_more = self.mock_generator.get_stripe_charges(
                    created_gte=since_unix,
                    limit=limit,
                    starting_after=starting_after
                )
            else:
                # Real API HTTP call
                url = "https://api.stripe.com/v1/charges"
                params: Dict[str, Any] = {"limit": limit}
                if since_unix:
                    params["created[gte]"] = since_unix
                if starting_after:
                    params["starting_after"] = starting_after

                response = self._make_request("GET", url, headers=self._get_headers(), params=params)
                res_data = response.json()
                batch = res_data.get("data", [])
                has_more = res_data.get("has_more", False)

            charges.extend(batch)
            if batch:
                starting_after = batch[-1]["id"]
                self.logger.info(f"Retrieved {len(batch)} charge records. Cursor: {starting_after}")
            else:
                has_more = False

        self.logger.info(f"Finished charge extraction. Total records: {len(charges)}")
        return charges

    def extract(self, since: Optional[datetime] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extracts both Stripe Customers and Charges.
        """
        since_unix = int(since.timestamp()) if since else None
        
        customers = self._extract_customers(since_unix)
        charges = self._extract_charges(since_unix)
        
        return {
            "customers": customers,
            "transactions": charges
        }
