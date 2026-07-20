from celery import Celery
from celery.schedules import crontab

from core.config import settings

celery_app = Celery(
    "aurum",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "agents.product_discovery.tasks",
        "agents.trend_intelligence.tasks",
        "agents.competitor_intel.tasks",
        "agents.executive_advisor.tasks",
        "agents.risk_intelligence.tasks",
        "agents.advertising.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.timezone,
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "agents.product_discovery.*": {"queue": "agents"},
        "agents.trend_intelligence.*": {"queue": "agents"},
        "agents.executive_advisor.*": {"queue": "reports"},
        "agents.risk_intelligence.*": {"queue": "agents"},
        "agents.advertising.*": {"queue": "agents"},
    },
    beat_schedule={
        # Product discovery runs every 6 hours
        "product-discovery": {
            "task": "agents.product_discovery.tasks.run_discovery",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        # Trend check every 2 hours
        "trend-intelligence": {
            "task": "agents.trend_intelligence.tasks.run_trend_scan",
            "schedule": crontab(minute=30, hour="*/2"),
        },
        # Competitor check daily
        "competitor-intel": {
            "task": "agents.competitor_intel.tasks.run_competitor_check",
            "schedule": crontab(minute=0, hour=3),
        },
        # Risk check every hour
        "risk-intelligence": {
            "task": "agents.risk_intelligence.tasks.run_risk_check",
            "schedule": crontab(minute=0),
        },
        # Morning executive brief
        "executive-brief": {
            "task": "agents.executive_advisor.tasks.generate_morning_brief",
            "schedule": crontab(minute=0, hour=7),
        },
        # Draft ad campaigns for top products daily — always requires
        # human approval before anything is created on Meta.
        "advertising-scan": {
            "task": "agents.advertising.tasks.run_advertising_scan",
            "schedule": crontab(minute=0, hour=8),
        },
    },
)
