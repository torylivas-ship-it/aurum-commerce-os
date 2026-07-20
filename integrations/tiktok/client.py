"""
TikTok client — wraps the TikTok for Business Marketing API (v1.3) for
creating and managing ad campaigns.

Same safety model as the Meta client: every campaign/ad group/ad this
creates is left in DISABLE (paused) operation status — nothing spends
until something explicitly enables it, on top of the human-approval
gate enforced upstream in the advertising agent.

Note: location and interest-category IDs in the TikTok Marketing API
are internal numeric codes (not ISO country codes), looked up via
their /tool/region/ and /tool/interest_category/ endpoints. This client
uses the commonly-documented ID for the United States (6252001) as a
default — verify against a real account's /tool/region/ response before
relying on it, since these codes are TikTok-internal and unverifiable
without live credentials.
"""
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.logging import get_logger

logger = get_logger(__name__)

API_VERSION = "v1.3"
API_BASE = f"https://business-api.tiktok.com/open_api/{API_VERSION}"

# Commonly-documented TikTok region code for the United States. TikTok's
# location targeting uses its own numeric IDs, not ISO codes — confirm
# via /tool/region/ against the real advertiser account before trusting
# this for anything beyond a US-default starting point.
US_LOCATION_ID = "6252001"


class TikTokClient:
    def __init__(self, access_token: str, advertiser_id: str):
        self.access_token = access_token
        self.advertiser_id = advertiser_id
        self._headers = {
            "Access-Token": access_token,
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self._headers, timeout=httpx.Timeout(30.0))

    # ── Assets ────────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def upload_image_by_url(self, image_url: str) -> Dict:
        """Register a hosted image (e.g. our Shopify CDN URL) with TikTok's
        asset library so it can be referenced by image_id in ad creation."""
        async with self._client() as client:
            r = await client.post(
                f"{API_BASE}/file/image/ad/upload/",
                json={
                    "advertiser_id": self.advertiser_id,
                    "upload_type": "UPLOAD_BY_URL",
                    "image_url": image_url,
                },
            )
            r.raise_for_status()
            return r.json()

    # ── Campaigns ─────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def create_campaign(
        self, name: str, objective_type: str = "CONVERSIONS",
        budget_mode: str = "BUDGET_MODE_DAY", budget: float = 20.0,
    ) -> Dict:
        async with self._client() as client:
            r = await client.post(
                f"{API_BASE}/campaign/create/",
                json={
                    "advertiser_id": self.advertiser_id,
                    "campaign_name": name,
                    "objective_type": objective_type,
                    "budget_mode": budget_mode,
                    "budget": budget,
                    # Created paused — same posture as the Meta client.
                    "operation_status": "DISABLE",
                },
            )
            r.raise_for_status()
            return r.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def create_ad_group(
        self,
        campaign_id: str,
        name: str,
        daily_budget: float,
        targeting: Dict,
        optimization_goal: str = "CONVERT",
        billing_event: str = "OCPM",
    ) -> Dict:
        async with self._client() as client:
            r = await client.post(
                f"{API_BASE}/adgroup/create/",
                json={
                    "advertiser_id": self.advertiser_id,
                    "campaign_id": campaign_id,
                    "adgroup_name": name,
                    "placement_type": "PLACEMENT_TYPE_AUTOMATIC",
                    "budget_mode": "BUDGET_MODE_DAY",
                    "budget": daily_budget,
                    "schedule_type": "SCHEDULE_FROM_NOW",
                    "optimization_goal": optimization_goal,
                    "billing_event": billing_event,
                    "pacing": "PACING_MODE_SMOOTH",
                    "location_ids": targeting.get("location_ids", [US_LOCATION_ID]),
                    "age_groups": targeting.get("age_groups", ["AGE_25_34", "AGE_35_44"]),
                    "gender": targeting.get("gender", "GENDER_UNLIMITED"),
                    # Created paused — same posture as the Meta client.
                    "operation_status": "DISABLE",
                },
            )
            r.raise_for_status()
            return r.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def create_ad(
        self,
        adgroup_id: str,
        image_id: str,
        ad_name: str,
        ad_text: str,
        landing_page_url: str,
        call_to_action: str = "SHOP_NOW",
    ) -> Dict:
        async with self._client() as client:
            r = await client.post(
                f"{API_BASE}/ad/create/",
                json={
                    "advertiser_id": self.advertiser_id,
                    "adgroup_id": adgroup_id,
                    "creatives": [{
                        "ad_name": ad_name,
                        "ad_format": "SINGLE_IMAGE",
                        "image_ids": [image_id],
                        "ad_text": ad_text,
                        "call_to_action": call_to_action,
                        "landing_page_url": landing_page_url,
                    }],
                    "operation_status": "DISABLE",
                },
            )
            r.raise_for_status()
            return r.json()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def set_status(self, object_type: str, object_ids: List[str], status: str) -> Dict:
        """object_type: CAMPAIGN | ADGROUP | AD. status: ENABLE | DISABLE."""
        endpoint = {
            "CAMPAIGN": "campaign/update/status/",
            "ADGROUP": "adgroup/update/status/",
            "AD": "ad/update/status/",
        }[object_type]
        id_field = {"CAMPAIGN": "campaign_ids", "ADGROUP": "adgroup_ids", "AD": "ad_ids"}[object_type]

        async with self._client() as client:
            r = await client.post(
                f"{API_BASE}/{endpoint}",
                json={
                    "advertiser_id": self.advertiser_id,
                    id_field: object_ids,
                    "operation_status": status,
                },
            )
            r.raise_for_status()
            return r.json()

    # ── Performance ───────────────────────────────────────────────────────────

    async def get_report(self, campaign_id: str) -> Dict:
        async with self._client() as client:
            r = await client.get(
                f"{API_BASE}/report/integrated/get/",
                params={
                    "advertiser_id": self.advertiser_id,
                    "report_type": "BASIC",
                    "dimensions": '["campaign_id"]',
                    "data_level": "AUCTION_CAMPAIGN",
                    "filters": f'[{{"field_name":"campaign_ids","filter_type":"IN","filter_value":"[\\"{campaign_id}\\"]"}}]',
                    "metrics": '["impressions","clicks","spend","conversion"]',
                },
            )
            r.raise_for_status()
            return r.json()

    async def validate_credentials(self) -> bool:
        """Cheap call to confirm the access token + advertiser ID are usable."""
        async with self._client() as client:
            r = await client.get(
                f"{API_BASE}/advertiser/info/",
                params={"advertiser_ids": f'["{self.advertiser_id}"]'},
            )
            return r.status_code == 200


def get_tiktok_client(access_token: str, advertiser_id: str) -> TikTokClient:
    return TikTokClient(access_token, advertiser_id)
