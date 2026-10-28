import json
import logging
import random
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.project_paths import fixture_path
from app.etl.validators import parse_date
from app.integrations.base import ConnectionResult, SyncResult

logger = logging.getLogger(__name__)

FIXTURE_ROOT = fixture_path()


def _load_fixture(provider_dir: str, name: str) -> Dict[str, Any]:
    path = FIXTURE_ROOT / provider_dir / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"fixture missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


class MockProvider:
    """Fixture-backed provider used when DATA_PROVIDER_MODE=mock.

    The mock serves the same payload shapes as the real provider adapters, so
    the whole RAW -> ETL -> CORE -> MART pipeline can run without credentials.
    """

    def __init__(self, provider: str, scenario: str = "healthy_growth"):
        self.provider = provider
        self.scenario = scenario
        self._fixture: Optional[Dict[str, Any]] = None
        self._rng = random.Random(hash((provider, scenario)) & 0xFFFFFFFF)

    def _dir(self) -> str:
        return {
            "META_ADS": "meta",
            "GOOGLE_ADS": "google",
            "SHOPIFY": "shopify",
        }.get(self.provider, "meta")

    def _data(self) -> Dict[str, Any]:
        if self._fixture is None:
            self._fixture = _load_fixture(self._dir(), self.scenario)
        return self._fixture

    async def validate_connection(self) -> ConnectionResult:
        data = self._data()
        account = (data.get("accounts") or [{}])[0]
        checks = {
            "api_reachable": True,
            "token_valid": True,
            "account_accessible": True,
            "scopes": data.get("scopes", ["read"]),
        }
        return ConnectionResult(
            ok=True,
            checks=checks,
            currency=account.get("currency", "USD"),
            timezone=account.get("timezone", "America/New_York"),
        )

    async def sync_accounts(self) -> List[Dict[str, Any]]:
        return list(self._data().get("accounts", []))

    async def sync_dimensions(self) -> Dict[str, List[Dict[str, Any]]]:
        data = self._data()
        return {
            "campaigns": data.get("campaigns", []),
            "ad_groups": data.get("ad_groups", []),
            "ads": data.get("ads", []),
            "creatives": data.get("creatives", []),
            "products": data.get("products", []),
            "variants": data.get("variants", []),
            "keywords": data.get("keywords", []),
            "search_terms": data.get("search_terms", []),
            "conversion_actions": data.get("conversion_actions", []),
            "asset_groups": data.get("asset_groups", []),
        }

    def _rows_in_range(
        self, rows: List[Dict[str, Any]], start_date: str, end_date: str, date_key: str = "date"
    ) -> List[Dict[str, Any]]:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        out = []
        for row in rows:
            row_date = parse_date(row.get(date_key))
            if row_date is None:
                continue
            if start <= row_date <= end:
                out.append(row)
        return out

    async def sync_performance(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        data = self._data()
        rows = self._rows_in_range(data.get("performance", []), start_date, end_date)
        # Simulate occasional rate limiting when the scenario asks for it.
        if self.scenario == "api_rate_limit":
            from app.integrations.base import ProviderRateLimited

            raise ProviderRateLimited("mock rate limit")
        if self.scenario == "schema_drift":
            from app.integrations.base import ProviderSchemaChanged

            raise ProviderSchemaChanged("mock schema drift: required field missing")
        return rows

    async def sync_commerce(self, start_date: str, end_date: str) -> Dict[str, List[Dict[str, Any]]]:
        data = self._data()
        orders = self._rows_in_range(data.get("orders", []), start_date, end_date, date_key="created_at")
        order_ids = {order.get("external_id") for order in orders}
        items = [
            item for item in data.get("order_items", []) if item.get("order_external_id") in order_ids
        ]
        refunds = [
            refund for refund in data.get("refunds", []) if refund.get("order_external_id") in order_ids
        ]
        return {"orders": orders, "order_items": items, "refunds": refunds}

    async def fetch_journey(self, external_order_id: str) -> Dict[str, Any]:
        journeys = self._data().get("journeys", [])
        for journey in journeys:
            if journey.get("order_external_id") == external_order_id:
                return journey
        return {"ready": False, "days_to_conversion": None}

    async def backfill(self, start_date: str, end_date: str) -> SyncResult:
        performance = await self.sync_performance(start_date, end_date)
        commerce = await self.sync_commerce(start_date, end_date)
        return SyncResult(
            provider=self.provider,
            job_type="INITIAL_BACKFILL",
            records_received=len(performance) + sum(len(v) for v in commerce.values()),
            api_requests=1,
            metadata={"scenario": self.scenario},
        )
