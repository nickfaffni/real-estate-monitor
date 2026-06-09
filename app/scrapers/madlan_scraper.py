from app.scrapers.base_scraper import BaseScraper
from typing import List, Dict, Optional
from urllib.parse import quote
import logging
import re

from app.core.config import settings

logger = logging.getLogger(__name__)


class MadlanScraper(BaseScraper):
    """Scraper for Madlan.co.il real estate listings"""

    def __init__(self, db_session):
        super().__init__(db_session, 'madlan')
        self.base_url = "https://www.madlan.co.il"

    def build_search_url(self, city: Optional[str] = None) -> str:
        """Build Madlan search URL for the given city or the first configured city.
        
        Madlan expects the city slug as hyphen-joined Hebrew words plus a trailing
        `-ישראל`, e.g. `/for-rent/תל-אביב-יפו-ישראל?priceMax=8000&tracking_search_source=new_search`.
        The `tracking_search_source=new_search` param is required — without it (or
        with the raw city name), Madlan serves an empty results page.
        """
        endpoint = "for-rent" if settings.listing_type.lower() == "rent" else "for-sale"
        
        target_city = city
        if not target_city:
            cities = settings.get_cities_list()
            target_city = cities[0] if cities else None
            
        if target_city:
            # Common city mappings for Madlan slugs
            city_mappings = {
                "תל אביב": "תל אביב-יפו",
                "תל אביב יפו": "תל אביב-יפו",
                "פתח תקווה": "פתח תקווה",
            }
            
            normalized_city = city_mappings.get(target_city.strip(), target_city.strip())
            slug = normalized_city.replace(" ", "-") + "-ישראל"
            city_path = quote(slug, safe="-")
            return (
                f"{self.base_url}/{endpoint}/{city_path}"
                f"?priceMax={int(settings.max_price)}&tracking_search_source=new_search"
            )
        return f"{self.base_url}/{endpoint}?priceMax={int(settings.max_price)}&tracking_search_source=new_search"

    def scrape(self) -> List[Dict]:
        """Scrape Madlan listings for all configured cities"""
        if not self.page:
            logger.error("[Madlan Scraper] Browser page not initialized")
            return []

        all_listings = []
        cities = settings.get_cities_list()
        
        if not cities:
            logger.warning("[Madlan Scraper] No cities configured for scraping")
            return []

        for city in cities:
            try:
                search_url = self.build_search_url(city)
                logger.info(f"[Madlan Scraper] Scraping city: {city}, url: {search_url}")

                # Navigate to the page
                self.page.get(search_url)
                logger.info(f"[Madlan Scraper] Page loaded for {city}")

                # Wait for page to settle
                self.random_delay(2, 3)

                # Check for anti-bot protection (CAPTCHA, etc.)
                self._handle_anti_bot_protection()

                # Longer initial delay to let anti-bot scripts run
                self.random_delay(3, 5)

                # Simulate human-like mouse movements
                self.human_like_mouse_movement()

                # Scroll to load more results - use setting or default to 3
                max_scrolls = getattr(settings, 'default_max_scrolls', 3)
                self.scroll_page(scrolls=max_scrolls)
                self.random_delay(1, 2)

                # Find listing cards
                listing_cards = self.page.eles('css:a[data-auto="listed-bulletin-clickable"]')
                if not listing_cards:
                    listing_cards = self.page.eles('css:a[href*="/listings/"]')

                logger.info(f"[Madlan Scraper] Found {len(listing_cards)} listings for {city}")

                if not listing_cards:
                    logger.warning(f"[Madlan Scraper] No listing cards found for {city} - saving debug output")
                    self.debug_save_page(f"no_listings_madlan_{city}")
                    continue

                # Two-pass: collect card data first (so we don't lose element
                # references when we navigate away), then fetch detail-page
                # text for new listings only. Madlan cards don't render
                # amenity words — those live on the detail page.
                # Increased limit to 60 to get past sponsored/over-budget listings.
                raw_cards = []
                for idx, card in enumerate(listing_cards[:60], 1):
                    try:
                        listing_data = self._extract_listing_data(card, idx=idx, city_hint=city)
                        if listing_data:
                            raw_cards.append(listing_data)
                    except Exception as e:
                        logger.warning(f"[Madlan Scraper] Error extracting listing for {city}, index: {idx}, error: {e}")
                        continue

                city_listings_count = 0
                for idx, listing_data in enumerate(raw_cards, 1):
                    try:
                        ext_id = listing_data.get('external_id')
                        price = listing_data.get('price') or 0
                        # Madlan mixes sponsored for-sale promos into for-rent
                        # search results. Their price is obviously over
                        # our cap, and the processor will filter them anyway —
                        # skip the detail fetch.
                        too_expensive = settings.max_price and price > (settings.max_price * 1.5) # allow some buffer for score
                        
                        if ext_id and not self.listing_exists(ext_id) and not too_expensive:
                            detail_url = listing_data.get('url')
                            logger.debug(f"[Madlan Scraper] New listing, fetching detail: {detail_url}")
                            listing_data['detail_text'] = self.fetch_detail_text(detail_url)
                            self.random_delay(1.5, 3)
                        elif too_expensive:
                            logger.debug(f"[Madlan Scraper] Skipping detail fetch — price {price} > max {settings.max_price} (likely for-sale promo)")
                        
                        parsed = self.parse_listing(listing_data)
                        if parsed:
                            all_listings.append(parsed)
                            city_listings_count += 1
                    except Exception as e:
                        logger.warning(f"[Madlan Scraper] Error parsing listing for {city}, index: {idx}, error: {e}")
                        continue
                
                logger.info(f"[Madlan Scraper] Successfully parsed {city_listings_count} listings for {city}")
                
                # Random delay between cities
                self.random_delay(3, 7)

            except Exception as e:
                logger.error(f"[Madlan Scraper] Error scraping city {city}: {e}")
                continue

        logger.info(f"[Madlan Scraper] Total scraping completed, total_listings: {len(all_listings)}")
        return all_listings

    def _extract_listing_data(self, card, idx: Optional[int] = None, city_hint: Optional[str] = None) -> Optional[Dict]:
        """Extract data from a single listing card"""
        tag = f"[Madlan] card {idx}" if idx is not None else "[Madlan] card"
        try:
            # If the card itself is the anchor, use its href directly; else find one inside.
            href = card.attr('href')
            if not href:
                link_element = card.ele('tag:a', timeout=2)
                href = link_element.link if link_element else None
            if not href:
                logger.warning(f"{tag}: no href on card or nested anchor")
                return None

            full_url = self.base_url + href if href.startswith('/') else href

            # Madlan IDs are alphanumeric under /listings/<id>.
            id_match = re.search(r'/listings/([^/?&#]+)', href)
            external_id = id_match.group(1) if id_match else None
            if not external_id:
                logger.warning(f"{tag}: could not parse external_id from href={href!r}")

            card_text = card.text or ""

            # Price via data-auto
            price_element = card.ele('css:[data-auto="property-price"]', timeout=1)
            price_text = price_element.text if price_element else ""
            if not price_text:
                logger.warning(f"{tag}: price selector [data-auto=property-price] missed")
            price = self._extract_number(price_text)

            # Rooms / floor / size each have their own data-auto
            rooms_el = card.ele('css:[data-auto="property-rooms"]', timeout=1)
            rooms = self._extract_number(rooms_el.text) if rooms_el else self._extract_rooms(card_text)

            size_el = card.ele('css:[data-auto="property-size"]', timeout=1)
            size_sqm = self._extract_number(size_el.text) if size_el else self._extract_size(card_text)

            floor_el = card.ele('css:[data-auto="property-floor"]', timeout=1)
            if floor_el:
                floor_num = self._extract_number(floor_el.text)
                floor = int(floor_num) if floor_num is not None else None
            else:
                floor = self._extract_floor(card_text)

            # Address: [property-address] gives e.g. "דירה, אבן גבירול 39, הצפון הישן"
            # (no city — it's implicit from the URL), so we prepend the configured city.
            address_element = card.ele('css:[data-auto="property-address"]', timeout=1)
            address_text = address_element.text.strip() if address_element else ""
            if not address_text:
                logger.warning(f"{tag}: address selector [data-auto=property-address] missed")

            # Use the city currently being scraped (one URL = one city on Madlan).
            # Fall back to the first configured city only if the caller didn't tell us.
            if not city_hint:
                configured_cities = settings.get_cities_list()
                city_hint = configured_cities[0] if configured_cities else ""
            location_text = f"{address_text}, {city_hint}".strip(", ") if address_text else city_hint

            # Madlan's address parts are "type, street, neighborhood"; the city comes from URL.
            parts = [p.strip() for p in address_text.split(',')]
            # Most specific first: type, street, neighborhood — map street & neighborhood, city from URL.
            street = parts[1] if len(parts) > 1 else (parts[0] if parts else None)
            neighborhood = parts[2] if len(parts) > 2 else None
            city = city_hint or None

            title = address_text or city_hint

            images = []
            img_elements = card.eles('css:img[data-auto="universal-card-image"]')
            if not img_elements:
                img_elements = card.eles('tag:img')
            for img in img_elements[:5]:
                src = img.attr('src')
                if src and ('http' in src or src.startswith('//')):
                    if src.startswith('//'):
                        src = 'https:' + src
                    images.append(src)

            try:
                card_html = card.html or ''
            except Exception:
                card_html = ''

            # "Posted X ago" — scan both card text and HTML since Madlan
            # sometimes buries the relative-time in an aria-label.
            posted_at = self.parse_relative_time(card_text) or self.parse_relative_time(card_html)

            return {
                'external_id': external_id,
                'url': full_url,
                'title': title.strip(),
                'price': price,
                'rooms': rooms,
                'size_sqm': size_sqm,
                'floor': floor,
                'city': city,
                'neighborhood': neighborhood,
                'street': street,
                'location_text': location_text,
                'details_text': card_text,
                'card_html': card_html,
                'posted_at': posted_at,
                'contact_name': '',
                'contact_phone': '',
                'images': images
            }

        except Exception as e:
            logger.warning(f"{tag}: exception while extracting: {e}")
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
                raw_data.get('location_text', '') or '',
                raw_data.get('detail_text', '') or '',
                raw_data.get('card_html', '') or '',
            ])
            features = self.extract_features(haystack)

            return {
                'source': 'madlan',
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
            logger.warning(f"Error parsing Madlan listing: {e}")
            return None

    def _extract_number(self, text: str) -> Optional[float]:
        """Extract number from text"""
        if not text:
            return None

        numbers = re.findall(r'[\d,]+', text.replace(',', ''))
        if numbers:
            try:
                return float(numbers[0])
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

    def _extract_floor(self, text: str) -> Optional[int]:
        """Extract floor number"""
        match = re.search(r'(?:קומה|floor)\s*(\d+)', text)
        if match:
            try:
                return int(match.group(1))
            except:
                pass
        return None

    def _extract_location_from_text(self, text: str) -> str:
        """Try to extract location from general text"""
        # Look for common Israeli city names
        cities = ['תל אביב', 'רמת גן', 'גבעתיים', 'הרצליה', 'רמת השרון', 'פתח תקווה']
        for city in cities:
            if city in text:
                # Try to find surrounding context
                idx = text.find(city)
                # Get ~50 chars before and after
                start = max(0, idx - 50)
                end = min(len(text), idx + len(city) + 50)
                return text[start:end].strip()
        return ""

    def _parse_location(self, location_text: str) -> tuple:
        """Parse location into city, neighborhood, street"""
        if not location_text:
            return None, None, None

        parts = [p.strip() for p in location_text.split(',')]

        city = parts[-1] if len(parts) > 0 else None
        neighborhood = parts[-2] if len(parts) > 1 else None
        street = parts[0] if len(parts) > 0 else None

        return city, neighborhood, street
