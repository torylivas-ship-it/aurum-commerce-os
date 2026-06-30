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

        shopify_admin_url = (
            f"https://{store.shopify_store_url}/admin/products/{shopify_product['id']}"
        )

        product.shopify_product_id = str(shopify_product["id"])
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
