"""In-process scheduler — refreshes prices/FX 4-5x/day (spec 2.4,
architecture 5.3) for as long as this backend process stays alive. This
is what actually makes the refresh automatic locally and on a
long-running host; a serverless deployment has no persistent process for
this loop to run in and should disable it (SCHEDULER_ENABLED=false) in
favor of an external cron hitting POST /internal/refresh instead.
"""

import asyncio
import logging

from app.core.config import get_settings
from app.scheduler.jobs import run_refresh

logger = logging.getLogger("familybank.scheduler")

settings = get_settings()


async def run_forever() -> None:
    logger.info(
        "In-process scheduler starting: refreshing prices/FX every %.1fh",
        settings.scheduler_interval_hours,
    )
    while True:
        try:
            await run_refresh()
        except Exception:
            logger.exception("Scheduled price/FX refresh failed — will retry next interval")
        await asyncio.sleep(settings.scheduler_interval_hours * 3600)
