"""Backfill images for existing Madlan listings that have empty images_json."""
import json
import time
from DrissionPage import ChromiumPage, ChromiumOptions
from app.core.config import settings
from app.core.database import init_db, Listing

engine, SessionLocal = init_db(settings.database_url)
db = SessionLocal()

opts = ChromiumOptions().set_local_port(9222)
page = ChromiumPage(addr_or_opts=opts)

try:
    rows = db.query(Listing).filter(Listing.source == 'madlan').all()
    for listing in rows:
        if listing.get_images():
            continue
        url = listing.url
        if not url:
            continue
        print(f"[{listing.id}] visiting {url}")
        page.get(url)
        time.sleep(3)
        for _ in range(2):
            page.scroll.down(500)
            time.sleep(1)

        imgs = page.eles('css:img')
        urls = []
        for img in imgs:
            src = img.attr('src') or ""
            if not src:
                continue
            if 'images2.madlan.co.il' in src and 'bulletins' in src:
                if src not in urls:
                    urls.append(src)
        urls = urls[:6]
        print(f"[{listing.id}] found {len(urls)} images")
        if urls:
            listing.set_images(urls)
            db.commit()
            print(f"[{listing.id}] saved")
finally:
    db.close()
