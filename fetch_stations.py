"""One-shot: fetch Israeli train/light-rail/subway/tram stations from OSM
Overpass API and save to data/transit_stations.json.

Re-run manually when new lines open.
"""
import json
import sys
from pathlib import Path

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUT = Path(__file__).resolve().parent / "data" / "transit_stations.json"

# area["ISO3166-1"="IL"] scopes to Israel.
QUERY = """
[out:json][timeout:60];
area["ISO3166-1"="IL"]->.il;
(
  node["railway"="station"](area.il);
  node["railway"="halt"](area.il);
  node["railway"="tram_stop"](area.il);
  node["station"="light_rail"](area.il);
  node["station"="subway"](area.il);
  node["public_transport"="station"]["train"="yes"](area.il);
  node["public_transport"="station"]["light_rail"="yes"](area.il);
  node["public_transport"="station"]["subway"="yes"](area.il);
);
out body;
"""


def classify(tags: dict) -> str:
    if tags.get("subway") == "yes" or tags.get("station") == "subway":
        return "subway"
    if tags.get("light_rail") == "yes" or tags.get("station") == "light_rail":
        return "light_rail"
    if tags.get("railway") == "tram_stop" or tags.get("tram") == "yes":
        return "tram"
    return "heavy_rail"


def main():
    print("Fetching stations from Overpass…")
    resp = requests.post(
        OVERPASS_URL,
        data={"data": QUERY},
        headers={"User-Agent": "real-estate-monitor/1.0 (nickgaffni140@gmail.com)"},
        timeout=90,
    )
    resp.raise_for_status()
    elements = resp.json().get("elements", [])
    stations = []
    seen = set()
    for e in elements:
        if "lat" not in e or "lon" not in e:
            continue
        tags = e.get("tags", {})
        name = tags.get("name:en") or tags.get("name") or tags.get("name:he")
        if not name:
            continue
        # Dedupe: a station often appears under multiple OSM nodes (platform + hall).
        key = (round(e["lat"], 4), round(e["lon"], 4), name)
        if key in seen:
            continue
        seen.add(key)
        stations.append({
            "name": name,
            "lat": e["lat"],
            "lon": e["lon"],
            "type": classify(tags),
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(stations, f, ensure_ascii=False, indent=2)
    by_type = {}
    for s in stations:
        by_type[s["type"]] = by_type.get(s["type"], 0) + 1
    print(f"Wrote {len(stations)} stations to {OUT}")
    print("By type:", by_type)


if __name__ == "__main__":
    sys.exit(main())
