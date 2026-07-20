"""
Meta client — wraps the Meta Marketing API (Graph API) for creating and
managing ad campaigns on Facebook/Instagram.

All spend-affecting calls create resources in PAUSED status — nothing
goes live until something explicitly activates it, on top of the
human-approval gate already enforced upstream in the advertising agent.
"""
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.logging import get_logger

logger = get_logger(__name__)

API_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{API_VERSION}"


class MetaClient:
    def __init__(self, access_token: str, ad_account_id: str, page_id: Optional[str] = None):
        self.access_token = access_token
        # Meta's API expects the "act_" prefix on ad account IDs.
        self.ad_account_id = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
        self.page_id = page_id

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    def _auth_params(self, **extra) -> Dict[str, Any]:
        return {"access_token": self.access_token, **extra}

    # ── Campaigns ─────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def create_campaign(
        self, name: str, objective: str = "OUTCOME_SALES", status: str = "PAUSED"
    ) -> Dict:
        async with self._client() as client:
            r = await client.post(
                f"{GRAPH_BASE}/{self.ad_account_id}/campaigns",
                data=self._auth_params(
                    name=name,
                    objective=objective,
                    status=status,
                    special_ad_categories="[]",
                ),
            )
            r.raise_for_status()
            return r.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def create_ad_set(
        self,
        campaign_id: str,
        name: str,
        daily_budget_cents: int,
        targeting: Dict,
        optimization_goal: str = "OFFSITE_CONVERSIONS",
        billing_event: str = "IMPRESSIONS",
        status: str = "PAUSED",
    ) -> Dict:
        async with self._client() as client:
            r = await client.post(
                f"{GRAPH_BASE}/{self.ad_account_id}/adsets",
                data=self._auth_params(
                    name=name,
                    campaign_id=campaign_id,
                    daily_budget=daily_budget_cents,
                    billing_event=billing_event,
                    optimization_goal=optimization_goal,
                    targeting=_json(targeting),
                    status=status,
                ),
            )
            r.raise_for_status()
            return r.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def create_ad_creative(
        self, name: str, message: str, link: str, image_url: str, headline: str,
        call_to_action: str = "SHOP_NOW",
    ) -> Dict:
        if not self.page_id:
            raise ValueError("page_id is required to create ad creative (object_story_spec needs a Facebook Page)")

        link_data = {
            "message": message,
            "link": link,
            "picture": image_url,
            "name": headline,
            "call_to_action": {"type": call_to_action, "value": {"link": link}},
        }
        async with self._client() as client:
            r = await client.post(
                f"{GRAPH_BASE}/{self.ad_account_id}/adcreatives",
                data=self._auth_params(
                    name=name,
                    object_story_spec=_json({"page_id": self.page_id, "link_data": link_data}),
                ),
            )
            r.raise_for_status()
            return r.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def create_ad(
        self, adset_id: str, creative_id: str, name: str, status: str = "PAUSED"
    ) -> Dict:
        async with self._client() as client:
            r = await client.post(
                f"{GRAPH_BASE}/{self.ad_account_id}/ads",
                data=self._auth_params(
                    name=name,
                    adset_id=adset_id,
                    creative=_json({"creative_id": creative_id}),
                    status=status,
                ),
            )
            r.raise_for_status()
            return r.json()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def set_status(self, object_id: str, status: str) -> Dict:
        """status: ACTIVE | PAUSED | ARCHIVED | DELETED"""
        async with self._client() as client:
            r = await client.post(
                f"{GRAPH_BASE}/{object_id}",
                data=self._auth_params(status=status),
            )
            r.raise_for_status()
            return r.json()

    # ── Performance ───────────────────────────────────────────────────────────

    async def get_insights(self, campaign_id: str) -> Dict:
        fields = "impressions,clicks,spend,actions,cpc,ctr,reach"
        async with self._client() as client:
            r = await client.get(
                f"{GRAPH_BASE}/{campaign_id}/insights",
                params=self._auth_params(fields=fields),
            )
            r.raise_for_status()
            data = r.json().get("data", [])
            return data[0] if data else {}

    async def validate_credentials(self) -> bool:
        """Cheap call to confirm the access token + ad account are usable."""
        async with self._client() as client:
            r = await client.get(
                f"{GRAPH_BASE}/{self.ad_account_id}",
                params=self._auth_params(fields="id,name,account_status"),
            )
            return r.status_code == 200


def _json(obj: Any) -> str:
    import json
    return json.dumps(obj)


def get_meta_client(access_token: str, ad_account_id: str, page_id: Optional[str] = None) -> MetaClient:
    return MetaClient(access_token, ad_account_id, page_id)
