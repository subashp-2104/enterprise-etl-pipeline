from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import urllib.parse
from src.extractors.base import BaseExtractor
from src.extractors.mock_api import MockAPIGenerator
from src.config import settings

class SalesforceExtractor(BaseExtractor):
    """
    Extractor class for pulling Salesforce Accounts and Opportunities.
    """
    def __init__(self):
        super().__init__(source_name="Salesforce")
        self.mock_generator = MockAPIGenerator() if settings.MOCK_MODE else None
        self.access_token: Optional[str] = None
        self.instance_url: Optional[str] = None

    def _authenticate(self) -> None:
        """
        Authenticates with Salesforce via OAuth2 username/password flow.
        """
        if settings.MOCK_MODE:
            self.access_token = "mock_sf_token"
            self.instance_url = "https://mock.salesforce.com"
            return

        if self.access_token and self.instance_url:
            return  # Already authenticated

        self.logger.info("Authenticating with Salesforce API...")
        auth_url = f"https://{settings.SALESFORCE_DOMAIN}.salesforce.com/services/oauth2/token"
        
        # Combine password and security token for API authentication
        password_with_token = f"{settings.SALESFORCE_PASSWORD}{settings.SALESFORCE_SECURITY_TOKEN}"
        
        data = {
            "grant_type": "password",
            "client_id": settings.SALESFORCE_CLIENT_ID,
            "client_secret": settings.SALESFORCE_CLIENT_SECRET,
            "username": settings.SALESFORCE_USERNAME,
            "password": password_with_token
        }

        # Authenticate uses a direct requests call (without standard retry headers, but using our standard wrapper)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = self._make_request("POST", auth_url, headers=headers, data=data)
        auth_data = response.json()
        
        self.access_token = auth_data["access_token"]
        self.instance_url = auth_data["instance_url"]
        self.logger.info("Salesforce authentication successful.")

    def _get_headers(self) -> Dict[str, str]:
        self._authenticate()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def _run_query(self, query: str, mock_callback) -> List[Dict[str, Any]]:
        self.logger.debug(f"Running SOQL Query: {query}")
        records: List[Dict[str, Any]] = []
        
        if settings.MOCK_MODE:
            # Under mock mode, the mock_callback parses the query limits & offsets
            has_more = True
            offset = 0
            limit = 50
            while has_more:
                batch, has_more = mock_callback(limit=limit, offset=offset)
                records.extend(batch)
                offset += limit
            return records

        # Real API SOQL query execution
        url = f"{self.instance_url}/services/data/v57.0/query"
        params = {"q": query}
        
        response = self._make_request("GET", url, headers=self._get_headers(), params=params)
        res_data = response.json()
        records.extend(res_data.get("records", []))
        
        next_url = res_data.get("nextRecordsUrl")
        while next_url:
            full_next_url = f"{self.instance_url}{next_url}"
            self.logger.info(f"Retrieving next page from: {next_url}")
            response = self._make_request("GET", full_next_url, headers=self._get_headers())
            res_data = response.json()
            records.extend(res_data.get("records", []))
            next_url = res_data.get("nextRecordsUrl")

        # Strip internal Salesforce attributes from final output
        for r in records:
            r.pop("attributes", None)
            
        return records

    def _extract_accounts(self, since_iso: Optional[str] = None) -> List[Dict[str, Any]]:
        self.logger.info("Extracting Salesforce Accounts...")
        
        soql = "SELECT Id, Name, Email__c, Phone, CreatedDate, SystemModstamp FROM Account"
        if since_iso:
            soql += f" WHERE SystemModstamp >= {since_iso}"
            
        mock_callback = lambda limit, offset: self.mock_generator.get_sf_accounts(
            modified_since_iso=since_iso, limit=limit, offset=offset
        )
        
        accounts = self._run_query(soql, mock_callback)
        self.logger.info(f"Finished Account extraction. Total records: {len(accounts)}")
        return accounts

    def _extract_opportunities(self, since_iso: Optional[str] = None) -> List[Dict[str, Any]]:
        self.logger.info("Extracting Salesforce Opportunities...")
        
        soql = ("SELECT Id, AccountId, Name, Amount, CurrencyIsoCode, StageName, "
                "CloseDate, CreatedDate, SystemModstamp FROM Opportunity")
        if since_iso:
            soql += f" WHERE SystemModstamp >= {since_iso}"
            
        mock_callback = lambda limit, offset: self.mock_generator.get_sf_opportunities(
            modified_since_iso=since_iso, limit=limit, offset=offset
        )
        
        opportunities = self._run_query(soql, mock_callback)
        self.logger.info(f"Finished Opportunity extraction. Total records: {len(opportunities)}")
        return opportunities

    def extract(self, since: Optional[datetime] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extracts Salesforce Accounts and Opportunities.
        """
        # Convert datetime to Salesforce SOQL standard format: YYYY-MM-DDTHH:MM:SSZ
        since_iso = None
        if since:
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
            since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        accounts = self._extract_accounts(since_iso)
        opportunities = self._extract_opportunities(since_iso)
        
        return {
            "customers": accounts,
            "transactions": opportunities
        }
