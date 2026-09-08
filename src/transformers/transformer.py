from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from pydantic import ValidationError

from src.utils.logger import get_logger
from src.validation.cleaner import clean_email, clean_phone, parse_datetime
from src.validation.models import (
    StripeCustomerRaw,
    StripeChargeRaw,
    SalesforceAccountRaw,
    SalesforceOpportunityRaw,
    UnifiedCustomer,
    UnifiedTransaction
)

class ETLTransformer:
    """
    Handles parsing, cleaning, validation, and schema unification for Stripe and Salesforce entities.
    """
    def __init__(self):
        self.logger = get_logger("Transformer")

    def _quarantine_record(self, raw_record: Dict[str, Any], error_msg: str, entity: str, source: str) -> Dict[str, Any]:
        """
        Formats a rejected record with execution context for quarantine logging.
        """
        return {
            "source_system": source,
            "entity": entity,
            "record": raw_record,
            "error_message": error_msg,
            "quarantined_at": datetime.now(timezone.utc).isoformat()
        }

    def transform_stripe_customers(
        self, raw_records: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validates raw Stripe customers and maps them to the Unified Customer format.
        """
        valid_records: List[Dict[str, Any]] = []
        quarantined: List[Dict[str, Any]] = []

        for record in raw_records:
            try:
                # 1. Validate raw API structure
                raw_model = StripeCustomerRaw(**record)
                
                # 2. Map and clean to Unified Schema
                unified = UnifiedCustomer(
                    source_system="stripe",
                    source_id=raw_model.id,
                    email=clean_email(raw_model.email),
                    name=raw_model.name,
                    phone=clean_phone(raw_model.phone),
                    created_at=parse_datetime(raw_model.created),
                    updated_at=datetime.now(timezone.utc)
                )
                valid_records.append(unified.model_dump())
            except (ValidationError, TypeError, ValueError) as e:
                err_msg = str(e)
                self.logger.warning(f"Quarantining Stripe Customer ({record.get('id', 'unknown')}): {err_msg}")
                quarantined.append(self._quarantine_record(record, err_msg, "customer", "stripe"))

        return valid_records, quarantined

    def transform_stripe_charges(
        self, raw_records: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validates raw Stripe charges and maps them to the Unified Transaction format.
        """
        valid_records: List[Dict[str, Any]] = []
        quarantined: List[Dict[str, Any]] = []

        # Stripe status mappings
        status_map = {
            "succeeded": "completed",
            "failed": "failed",
            "pending": "pending"
        }

        for record in raw_records:
            try:
                # 1. Validate raw API structure
                raw_model = StripeChargeRaw(**record)
                
                # 2. Standardize status
                status = status_map.get(raw_model.status.lower(), "pending")
                
                # 3. Map and clean to Unified Schema
                unified = UnifiedTransaction(
                    source_system="stripe",
                    source_transaction_id=raw_model.id,
                    customer_id=raw_model.customer,
                    amount=float(raw_model.amount) / 100.0,  # Convert cents to dollars
                    currency=raw_model.currency.upper(),
                    status=status,
                    transaction_date=parse_datetime(raw_model.created),
                    updated_at=datetime.now(timezone.utc)
                )
                valid_records.append(unified.model_dump())
            except (ValidationError, TypeError, ValueError) as e:
                err_msg = str(e)
                self.logger.warning(f"Quarantining Stripe Charge ({record.get('id', 'unknown')}): {err_msg}")
                quarantined.append(self._quarantine_record(record, err_msg, "transaction", "stripe"))

        return valid_records, quarantined

    def transform_salesforce_accounts(
        self, raw_records: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validates raw Salesforce Accounts and maps them to the Unified Customer format.
        """
        valid_records: List[Dict[str, Any]] = []
        quarantined: List[Dict[str, Any]] = []

        for record in raw_records:
            try:
                # 1. Validate raw API structure
                raw_model = SalesforceAccountRaw(**record)
                
                # 2. Map and clean to Unified Schema
                unified = UnifiedCustomer(
                    source_system="salesforce",
                    source_id=raw_model.Id,
                    email=clean_email(raw_model.Email__c),
                    name=raw_model.Name,
                    phone=clean_phone(raw_model.Phone),
                    created_at=parse_datetime(raw_model.CreatedDate),
                    updated_at=parse_datetime(raw_model.SystemModstamp)
                )
                valid_records.append(unified.model_dump())
            except (ValidationError, TypeError, ValueError) as e:
                err_msg = str(e)
                self.logger.warning(f"Quarantining Salesforce Account ({record.get('Id', 'unknown')}): {err_msg}")
                quarantined.append(self._quarantine_record(record, err_msg, "customer", "salesforce"))

        return valid_records, quarantined

    def transform_salesforce_opportunities(
        self, raw_records: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validates raw Salesforce Opportunities and maps them to the Unified Transaction format.
        """
        valid_records: List[Dict[str, Any]] = []
        quarantined: List[Dict[str, Any]] = []

        for record in raw_records:
            try:
                # 1. Validate raw API structure
                raw_model = SalesforceOpportunityRaw(**record)
                
                # 2. Standardize status based on opportunity stage
                stage = raw_model.StageName.lower()
                if stage == "closed won":
                    status = "completed"
                elif stage == "closed lost":
                    status = "failed"
                else:
                    status = "pending"

                # 3. Map and clean to Unified Schema
                unified = UnifiedTransaction(
                    source_system="salesforce",
                    source_transaction_id=raw_model.Id,
                    customer_id=raw_model.AccountId,
                    amount=raw_model.Amount or 0.0,
                    currency=raw_model.CurrencyIsoCode.upper(),
                    status=status,
                    transaction_date=parse_datetime(raw_model.CreatedDate),
                    updated_at=parse_datetime(raw_model.SystemModstamp)
                )
                valid_records.append(unified.model_dump())
            except (ValidationError, TypeError, ValueError) as e:
                err_msg = str(e)
                self.logger.warning(f"Quarantining Salesforce Opportunity ({record.get('Id', 'unknown')}): {err_msg}")
                quarantined.append(self._quarantine_record(record, err_msg, "transaction", "salesforce"))

        return valid_records, quarantined
