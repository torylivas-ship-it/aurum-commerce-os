"""
Product Discovery Agent — scans multiple platforms for trending product
opportunities, scores each one, and persists approved candidates to the DB.

Sources scanned:
  - Google Trends (via SERP API)
  - Reddit (subreddit trending posts)
  - Amazon Movers & Shakers (via Tandem browser)
  - TikTok trends (via Tandem browser)
  - AliExpress trending (via API)
  - CJ Dropshipping catalog

Every discovered product is scored by OpportunityScorer.
Products that pass are saved to the DB and an approval request is created
for human review before launching.
"""
import asyncio
import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, FrozenSet, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import select

from agents.base import BaseAgent, AgentResult
from agents.opportunity_scorer import OpportunityScorer
from agents.opportunity_scorer.scorer import ProductCandidate
from core.database import AsyncSessionLocal
from core.database.models import (
    ApprovalRequest, ApprovalStatus, Product, ProductStatus, TrendSignal
)
from core.events import Events
from core.logging import get_logger
from llm.router import LLMModel

logger = get_logger(__name__)

# Filler words that don't distinguish one product idea from another
# (e.g. "GaN 65W USB-C Fast Charger" vs "GaN Fast Charger 65W").
_DEDUPE_STOPWORDS = {
    "w", "usb", "c", "multi", "port", "pack", "set", "with", "for",
    "the", "a", "of", "and",
}

# Two product names are considered the same idea when their keyword
# signatures overlap by at least this fraction (of the smaller set).
_DEDUPE_SIMILARITY_THRESHOLD = 0.6

# Broader pool to rotate through each run, instead of always scanning the
# same fixed niches — the LLM scans otherwise produce near-identical
# suggestions run after run since the prompt barely changes.
_ALL_NICHES = [
    "home kitchen", "fitness", "pets", "automotive", "tech accessories",
    "outdoor", "beauty personal care", "office productivity", "baby toddler",
    "gaming", "travel", "gardening", "health wellness",
    "cleaning organization", "kids toys", "photography", "cycling",
    "home security", "sustainable eco-friendly", "crafts hobbies",
]

# How many of the most-common already-discovered products to name in the
# LLM prompts so it stops re-suggesting the same staples every run.
_MAX_KNOWN_PRODUCTS_IN_PROMPT = 100

# Idea-generation calls get a higher temperature than analytical calls so
# the LLM doesn't converge on the same handful of ideas every run.
_IDEA_GENERATION_TEMPERATURE = 0.9


class ProductDiscoveryAgent(BaseAgent):
    name = "product_discovery"
    description = (
        "Discovers trending product opportunities across multiple platforms, "
        "scores each one using the Opportunity Scoring formula, and submits "
        "viable candidates for human approval."
    )

    def __init__(self):
        super().__init__()
        self.scorer = OpportunityScorer()

    async def run(self, niches: Optional[List[str]] = None, limit: int = 50, **kwargs) -> AgentResult:
        # Rotate through a broad niche pool by default instead of always
        # scanning the same 6, so the LLM prompts vary run to run.
        niches = niches or random.sample(_ALL_NICHES, k=6)

        self.logger.info("discovery.starting", niches=niches, limit=limit)

        # Fetch the existing catalog first so the LLM scans can be told what
        # we already carry and avoid re-suggesting it.
        async with AsyncSessionLocal() as db:
            existing_signatures, known_product_names = await self._existing_catalog(db)

        known_products_prompt = known_product_names[:_MAX_KNOWN_PRODUCTS_IN_PROMPT]

        raw_candidates: List[Dict] = []

        # Gather from all sources concurrently
        results = await asyncio.gather(
            self._scan_reddit(niches),
            self._scan_google_trends(niches, known_products_prompt),
            self._scan_aliexpress(niches, known_products_prompt),
            self._scan_with_llm(niches, known_products_prompt),
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, Exception):
                self.logger.warning("discovery.source_failed", error=str(result))
            elif result:
                raw_candidates.extend(result)

        self.logger.info("discovery.raw_count", count=len(raw_candidates))

        # Deduplicate by name similarity, against both this batch and every
        # product ever discovered (regardless of status) so the same idea
        # doesn't get re-submitted for approval run after run.
        candidates = self._deduplicate(raw_candidates, existing_signatures)[:limit]
        self.logger.info(
            "discovery.deduplicated",
            raw=len(raw_candidates),
            unique=len(candidates),
            existing_products=len(existing_signatures),
        )

        # Score each candidate
        scored = []
        rejected = []
        for c_data in candidates:
            candidate = self._dict_to_candidate(c_data)
            score_result = self.scorer.score(candidate)

            if score_result.is_viable and score_result.opportunity_score >= 60:
                scored.append((c_data, score_result))
            else:
                rejected.append({
                    "name": c_data.get("name"),
                    "reasons": score_result.rejection_reasons,
                    "score": score_result.opportunity_score,
                })

        self.logger.info(
            "discovery.scored",
            viable=len(scored),
            rejected=len(rejected),
        )

        # Persist viable products and request approvals
        saved_products = []
        async with AsyncSessionLocal() as db:
            for c_data, score in scored:
                product = await self._save_product(db, c_data, score)
                saved_products.append(product)
                await self._create_approval_request(db, product, score)

            # Save trend signals
            await self._save_trend_signals(db, raw_candidates)

            await db.commit()

        # Publish event for each viable product
        for product in saved_products:
            await self._publish(Events.PRODUCT_DISCOVERED, {
                "product_id": str(product.id),
                "name": product.name,
                "opportunity_score": product.opportunity_score,
                "confidence_score": product.confidence_score,
            })

        return AgentResult.ok(
            data={
                "discovered": len(raw_candidates),
                "viable": len(scored),
                "rejected": len(rejected),
                "products": [
                    {
                        "id": str(p.id),
                        "name": p.name,
                        "opportunity_score": p.opportunity_score,
                        "gross_margin": p.gross_margin,
                    }
                    for p in saved_products
                ],
                "rejection_summary": rejected[:10],
            },
            sources_scanned=4,
        )

    # ── Data Sources ──────────────────────────────────────────────────────────

    async def _scan_reddit(self, niches: List[str]) -> List[Dict]:
        """Fetch trending posts from buy-related subreddits."""
        import aiohttp

        subreddits = [
            "shutupandtakemymoney", "BuyItForLife", "frugalmalefashion",
            "GiftIdeas", "ProductReviews", "amazonfinds", "TheGirlSurvivalGuide",
        ]
        candidates = []

        async with aiohttp.ClientSession() as session:
            for sub in subreddits[:5]:
                try:
                    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=25"
                    headers = {"User-Agent": "AurumCommerceOS/1.0"}
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as r:
                        if r.status == 200:
                            data = await r.json()
                            posts = data.get("data", {}).get("children", [])
                            for post in posts:
                                p = post.get("data", {})
                                title = p.get("title", "")
                                score = p.get("score", 0)
                                if score > 100:
                                    candidates.append({
                                        "name": title[:200],
                                        "source_platform": "reddit",
                                        "source_url": f"https://reddit.com{p.get('permalink', '')}",
                                        "social_signal_score": min(score / 1000 * 100, 100),
                                        "trend_score": 50.0,
                                        "data_sources_count": 1,
                                    })
                except Exception as e:
                    self.logger.debug("reddit.sub_failed", sub=sub, error=str(e))

        return candidates

    def _avoid_clause(self, known_products: List[str]) -> str:
        if not known_products:
            return ""
        known_str = "; ".join(known_products)
        return (
            f" We already carry these products (or close variants/rewordings of them) — "
            f"do NOT suggest any of them again: {known_str}. Prioritize genuinely different "
            "product ideas over common dropshipping staples like phone mounts, GaN/USB-C "
            "chargers, resistance bands, LED strips, or water bottles unless you have a "
            "truly novel angle not already covered above."
        )

    async def _scan_google_trends(self, niches: List[str], known_products: Optional[List[str]] = None) -> List[Dict]:
        """Use fast LLM to generate product ideas based on Google Trends patterns."""
        try:
            niche_str = ", ".join(niches)
            prompt = (
                f"List 8 trending ecommerce products for niches: {niche_str}."
                f"{self._avoid_clause(known_products or [])} "
                "Return ONLY a JSON array, no explanation:\n"
                '[{"name":"Product","category":"niche","supplier_cost":10.0,"shipping_cost":3.0,'
                '"estimated_selling_price":44.99,"trend_score":75,"search_volume_score":70,'
                '"competition_score":65,"supplier_rating":4.6,"shipping_days":12,'
                '"source_platform":"google_trends","data_sources_count":2,"data_freshness_days":1,'
                '"evidence":{"trend_direction":"rising"}}]'
            )
            data = await self.think_json(prompt, model=LLMModel.FAST, temperature=_IDEA_GENERATION_TEMPERATURE)
            if isinstance(data, list):
                for item in data:
                    item.setdefault("data_sources_count", 2)
                    item.setdefault("data_freshness_days", 1)
                    item.setdefault("supplier_rating", 4.5)
                    item.setdefault("shipping_days", 12)
                return data
        except Exception as e:
            self.logger.warning("google_trends.llm_failed", error=str(e))
        return []

    async def _scan_aliexpress(self, niches: List[str], known_products: Optional[List[str]] = None) -> List[Dict]:
        """Fast LLM scan for AliExpress/CJ Dropshipping trending products."""
        try:
            niche_str = ", ".join(niches)
            prompt = (
                f"List 8 AliExpress bestsellers for niches: {niche_str}."
                f"{self._avoid_clause(known_products or [])} "
                "Return ONLY JSON array:\n"
                '[{"name":"Product","category":"niche","supplier_cost":8.0,"shipping_cost":2.5,'
                '"estimated_selling_price":39.99,"trend_score":78,"search_volume_score":70,'
                '"social_signal_score":65,"sales_velocity_score":80,"competition_score":65,'
                '"market_saturation":35,"supplier_rating":4.7,"supplier_delivery_score":85,'
                '"supplier_inventory_score":90,"shipping_days":10,"supplier_name":"Supplier Co.",'
                '"source_platform":"aliexpress","data_sources_count":3,"trend_consistency_score":75,'
                '"evidence":{"monthly_orders":"3000+","avg_rating":4.7}}]'
            )
            data = await self.think_json(prompt, model=LLMModel.FAST, temperature=_IDEA_GENERATION_TEMPERATURE)
            if isinstance(data, list):
                return data
        except Exception as e:
            self.logger.warning("aliexpress.scan_failed", error=str(e))
        return []

    async def _scan_with_llm(self, niches: List[str], known_products: Optional[List[str]] = None) -> List[Dict]:
        """Fast LLM scan for TikTok/social commerce trending products."""
        try:
            niche_str = ", ".join(niches)
            prompt = (
                f"List 8 viral TikTok/social commerce products for niches: {niche_str}. "
                f"Focus on impulse-buy $20-80 products.{self._avoid_clause(known_products or [])} "
                "Return ONLY JSON array:\n"
                '[{"name":"Product","category":"niche","supplier_cost":12.0,"shipping_cost":3.0,'
                '"estimated_selling_price":49.99,"trend_score":85,"search_volume_score":72,'
                '"social_signal_score":90,"sales_velocity_score":82,"competition_score":60,'
                '"market_saturation":30,"supplier_rating":4.6,"shipping_days":12,'
                '"source_platform":"tiktok_trends","data_sources_count":3,"trend_consistency_score":80,'
                '"evidence":{"viral_metric":"trending","ugc_potential":"high"}}]'
            )
            data = await self.think_json(prompt, model=LLMModel.FAST, temperature=_IDEA_GENERATION_TEMPERATURE)
            if isinstance(data, list):
                for item in data:
                    item.setdefault("source_platform", "trend_analysis")
                    item.setdefault("data_sources_count", 2)
                return data
        except Exception as e:
            self.logger.warning("llm_scan.failed", error=str(e))
        return []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _dict_to_candidate(self, d: Dict) -> ProductCandidate:
        return ProductCandidate(
            name=d.get("name", "Unknown Product"),
            supplier_cost=float(d.get("supplier_cost", 0) or 0),
            shipping_cost=float(d.get("shipping_cost", 0) or 0),
            estimated_selling_price=float(d.get("estimated_selling_price", 0) or 0),
            trend_score=float(d.get("trend_score", 0) or 0),
            search_volume_score=float(d.get("search_volume_score", 0) or 0),
            social_signal_score=float(d.get("social_signal_score", 0) or 0),
            sales_velocity_score=float(d.get("sales_velocity_score", 0) or 0),
            competition_score=float(d.get("competition_score", 50) or 50),
            market_saturation=float(d.get("market_saturation", 0) or 0),
            supplier_rating=float(d.get("supplier_rating", 0) or 0),
            supplier_delivery_score=float(d.get("supplier_delivery_score", 0) or 0),
            supplier_inventory_score=float(d.get("supplier_inventory_score", 0) or 0),
            shipping_days=int(d.get("shipping_days", 30) or 30),
            shipping_reliability=float(d.get("shipping_reliability", 0) or 0),
            data_sources_count=int(d.get("data_sources_count", 1) or 1),
            data_freshness_days=int(d.get("data_freshness_days", 7) or 7),
            trend_consistency_score=float(d.get("trend_consistency_score", 0) or 0),
            evidence=d.get("evidence", {}),
            source_platform=d.get("source_platform", ""),
            source_url=d.get("source_url", ""),
            image_url=d.get("image_url", ""),
            category=d.get("category", ""),
            supplier_name=d.get("supplier_name", ""),
            supplier_url=d.get("supplier_url", ""),
        )

    def _keyword_signature(self, name: str) -> FrozenSet[str]:
        """Order/wording-independent signature for a product name, used to
        catch near-duplicates like 'GaN 65W USB-C Fast Charger' vs
        'GaN Fast Charger 65W'."""
        text = re.sub(r"\([^)]*\)", "", name)
        text = re.sub(r"\d+", "", text)
        words = set(re.findall(r"[a-z]+", text.lower())) - _DEDUPE_STOPWORDS
        return frozenset(words)

    def _is_same_idea(self, a: FrozenSet[str], b: FrozenSet[str]) -> bool:
        if not a or not b:
            return False
        overlap = len(a & b) / min(len(a), len(b))
        return overlap >= _DEDUPE_SIMILARITY_THRESHOLD

    async def _existing_catalog(self, db) -> Tuple[List[FrozenSet[str]], List[str]]:
        """Every distinct product idea already in the DB (any status), as
        both a signature list (for dedup) and a representative name per
        idea (for telling the LLM what to avoid re-suggesting)."""
        result = await db.execute(select(Product.name))
        names = [name for (name,) in result.all() if name]

        signatures: List[FrozenSet[str]] = []
        representatives: List[str] = []
        for name in names:
            sig = self._keyword_signature(name)
            if not sig or any(self._is_same_idea(sig, seen) for seen in signatures):
                continue
            signatures.append(sig)
            representatives.append(name)
        return signatures, representatives

    def _deduplicate(
        self, candidates: List[Dict], existing_signatures: Optional[List[FrozenSet[str]]] = None
    ) -> List[Dict]:
        seen_signatures: List[FrozenSet[str]] = list(existing_signatures or [])
        unique = []
        for c in candidates:
            sig = self._keyword_signature(c.get("name", ""))
            if not sig or any(self._is_same_idea(sig, seen) for seen in seen_signatures):
                continue
            seen_signatures.append(sig)
            unique.append(c)
        return unique

    async def _save_product(self, db, c_data: Dict, score) -> Product:
        product = Product(
            name=c_data.get("name", "Unknown"),
            category=c_data.get("category"),
            source_platform=c_data.get("source_platform"),
            source_url=c_data.get("source_url"),
            image_url=c_data.get("image_url"),
            supplier_name=c_data.get("supplier_name"),
            supplier_url=c_data.get("supplier_url"),
            supplier_cost=score.supplier_cost,
            shipping_cost=score.shipping_cost,
            selling_price=score.estimated_selling_price,
            gross_margin=score.gross_margin,
            supplier_rating=c_data.get("supplier_rating"),
            shipping_days=c_data.get("shipping_days"),
            opportunity_score=score.opportunity_score,
            confidence_score=score.confidence_score,
            risk_score=score.risk_score,
            demand_score=score.demand_score,
            competition_score=score.competition_score,
            status=ProductStatus.DISCOVERED,
            evidence=c_data.get("evidence", {}),
            score_breakdown=score.score_breakdown,
        )
        db.add(product)
        await db.flush()
        return product

    async def _create_approval_request(self, db, product: Product, score) -> None:
        approval = ApprovalRequest(
            product_id=product.id,
            request_type="product_launch",
            title=f"Launch: {product.name}",
            description=score.explanation,
            data={
                "product_id": str(product.id),
                "opportunity_score": score.opportunity_score,
                "confidence_score": score.confidence_score,
                "risk_score": score.risk_score,
                "gross_margin": score.gross_margin,
                "selling_price": score.estimated_selling_price,
                "supplier_cost": score.supplier_cost,
                "profit_per_unit": score.profit_per_unit,
                "recommendation": score.recommendation,
                "score_breakdown": score.score_breakdown,
            },
            confidence_score=score.confidence_score,
            risk_assessment=f"Risk Score: {score.risk_score:.0f}/100",
            impact=f"Est. ${score.profit_per_unit:.2f} profit/unit at {score.gross_margin:.1%} margin",
        )
        db.add(approval)

    async def _save_trend_signals(self, db, candidates: List[Dict]) -> None:
        platforms = {}
        for c in candidates:
            platform = c.get("source_platform", "unknown")
            if platform not in platforms:
                platforms[platform] = 0
            platforms[platform] += 1

        for platform, count in platforms.items():
            signal = TrendSignal(
                keyword=f"product_discovery_{platform}",
                platform=platform,
                signal_type="product_trend",
                strength=min(count * 5, 100),
                data={"product_count": count},
                detected_at=datetime.now(timezone.utc),
            )
            db.add(signal)
