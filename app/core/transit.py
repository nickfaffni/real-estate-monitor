"""Transit proximity: geocoding + nearest-station lookup.

Uses Nominatim for address -> (lat, lon) and a local station snapshot
(data/transit_stations.json) harvested from OSM Overpass. Per Nominatim's
usage policy we throttle to 1 req/sec and send a real User-Agent.
"""
import json
import logging
import math
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

STATIONS_FILE = Path(__file__).resolve().parents[2] / "data" / "transit_stations.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "real-estate-monitor/1.0 (nickgaffni140@gmail.com)"

# Type -> score multiplier. Heavy rail / subway = 1.0, light rail/tram = 0.85.
TYPE_WEIGHTS = {
    "heavy_rail": 1.0,
    "subway": 1.0,
    "light_rail": 0.85,
    "tram": 0.85,
}

_stations_cache = None
_nominatim_lock = threading.Lock()
_last_nominatim_call = 0.0


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def load_stations():
    global _stations_cache
    if _stations_cache is not None:
        return _stations_cache
    if not STATIONS_FILE.exists():
        logger.warning("[transit] stations file missing at %s", STATIONS_FILE)
        _stations_cache = []
        return _stations_cache
    try:
        with open(STATIONS_FILE, "r", encoding="utf-8") as f:
            _stations_cache = json.load(f)
        logger.info("[transit] loaded %d stations", len(_stations_cache))
    except Exception as e:
        logger.error("[transit] failed to load stations: %s", e)
        _stations_cache = []
    return _stations_cache


def geocode(address: str, city: Optional[str] = None, neighborhood: Optional[str] = None) -> Optional[Tuple[float, float]]:
    """Geocode a free-text Israeli address via Nominatim. Returns (lat, lon) or None."""
    global _last_nominatim_call
    parts = [p for p in (address, neighborhood, city, "Israel") if p]
    q = ", ".join(parts).strip(", ")
    if not q or q == "Israel":
        return None
    with _nominatim_lock:
        # 1 req/sec policy.
        wait = 1.05 - (time.time() - _last_nominatim_call)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = requests.get(
                NOMINATIM_URL,
                params={"q": q, "format": "json", "limit": 1, "accept-language": "he,en", "countrycodes": "il"},
                headers={"User-Agent": USER_AGENT},
                timeout=10,
            )
            _last_nominatim_call = time.time()
            if resp.status_code != 200:
                logger.warning("[transit] nominatim %s for '%s'", resp.status_code, q[:80])
                return None
            data = resp.json()
            if not data:
                return None
            return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception as e:
            logger.warning("[transit] geocode failed for '%s': %s", q[:80], e)
            return None


def nearest_station(lat: float, lon: float, max_meters: float = 2000.0):
    """Return (name, meters, type) of the closest station within max_meters, else None."""
    stations = load_stations()
    if not stations:
        return None
    best = None
    for st in stations:
        d = haversine_meters(lat, lon, st["lat"], st["lon"])
        if d > max_meters:
            continue
        if best is None or d < best[1]:
            best = (st["name"], d, st["type"])
    return best


def resolve_for_listing(listing) -> dict:
    """Geocode + find nearest station for a listing. Returns dict of fields to set.
    Returns {} if nothing resolved (caller should still stamp geocoded_at to avoid re-querying)."""
    lat, lon = None, None
    if listing.latitude and listing.longitude:
        lat, lon = listing.latitude, listing.longitude
    else:
        # Try full address first, then neighborhood centroid as fallback.
        result = None
        if listing.address or listing.street:
            result = geocode(listing.address or listing.street, listing.city, listing.neighborhood)
        if not result and listing.neighborhood:
            result = geocode(None, listing.city, listing.neighborhood)
        if not result and listing.city:
            result = geocode(None, listing.city, None)
        if result:
            lat, lon = result

    out = {"geocoded_at": datetime.utcnow()}
    if lat is not None and lon is not None:
        out["latitude"] = lat
        out["longitude"] = lon
        near = nearest_station(lat, lon)
        if near:
            name, meters, typ = near
            out["nearest_station_name"] = name
            out["nearest_station_meters"] = meters
            out["nearest_station_type"] = typ
    return out
