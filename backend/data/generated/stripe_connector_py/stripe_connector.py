import logging
import time
from typing import Any, Dict, List, Optional

import requests


logger = logging.getLogger(__name__)


class ConnectorError(Exception):
    pass


class StripeConnector:
    def __init__(self, base_url: str, token: str, timeout: int = 30, max_retries: int = 3, rate_limit_per_second: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_per_second = rate_limit_per_second
        self._last_request_ts = 0.0
        self.session = requests.Session()

    def authenticate(self) -> Dict[str, str]:
        if not self.token:
            raise ConnectorError("Missing API token")
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _respect_rate_limit(self) -> None:
        minimum_interval = 1.0 / max(self.rate_limit_per_second, 1.0)
        now = time.monotonic()
        elapsed = now - self._last_request_ts
        if elapsed < minimum_interval:
            time.sleep(minimum_interval - elapsed)
        self._last_request_ts = time.monotonic()

    def _request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = self.authenticate()
        errors: List[str] = []
        for attempt in range(1, self.max_retries + 1):
            self._respect_rate_limit()
            try:
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    params=params,
                    json=payload,
                    timeout=self.timeout,
                )
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", "1"))
                    logger.warning("Rate limited by Stripe; sleeping for %s seconds", retry_after)
                    time.sleep(retry_after)
                    continue
                response.raise_for_status()
                if not response.content:
                    return {}
                return response.json()
            except requests.RequestException as exc:
                errors.append(str(exc))
                logger.warning("Attempt %s failed for %s %s: %s", attempt, method, url, exc)
                if attempt == self.max_retries:
                    raise ConnectorError(f"Request failed after {self.max_retries} attempts: {'; '.join(errors)}") from exc
                time.sleep(attempt)
        raise ConnectorError("Request unexpectedly exhausted retries")

    def create_record(self, entity: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", f"api/{entity}", payload=payload)

    def get_record(self, entity: str, record_id: str) -> Dict[str, Any]:
        return self._request("GET", f"api/{entity}/{record_id}")

    def update_record(self, entity: str, record_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PUT", f"api/{entity}/{record_id}", payload=payload)

    def delete_record(self, entity: str, record_id: str) -> Dict[str, Any]:
        return self._request("DELETE", f"api/{entity}/{record_id}")

    def list_records(self, entity: str, page_size: int = 100) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        page = 1
        while True:
            result = self._request("GET", f"api/{entity}", params={"page": page, "page_size": page_size})
            batch = result.get("items", [])
            records.extend(batch)
            if not result.get("next_page"):
                break
            page = int(result["next_page"])
        return records


__all__ = ["StripeConnector", "ConnectorError"]