import time
from typing import Any, Dict, List, Optional
from datetime import datetime
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.utils.logger import get_logger

class RateLimitError(requests.exceptions.HTTPError):
    """Exception raised when an API rate limit is exceeded (HTTP 429)."""
    pass

class BaseExtractor:
    """
    Base Extractor class providing robust, retry-safe API consumption logic.
    """
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """
        Inspects responses for rate limiting. If encountered, parses headers 
        and pauses execution prior to throwing an error to trigger a retry.
        """
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            sleep_time = 2.0
            if retry_after:
                try:
                    sleep_time = float(retry_after)
                except ValueError:
                    # In case of HTTP date formats (e.g. Wed, 21 Oct 2015 07:28:00 GMT)
                    sleep_time = 5.0
            
            self.logger.warning(
                f"Rate limit hit (429) on {self.source_name}. Sleeping for {sleep_time}s before retrying."
            )
            time.sleep(sleep_time)
            raise RateLimitError("Rate limit exceeded", response=response)

    @retry(
        retry=retry_if_exception_type((requests.exceptions.RequestException, RateLimitError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        reraise=True
    )
    def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> requests.Response:
        """
        Wrapper to perform HTTP calls utilizing tenacity retries for network 
        failures, timeouts, and rate limits.
        """
        self.logger.debug(f"Executing API request: {method} {url}")
        
        # Enable auto-raise of connection issues or standard timeouts
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_data,
            timeout=30.0,
            **kwargs
        )
        
        self._handle_rate_limit(response)
        response.raise_for_status()
        return response

    def extract(self, since: Optional[datetime] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extracts data since the given datetime (incremental load) or all records (full load).
        Returns a dictionary of entity lists, e.g. {'customers': [...], 'transactions': [...]}
        """
        raise NotImplementedError("Subclasses must implement extract()")
