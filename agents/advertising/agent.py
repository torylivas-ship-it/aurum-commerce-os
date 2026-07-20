"""
Advertising Agent — drafts Meta (Facebook/Instagram) ad campaigns for the
best-performing launched products, with AI-generated creative and basic
audience targeting.

Safety model, matching the human-in-the-loop pattern used everywhere
else in Aurum: this agent only ever creates campaigns in
PENDING_APPROVAL status plus an ApprovalRequest. Nothing is created on
Meta's platform until a human approves — and even then, every object
created on Meta (campaign/ad set/ad) is left PAUSED there. Actually
spending money requires a separate, explicit activation step that this
agent does not perform.
"""
from typing import Dict, List, Optional

from agents.base import BaseAgent, AgentResult
from core.config import settings
from core.database import AsyncSessionLocal
from core.database.models import (
    AdCampaign, ApprovalRequest, CampaignStatus, Product, ProductStatus,
)
from core.events import Events
from core.logging import get_logger
from integrations.meta import MetaClient
from llm.router import LLMModel
from sqlalchemy import select

logger = get_logger(__name__)

DEFAULT_DAILY_BUDGET = 15.00  # USD — conservative starter budget per campaign
MAX_CAMPAIGNS_PER_RUN = 3
MIN_OPPORTUNITY_SCORE_FOR_ADS = 75.0

CATEGORY_INTERESTS = {
    "fitness": ["Physical fitness", "Gym", "Bodybuilding"],
    "pets": ["Pet", "Dog", "Cat"],
    "automotive": ["Car", "Automobile"],
    "tech accessories": ["Consumer electronics", "Gadgets"],
    "home kitchen": ["Home appliance", "Cooking"],
    "outdoor": ["Outdoor recreation", "Camping"],
}


class AdvertisingAgent(BaseAgent):
    name = "advertising"
    description = (
        "Drafts Meta ad campaigns for the best-performing launched products, "
        "with AI-generated creative and audience targeting. Every campaign "
        "requires human approval before any spend — nothing goes live "
        "automatically, and objects created on Meta stay paused until "
        "separately activated."
    )

    async def run(self, **kwargs) -> AgentResult:
        drafted: List[AdCampaign] = []
        async with AsyncSessionLocal() as db:
            candidates = await self._find_candidates(db)
            for product in candidates[:MAX_CAMPAIGNS_PER_RUN]:
                campaign = await self._draft_campaign(db, product)
                if campaign:
                    drafted.append(campaign)
            await db.commit()

        for campaign in drafted:
            await self._publish(Events.AD_CAMPAIGN_DRAFTED, {
                "campaign_id": str(campaign.id),
                "name": campaign.name,
                "daily_budget": campaign.daily_budget,
            })

        return AgentResult.ok(
            data={
                "campaigns_drafted": len(drafted),
                "candidates_considered": len(candidates),
            }
        )

    async def _find_candidates(self, db) -> List[Product]:
        """Launched products with a good opportunity score that don't
        already have a campaign in flight."""
        result = await db.execute(
            select(Product)
            .where(Product.status.in_([ProductStatus.LAUNCHED, ProductStatus.SCALING]))
            .where(Product.opportunity_score >= MIN_OPPORTUNITY_SCORE_FOR_ADS)
            .order_by(Product.opportunity_score.desc())
        )
        products = result.scalars().all()

        existing = await db.execute(
            select(AdCampaign.product_id).where(
                AdCampaign.status.in_([
                    CampaignStatus.DRAFT, CampaignStatus.PENDING_APPROVAL,
                    CampaignStatus.ACTIVE, CampaignStatus.PAUSED,
                ])
            )
        )
        already_has_campaign = {row[0] for row in existing.all()}

        return [p for p in products if p.id not in already_has_campaign]

    async def _draft_campaign(self, db, product: Product) -> Optional[AdCampaign]:
        creative = await self._generate_creative(product)
        targeting = self._build_targeting(product)

        campaign = AdCampaign(
            product_id=product.id,
            store_id=product.store_id,
            platform="meta",
            name=f"{product.name} — Conversions",
            objective="OUTCOME_SALES",
            status=CampaignStatus.PENDING_APPROVAL,
            daily_budget=DEFAULT_DAILY_BUDGET,
            creative=creative,
            targeting=targeting,
        )
        db.add(campaign)
        await db.flush()

        margin_note = f" at {product.gross_margin:.1%} margin" if product.gross_margin else ""
        db.add(ApprovalRequest(
            campaign_id=campaign.id,
            request_type="ad_campaign_launch",
            title=f"Launch ad campaign: {product.name}",
            description=(
                f"{creative.get('primary_text', '')}\n\n"
                f"Daily budget: ${DEFAULT_DAILY_BUDGET:.2f} | "
                f"Targeting: {targeting.get('summary', 'general audience')}"
            ),
            data={
                "campaign_id": str(campaign.id),
                "product_id": str(product.id),
                "daily_budget": DEFAULT_DAILY_BUDGET,
                "creative": creative,
                "targeting": targeting,
            },
            impact=f"Est. reach driven by ${DEFAULT_DAILY_BUDGET:.2f}/day{margin_note}",
            confidence_score=product.confidence_score,
            risk_assessment=(
                "Real ad spend once activated. Approving here only creates "
                "the campaign on Meta in PAUSED status — a separate manual "
                "step in Meta Ads Manager is required to actually spend."
            ),
        ))

        logger.info("ad_campaign.drafted", product=product.name, campaign_id=str(campaign.id))
        return campaign

    async def _generate_creative(self, product: Product) -> Dict:
        prompt = (
            f"Write Facebook/Instagram ad copy for this product:\n"
            f"Name: {product.name}\n"
            f"Category: {product.category}\n"
            f"Price: ${product.selling_price or 0:.2f}\n"
            f"Description: {(product.description or '')[:300]}\n\n"
            "Return JSON only:\n"
            '{"headline": "...", "primary_text": "...", "description": "..."}\n'
            "headline: max 40 chars, punchy. primary_text: 1-2 sentences, "
            "benefit-focused, include a light call to action. description: "
            "max 30 chars, e.g. a price or urgency hook."
        )
        try:
            data = await self.think_json(prompt, model=LLMModel.FAST, temperature=0.7)
            link = None
            if product.evidence:
                link = product.evidence.get("shopify_admin_url")
            return {
                "headline": (data.get("headline") or product.name)[:40],
                "primary_text": data.get("primary_text", ""),
                "description": data.get("description", ""),
                "image_url": product.image_url,
                "link": link,
            }
        except Exception as exc:
            logger.warning("ad_creative_generation_failed", product=product.name, error=str(exc))
            return {
                "headline": product.name[:40],
                "primary_text": f"Check out {product.name} — now available.",
                "description": f"${product.selling_price or 0:.2f}",
                "image_url": product.image_url,
                "link": None,
            }

    def _build_targeting(self, product: Product) -> Dict:
        """Basic interest-based targeting derived from category. A human
        reviews this at approval time — nothing here is final until then."""
        category = (product.category or "").lower()
        interests = CATEGORY_INTERESTS.get(category, ["Online shopping"])

        return {
            "age_min": 22,
            "age_max": 55,
            "genders": [0],  # 0 = all genders
            "geo_locations": {"countries": ["US"]},
            "interests": interests,
            "summary": f"US, ages 22-55, interests: {', '.join(interests)}",
        }


async def launch_ad_campaign(campaign: AdCampaign, db) -> dict:
    """Actually create the campaign/ad set/creative/ad on Meta after human
    approval. Everything is created PAUSED on Meta's side — this never
    spends money by itself; a separate explicit activation in Meta Ads
    Manager is required for that."""
    if not settings.meta_access_token or not settings.meta_ad_account_id:
        campaign.status = CampaignStatus.FAILED
        campaign.rejection_reason = "Meta not configured (missing access token / ad account id)"
        await db.commit()
        return {"launched": False, "reason": "meta_not_configured"}

    client = MetaClient(
        access_token=settings.meta_access_token,
        ad_account_id=settings.meta_ad_account_id,
        page_id=settings.meta_page_id,
    )

    try:
        campaign_resp = await client.create_campaign(name=campaign.name, objective=campaign.objective)
        platform_campaign_id = campaign_resp["id"]

        adset_resp = await client.create_ad_set(
            campaign_id=platform_campaign_id,
            name=f"{campaign.name} — Ad Set",
            daily_budget_cents=int((campaign.daily_budget or DEFAULT_DAILY_BUDGET) * 100),
            targeting=campaign.targeting,
        )
        platform_adset_id = adset_resp["id"]

        creative = campaign.creative or {}
        creative_resp = await client.create_ad_creative(
            name=f"{campaign.name} — Creative",
            message=creative.get("primary_text", ""),
            link=creative.get("link") or "https://theoasismarket-store.myshopify.com",
            image_url=creative.get("image_url"),
            headline=creative.get("headline", campaign.name),
        )
        platform_creative_id = creative_resp["id"]

        ad_resp = await client.create_ad(
            adset_id=platform_adset_id,
            creative_id=platform_creative_id,
            name=f"{campaign.name} — Ad",
        )

        campaign.platform_campaign_id = platform_campaign_id
        campaign.platform_adset_id = platform_adset_id
        campaign.platform_ad_id = ad_resp["id"]
        # Created on Meta, but every object above defaults to PAUSED status
        # there — reflect that here rather than implying it's spending.
        campaign.status = CampaignStatus.PAUSED
        await db.commit()

        logger.info(
            "ad_campaign_launched",
            campaign=campaign.name,
            platform_campaign_id=platform_campaign_id,
        )
        return {
            "launched": True,
            "platform_campaign_id": platform_campaign_id,
            "note": "Created on Meta in PAUSED status — activate manually in Meta Ads Manager to start spending.",
        }
    except Exception as exc:
        logger.error("ad_campaign_launch_failed", campaign=campaign.name, error=str(exc))
        campaign.status = CampaignStatus.FAILED
        campaign.rejection_reason = str(exc)
        await db.commit()
        return {"launched": False, "reason": "meta_error", "error": str(exc)}
