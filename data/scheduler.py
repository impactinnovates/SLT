"""
data/scheduler.py
In-app nightly sync (same idea as the Financial Dashboard's in-app scheduler):
a daemon thread that runs the Cost Takeout Tracker -> List sync once a day.

Enabled only when SYNC_SCHEDULE_ENABLED is true (set that on the Azure app), and
only when Graph is configured. Safe to import everywhere; start() is a no-op
unless enabled, and it only starts once per process.

Deploy note: the App Service runs a single gunicorn worker (see AZURE_RUNBOOK),
so exactly one scheduler thread runs. If you ever scale to multiple workers,
move this to an Azure timer/WebJob hitting a sync endpoint instead, so the write
doesn't run once per worker.
"""
import time
import logging
import threading
from datetime import datetime, timedelta

from config import settings

log = logging.getLogger(__name__)
_started = False


def _seconds_until(hour: int) -> float:
    now = datetime.now()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _run_once():
    from data import excel_sync
    from data.loader import clear_cache
    updates, cfg = excel_sync.compute_updates()
    results = excel_sync.apply_updates(updates, cfg)
    clear_cache()
    ok = sum(1 for r in results if r.get("status") == "updated")
    log.info("Scheduled cost-takeout sync: %d/%d initiatives updated", ok, len(results))


def _loop(hour: int):
    while True:
        time.sleep(_seconds_until(hour))
        try:
            _run_once()
        except Exception as e:                       # never let the thread die
            log.warning("Scheduled sync failed: %s", str(e)[:200])
        time.sleep(60)  # step past the target minute so we don't double-fire


def start():
    """Start the nightly sync thread once, if enabled and Graph is configured."""
    global _started
    if _started or not settings.SYNC_SCHEDULE_ENABLED:
        return
    if not settings.graph_is_configured():
        log.info("Sync schedule enabled but Graph not configured; not starting.")
        return
    _started = True
    threading.Thread(target=_loop, args=(settings.SYNC_SCHEDULE_HOUR,),
                     daemon=True, name="cost-takeout-sync").start()
    log.info("Cost-takeout sync scheduled daily at %02d:00 (server time).",
             settings.SYNC_SCHEDULE_HOUR)
