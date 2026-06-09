import asyncio
from typing import Optional
from app.services.scheduler import ScrapingScheduler

# Global scheduler instance
_scheduler: Optional[ScrapingScheduler] = None
# Global shutdown event
_shutdown_event: asyncio.Event = asyncio.Event()

def get_scheduler() -> ScrapingScheduler:
    """Get or create the global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = ScrapingScheduler(_shutdown_event)
    return _scheduler

def get_shutdown_event() -> asyncio.Event:
    """Get the global shutdown event"""
    return _shutdown_event
