"""
Shopify client — wraps the Shopify Admin REST + GraphQL APIs.
Handles auth, rate limiting, pagination, and retry logic.
"""
import asyncio
from typing import Any, Dict, List, Optional
from functools import lru_cache

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class ShopifyClient:
    def __init__(self, store_url: str, access_token: str):
        self.store_url = store_url.rstrip("/")
        self.access_token = access_token
        self.api_version = settings.shopify_api_version
        self.base_url = f"https://{self.store_url}/admin/api/{self.api_version}"
        self._headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=self._headers,
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=10),
        )

    # ── Products ──────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def create_product(self, product_data: Dict) -> Dict:
        async with self._client() as client:
            r = await client.post(
                f"{self.base_url}/products.json",
                json={"product": product_data},
            )
            r.raise_for_status()
            return r.json()["product"]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def update_product(self, product_id: str, product_data: Dict) -> Dict:
        async with self._client() as client:
            r = await client.put(
                f"{self.base_url}/products/{product_id}.json",
                json={"product": product_data},
            )
            r.raise_for_status()
            return r.json()["product"]

    async def list_products(self, limit: int = 250) -> List[Dict]:
        products = []
        url = f"{self.base_url}/products.json?limit={min(limit, 250)}"

        async with self._client() as client:
            while url:
                r = await client.get(url)
                r.raise_for_status()
                data = r.json()
                products.extend(data.get("products", []))

                # Handle pagination
                link = r.headers.get("Link", "")
                if 'rel="next"' in link:
                    import re
                    match = re.search(r'<([^>]+)>; rel="next"', link)
                    url = match.group(1) if match else None
                else:
                    url = None

        return products

    # ── Orders ────────────────────────────────────────────────────────────────

    async def get_orders(self, status: str = "any", limit: int = 50) -> List[Dict]:
        async with self._client() as client:
            r = await client.get(
                f"{self.base_url}/orders.json",
                params={"status": status, "limit": min(limit, 250)},
            )
            r.raise_for_status()
            return r.json().get("orders", [])

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_report_summary(self, start_date: str, end_date: str) -> Dict:
        """Get revenue/order summary via GraphQL for a date range."""
        query = """
        query GetReport($start: DateTime!, $end: DateTime!) {
          orders(query: "created_at:>=$start created_at:<=$end", first: 250) {
            edges {
              node {
                totalPriceSet { shopMoney { amount } }
                subtotalPriceSet { shopMoney { amount } }
                totalRefundedSet { shopMoney { amount } }
                financialStatus
              }
            }
          }
        }
        """
        result = await self.graphql(query, variables={"start": start_date, "end": end_date})
        orders = result.get("data", {}).get("orders", {}).get("edges", [])

        total_revenue = sum(
            float(o["node"]["totalPriceSet"]["shopMoney"]["amount"])
            for o in orders
        )
        total_refunds = sum(
            float(o["node"]["totalRefundedSet"]["shopMoney"]["amount"])
            for o in orders
        )

        return {
            "order_count": len(orders),
            "total_revenue": total_revenue,
            "total_refunds": total_refunds,
            "refund_rate": total_refunds / total_revenue if total_revenue > 0 else 0,
            "aov": total_revenue / len(orders) if orders else 0,
        }

    # ── Inventory ─────────────────────────────────────────────────────────────

    async def get_inventory_levels(self, inventory_item_ids: List[str]) -> List[Dict]:
        async with self._client() as client:
            r = await client.get(
                f"{self.base_url}/inventory_levels.json",
                params={"inventory_item_ids": ",".join(inventory_item_ids)},
            )
            r.raise_for_status()
            return r.json().get("inventory_levels", [])

    # ── GraphQL ───────────────────────────────────────────────────────────────

    async def graphql(self, query: str, variables: Optional[Dict] = None) -> Dict:
        async with self._client() as client:
            r = await client.post(
                f"https://{self.store_url}/admin/api/{self.api_version}/graphql.json",
                json={"query": query, "variables": variables or {}},
            )
            r.raise_for_status()
            return r.json()

    # ── Webhooks ──────────────────────────────────────────────────────────────

    async def register_webhooks(self, webhooks: List[Dict]) -> List[Dict]:
        created = []
        for webhook in webhooks:
            async with self._client() as client:
                r = await client.post(
                    f"{self.base_url}/webhooks.json",
                    json={"webhook": webhook},
                )
                if r.status_code in (200, 201, 422):  # 422 = already exists
                    created.append(r.json())
        return created


def get_shopify_client(store_url: str, access_token: str) -> ShopifyClient:
    return ShopifyClient(store_url, access_token)
