#!/usr/bin/env python3
"""
Quick CLI to run any agent locally without Docker/Celery.
Usage: python scripts/run_agent.py product_discovery
       python scripts/run_agent.py executive_advisor
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logging import setup_logging

setup_logging()

AGENTS = {
    "product_discovery": lambda: __import__("agents.product_discovery", fromlist=["ProductDiscoveryAgent"]).ProductDiscoveryAgent(),
    "trend_intelligence": lambda: __import__("agents.trend_intelligence", fromlist=["TrendIntelligenceAgent"]).TrendIntelligenceAgent(),
    "executive_advisor": lambda: __import__("agents.executive_advisor", fromlist=["ExecutiveAdvisorAgent"]).ExecutiveAdvisorAgent(),
    "risk_intelligence": lambda: __import__("agents.risk_intelligence", fromlist=["RiskIntelligenceAgent"]).RiskIntelligenceAgent(),
    "competitor_intel": lambda: __import__("agents.competitor_intel", fromlist=["CompetitorIntelAgent"]).CompetitorIntelAgent(),
}


async def main():
    if len(sys.argv) < 2 or sys.argv[1] not in AGENTS:
        print(f"Usage: python scripts/run_agent.py <agent_name>")
        print(f"Available: {', '.join(AGENTS.keys())}")
        sys.exit(1)

    agent_name = sys.argv[1]
    print(f"\nRunning {agent_name}...\n")

    agent = AGENTS[agent_name]()
    result = await agent.execute()

    if result.success:
        print(f"\nSuccess: {result.data}")
    else:
        print(f"\nFailed: {result.error}")
        sys.exit(1)


asyncio.run(main())
