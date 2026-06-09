from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.core.database import Listing, NeighborhoodStats, init_db
from app.core.config import settings
from datetime import datetime, timedelta
from typing import Optional
import urllib.parse
from app.core.lifecycle import get_scheduler
from dotenv import set_key, load_dotenv
import os
import logging
import asyncio

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Real Estate Monitor")

# Mount static files (Signal dashboard assets)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Add template helper functions
def format_price(price):
    """Format price with thousands separator"""
    if not price:
        return "N/A"
    return f"₪{price:,.0f}"

def days_ago(date):
    """Return human-readable time since date"""
    if not date:
        return "Unknown"

    delta = datetime.utcnow() - date

    if delta.days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            minutes = delta.seconds // 60
            return f"{minutes} minutes ago" if minutes > 1 else "Just now"
        return f"{hours} hours ago" if hours > 1 else "1 hour ago"
    elif delta.days == 1:
        return "Yesterday"
    elif delta.days < 7:
        return f"{delta.days} days ago"
    elif delta.days < 30:
        weeks = delta.days // 7
        return f"{weeks} weeks ago" if weeks > 1 else "1 week ago"
    else:
        months = delta.days // 30
        return f"{months} months ago" if months > 1 else "1 month ago"

def ago_label(dt: Optional[datetime]) -> Optional[str]:
    """Compact relative-age label with hour granularity under a day.

    None in → None out (client renders 'unknown'). We anchor at utcnow, so a
    posted_at from the future (shouldn't happen) clamps to 'just now'.
    """
    if not dt:
        return None
    delta = datetime.utcnow() - dt
    secs = max(0, int(delta.total_seconds()))
    if secs < 3600:
        return "just now"
    hours = secs // 3600
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 7:
        return f"{days}d ago"
    weeks = days // 7
    if weeks < 5:
        return f"{weeks}w ago"
    months = days // 30
    return f"{months}mo ago"


def format_date(date):
    """Format a datetime as YYYY-MM-DD HH:MM (falls back for None)."""
    if not date:
        return "Unknown"
    return date.strftime("%Y-%m-%d %H:%M")

def get_whatsapp_url(phone, address, source):
    """Generate WhatsApp URL with pre-filled message"""
    if not phone:
        return None

    # Clean phone number
    phone = phone.strip().replace('-', '').replace(' ', '')

    # Add country code if not present
    if not phone.startswith('+'):
        if phone.startswith('0'):
            phone = '+972' + phone[1:]
        else:
            phone = '+972' + phone

    # Create message
    message = f"Hi, I saw your listing on {source} for {address}. Is it still available?"
    encoded_message = urllib.parse.quote(message)

    return f"https://wa.me/{phone}?text={encoded_message}"

# Register template filters
templates.env.globals['format_price'] = format_price
templates.env.globals['days_ago'] = days_ago
templates.env.globals['format_date'] = format_date
templates.env.globals['get_whatsapp_url'] = get_whatsapp_url
templates.env.globals['datetime'] = datetime

# Database
engine, SessionLocal = init_db(settings.database_url)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def normalize_city_name(name: str) -> str:
    if not name: return ""
    # Standardize common variations (hyphens, spaces, double vavs)
    n = str(name).replace("-", " ").strip()
    n = " ".join(n.split()) # collapse whitespace
    if n == "פתח תקוה": n = "פתח תקווה"
    if n == "תל אביב יפו": n = "תל אביב-יפו"
    if n == "תל אביב": n = "תל אביב-יפו"
    return n


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    """Main dashboard page (Signal UI). The React app fetches /api/listings itself."""

    total_listings = db.query(Listing).count()
    today = datetime.utcnow().date()
    new_today = db.query(Listing).filter(func.date(Listing.first_seen) == today).count()
    high_score = db.query(Listing).filter(Listing.deal_score >= 80).count()
    avg_score = db.query(func.avg(Listing.deal_score)).scalar() or 0
    
    raw_cities = [c[0] for c in db.query(Listing.city).distinct().all() if c[0]]
    cities_set = set()
    for c in raw_cities:
        cities_set.add(normalize_city_name(c))
    cities = list(cities_set)
    cities.sort()
    
    # Get city-neighborhood pairs for dynamic filtering, normalize
    city_hood_pairs = db.query(Listing.city, Listing.neighborhood).distinct().all()
    neighborhoods_map = []
    seen_pairs = set()
    for city_name, hood_name in city_hood_pairs:
        if city_name and hood_name:
            norm_city = normalize_city_name(city_name)
            if (norm_city, hood_name) not in seen_pairs:
                neighborhoods_map.append({"city": norm_city, "name": hood_name})
                seen_pairs.add((norm_city, hood_name))
    
    # Sort for consistent UI
    neighborhoods_map.sort(key=lambda x: (x["city"], x["name"]))

    return templates.TemplateResponse("index.html", {
        "request": request,
        "total_listings": total_listings,
        "new_today": new_today,
        "high_score": high_score,
        "avg_score": round(avg_score),
        "cities": cities,
        "neighborhoods": neighborhoods_map,
        "current_city": "",
        "current_neighborhood": "",
        "current_min_score": 0,
        "current_mamad": False,
        "current_status": "all",
        "current_sort": "deal_score",
    })


@app.get("/api/listings")
async def api_listings(
    city: list[str] = Query([]),
    neighborhood: list[str] = Query([]),
    min_score: int = 0,
    has_mamad: bool = False,
    sort_by: str = "deal_score",
    status: str = "all",
    db: Session = Depends(get_db),
):
    """JSON feed consumed by the Signal React dashboard."""
    q = db.query(Listing)
    
    # Handle cases where city might be passed as a single string with commas
    actual_cities = []
    if city:
        for c in city:
            if "," in c:
                actual_cities.extend([x.strip() for x in c.split(",") if x.strip()])
            else:
                if c.strip():
                    actual_cities.append(c.strip())
        
    if actual_cities:
        # For each selected city, also include common variations in the query
        query_cities = set(actual_cities)
        for c in actual_cities:
            if c == "תל אביב-יפו":
                query_cities.add("תל אביב יפו")
                query_cities.add("תל אביב")
            if c == "פתח תקווה":
                query_cities.add("פתח תקוה")
            # Also add hyphenated versions for all cities
            if " " in c:
                query_cities.add(c.replace(" ", "-"))
            if "-" in c:
                query_cities.add(c.replace("-", " "))
                
        q = q.filter(Listing.city.in_(list(query_cities)))

    if neighborhood:
        # Handle cases where neighborhood might be passed as a single string with commas
        actual_neighborhoods = []
        for n in neighborhood:
            if "," in n:
                actual_neighborhoods.extend([x.strip() for x in n.split(",") if x.strip()])
            else:
                if n.strip():
                    actual_neighborhoods.append(n.strip())
        
        if actual_neighborhoods:
            q = q.filter(Listing.neighborhood.in_(actual_neighborhoods))

    if min_score:
        q = q.filter(Listing.deal_score >= min_score)
    if has_mamad:
        q = q.filter(Listing.has_mamad == True)
    if status and status != "all":
        q = q.filter(Listing.status == status)

    sort_col = {
        "deal_score": desc(Listing.deal_score),
        "price_asc": Listing.price.asc(),
        "price_desc": desc(Listing.price),
        "newest": desc(Listing.first_seen),
        "price_per_sqm": Listing.price_per_sqm.asc(),
    }.get(sort_by, desc(Listing.deal_score))
    q = q.order_by(sort_col)

    now = datetime.utcnow()
    out = []
    for l in q.limit(200).all():
        images = l.get_images() if hasattr(l, "get_images") else []
        days = (now - l.first_seen).days if l.first_seen else 0
        city_name = normalize_city_name(l.city)
            
        out.append({
            "id": l.id,
            "he": l.title or "",
            "neighborhood": l.neighborhood or "",
            "city": city_name,
            "price": l.price or 0,
            "sqm": l.size_sqm or 0,
            "rooms": l.rooms or 0,
            "floor": l.floor or 0,
            "pricePerSqm": l.price_per_sqm or 0,
            "score": l.deal_score or 0,
            "scoreBreakdown": l.get_score_breakdown() if hasattr(l, "get_score_breakdown") else None,
            "status": l.status or "unseen",
            "source": l.source or "",
            "daysAgo": days,
            "postedLabel": ago_label(l.posted_at),
            "scrapedLabel": ago_label(l.first_seen),
            "features": {
                "mamad": bool(getattr(l, "has_mamad", False)),
                "miklat": bool(getattr(l, "has_miklat", False)),
                "parking": bool(getattr(l, "has_parking", False)),
                "elevator": bool(getattr(l, "has_elevator", False)),
                "balcony": bool(getattr(l, "has_balcony", False)),
            },
            "trend": 0,
            "isNew": days == 0,
            "image": images[0] if images else None,
            "url": l.url or "#",
            "lat": l.latitude,
            "lng": l.longitude,
        })
    return out


@app.get("/listing/{listing_id}", response_class=HTMLResponse)
async def listing_detail(request: Request, listing_id: int, db: Session = Depends(get_db)):
    """Listing detail page"""

    listing = db.query(Listing).filter(Listing.id == listing_id).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Get neighborhood stats
    neighborhood_stats = db.query(NeighborhoodStats).filter(
        NeighborhoodStats.city == listing.city,
        NeighborhoodStats.neighborhood == listing.neighborhood
    ).first()

    # Get price history for chart
    price_history = sorted(listing.price_history, key=lambda x: x.timestamp)

    return templates.TemplateResponse("listing_detail.html", {
        "request": request,
        "listing": listing,
        "neighborhood_stats": neighborhood_stats,
        "price_history": price_history
    })


@app.post("/api/listing/{listing_id}/status")
async def update_listing_status(
    listing_id: int,
    status: str,
    note: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update listing status (like/hide/contacted)"""

    valid_statuses = ['unseen', 'viewed', 'interested', 'not_interested', 'contacted']
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")

    listing = db.query(Listing).filter(Listing.id == listing_id).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing.status = status
    if note:
        listing.user_note = note

    db.commit()

    logger.info(f"Updated listing {listing_id} status to {status}")

    return {"success": True, "status": status}


@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get dashboard statistics"""

    total = db.query(Listing).count()

    new_today = db.query(Listing).filter(
        Listing.first_seen >= datetime.utcnow() - timedelta(days=1)
    ).count()

    new_week = db.query(Listing).filter(
        Listing.first_seen >= datetime.utcnow() - timedelta(days=7)
    ).count()

    high_score = db.query(Listing).filter(
        Listing.deal_score >= 80
    ).count()

    avg_price = db.query(func.avg(Listing.price)).filter(
        Listing.price > 0
    ).scalar()

    avg_price_per_sqm = db.query(func.avg(Listing.price_per_sqm)).filter(
        Listing.price_per_sqm > 0
    ).scalar()

    by_status = db.query(
        Listing.status,
        func.count(Listing.id)
    ).group_by(Listing.status).all()

    by_source = db.query(
        Listing.source,
        func.count(Listing.id)
    ).group_by(Listing.source).all()

    return {
        "total_listings": total,
        "new_today": new_today,
        "new_this_week": new_week,
        "high_score_count": high_score,
        "avg_price": round(avg_price, 2) if avg_price else 0,
        "avg_price_per_sqm": round(avg_price_per_sqm, 2) if avg_price_per_sqm else 0,
        "by_status": {status: count for status, count in by_status},
        "by_source": {source: count for source, count in by_source}
    }


@app.get("/api/neighborhood-stats")
async def get_neighborhood_stats(
    city: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get neighborhood statistics"""

    query = db.query(NeighborhoodStats)

    if city:
        query = query.filter(NeighborhoodStats.city == city)

    stats = query.all()

    return {
        "neighborhoods": [
            {
                "city": s.city,
                "neighborhood": s.neighborhood,
                "avg_price": s.avg_price,
                "avg_price_per_sqm": s.avg_price_per_sqm,
                "median_price": s.median_price,
                "median_price_per_sqm": s.median_price_per_sqm,
                "sample_size": s.sample_size
            }
            for s in stats
        ]
    }


@app.get("/api/price-history/{listing_id}")
async def get_price_history(listing_id: int, db: Session = Depends(get_db)):
    """Get price history for a listing"""

    listing = db.query(Listing).filter(Listing.id == listing_id).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    history = sorted(listing.price_history, key=lambda x: x.timestamp)

    return {
        "listing_id": listing_id,
        "history": [
            {
                "timestamp": h.timestamp.isoformat(),
                "price": h.price,
                "price_per_sqm": h.price_per_sqm
            }
            for h in history
        ]
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint with scraper status"""
    from app.core.database import ScrapingState

    # Get scraping states
    states = db.query(ScrapingState).all()

    scraper_status = {}
    for state in states:
        time_since_scrape = None
        if state.last_scrape_time:
            time_since_scrape = (datetime.utcnow() - state.last_scrape_time).total_seconds()

        scraper_status[state.source] = {
            "status": state.status,
            "last_scrape": state.last_scrape_time.isoformat() if state.last_scrape_time else None,
            "seconds_since_scrape": time_since_scrape,
            "error_count": state.error_count,
            "error_message": state.error_message
        }

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "scrapers": scraper_status
    }


@app.get("/api/health")
async def api_health_check(db: Session = Depends(get_db)):
    """API health check endpoint with CAPTCHA state and last run info"""
    from app.core.database import ScrapingState
    from app.scrapers.base_scraper import captcha_state

    # Get CAPTCHA state
    is_blocked = captcha_state.is_waiting()
    captcha_info = captcha_state.get_status()

    # Get most recent scrape time across all sources
    states = db.query(ScrapingState).all()
    last_run = None
    for state in states:
        if state.last_scrape_time:
            if last_run is None or state.last_scrape_time > last_run:
                last_run = state.last_scrape_time

    return {
        "is_blocked": is_blocked,
        "last_run": last_run.isoformat() if last_run else None,
        "captcha_state": captcha_info,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/status")
async def get_scraper_status():
    """Get current scraper status including CAPTCHA state"""
    from app.scrapers.base_scraper import captcha_state

    captcha_info = captcha_state.get_status()

    # The Pause/Start button reads is_paused to decide its label and which
    # endpoint to hit. It must reflect the *scheduler* state (not just
    # CAPTCHA) — otherwise clicking Pause calls /stop successfully but the
    # next status poll still says is_paused=false, the button keeps reading
    # "Pause", and the Start button never appears.
    scheduler = get_scheduler()
    # APScheduler states: 0=STOPPED, 1=RUNNING, 2=PAUSED. is_running is our
    # "has ever been started" flag — so we treat "paused" as not-running
    # from the UI's point of view.
    aps_state = getattr(scheduler.scheduler, "state", 0)
    scheduler_active = bool(getattr(scheduler, "is_running", False)) and aps_state == 1

    return {
        "captcha": captcha_info,
        "is_paused": (not scheduler_active) or captcha_state.is_waiting(),
        "scheduler_running": scheduler_active,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/db-stats")
async def database_stats(db: Session = Depends(get_db)):
    """Get detailed database statistics for monitoring"""
    from app.core.database import ScrapingState, PriceHistory

    # Listing stats
    total_listings = db.query(Listing).count()

    # By status
    by_status = db.query(
        Listing.status,
        func.count(Listing.id)
    ).group_by(Listing.status).all()

    # By source
    by_source = db.query(
        Listing.source,
        func.count(Listing.id)
    ).group_by(Listing.source).all()

    # By city
    by_city = db.query(
        Listing.city,
        func.count(Listing.id)
    ).group_by(Listing.city).all()

    # Recent activity
    new_today = db.query(Listing).filter(
        Listing.first_seen >= datetime.utcnow() - timedelta(days=1)
    ).count()

    new_week = db.query(Listing).filter(
        Listing.first_seen >= datetime.utcnow() - timedelta(days=7)
    ).count()

    # Scraper status
    scraper_states = db.query(ScrapingState).all()

    return {
        "database": {
            "total_listings": total_listings,
            "new_today": new_today,
            "new_this_week": new_week,
            "by_status": {status: count for status, count in by_status},
            "by_source": {source: count for source, count in by_source},
            "by_city": {city: count for city, count in by_city}
        },
        "scrapers": [
            {
                "source": s.source,
                "status": s.status,
                "last_scrape": s.last_scrape_time.isoformat() if s.last_scrape_time else None,
                "error_count": s.error_count,
                "error_message": s.error_message
            }
            for s in scraper_states
        ],
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/scraper/start")
async def start_scraper():
    """Start (or resume) the scraping scheduler.

    APScheduler's lifecycle is one-shot — once `.shutdown()` is called the
    instance can't be `.start()`-ed again. So we model the Pause button as
    `scheduler.pause()` / `scheduler.resume()` instead of stop/start, which
    is what the underlying library actually supports."""
    scheduler = get_scheduler()
    aps = scheduler.scheduler  # underlying AsyncIOScheduler
    try:
        if not scheduler.is_running:
            # First run: full .start() (wires jobs, kicks off initial scrape)
            scheduler.start()
            logger.info("Scraper started via dashboard")
            return {"success": True, "message": "Scraper started"}
        if aps.state == 2:  # STATE_PAUSED
            aps.resume()
            logger.info("Scraper resumed via dashboard")
            return {"success": True, "message": "Scraper resumed"}
        return {"success": False, "message": "Scraper is already running"}
    except Exception as e:
        logger.error(f"Error starting/resuming scheduler: {e}")
        return {"success": False, "message": f"Error: {e}"}


@app.post("/api/scraper/stop")
async def stop_scraper():
    """Pause the scraping scheduler (does NOT shut it down — that would
    make a later Start impossible). Currently-running jobs finish on their
    own; pausing only prevents the scheduler from kicking off new ones."""
    scheduler = get_scheduler()
    aps = scheduler.scheduler
    try:
        if not scheduler.is_running:
            return {"success": False, "message": "Scraper is already stopped"}
        if aps.state == 1:  # STATE_RUNNING
            aps.pause()
            logger.info("Scraper paused via dashboard")
            return {"success": True, "message": "Scraper paused"}
        return {"success": False, "message": "Scraper is not running"}
    except Exception as e:
        logger.error(f"Error pausing scheduler: {e}")
        return {"success": False, "message": f"Error: {e}"}


@app.post("/api/scraper/restart")
async def restart_scraper():
    """Restart the scraping scheduler and force an immediate scrape run."""
    scheduler = get_scheduler()
    try:
        logger.info("Restarting scraper scheduler via dashboard...")
        if scheduler.is_running:
            scheduler.stop(wait=False)
            # Give it a brief moment to stabilize
            await asyncio.sleep(1.5)
        
        # Start the scheduler (re-registers jobs and triggers run_initial_scrape)
        scheduler.start()
        logger.info("Scraper scheduler restarted successfully via dashboard")
        return {"success": True, "message": "Scraper restarted successfully. Scraping will begin shortly."}
    except Exception as e:
        logger.error(f"Error restarting scheduler: {e}")
        return {"success": False, "message": f"Error: {e}"}


@app.get("/api/settings")
async def get_dashboard_settings():
    """Get current configuration from settings object"""
    return {
        "cities": settings.cities,
        "max_price": settings.max_price,
        "min_rooms": settings.min_rooms,
        "max_rooms": settings.max_rooms,
        "min_size_sqm": settings.min_size_sqm,
        "require_mamad": settings.require_mamad,
        "yad2_interval": settings.yad2_interval_minutes,
        "madlan_interval": settings.madlan_interval_minutes,
        "facebook_interval": settings.facebook_interval_minutes,
        "min_deal_score": settings.min_deal_score_for_noti
    }


@app.post("/api/settings")
async def update_dashboard_settings(data: dict):
    """Update settings in .env and refresh running settings object"""
    env_path = ".env"
    
    # Update .env file
    if "cities" in data:
        set_key(env_path, "CITIES", data["cities"])
        settings.cities = data["cities"]
    if "max_price" in data:
        set_key(env_path, "MAX_PRICE", str(data["max_price"]))
        settings.max_price = float(data["max_price"])
    if "min_rooms" in data:
        set_key(env_path, "MIN_ROOMS", str(data["min_rooms"]))
        settings.min_rooms = float(data["min_rooms"])
    if "max_rooms" in data:
        val = str(data["max_rooms"]) if data["max_rooms"] is not None else ""
        set_key(env_path, "MAX_ROOMS", val)
        settings.max_rooms = float(data["max_rooms"]) if data["max_rooms"] else None
    if "min_size_sqm" in data:
        set_key(env_path, "MIN_SIZE_SQM", str(data["min_size_sqm"]))
        settings.min_size_sqm = float(data["min_size_sqm"])
    if "require_mamad" in data:
        val = "true" if data["require_mamad"] else "false"
        set_key(env_path, "REQUIRE_MAMAD", val)
        settings.require_mamad = bool(data["require_mamad"])
    if "yad2_interval" in data:
        set_key(env_path, "YAD2_INTERVAL_MINUTES", str(data["yad2_interval"]))
        settings.yad2_interval_minutes = int(data["yad2_interval"])
    if "madlan_interval" in data:
        set_key(env_path, "MADLAN_INTERVAL_MINUTES", str(data["madlan_interval"]))
        settings.madlan_interval_minutes = int(data["madlan_interval"])
    if "facebook_interval" in data:
        set_key(env_path, "FACEBOOK_INTERVAL_MINUTES", str(data["facebook_interval"]))
        settings.facebook_interval_minutes = int(data["facebook_interval"])
    if "min_deal_score" in data:
        set_key(env_path, "MIN_DEAL_SCORE_FOR_NOTI", str(data["min_deal_score"]))
        set_key(env_path, "MIN_DEAL_SCORE_NOTIFY", str(data["min_deal_score"]))
        settings.min_deal_score_for_noti = float(data["min_deal_score"])
        settings.min_deal_score_notify = float(data["min_deal_score"])

    logger.info("Settings updated via dashboard")
    
    # Optionally restart scheduler jobs to apply new intervals
    try:
        scheduler = get_scheduler()
        if scheduler.is_running:
            logger.info("Restarting scheduler to apply new settings...")
            scheduler.stop(wait=False)
            # Give it a moment to stabilize
            await asyncio.sleep(1)
            scheduler.start()
            logger.info("Scheduler restarted successfully")
    except Exception as e:
        logger.error(f"Error restarting scheduler: {e}")
        # Even if restart fails, we want to return success for the settings save
        return {"success": True, "message": "Settings saved, but scheduler restart failed. Please restart the app manually if needed."}

    return {"success": True, "message": "Settings updated and scheduler restarted"}

