from app.scrapers.base_scraper import BaseScraper
from typing import List, Dict, Optional
import logging
import re
from app.core.config import settings

logger = logging.getLogger(__name__)


class Yad2Scraper(BaseScraper):
    """Scraper for Yad2.co.il real estate listings"""

    def __init__(self, db_session):
        super().__init__(db_session, 'yad2')
        self.base_url = "https://www.yad2.co.il"
        self.city_map = {
            'תל אביב-יפו': '5000',
            'תל אביב': '5000',
            'ירושלים': '3000',
            'חיפה': '4000',
            'פתח תקווה': '7900',
            'כפר סבא': '6900',
            'הוד השרון': '9700',
            'הרצליה': '6400',
            'רעננה': '8700',
            'רמת גן': '8600',
            'גבעתיים': '6300',
            'רמת השרון': '2640',
            'חולון': '6600',
            'ראשון לציון': '8300',
            'נתניה': '7400',
            'אשדוד': '70',
            'באר שבע': '9000',
            'רחובות': '8400',
            'כפר שמריהו': '7000',
            'רשפון': '887',
            'בצרה': '885',
            'בני ציון': '883',
            'צופית': '884',
            'גן חיים': '882',
            'גבעת חן': '881',
        }

    def build_search_url(self, area_params: Optional[Dict] = None) -> str:
        """Build Yad2 search URL with filters.

        If area_params is broad (e.g. topArea=2), it covers many cities. 
        The listing_filter narrows further by city allowlist.
        """
        endpoint = "rent" if settings.listing_type.lower() == "rent" else "forsale"
        
        # Default to Center region if none specified
        params = {
            'topArea': '2',
            'maxPrice': str(int(settings.max_price)),
            'minRooms': str(settings.min_rooms),
            'Order': '1',
        }
        
        if area_params:
            params.update(area_params)
            
        return f"{self.base_url}/realestate/{endpoint}?" + "&".join(f"{k}={v}" for k, v in params.items())

    def scrape(self) -> List[Dict]:
        """Scrape Yad2 listings across Center and Sharon regions"""
        if not self.page:
            logger.error("[Yad2 Scraper] Browser page not initialized")
            return []

        all_listings = []
        
        # Build search areas based on exact city IDs from settings
        areas = []
        for city_name in settings.get_cities_list():
            if city_name in self.city_map:
                areas.append({'city': self.city_map[city_name], '_name': city_name})
            else:
                logger.warning(f"[Yad2 Scraper] City '{city_name}' not in Yad2 city map, skipping.")
        
        if not areas:
            logger.warning("[Yad2 Scraper] No valid cities mapped, falling back to Center.")
            areas = [{'topArea': '2', '_name': 'Center'}]

        for area_params in areas:
            area_name = area_params.pop('_name', 'Unknown')
            try:
                # Navigate to search results
                search_url = self.build_search_url(area_params)
                logger.info(f"[Yad2 Scraper] Scraping area {area_name}, url: {search_url}")

                # Navigate to the page
                self.page.get(search_url)
                logger.info(f"[Yad2 Scraper] Page loaded for area {area_name}")

                # Wait for page to settle
                self.random_delay(2, 3)

                # Check for anti-bot protection (CAPTCHA, etc.)
                self._handle_anti_bot_protection()

                # Longer initial delay to let anti-bot scripts run
                self.random_delay(3, 5)

                # Simulate human-like mouse movements
                self.human_like_mouse_movement()

                # Scroll to load more results
                self.scroll_page(scrolls=2)
                self.random_delay(1, 2)

                # Find listing cards
                listing_cards = self.page.eles('css:a[data-nagish="property-ad-card-link"]')
                if not listing_cards:
                    listing_cards = self.page.eles('css:a[href*="/realestate/item/"]')

                logger.info(f"[Yad2 Scraper] Found {len(listing_cards)} listings in area {area_name}")

                # Two-pass: collect card data first, then fetch detail pages
                # for new listings only. Yad2 cards show rooms/size/floor but
                # not amenity text (elevator/parking/balcony/mamad) — those
                # are on the detail page.
                raw_cards = []
                for idx, card in enumerate(listing_cards[:25], 1):
                    try:
                        listing_data = self._extract_listing_data(card, idx=idx)
                        if listing_data:
                            raw_cards.append(listing_data)
                    except Exception as e:
                        logger.warning(f"[Yad2 Scraper] Error extracting listing in area {area_name}, index: {idx}, error: {e}")
                        continue

                area_listings_count = 0
                for idx, listing_data in enumerate(raw_cards, 1):
                    try:
                        ext_id = listing_data.get('external_id')
                        price = listing_data.get('price') or 0
                        # Skip detail-page fetch for cards that are already
                        # over MAX_PRICE — the processor will reject them;
                        # no reason to navigate Chrome there.
                        too_expensive = settings.max_price and price > settings.max_price
                        if ext_id and not self.listing_exists(ext_id) and not too_expensive:
                            detail_url = listing_data.get('url')
                            logger.debug(f"[Yad2 Scraper] New listing, fetching detail: {detail_url}")
                            listing_data['detail_text'] = self.fetch_detail_text(detail_url)
                            self.random_delay(1.5, 3)
                        elif too_expensive:
                            logger.debug(f"[Yad2 Scraper] Skipping detail fetch — price {price} > max {settings.max_price}")
                        parsed = self.parse_listing(listing_data)
                        if parsed:
                            all_listings.append(parsed)
                            area_listings_count += 1
                    except Exception as e:
                        logger.warning(f"[Yad2 Scraper] Error parsing listing in area {area_params.get('topArea')}, index: {idx}, error: {e}")
                        continue
                
                logger.info(f"[Yad2 Scraper] Successfully parsed {area_listings_count} listings in area {area_params.get('topArea')}")
                
                # Random delay between areas
                self.random_delay(4, 8)

            except Exception as e:
                logger.error(f"[Yad2 Scraper] Error scraping area {area_params.get('topArea')}: {e}")
                continue

        logger.info(f"[Yad2 Scraper] Total scraping completed, total_listings: {len(all_listings)}")
        return all_listings

    def _extract_listing_data(self, card, idx: Optional[int] = None) -> Optional[Dict]:
        """Extract data from a single listing card.

        Yad2's 2026 markup: the card IS an <a data-nagish="property-ad-card-link">
        wrapping the image, price ([data-testid="price"]), address
        ([data-testid="address-line"]), and a details blurb ("N חדרים • קומה X • Y מ\"ר").
        """
        tag = f"[Yad2] card {idx}" if idx is not None else "[Yad2] card"
        try:
            # The card itself is the <a>; href lives on its attribute.
            href = card.attr('href')
            if not href:
                # Fallback: maybe it's a wrapper with a nested anchor.
                inner = card.ele('tag:a', timeout=1)
                href = inner.link if inner else None
            if not href:
                logger.warning(f"{tag}: no href on anchor")
                return None

            full_url = self.base_url + href if href.startswith('/') else href

            # Yad2 listing IDs are alphanumeric, e.g. /realestate/item/<region>/<id>?...
            id_match = re.search(r'/realestate/item/[^/]+/([^?&/]+)', href)
            external_id = id_match.group(1) if id_match else None
            if not external_id:
                logger.warning(f"{tag}: could not parse external_id from href={href!r}")

            details_text = card.text or ""

            # Price via data-testid
            price_element = card.ele('css:[data-testid="price"]', timeout=1)
            price_text = price_element.text if price_element else ""
            if not price_text:
                logger.warning(f"{tag}: price selector [data-testid=price] missed")
            price = self._extract_number(price_text)

            # Address via data-testid
            address_element = card.ele('css:[data-testid="address-line"]', timeout=1)
            location_text = address_element.text if address_element else ""
            if not location_text:
                logger.warning(f"{tag}: address selector [data-testid=address-line] missed")

            # Title falls back to address (yad2 cards have no dedicated title).
            title = location_text

            rooms = self._extract_rooms(details_text)
            size_sqm = self._extract_size(details_text)
            floor = self._extract_floor(details_text)

            city, neighborhood, street = self._parse_location(location_text)

            # "Posted X ago" — Yad2 renders this inline in the card text.
            posted_at = self.parse_relative_time(details_text)

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
                'details_text': details_text,
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
                'source': 'yad2',
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
            logger.warning(f"Error parsing Yad2 listing: {e}")
            return None

    def _extract_number(self, text: str) -> Optional[float]:
        """Extract number from text"""
        if not text:
            return None

        # Remove commas and extract numbers
        numbers = re.findall(r'[\d,]+', text.replace(',', ''))
        if numbers:
            try:
                return float(numbers[0])
            except:
                pass
        return None

    def _extract_rooms(self, text: str) -> Optional[float]:
        """Extract number of rooms"""
        # Look for patterns like "3 חדרים", "3.5 חד'", or "5 חד"
        match = re.search(r'(\d+\.?\d*)\s*(?:חדרים|חד\'|חד|rooms)', text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None

    def _extract_size(self, text: str) -> Optional[float]:
        """Extract size in sqm"""
        # Look for patterns like "80 מ\"ר" or "80 sqm"
        match = re.search(r'(\d+)\s*(?:מ"ר|מ״ר|sqm|m2)', text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None

    def _extract_floor(self, text: str) -> Optional[int]:
        """Extract floor number"""
        # Look for patterns like "קומה 3" or "floor 3"
        match = re.search(r'(?:קומה|floor)\s*(\d+)', text)
        if match:
            try:
                return int(match.group(1))
            except:
                pass
        return None

    def _parse_location(self, location_text: str) -> tuple:
        """Parse location into city, neighborhood, street"""
        if not location_text:
            return None, None, None

        # Location usually in format: "Street, Neighborhood, City"
        parts = [p.strip() for p in location_text.split(',')]

        city = parts[-1] if len(parts) > 0 else None
        neighborhood = parts[-2] if len(parts) > 1 else None
        street = parts[0] if len(parts) > 0 else None

        return city, neighborhood, street
