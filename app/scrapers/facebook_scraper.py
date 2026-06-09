from app.scrapers.base_scraper import BaseScraper
from typing import List, Dict, Optional
from urllib.parse import quote
import logging
import re
import json
import os

from app.core.config import settings

logger = logging.getLogger(__name__)


# Hebrew city name -> Facebook Marketplace location slug.
# Unknown slugs cause FB to silently fall back to the account's IP location.
FB_CITY_SLUGS = {
    'תל אביב-יפו': 'telaviv',
    'תל אביב': 'telaviv',
    'רמת גן': 'ramatgan',
    'גבעתיים': 'givatayim',
    'הרצליה': 'herzliya',
    'רמת השרון': 'ramathasharon',
    'פתח תקווה': 'petahtikva',
    'ראשון לציון': 'rishonlezion',
    'הוד השרון': 'hodhasharon',
    'כפר סבא': 'kfarsaba',
    'רעננה': 'raanana',
    'בצרה': 'basra',
    'בני ציון': 'bneizion',
    'צופית': 'tzofit',
    'גן חיים': 'ganhaim',
    'גבעת חן': 'givathen',
}


class FacebookScraper(BaseScraper):
    """Scraper for Facebook Marketplace and Groups"""

    def __init__(self, db_session, cookies_file: Optional[str] = None):
        super().__init__(db_session, 'facebook')
        self.base_url = "https://www.facebook.com"
        self.cookies_file = cookies_file

    def _load_cookies(self):
        """Load Facebook cookies from file"""
        if not self.cookies_file or not os.path.exists(self.cookies_file):
            logger.warning("Facebook cookies file not found. Facebook scraping may not work.")
            return

        # Chrome exports use lowercase "no_restriction"/"lax"/"strict" or null;
        # DrissionPage/CDP wants "None"/"Lax"/"Strict".
        same_site_map = {
            'no_restriction': 'None',
            'unspecified': 'None',
            'lax': 'Lax',
            'strict': 'Strict',
            'none': 'None',
        }

        try:
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)

            if not cookies or not self.page:
                return

            loaded = 0
            for cookie in cookies:
                raw_ss = cookie.get('sameSite')
                if raw_ss is None:
                    cookie.pop('sameSite', None)
                else:
                    cookie['sameSite'] = same_site_map.get(str(raw_ss).lower(), 'None')
                # Strip Chrome-export-only fields that CDP rejects.
                for k in ('hostOnly', 'session', 'storeId'):
                    cookie.pop(k, None)
                try:
                    self.page.set.cookies(cookie)
                    loaded += 1
                except Exception as inner:
                    logger.warning(f"[Facebook] skipping cookie {cookie.get('name')!r}: {inner}")
            logger.info(f"Loaded {loaded}/{len(cookies)} Facebook cookies from file")
        except Exception as e:
            logger.warning(f"Failed to load Facebook cookies: {e}")

    def scrape(self) -> List[Dict]:
        """Scrape Facebook Marketplace listings across all configured cities."""
        if not self.page:
            logger.error("[Facebook Scraper] Browser page not initialized")
            return []

        listings: List[Dict] = []
        seen_ids: set = set()

        configured_cities = settings.get_cities_list()
        query = quote("דירה להשכרה")

        for city in configured_cities:
            slug = FB_CITY_SLUGS.get(city)
            if not slug:
                logger.warning(f"[Facebook Scraper] No FB Marketplace slug mapped for city {city!r} — skipping")
                continue

            search_url = f"{self.base_url}/marketplace/{slug}/search?query={query}&exact=false"
            logger.info(f"[Facebook Scraper] Navigating to search page, city: {city}, url: {search_url}")

            try:
                self.page.get(search_url)
                self.random_delay(2, 3)
                self._handle_anti_bot_protection()
                self.random_delay(4, 7)

                current_url = self.page.url
                logger.debug(f"[Facebook Scraper] Checking current URL, url: {current_url}")

                if 'login' in current_url.lower():
                    logger.warning("[Facebook Scraper] Login required - cookies missing or expired")
                    return listings

                # Guard against FB silently redirecting to the account's home
                # location when it doesn't recognize the slug.
                if f"/marketplace/{slug}/" not in current_url:
                    logger.warning(
                        f"[Facebook Scraper] Post-navigation URL dropped slug {slug!r} "
                        f"(now {current_url}); skipping {city}"
                    )
                    continue

                self.human_like_mouse_movement()

                logger.info("[Facebook Scraper] Scrolling page to load dynamic content, scrolls: 4")
                self.scroll_page(scrolls=4)
                self.random_delay(2, 4)

                logger.info('[Facebook Scraper] Attempting to find listing cards with selector: css:a[href^="/marketplace/item/"]')
                listing_cards = self.page.eles('css:a[href^="/marketplace/item/"]')

                if not listing_cards:
                    logger.info("[Facebook Scraper] Primary selector failed, trying alternative: css:div[role=\"article\"]")
                    listing_cards = self.page.eles('css:div[role="article"]')

                logger.info(f"[Facebook Scraper] Found listing cards, city: {city}, count: {len(listing_cards)}")

                if len(listing_cards) == 0:
                    logger.warning(f"[Facebook Scraper] No listing cards found for {city} - saving debug output")
                    self.debug_save_page(f"no_listings_{slug}")
                    continue

                max_listings = min(len(listing_cards), 30)
                logger.info(f"[Facebook Scraper] Processing listings, city: {city}, max_count: {max_listings}")

                raw_cards = []
                for idx, card in enumerate(listing_cards[:30], 1):
                    try:
                        listing_data = self._extract_listing_data(card)
                        if listing_data:
                            raw_cards.append(listing_data)
                    except Exception as e:
                        logger.warning(f"[Facebook Scraper] Error extracting listing, index: {idx}, error: {e}")
                        continue

                for idx, listing_data in enumerate(raw_cards, 1):
                    try:
                        ext_id = listing_data.get('external_id')
                        if ext_id and ext_id in seen_ids:
                            continue
                        price = listing_data.get('price') or 0
                        too_expensive = settings.max_price and price > settings.max_price
                        if ext_id and not self.listing_exists(ext_id) and not too_expensive:
                            detail_url = listing_data.get('url')
                            logger.debug(f"[Facebook Scraper] New listing, fetching detail: {detail_url}")
                            listing_data['detail_text'] = self.fetch_detail_text(detail_url)
                            self.random_delay(1.5, 3)
                        elif too_expensive:
                            logger.debug(f"[Facebook Scraper] Skipping detail fetch — price {price} > max {settings.max_price}")
                        parsed = self.parse_listing(listing_data)
                        if parsed:
                            listings.append(parsed)
                            if ext_id:
                                seen_ids.add(ext_id)
                    except Exception as e:
                        logger.warning(f"[Facebook Scraper] Error parsing listing, index: {idx}, error: {e}")
                        continue

            except Exception as e:
                logger.error(f"[Facebook Scraper] Error scraping city {city}: {e}")
                continue

        logger.info(f"[Facebook Scraper] Scraping completed, total_listings: {len(listings)}")
        return listings

    def _extract_listing_data(self, card) -> Optional[Dict]:
        """Extract data from a single Facebook listing card"""
        try:
            # Current live DOM: the card IS an anchor (role=link, href=/marketplace/item/<id>/...)
            # so read href directly before falling back to a nested <a>.
            href = card.attr('href')
            if not href:
                link_element = card.ele('tag:a', timeout=2)
                href = link_element.link if link_element else None
            if not href:
                return None

            # Facebook URLs can be complex, extract clean URL
            if '/marketplace/item/' in href:
                id_match = re.search(r'/marketplace/item/(\d+)', href)
                external_id = id_match.group(1) if id_match else None
                full_url = f"{self.base_url}/marketplace/item/{external_id}" if external_id else href
            else:
                external_id = None
                full_url = href

            # Extract all text content
            card_text = card.text

            # Extract title
            title = ""
            title_selectors = ['css:span[class*="title"]', 'tag:h2', 'tag:h3']
            for selector in title_selectors:
                title_element = card.ele(selector, timeout=2)
                if title_element:
                    title = title_element.text
                    break

            # Extract price
            price = self._extract_price_from_text(card_text)

            # Extract details
            rooms = self._extract_rooms(card_text)
            size_sqm = self._extract_size(card_text)

            # Location (often in description or title)
            city, neighborhood, street = self._extract_location_from_text(card_text)

            # Extract images
            images = []
            img_elements = card.eles('tag:img')
            for img in img_elements[:5]:
                src = img.attr('src')
                if src and 'http' in src:
                    images.append(src)

            try:
                card_html = card.html or ''
            except Exception:
                card_html = ''

            # Facebook renders "Listed X hours ago" / "Listed 2 days ago" in
            # card text. parse_relative_time handles both English and Hebrew.
            posted_at = self.parse_relative_time(card_text)

            return {
                'external_id': external_id,
                'url': full_url,
                'title': title.strip(),
                'price': price,
                'rooms': rooms,
                'size_sqm': size_sqm,
                'floor': None,
                'city': city,
                'neighborhood': neighborhood,
                'street': street,
                'location_text': '',
                'details_text': card_text,
                'card_html': card_html,
                'posted_at': posted_at,
                'contact_name': '',
                'contact_phone': '',
                'images': images
            }

        except Exception as e:
            logger.debug(f"Error extracting Facebook listing data: {e}")
            return None

    def parse_listing(self, raw_data: Dict) -> Optional[Dict]:
        """Parse raw listing data into standardized format"""
        try:
            # Calculate price per sqm
            price_per_sqm = None
            if raw_data.get('price') and raw_data.get('size_sqm') and raw_data['size_sqm'] > 0:
                price_per_sqm = raw_data['price'] / raw_data['size_sqm']

            haystack = ' '.join([
                raw_data.get('details_text', '') or '',
                raw_data.get('title', '') or '',
                raw_data.get('detail_text', '') or '',
                raw_data.get('card_html', '') or '',
            ])
            features = self.extract_features(haystack)

            return {
                'source': 'facebook',
                'external_id': raw_data.get('external_id'),
                'url': raw_data.get('url'),
                'title': raw_data.get('title'),
                'description': raw_data.get('details_text', ''),
                'address': f"{raw_data.get('street', '')}, {raw_data.get('neighborhood', '')}, {raw_data.get('city', '')}".strip(', '),
                'city': raw_data.get('city'),
                'neighborhood': raw_data.get('neighborhood'),
                'street': raw_data.get('street'),
                'rooms': raw_data.get('rooms'),
                'size_sqm': raw_data.get('size_sqm'),
                'floor': raw_data.get('floor'),
                'price': raw_data.get('price'),
                'price_per_sqm': price_per_sqm,
                'posted_at': raw_data.get('posted_at'),
                **features,
                'contact_name': raw_data.get('contact_name'),
                'contact_phone': raw_data.get('contact_phone'),
                'images': raw_data.get('images', [])
            }

        except Exception as e:
            logger.warning(f"Error parsing Facebook listing: {e}")
            return None

    def _extract_price_from_text(self, text: str) -> Optional[float]:
        """Extract price from text"""
        # Look for patterns like "₪5,000" or "5000 ₪" or "5,000 shekels"
        patterns = [
            r'₪\s*([\d,]+)',
            r'([\d,]+)\s*₪',
            r'([\d,]+)\s*(?:ש"ח|שקל)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    price_str = match.group(1).replace(',', '')
                    return float(price_str)
                except:
                    pass
        return None

    def _extract_rooms(self, text: str) -> Optional[float]:
        """Extract number of rooms"""
        match = re.search(r'(\d+\.?\d*)\s*(?:חדרים|חד\'|rooms)', text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None

    def _extract_size(self, text: str) -> Optional[float]:
        """Extract size in sqm"""
        match = re.search(r'(\d+)\s*(?:מ"ר|מ״ר|sqm|m2)', text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None

    def _extract_location_from_text(self, text: str) -> tuple:
        """Extract location information from text"""
        # Longer names first so 'תל אביב-יפו' wins before its prefix 'תל אביב' can match.
        cities = [
            'תל אביב-יפו', 'תל אביב', 'רמת גן', 'גבעתיים',
            'הרצליה', 'רמת השרון', 'פתח תקווה', 'ראשון לציון',
            'הוד השרון', 'כפר סבא', 'רעננה',
        ]
        # Map FB's short form to the canonical form used elsewhere in the app.
        city_aliases = {'תל אביב': 'תל אביב-יפו'}

        city = None
        neighborhood = None
        street = None

        # Find city
        for c in cities:
            if c in text:
                city = city_aliases.get(c, c)
                break

        neighborhoods = [
            # Tel Aviv
            'רמת אביב', 'בבלי', 'יד אליהו', 'נווה אביבים',
            'פלורנטין', 'נווה צדק', 'רמת החייל',
            # Priority areas the user asked for (Hod HaSharon / Kfar Saba / Herzliya / PT)
            'גאולים', 'נווה הדרים', 'הדרים', 'השכונה הירוקה',
            'מתחם 1200', 'מגדיאל', 'אם המושבות החדשה', 'אם המושבות',
        ]

        for n in neighborhoods:
            if n in text:
                neighborhood = n
                break

        return city, neighborhood, street
