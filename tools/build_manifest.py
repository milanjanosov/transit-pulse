"""Write data/cities.json - the landing map's list of exported cities.

Run after any export_city.py. Reads each data/<key>.json once and keeps
only what the landing page needs to place a marker and fly to the city.
"""
import json
import os

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data")

cities = []
for f in sorted(os.listdir(DATA)):
    if not f.endswith(".json") or f == "cities.json":
        continue
    with open(os.path.join(DATA, f)) as fh:
        d = json.load(fh)
    n = len(d["trips"]) // 4
    cities.append({"key": f[:-5], "name": d["city"], "center": d["center"],
                   "bbox": d["bbox"], "date": d["date"], "trips": n,
                   "mb": round(os.path.getsize(os.path.join(DATA, f)) / 1e6, 1)})
    print(f"  {f[:-5]:<14} {d['city']:<12} {n:>7,} trips")

with open(os.path.join(DATA, "cities.json"), "w") as fh:
    json.dump(cities, fh, separators=(",", ":"))
print(f"wrote {len(cities)} cities")
