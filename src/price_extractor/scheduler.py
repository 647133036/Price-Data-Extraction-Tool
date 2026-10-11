from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Settings
from .pipeline import ExtractionPipeline

logger = logging.getLogger(__name__)

WEEKDAYS = {
    "mon": "mon",
    "tue": "tue",
    "wed": "wed",
    "thu": "thu",
    "fri": "fri",
    "sat": "sat",
    "sun": "sun",
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}


def start_scheduler(settings: Settings, pipeline: ExtractionPipeline) -> None:
    weekday = WEEKDAYS.get(settings.schedule.weekday.lower())
    if not weekday:
        raise ValueError(f"Unsupported weekday: {settings.schedule.weekday}")
    scheduler = BlockingScheduler(timezone=settings.app.timezone)
    scheduler.add_job(
        pipeline.run,
        CronTrigger(
            day_of_week=weekday,
            hour=settings.schedule.hour,
            minute=settings.schedule.minute,
            timezone=settings.app.timezone,
        ),
        id="weekly-price-extraction",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info(
        "Scheduler started: every %s at %02d:%02d %s",
        weekday,
        settings.schedule.hour,
        settings.schedule.minute,
        settings.app.timezone,
    )
    scheduler.start()
