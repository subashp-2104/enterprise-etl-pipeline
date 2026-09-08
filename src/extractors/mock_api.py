import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple, Optional

class MockAPIGenerator:
    """
    Generates realistic, reproducible mock data for Stripe and Salesforce APIs.
    Supports timestamp filtering, pagination, and relation linking.
    """
    def __init__(self, seed: int = 42):
        # We seed values to keep mock generation predictable but rich
        self.customers_count = 50
        self.stripe_customers = self._build_stripe_customers()
        self.stripe_charges = self._build_stripe_charges()
        
        self.sf_accounts = self._build_sf_accounts()
        self.sf_opportunities = self._build_sf_opportunities()

    def _build_stripe_customers(self) -> List[Dict[str, Any]]:
        customers = []
        base_time = datetime(2026, 8, 1, tzinfo=timezone.utc)
        
        first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson"]
        
        for i in range(self.customers_count):
            customer_id = f"cus_stripe_{1000 + i}"
            fn = first_names[i % len(first_names)]
            ln = last_names[(i + 3) % len(last_names)]
            name = f"{fn} {ln}"
            email = f"{fn.lower()}.{ln.lower()}{i}@example.com"
            phone = f"+1-555-010-{i:04d}"
            # Customers created spread across August 2026
            created_at = base_time + timedelta(days=i * 0.5)
            
            customers.append({
                "id": customer_id,
                "object": "customer",
                "name": name,
                "email": email,
                "phone": phone,
                "created": int(created_at.timestamp()),
                "currency": "usd",
                "delinquent": False,
                "metadata": {"department": "sales"}
            })
        return customers

    def _build_stripe_charges(self) -> List[Dict[str, Any]]:
        charges = []
        base_time = datetime(2026, 8, 2, tzinfo=timezone.utc)
        
        for i in range(120): # Generate 120 charges
            charge_id = f"ch_stripe_{5000 + i}"
            # Link to a customer
            cust_idx = i % self.customers_count
            customer_id = self.stripe_customers[cust_idx]["id"]
            
            amount = (1000 + (i * 250)) # From $10.00 to $310.00
            created_at = base_time + timedelta(hours=i * 5)
            status = "succeeded" if i % 15 != 0 else "failed" # A few failed charges
            
            charges.append({
                "id": charge_id,
                "object": "charge",
                "customer": customer_id,
                "amount": amount,
                "currency": "usd",
                "status": status,
                "paid": status == "succeeded",
                "refunded": False,
                "created": int(created_at.timestamp()),
                "receipt_email": self.stripe_customers[cust_idx]["email"]
            })
        return charges

    def _build_sf_accounts(self) -> List[Dict[str, Any]]:
        accounts = []
        base_time = datetime(2026, 8, 1, tzinfo=timezone.utc)
        
        companies = ["Acme Corp", "Globex", "Initech", "Umbrella Corp", "Vehement Capital", "Hooli", "Soylent Corp", "Aperture Sci", "Stark Ind", "Wayne Ent"]
        
        for i in range(self.customers_count):
            account_id = f"001sf{i:012d}"
            company_name = f"{companies[i % len(companies)]} {100 + i}"
            email = f"billing@{company_name.lower().replace(' ', '')}.com"
            phone = f"+1-800-555-{i:04d}"
            # Salesforce modified stamps
            created_date = base_time + timedelta(days=i * 0.5)
            
            accounts.append({
                "Id": account_id,
                "Name": company_name,
                "Email__c": email,
                "Phone": phone,
                "CreatedDate": created_date.isoformat(),
                "SystemModstamp": (created_date + timedelta(minutes=10)).isoformat(),
                "BillingCity": "San Francisco",
                "BillingState": "CA"
            })
        return accounts

    def _build_sf_opportunities(self) -> List[Dict[str, Any]]:
        opportunities = []
        base_time = datetime(2026, 8, 2, tzinfo=timezone.utc)
        
        stages = ["Prospecting", "Needs Analysis", "Proposal/Price Quote", "Closed Won", "Closed Lost"]
        
        for i in range(80):
            opp_id = f"006sf{i:012d}"
            acc_idx = i % self.customers_count
            account_id = self.sf_accounts[acc_idx]["Id"]
            
            amount = 5000.0 + (i * 1250.0) # $5,000 to $103,750
            created_date = base_time + timedelta(days=i * 0.3)
            stage = stages[i % len(stages)] if i % 10 != 0 else "Closed Won"
            close_date = (created_date + timedelta(days=15)).strftime("%Y-%m-%d")
            
            opportunities.append({
                "Id": opp_id,
                "AccountId": account_id,
                "Name": f"{self.sf_accounts[acc_idx]['Name']} - Deal {i}",
                "Amount": amount,
                "CurrencyIsoCode": "USD",
                "StageName": stage,
                "CloseDate": close_date,
                "CreatedDate": created_date.isoformat(),
                "SystemModstamp": (created_date + timedelta(days=5)).isoformat()
            })
        return opportunities

    # Stripe Mock API methods
    def get_stripe_customers(
        self, 
        created_gte: Optional[int] = None, 
        limit: int = 10, 
        starting_after: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], bool]:
        
        # Filter by date
        data = self.stripe_customers
        if created_gte:
            data = [c for c in data if c["created"] >= created_gte]
            
        # Find index for starting_after
        start_idx = 0
        if starting_after:
            for idx, c in enumerate(data):
                if c["id"] == starting_after:
                    start_idx = idx + 1
                    break
        
        sliced_data = data[start_idx : start_idx + limit]
        has_more = (start_idx + limit) < len(data)
        
        return sliced_data, has_more

    def get_stripe_charges(
        self, 
        created_gte: Optional[int] = None, 
        limit: int = 10, 
        starting_after: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], bool]:
        
        data = self.stripe_charges
        if created_gte:
            data = [c for c in data if c["created"] >= created_gte]
            
        start_idx = 0
        if starting_after:
            for idx, c in enumerate(data):
                if c["id"] == starting_after:
                    start_idx = idx + 1
                    break
                    
        sliced_data = data[start_idx : start_idx + limit]
        has_more = (start_idx + limit) < len(data)
        
        return sliced_data, has_more

    # Salesforce Mock API methods
    def get_sf_accounts(
        self, 
        modified_since_iso: Optional[str] = None, 
        limit: int = 10, 
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], bool]:
        
        data = self.sf_accounts
        if modified_since_iso:
            since_dt = datetime.fromisoformat(modified_since_iso.replace("Z", "+00:00"))
            valid_accounts = []
            for a in data:
                mod_dt = datetime.fromisoformat(a["SystemModstamp"].replace("Z", "+00:00"))
                if mod_dt >= since_dt:
                    valid_accounts.append(a)
            data = valid_accounts
            
        sliced_data = data[offset : offset + limit]
        has_more = (offset + limit) < len(data)
        
        return sliced_data, has_more

    def get_sf_opportunities(
        self, 
        modified_since_iso: Optional[str] = None, 
        limit: int = 10, 
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], bool]:
        
        data = self.sf_opportunities
        if modified_since_iso:
            since_dt = datetime.fromisoformat(modified_since_iso.replace("Z", "+00:00"))
            valid_opps = []
            for o in data:
                mod_dt = datetime.fromisoformat(o["SystemModstamp"].replace("Z", "+00:00"))
                if mod_dt >= since_dt:
                    valid_opps.append(o)
            data = valid_opps
            
        sliced_data = data[offset : offset + limit]
        has_more = (offset + limit) < len(data)
        
        return sliced_data, has_more
