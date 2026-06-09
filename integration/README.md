# NadlanScraper — Signal integration

Drop-in files to replace your existing Bootstrap dashboard with the Signal design, wired to your FastAPI backend.

## Files

```
integration/
  templates/index.html      →  copy to  templates/index.html
  static/app.css            →  copy to  static/app.css
  static/app.js             →  copy to  static/app.js
```

## 1. Mount static files in FastAPI

In your `app/main.py` (or wherever `app = FastAPI()` lives):

```python
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
```

## 2. Update the index view to pass bootstrap data

```python
@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    total = db.query(Listing).count()
    today = datetime.now().date()
    new_today = db.query(Listing).filter(func.date(Listing.first_seen) == today).count()
    high_score = db.query(Listing).filter(Listing.deal_score >= 80).count()
    avg_score = db.query(func.avg(Listing.deal_score)).scalar() or 0

    cities = [c[0] for c in db.query(Listing.city).distinct().all() if c[0]]
    neighborhoods = [n[0] for n in db.query(Listing.neighborhood).distinct().all() if n[0]]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "total_listings": total,
        "new_today": new_today,
        "high_score": high_score,
        "avg_score": round(avg_score),
        "cities": cities,
        "neighborhoods": neighborhoods,
        "current_city": "",
        "current_neighborhood": "",
        "current_min_score": 0,
        "current_mamad": False,
        "current_status": "all",
        "current_sort": "deal_score",
    })
```

## 3. Add the `/api/listings` endpoint

The React app calls `GET /api/listings?city=&neighborhood=&min_score=&has_mamad=&sort_by=&status=`.

```python
@app.get("/api/listings")
def api_listings(
    city: str = "",
    neighborhood: str = "",
    min_score: int = 0,
    has_mamad: bool = False,
    sort_by: str = "deal_score",
    status: str = "all",
    db: Session = Depends(get_db),
):
    q = db.query(Listing)
    if city: q = q.filter(Listing.city == city)
    if neighborhood: q = q.filter(Listing.neighborhood == neighborhood)
    if min_score: q = q.filter(Listing.deal_score >= min_score)
    if has_mamad: q = q.filter(Listing.has_mamad == True)
    if status and status != "all":
        q = q.filter(Listing.user_status == status)

    sort_col = {
        "deal_score": Listing.deal_score.desc(),
        "price_asc": Listing.price.asc(),
        "price_desc": Listing.price.desc(),
        "newest": Listing.first_seen.desc(),
        "price_per_sqm": Listing.price_per_sqm.asc(),
    }.get(sort_by, Listing.deal_score.desc())
    q = q.order_by(sort_col)

    now = datetime.now()
    out = []
    for l in q.limit(200).all():
        images = l.get_images() if hasattr(l, "get_images") else []
        days = (now - l.first_seen).days if l.first_seen else 0
        out.append({
            "id": l.id,
            "he": l.title or "",
            "neighborhood": l.neighborhood or "",
            "city": l.city or "",
            "price": l.price or 0,
            "sqm": l.size_sqm or 0,
            "rooms": l.rooms or 0,
            "floor": l.floor or 0,
            "pricePerSqm": l.price_per_sqm or 0,
            "score": l.deal_score or 0,
            "source": l.source or "",
            "daysAgo": days,
            "features": {
                "mamad": bool(getattr(l, "has_mamad", False)),
                "parking": bool(getattr(l, "has_parking", False)),
                "elevator": bool(getattr(l, "has_elevator", False)),
                "balcony": bool(getattr(l, "has_balcony", False)),
            },
            "trend": getattr(l, "price_change_pct", 0) or 0,
            "isNew": days == 0,
            "image": images[0] if images else None,
            "url": l.url or "#",
        })
    return out
```

## 4. Status mutation endpoint

The Like / Called / Hide buttons POST to:
`POST /api/listing/{id}/status?status=liked|called|hidden`

If you already have this — great. If not:

```python
@app.post("/api/listing/{listing_id}/status")
def set_status(listing_id: int, status: str, db: Session = Depends(get_db)):
    l = db.query(Listing).filter(Listing.id == listing_id).first()
    if not l:
        raise HTTPException(404)
    l.user_status = status if status in ("liked","called","hidden") else None
    db.commit()
    return {"ok": True, "status": l.user_status}
```

## 5. What's already wired

- **Listings grid / list / map** — fetches from `/api/listings` on mount and whenever filters change
- **Filters sidebar** — city, neighborhood, min score, mamad toggle, sort
- **Card actions** — Like / Called / Hide POST to your API
- **"Open on yad2"** — opens `it.url` in a new tab
- **Photos** — if `image` is a URL, renders `<img>`; otherwise a warm placeholder block
- **Stats strip** — reads from the Jinja bootstrap JSON

## 6. Optional polish

- The `Marketing` section at the top can be hidden — toggle via Tweaks or conditionally render based on an auth flag
- Swap the dev React/Babel scripts for production builds once settled (`esbuild app.jsx --bundle --minify --outfile=static/app.js`)
- Add a `/api/status` endpoint so the "next scrape" clock and source counts in the sidebar become live
