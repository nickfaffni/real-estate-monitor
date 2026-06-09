from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from app.core.database import Listing, NeighborhoodStats
from app.core.config import settings
import statistics


class DealScoreCalculator:
    """Calculate deal score for listings based on multiple factors"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.settings = settings

    def calculate_score(self, listing: Listing) -> float:
        score, _ = self.calculate_score_with_breakdown(listing)
        return score

    def calculate_score_with_breakdown(self, listing: Listing) -> Tuple[float, Dict[str, Any]]:
        """Return (final_score, breakdown dict) for the listing."""
        price_pts, price_detail = self._score_price_competitiveness(listing)
        feat_pts, feat_detail = self._score_features(listing)
        rec_pts, rec_detail = self._score_recency(listing)
        trend_pts, trend_detail = self._score_price_trend(listing)
        transit_pts, transit_detail = self._score_transit(listing)

        raw_total = price_pts + feat_pts + rec_pts + trend_pts + transit_pts
        total = min(100.0, max(0.0, raw_total))

        breakdown = {
            "total": round(total, 1),
            "components": [
                {
                    "key": "price",
                    "label": "Price vs. neighborhood",
                    "points": round(price_pts, 1),
                    "max": self.settings.deal_score_weight_price,
                    "detail": price_detail,
                },
                {
                    "key": "features",
                    "label": "Features match",
                    "points": round(feat_pts, 1),
                    "max": self.settings.deal_score_weight_features,
                    "detail": feat_detail,
                },
                {
                    "key": "recency",
                    "label": "Freshness",
                    "points": round(rec_pts, 1),
                    "max": self.settings.deal_score_weight_recency,
                    "detail": rec_detail,
                },
                {
                    "key": "trend",
                    "label": "Price trend",
                    "points": round(trend_pts, 1),
                    "max": self.settings.deal_score_weight_price_trend,
                    "detail": trend_detail,
                },
                {
                    "key": "transit",
                    "label": "Transit proximity",
                    "points": round(transit_pts, 1),
                    "max": self.settings.deal_score_weight_transit,
                    "detail": transit_detail,
                },
            ],
        }
        return total, breakdown

    def _score_price_competitiveness(self, listing: Listing) -> Tuple[float, str]:
        """Score based on price per sqm vs neighborhood average"""
        max_score = self.settings.deal_score_weight_price

        if not listing.price_per_sqm or listing.price_per_sqm <= 0:
            return 0.0, "no price/sqm data"

        stats = self.db.query(NeighborhoodStats).filter(
            NeighborhoodStats.city == listing.city,
            NeighborhoodStats.neighborhood == listing.neighborhood
        ).first()

        if not stats or not stats.avg_price_per_sqm:
            return max_score * 0.5, "no neighborhood baseline — neutral"

        avg_price = stats.avg_price_per_sqm
        price_ratio = listing.price_per_sqm / avg_price
        diff_pct = (price_ratio - 1.0) * 100
        direction = "below" if diff_pct < 0 else "above"
        detail = f"{abs(diff_pct):.0f}% {direction} neighborhood avg"

        if price_ratio <= 0.7:
            return max_score * 1.0, detail
        elif price_ratio <= 0.8:
            return max_score * 0.875, detail
        elif price_ratio <= 0.9:
            return max_score * 0.75, detail
        elif price_ratio <= 1.0:
            return max_score * 0.625, detail
        elif price_ratio <= 1.1:
            return max_score * 0.375, detail
        elif price_ratio <= 1.2:
            return max_score * 0.25, detail
        else:
            return max_score * 0.125, detail

    def _score_features(self, listing: Listing) -> Tuple[float, str]:
        """Score based on matching user preferences"""
        score = 0.0
        max_score = self.settings.deal_score_weight_features

        features = []
        if self.settings.prefer_parking:
            features.append(('parking', listing.has_parking, 10.0))
        if self.settings.prefer_balcony:
            features.append(('balcony', listing.has_balcony, 8.0))
        if self.settings.prefer_elevator:
            features.append(('elevator', listing.has_elevator, 7.0))
        if self.settings.prefer_mamad:
            features.append(('mamad', listing.has_mamad, 8.0))
        if self.settings.prefer_miklat:
            # miklat (shared building shelter) = weaker than unit-level mamad.
            # If the unit already has a mamad, miklat adds no extra value.
            miklat_counts = bool(getattr(listing, 'has_miklat', False)) and not listing.has_mamad
            features.append(('miklat', miklat_counts, 4.0))
        if self.settings.prefer_top_floors and listing.floor and listing.total_floors:
            is_top_half = listing.floor >= (listing.total_floors / 2)
            features.append(('top_floor', is_top_half, 5.0))

        if not features:
            return 0.0, "no preferences set"

        total_weight = sum(weight for _, _, weight in features)
        matched = []
        for name, has_feature, weight in features:
            if has_feature:
                score += (weight / total_weight) * max_score
                matched.append(name)

        detail = f"{len(matched)}/{len(features)} matched"
        if matched:
            detail += f" ({', '.join(matched)})"
        return score, detail

    def _score_recency(self, listing: Listing) -> Tuple[float, str]:
        """Score based on how fresh the listing is"""
        max_score = self.settings.deal_score_weight_recency

        if not listing.first_seen:
            return max_score, "just seen"

        days_old = (datetime.utcnow() - listing.first_seen).days
        detail = "today" if days_old == 0 else f"{days_old}d old"

        if days_old == 0:
            return max_score * 1.0, detail
        elif days_old <= 2:
            return max_score * 0.8, detail
        elif days_old <= 5:
            return max_score * 0.6, detail
        elif days_old <= 10:
            return max_score * 0.4, detail
        elif days_old <= 20:
            return max_score * 0.2, detail
        else:
            return max_score * 0.067, detail

    def _score_price_trend(self, listing: Listing) -> Tuple[float, str]:
        """Score based on price changes"""
        max_score = self.settings.deal_score_weight_price_trend
        neutral_score = max_score * 0.333

        if not listing.price_history or len(listing.price_history) < 2:
            return neutral_score, "no price history"

        sorted_history = sorted(listing.price_history, key=lambda x: x.timestamp, reverse=True)
        if len(sorted_history) < 2:
            return neutral_score, "no price history"

        current_price = sorted_history[0].price
        previous_price = sorted_history[1].price
        if not current_price or not previous_price or previous_price <= 0:
            return neutral_score, "no price history"

        pct = ((current_price - previous_price) / previous_price) * 100
        if pct < 0:
            detail = f"dropped {abs(pct):.1f}%"
        elif pct == 0:
            detail = "unchanged"
        else:
            detail = f"raised {pct:.1f}%"

        if pct <= -10:
            return max_score * 1.0, detail
        elif pct <= -5:
            return max_score * 0.8, detail
        elif pct <= -2:
            return max_score * 0.6, detail
        elif pct < 0:
            return max_score * 0.467, detail
        elif pct == 0:
            return neutral_score, detail
        else:
            return max_score * 0.133, detail

    def _score_transit(self, listing: Listing) -> Tuple[float, str]:
        """Score based on proximity to train/light-rail/subway stations."""
        from app.core.transit import TYPE_WEIGHTS
        max_score = self.settings.deal_score_weight_transit

        if listing.geocoded_at is None:
            return 0.0, "not yet geocoded"
        if listing.latitude is None or listing.longitude is None:
            return 0.0, "address could not be geocoded"
        if not listing.nearest_station_meters or not listing.nearest_station_type:
            return 0.0, "no station within 2km"

        meters = listing.nearest_station_meters
        type_mult = TYPE_WEIGHTS.get(listing.nearest_station_type, 0.85)

        if meters <= 500:
            dist_mult = 1.0
        elif meters <= 1000:
            dist_mult = 0.7
        elif meters <= 1500:
            dist_mult = 0.4
        else:
            dist_mult = 0.0

        points = max_score * type_mult * dist_mult
        type_label = {
            "heavy_rail": "heavy rail",
            "light_rail": "light rail",
            "subway": "subway",
            "tram": "tram",
        }.get(listing.nearest_station_type, listing.nearest_station_type)
        detail = f"{listing.nearest_station_name} · {int(meters)}m · {type_label}"
        return points, detail

    def get_price_drop_percentage(self, listing: Listing) -> Optional[float]:
        """Get percentage of price drop if any"""
        if not listing.price_history or len(listing.price_history) < 2:
            return None

        sorted_history = sorted(listing.price_history, key=lambda x: x.timestamp, reverse=True)

        if len(sorted_history) < 2:
            return None

        current_price = sorted_history[0].price
        previous_price = sorted_history[1].price

        if not current_price or not previous_price or previous_price <= 0:
            return None

        return ((previous_price - current_price) / previous_price) * 100


def update_neighborhood_stats(db_session: Session):
    """Update neighborhood statistics from current listings"""

    # Get all active listings grouped by neighborhood
    listings = db_session.query(Listing).filter(
        Listing.price > 0,
        Listing.price_per_sqm > 0
    ).all()

    # Group by city and neighborhood
    neighborhoods = {}
    for listing in listings:
        key = (listing.city, listing.neighborhood)
        if key not in neighborhoods:
            neighborhoods[key] = []
        neighborhoods[key].append(listing)

    # Calculate stats for each neighborhood
    for (city, neighborhood), listing_group in neighborhoods.items():
        if len(listing_group) < 3:  # Need at least 3 samples
            continue

        prices = [l.price for l in listing_group if l.price]
        prices_per_sqm = [l.price_per_sqm for l in listing_group if l.price_per_sqm]

        if not prices_per_sqm:
            continue

        # Get or create stats record
        stats = db_session.query(NeighborhoodStats).filter(
            NeighborhoodStats.city == city,
            NeighborhoodStats.neighborhood == neighborhood
        ).first()

        if not stats:
            stats = NeighborhoodStats(city=city, neighborhood=neighborhood)
            db_session.add(stats)

        # Update stats
        stats.avg_price = statistics.mean(prices)
        stats.avg_price_per_sqm = statistics.mean(prices_per_sqm)
        stats.median_price = statistics.median(prices)
        stats.median_price_per_sqm = statistics.median(prices_per_sqm)
        stats.sample_size = len(listing_group)
        stats.last_updated = datetime.utcnow()

    db_session.commit()
