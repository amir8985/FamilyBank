"""In-process scheduler — refreshes prices/FX 4-5x/day (spec 2.4,
architecture 5.3) for as long as this backend process stays alive. This
is what actually makes the refresh automatic locally and on a
long-running host; a serverless deployment has no persistent process for
this loop to run in and should disable it (SCHEDULER_ENABLED=false) in
favor of an external cron hitting POST /internal/refresh instead.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import get_settings
from app.scheduler.jobs import last_refresh_at, run_refresh

logger = logging.getLogger("familybank.scheduler")

settings = get_settings()


async def run_forever() -> None:
    logger.info(
        "In-process scheduler starting: refreshing prices/FX every %.1fh",
        settings.scheduler_interval_hours,
    )
    interval_seconds = settings.scheduler_interval_hours * 3600
    while True:
        # A process restart (every deploy, or a free-tier wake-from-sleep)
        # used to always trigger an immediate refresh regardless of when
        # one last actually ran — on a host that redeploys often, that
        # meant real users could hit the ~10s refresh window far more
        # often than the intended "4-5x/day". Skip straight to sleeping
        # until it's actually due instead.
        last = await last_refresh_at()
        if last is not None:
            elapsed_seconds = (datetime.now(timezone.utc) - last).total_seconds()
            remaining_seconds = interval_seconds - elapsed_seconds
            if remaining_seconds > 0:
                logger.info(
                    "Last refresh was %.1fh ago (interval is %.1fh) — skipping immediate "
                    "run, sleeping %.0fs until it's actually due",
                    elapsed_seconds / 3600,
                    settings.scheduler_interval_hours,
                    remaining_seconds,
                )
                await asyncio.sleep(remaining_seconds)
                continue
        try:
            await run_refresh()
        except Exception:
            logger.exception("Scheduled price/FX refresh failed — will retry next interval")
        await asyncio.sleep(interval_seconds)
