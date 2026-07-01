"""
Enriches Shopify product listings with AI-generated descriptions and stock images.
Uses Ollama qwen3.6:35b (thinking disabled) for descriptions.
Uses Unsplash topic images keyed by product category.
"""
import json
import os
import re
import time
import urllib.request
import urllib.parse

import os

SHOPIFY_SHOP = os.environ.get("SHOPIFY_STORE_URL", "qdfz1t-p9.myshopify.com")
SHOPIFY_TOKEN = os.environ["SHOPIFY_ACCESS_TOKEN"]
SHOPIFY_API = f"https://{SHOPIFY_SHOP}/admin/api/2025-01"
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3.6:35b"

HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_TOKEN,
    "Content-Type": "application/json",
}

# Curated Unsplash photo IDs by product category (reliably public domain-style)
CATEGORY_IMAGES = {
    "fitness": "photo-1571019613454-1cb2f99b2d8b",
    "pets": "photo-1543466835-00a7907e9de1",
    "automotive": "photo-1492144534655-ae79c964c9d7",
    "tech accessories": "photo-1519389950473-47ba0277781c",
    "home kitchen": "photo-1556909114-f6e7ad7d3136",
    "outdoor": "photo-1476231682828-37e571bc172f",
    "general": "photo-1523275335684-37898b6baf30",
}


def shopify_get(path):
    req = urllib.request.Request(f"{SHOPIFY_API}{path}", headers=HEADERS)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def shopify_put(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SHOPIFY_API}{path}", data=body, headers=HEADERS, method="PUT"
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def ollama_chat(prompt):
    body = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.7, "num_predict": 500},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read())
        return data["message"]["content"].strip()


def get_image_url(name, category):
    """Return a stable Unsplash CDN URL keyed by category."""
    cat = (category or "general").lower()
    photo_id = CATEGORY_IMAGES.get(cat, CATEGORY_IMAGES["general"])
    # Use Unsplash CDN direct URL (no auth needed, public images)
    return f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=800&q=80"


def build_prompt(name, category, price, tags):
    return f"""Write a compelling Shopify product description in HTML for this product.

Product: {name}
Category: {category or "general"}
Price: ${price}
Tags: {", ".join(tags) if tags else "none"}

Rules:
- 2-3 short paragraphs in <p> tags, benefit-focused (not spec-heavy)
- One <ul> with 4-5 key features
- End with a one-sentence call to action in a final <p>
- Output ONLY valid HTML, no markdown, no preamble, no explanation"""


def enrich_product(product):
    name = product["title"]
    pid = product["id"]
    variants = product.get("variants", [{}])
    price = float(variants[0].get("price", 0)) if variants else 0
    tags = [t.strip() for t in (product.get("tags") or "").split(",") if t.strip()]
    category = product.get("product_type") or "general"

    has_desc = bool(re.sub(r"<[^>]+>", "", product.get("body_html") or "").strip())
    has_image = bool(product.get("images"))

    updates = {}

    if not has_desc:
        prompt = build_prompt(name, category, price, tags)
        raw = ollama_chat(prompt)
        # Strip accidental markdown fences
        if "```" in raw:
            raw = re.sub(r"```(?:html)?\n?", "", raw).strip()
        if raw:
            updates["body_html"] = raw

    if not has_image:
        updates["images"] = [{"src": get_image_url(name, category), "alt": name}]

    if not updates:
        return False

    shopify_put(f"/products/{pid}.json", {"product": {"id": pid, **updates}})
    return True


def main():
    print("Fetching all active Shopify products...", flush=True)
    data = shopify_get(
        "/products.json?status=active&limit=250"
        "&fields=id,title,body_html,images,variants,product_type,tags"
    )
    all_products = data.get("products", [])

    needs_work = [
        p for p in all_products
        if not re.sub(r"<[^>]+>", "", p.get("body_html") or "").strip()
        or not p.get("images")
    ]
    print(f"Need enrichment: {len(needs_work)}/{len(all_products)}", flush=True)

    ok, fail = 0, 0
    for i, product in enumerate(needs_work, 1):
        name = product["title"]
        print(f"  [{i}/{len(needs_work)}] {name[:50]}", end="  ", flush=True)
        try:
            enrich_product(product)
            print("✓", flush=True)
            ok += 1
        except Exception as e:
            print(f"✗  {e}", flush=True)
            fail += 1
        time.sleep(0.5)

    print(f"\nDone — {ok} enriched, {fail} failed", flush=True)


if __name__ == "__main__":
    main()
