# Aurum Commerce OS

AI-Powered Commerce Operating System running on NVIDIA DGX Spark.

## Quick Start

```bash
# 1. Setup
bash scripts/setup.sh

# 2. Start full stack
make up

# 3. Open dashboard
open http://localhost:3000

# 4. Run product discovery now
make run-agent agent=product_discovery

# 5. Generate morning brief
make brief
```

## Architecture

```
aurum-commerce-os/
├── core/               # Config, DB, Events, Tasks, Logging
├── agents/             # 18 independent AI agents
├── api/                # FastAPI backend (port 8000)
├── dashboard/          # Next.js dashboard (port 3000)
├── integrations/       # Shopify, Meta, TikTok, AliExpress...
├── llm/                # LLM Router (Ollama local → Claude cloud fallback)
└── docker-compose.yml  # Full stack: Postgres, Redis, ChromaDB
```

## Services

| Service      | Port | Purpose                          |
|-------------|------|----------------------------------|
| Dashboard   | 3000 | Executive web dashboard           |
| API         | 8000 | FastAPI backend + /docs           |
| Flower      | 5555 | Celery task monitor               |
| PostgreSQL  | 5432 | Primary database                  |
| Redis       | 6379 | Cache + task queue                |
| ChromaDB    | 8001 | Vector store (business memory)    |

## Agents

| Agent                | Schedule      | Purpose                              |
|---------------------|---------------|--------------------------------------|
| product_discovery    | Every 6h      | Scans 4+ platforms for opportunities |
| trend_intelligence   | Every 2h      | Detects trend signals, 90-day forecast|
| competitor_intel     | Daily 3am     | Monitors competitor activity          |
| risk_intelligence    | Every hour    | Detects margin/shipping/review risks  |
| executive_advisor    | Daily 7am CT  | Morning business brief + email        |

## Opportunity Score Formula

```
Opportunity Score = 30% Demand + 25% Margin + 20% Competition + 15% Supplier + 10% Shipping

Hard Rejects:
  - Gross margin < 40%
  - Shipping > 15 days
  - Supplier rating < 4.0
  - Confidence score < 65
```

## Human Approval Required For

- Publishing products to Shopify
- Spending advertising budget (> $100)
- Price changes > 15%
- Refunds
- Irreversible business decisions

## LLM Strategy

- **Primary**: Ollama on DGX Spark (70B for reasoning, 3B for fast tasks)
- **Fallback**: Claude API (only when Ollama unavailable)
- **Embeddings**: nomic-embed-text (local only)
- **Zero proprietary data sent to cloud** unless Ollama is down

## Environment

Copy `.env.example` to `.env` and fill in:
- `SHOPIFY_STORES` — JSON array of store credentials
- `ANTHROPIC_API_KEY` — Claude fallback (optional if Ollama always available)
- `SMTP_USER/PASSWORD` — For morning brief email delivery
