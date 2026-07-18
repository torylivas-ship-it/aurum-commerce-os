"""
ProductLauncher — pushes an approved product to Shopify and marks it LAUNCHED.

Called synchronously from the approval route after a product_launch is approved.
Also exposes a Celery task for async retries.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import Product, ProductStatus, Store
from core.events import event_bus, Events
from core.logging import get_logger
from integrations.shopify import ShopifyClient

logger = get_logger(__name__)


class ProductLauncher:
    async def launch(
        self,
        product: Product,
        db: AsyncSession,
    ) -> dict:
        """Push product to Shopify. Returns launch result dict."""

        store = await self._get_store(product, db)
        if not store:
            return {"launched": False, "reason": "no_store"}

        access_token = store.config.get("shopify_access_token")
        if not access_token or not store.shopify_store_url:
            return {"launched": False, "reason": "store_not_connected"}

        client = ShopifyClient(store.shopify_store_url, access_token)

        payload = self._build_shopify_payload(product)

        try:
            shopify_product = await client.create_product(payload)
        except Exception as exc:
            logger.error(
                "shopify_create_failed",
                product_id=str(product.id),
                error=str(exc),
            )
            return {"launched": False, "reason": "shopify_error", "error": str(exc)}

        shopify_pid = shopify_product["id"]
        shopify_admin_url = (
            f"https://{store.shopify_store_url}/admin/products/{shopify_pid}"
        )

        # Enrich with AI description + image immediately after creation
        await self._enrich_shopify_product(client, shopify_pid, product)

        product.shopify_product_id = str(shopify_pid)
        product.status = ProductStatus.LAUNCHED
        product.evidence = {
            **(product.evidence or {}),
            "shopify_handle": shopify_product.get("handle"),
            "shopify_admin_url": shopify_admin_url,
            "launched_at": datetime.now(timezone.utc).isoformat(),
            "store_name": store.name,
        }

        await db.commit()

        await event_bus.publish(Events.PRODUCT_LAUNCHED, {
            "product_id": str(product.id),
            "product_name": product.name,
            "shopify_product_id": product.shopify_product_id,
            "store_id": str(store.id),
        })

        logger.info(
            "product_launched",
            product=product.name,
            shopify_id=product.shopify_product_id,
            store=store.name,
        )

        return {
            "launched": True,
            "shopify_product_id": product.shopify_product_id,
            "shopify_admin_url": shopify_admin_url,
            "store": store.name,
        }

    async def _get_store(
        self, product: Product, db: AsyncSession
    ) -> Optional[Store]:
        if product.store_id:
            result = await db.execute(
                select(Store).where(Store.id == product.store_id)
            )
            return result.scalar_one_or_none()

        # Fall back to first active connected store
        result = await db.execute(
            select(Store).where(Store.shopify_store_url.isnot(None)).limit(1)
        )
        return result.scalar_one_or_none()

    async def _enrich_shopify_product(
        self, client: ShopifyClient, shopify_pid: int, product: Product
    ) -> None:
        """Generate AI description and attach a stock image to the Shopify product."""
        import asyncio, json
        import urllib.request, urllib.parse

        CATEGORY_IMAGES = {
            "fitness": "photo-1571019613454-1cb2f99b2d8b",
            "pets": "photo-1543466835-00a7907e9de1",
            "automotive": "photo-1492144534655-ae79c964c9d7",
            "tech accessories": "photo-1519389950473-47ba0277781c",
            "home kitchen": "photo-1556909114-f6e7ad7d3136",
            "outdoor": "photo-1476231682828-37e571bc172f",
            "general": "photo-1523275335684-37898b6baf30",
        }

        category = (product.category or "general").lower()
        photo_id = CATEGORY_IMAGES.get(category, CATEGORY_IMAGES["general"])
        image_url = f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=800&q=80"

        prompt = (
            f"Write a compelling Shopify product description in HTML for: {product.name}. "
            f"Category: {category}. Price: ${product.selling_price or 0:.2f}. "
            "Include 2-3 benefit-focused <p> tags and a <ul> with 4-5 features. "
            "Output ONLY valid HTML, no preamble."
        )

        description = ""
        try:
            body = json.dumps({
                "model": "qwen3.6:35b",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "options": {"temperature": 0.7, "num_predict": 500},
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/chat", data=body,
                headers={"Content-Type": "application/json"}
            )
            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(
                None,
                lambda: json.loads(urllib.request.urlopen(req, timeout=180).read())["message"]["content"].strip()
            )
            description = raw
        except Exception as exc:
            logger.warning("enrich_description_failed", error=str(exc))

        # "status": "active" alone does NOT publish the product to the Online
        # Store sales channel — that's controlled separately by published_at.
        # Without it, products sit active-but-invisible/unpurchasable.
        updates: dict = {
            "status": "active",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "published_scope": "web",
        }
        if description:
            updates["body_html"] = description
        updates["images"] = [{"src": image_url, "alt": product.name}]

        try:
            await client.update_product(str(shopify_pid), updates)
        except Exception as exc:
            logger.warning("enrich_shopify_update_failed", error=str(exc))

    def _build_shopify_payload(self, product: Product) -> dict:
        price = round(product.selling_price or 0, 2)
        cost = round(product.supplier_cost or 0, 2)

        payload: dict = {
            "title": product.name,
            "body_html": product.description or "",
            "vendor": product.supplier_name or "Aurum Commerce",
            "product_type": product.category or "",
            "tags": ",".join(product.tags or []),
            "status": "draft",  # draft until manual publish
            "variants": [
                {
                    "price": str(price),
                    "cost": str(cost),
                    "inventory_management": "shopify",
                    "inventory_quantity": 0,
                    "fulfillment_service": "manual",
                    "requires_shipping": True,
                    "weight": 0.5,
                    "weight_unit": "lb",
                }
            ],
        }

        if product.image_url:
            payload["images"] = [{"src": product.image_url}]

        return payload


# Module-level singleton
_launcher = ProductLauncher()


async def launch_product(product: Product, db: AsyncSession) -> dict:
    return await _launcher.launch(product, db)
