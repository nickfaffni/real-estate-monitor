import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.database import init_db
from app.core.deal_score import update_neighborhood_stats
from app.core.listing_processor import ListingProcessor
from app.scrapers.base_scraper import ScraperWithRetry
from app.scrapers.facebook_scraper import FacebookScraper
from app.scrapers.madlan_scraper import MadlanScraper
from app.scrapers.yad2_scraper import Yad2Scraper
from app.services.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class ScrapingScheduler:
    """Manage scheduled scraping jobs"""

    def __init__(self, shutdown_event: asyncio.Event = None):
        self.scheduler = AsyncIOScheduler()
        self.engine, self.SessionLocal = init_db(settings.database_url)
        self.is_running = False
        self.shutdown_event = shutdown_event or asyncio.Event()
        # Thread pool for running synchronous scrapers
        self.executor = ThreadPoolExecutor(max_workers=3)

    def start(self):
        """Start the scheduler"""
        logger.info("[Scheduler] Starting scraping scheduler...")

        # Re-initialize executor if it was shut down or doesn't exist
        try:
            # Check if executor is shut down by trying to submit a dummy task
            self.executor.submit(lambda: None)
        except (RuntimeError, AttributeError):
            logger.info("[Scheduler] Re-initializing ThreadPoolExecutor")
            self.executor = ThreadPoolExecutor(max_workers=3)

        # Schedule Yad2
        logger.info(f"[Scheduler] Scheduling Yad2 scraper, interval: {settings.yad2_interval_minutes} minutes")
        self.scheduler.add_job(
            self.scrape_yad2,
            trigger=IntervalTrigger(minutes=settings.yad2_interval_minutes),
            id='yad2_scraper',
            name='Yad2 Scraper',
            replace_existing=True
        )

        # Schedule Madlan
        logger.info(f"[Scheduler] Scheduling Madlan scraper, interval: {settings.madlan_interval_minutes} minutes")
        self.scheduler.add_job(
            self.scrape_madlan,
            trigger=IntervalTrigger(minutes=settings.madlan_interval_minutes),
            id='madlan_scraper',
            name='Madlan Scraper',
            replace_existing=True
        )

        # Schedule Facebook
        logger.info(f"[Scheduler] Scheduling Facebook scraper, interval: {settings.facebook_interval_minutes} minutes")
        self.scheduler.add_job(
            self.scrape_facebook,
            trigger=IntervalTrigger(minutes=settings.facebook_interval_minutes),
            id='facebook_scraper',
            name='Facebook Scraper',
            replace_existing=True
        )

        # Schedule neighborhood stats update (every 6 hours)
        logger.info("[Scheduler] Scheduling neighborhood stats updater, interval: 6 hours")
        self.scheduler.add_job(
            self.update_stats,
            trigger=IntervalTrigger(hours=6),
            id='stats_updater',
            name='Neighborhood Stats Updater',
            replace_existing=True
        )

        self.scheduler.start()
        self.is_running = True

        logger.info("[Scheduler] ✅ Scheduler started successfully")
        logger.info(f"[Scheduler] Job schedule - Yad2: Every {settings.yad2_interval_minutes} min | Madlan: Every {settings.madlan_interval_minutes} min | Facebook: Every {settings.facebook_interval_minutes} min")
        logger.info("[Scheduler] ⏰ Initial scrape will begin in 5 seconds...")

        # Run initial scrape immediately
        asyncio.create_task(self.run_initial_scrape())

    async def run_initial_scrape(self):
        """Run initial scrape on startup"""
        logger.info("[Scheduler] 🚀 Running initial scrape sequence...")
        logger.info("[Scheduler] Waiting 5 seconds for system initialization...")
        await asyncio.sleep(5)

        logger.info("[Scheduler] Starting Yad2 initial scrape")
        await self.scrape_yad2()
        logger.info("[Scheduler] Waiting 30 seconds before next source...")
        await asyncio.sleep(30)

        logger.info("[Scheduler] Starting Madlan initial scrape")
        await self.scrape_madlan()
        logger.info("[Scheduler] Waiting 30 seconds before next source...")
        await asyncio.sleep(30)

        logger.info("[Scheduler] Starting Facebook initial scrape")
        await self.scrape_facebook()

        # Update stats after initial scrape
        logger.info("[Scheduler] Updating neighborhood statistics after initial scrape")
        await self.update_stats()

        logger.info("[Scheduler] ✅ Initial scrape sequence completed successfully")

    async def scrape_yad2(self):
        """Scrape Yad2"""
        # Check if shutdown requested
        if self.shutdown_event.is_set():
            logger.info("[Scheduler] Shutdown requested, skipping Yad2 scrape")
            return

        logger.info("=" * 60)
        logger.info("[Scheduler] 🔍 Starting Yad2 scrape job")
        logger.info("=" * 60)
        db = self.SessionLocal()

        try:
            logger.info("[Scheduler] Initializing Yad2 scraper")
            scraper = Yad2Scraper(db)
            scraper_with_retry = ScraperWithRetry(
                scraper,
                max_retries=settings.scraper_max_retries,
                retry_delay=settings.retry_delay_seconds,
                shutdown_event=self.shutdown_event
            )

            logger.info("[Scheduler] Executing Yad2 scraper with retry logic")
            # Run synchronous scraper in thread pool
            loop = asyncio.get_event_loop()
            listings = await loop.run_in_executor(
                self.executor,
                scraper_with_retry.scrape_with_retry
            )

            if listings:
                logger.info(f"[Scheduler] Yad2 scraper returned listings, count: {len(listings)}")
                processor = ListingProcessor(db)
                stats = processor.process_listings(listings, 'yad2')

                logger.info(f"[Scheduler] Yad2 scrape completed successfully, stats: {stats}")

                # Send notifications for new listings
                if stats['new'] > 0 or stats['price_drops'] > 0:
                    logger.info(f"[Scheduler] Sending notifications, new: {stats['new']}, price_drops: {stats['price_drops']}")
                    await self._notify_new_listings(db, stats)
            else:
                logger.warning("[Scheduler] Yad2 scraper returned no listings")

        except Exception as e:
            logger.error(f"[Scheduler] Error in Yad2 scrape job, error: {e}")
            try:
                from app.services.telegram_notifier import notify_scraper_error
                notify_scraper_error('yad2', str(e))
            except Exception:
                pass
        finally:
            db.close()
            logger.info("[Scheduler] Yad2 scrape job finished")

    async def scrape_madlan(self):
        """Scrape Madlan"""
        # Check if shutdown requested
        if self.shutdown_event.is_set():
            logger.info("[Scheduler] Shutdown requested, skipping Madlan scrape")
            return

        logger.info("=" * 60)
        logger.info("[Scheduler] 🔍 Starting Madlan scrape job")
        logger.info("=" * 60)
        db = self.SessionLocal()

        try:
            logger.info("[Scheduler] Initializing Madlan scraper")
            scraper = MadlanScraper(db)
            scraper_with_retry = ScraperWithRetry(
                scraper,
                max_retries=settings.scraper_max_retries,
                retry_delay=settings.retry_delay_seconds,
                shutdown_event=self.shutdown_event
            )

            logger.info("[Scheduler] Executing Madlan scraper with retry logic")
            # Run synchronous scraper in thread pool
            loop = asyncio.get_event_loop()
            listings = await loop.run_in_executor(
                self.executor,
                scraper_with_retry.scrape_with_retry
            )

            if listings:
                logger.info(f"[Scheduler] Madlan scraper returned listings, count: {len(listings)}")
                processor = ListingProcessor(db)
                stats = processor.process_listings(listings, 'madlan')

                logger.info(f"[Scheduler] Madlan scrape completed successfully, stats: {stats}")

                # Send notifications
                if stats['new'] > 0 or stats['price_drops'] > 0:
                    logger.info(f"[Scheduler] Sending notifications, new: {stats['new']}, price_drops: {stats['price_drops']}")
                    await self._notify_new_listings(db, stats)
            else:
                logger.warning("[Scheduler] Madlan scraper returned no listings")

        except Exception as e:
            logger.error(f"[Scheduler] Error in Madlan scrape job, error: {e}")
            try:
                from app.services.telegram_notifier import notify_scraper_error
                notify_scraper_error('madlan', str(e))
            except Exception:
                pass
        finally:
            db.close()
            logger.info("[Scheduler] Madlan scrape job finished")

    async def scrape_facebook(self):
        """Scrape Facebook"""
        # Check if shutdown requested
        if self.shutdown_event.is_set():
            logger.info("[Scheduler] Shutdown requested, skipping Facebook scrape")
            return

        logger.info("=" * 60)
        logger.info("[Scheduler] 🔍 Starting Facebook scrape job")
        logger.info("=" * 60)
        db = self.SessionLocal()

        try:
            cookies_file = settings.facebook_cookies_file
            logger.info(f"[Scheduler] Initializing Facebook scraper, cookies_file: {cookies_file}")
            scraper = FacebookScraper(db, cookies_file=cookies_file)
            scraper_with_retry = ScraperWithRetry(
                scraper,
                max_retries=settings.scraper_max_retries,
                retry_delay=settings.retry_delay_seconds,
                shutdown_event=self.shutdown_event
            )

            logger.info("[Scheduler] Executing Facebook scraper with retry logic")
            # Run synchronous scraper in thread pool
            loop = asyncio.get_event_loop()
            listings = await loop.run_in_executor(
                self.executor,
                scraper_with_retry.scrape_with_retry
            )

            if listings:
                logger.info(f"[Scheduler] Facebook scraper returned listings, count: {len(listings)}")
                processor = ListingProcessor(db)
                stats = processor.process_listings(listings, 'facebook')

                logger.info(f"[Scheduler] Facebook scrape completed successfully, stats: {stats}")

                # Send notifications
                if stats['new'] > 0 or stats['price_drops'] > 0:
                    logger.info(f"[Scheduler] Sending notifications, new: {stats['new']}, price_drops: {stats['price_drops']}")
                    await self._notify_new_listings(db, stats)
            else:
                logger.warning("[Scheduler] Facebook scraper returned no listings")

        except Exception as e:
            logger.error(f"[Scheduler] Error in Facebook scrape job, error: {e}")
            try:
                from app.services.telegram_notifier import notify_scraper_error
                notify_scraper_error('facebook', str(e))
            except Exception:
                pass
        finally:
            db.close()
            logger.info("[Scheduler] Facebook scrape job finished")

    async def update_stats(self):
        """Update neighborhood statistics"""
        logger.info("[Scheduler] 📊 Starting neighborhood statistics update")
        db = self.SessionLocal()

        try:
            update_neighborhood_stats(db)
            logger.info("[Scheduler] Neighborhood statistics updated successfully")
        except Exception as e:
            logger.error(f"[Scheduler] Error updating neighborhood stats, error: {e}")
        finally:
            db.close()

    async def _notify_new_listings(self, db, stats: dict):
        """Send notifications for new/updated listings"""
        if stats['new'] == 0 and stats['price_drops'] == 0:
            return

        try:
            from datetime import datetime, timedelta

            from app.core.database import Listing

            notifier = TelegramNotifier(db)

            # Get recent new listings (last 60 minutes) to ensure we don't miss any during long scrapes
            lookback_minutes = 60
            recent_listings = db.query(Listing).filter(
                Listing.first_seen > datetime.utcnow() - timedelta(minutes=lookback_minutes),
                Listing.status == 'unseen'
            ).all()

            logger.info(f"[Scheduler] Found {len(recent_listings)} unseen listings in the last {lookback_minutes} minutes")

            for listing in recent_listings:
                # Try to notify
                if listing.deal_score >= settings.min_deal_score_notify:
                    await notifier.notify_high_score(listing)
                else:
                    await notifier.notify_new_listing(listing)

                # Small delay between notifications
                await asyncio.sleep(1)

            # Check for price drops in listings seen recently
            price_drop_listings = db.query(Listing).filter(
                Listing.last_seen > datetime.utcnow() - timedelta(minutes=lookback_minutes)
            ).all()

            for listing in price_drop_listings:
                await notifier.notify_price_drop(listing)
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error sending notifications: {e}")

    def stop(self, wait=True):
        """Stop the scheduler"""
        if not self.is_running:
            return

        logger.info(f"Stopping scraping scheduler (wait={wait})...")
        try:
            # Shutdown scheduler
            self.scheduler.shutdown(wait=wait)
            
            # Only shutdown executor if we are not planning to restart soon
            # or if wait is True (indicating a full app shutdown)
            if wait:
                logger.info("Shutting down ThreadPoolExecutor...")
                self.executor.shutdown(wait=wait)
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
        finally:
            self.is_running = False
            logger.info("Scheduler stopped")

    def get_status(self) -> dict:
        """Get scheduler status"""
        jobs = self.scheduler.get_jobs()

        return {
            'running': self.is_running,
            'jobs': [
                {
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in jobs
            ]
        }
