"""Export one city-day of TransitPulse vehicles for the browser.

Reuses the reel engine (tp_china.build_trip_tracks) so the web map moves
exactly like the reels. Instead of sampling positions, it ships the
engine's own breakpoints - time -> distance along shape - plus the shapes,
and the browser does the same two np.interp calls per frame.

Compact by dedupe: trips that share a shape and stop distances share a
"pattern"; trips that share relative stop times share a "profile". A trip
is then just (pattern, profile, start second).

Usage: python export_city.py budapest
"""
import json
import os
import sys

import numpy as np
import pandas as pd

TP = "/Users/milan/Dropbox/Dataprojects/NEW SCIENCE OF MAPS/Youtube/TransitPulse"
sys.path.insert(0, TP)
import tp_china as tp  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data")

T0, T1 = 4 * 3600, 28 * 3600      # 04:00 -> 04:00 next day, same service date


def colour_tracks(cfg, g, tracks):
    """Same colour precedence as tp_china.run_city."""
    if cfg.get("force_color"):
        for tr in tracks:
            tr["color"] = cfg["force_color"]
    for tr in tracks:
        c = (cfg.get("mode_colors") or {}).get(tr["route_type"])
        if c:
            tr["color"] = c
    for tr in tracks:
        c = (cfg.get("colors") or {}).get(tr["route_id"])
        if c:
            tr["color"] = c
    by_name = cfg.get("name_colors")
    if by_name:
        rn = g["routes"].set_index("route_id")["route_short_name"].to_dict()
        for tr in tracks:
            c = by_name.get(str(rn.get(tr["route_id"], "")).strip())
            if c:
                tr["color"] = c


FULLDAY = os.path.join(os.path.dirname(OUT), "_nosync_data", "data")


def main(key):
    cfg = tp.CITIES[key]
    # a full-day re-trim (tools/trim_fullday.py) wins over the reel's
    # morning-only trim when it exists
    full = os.path.join(FULLDAY, f"{key}_gtfs")
    src = full if os.path.exists(os.path.join(full, "stop_times.txt")) \
        else tp.ensure_feed(cfg)
    print(f"[{key}] {src}")
    g = tp.load_gtfs(src)
    date = tp.pick_service_date(g)
    sids = tp.services_on(g, date)
    tf = tp.mercator_transformer()
    x0, y0 = tf.transform(cfg["bbox_ll"][0], cfg["bbox_ll"][1])
    x1, y1 = tf.transform(cfg["bbox_ll"][2], cfg["bbox_ll"][3])
    max_leg = 5000.0 / np.cos(np.radians(cfg["center"][1]))
    tracks, shapes = tp.build_trip_tracks(
        g, sids, T0, T1, tf, route_filter=cfg["route_filter"],
        bbox=(x0, y0, x1, y1), max_leg=max_leg)
    colour_tracks(cfg, g, tracks)
    emph = cfg.get("emphasis") or set()
    rnames = g["routes"].set_index("route_id")["route_short_name"].to_dict()
    print(f"  {len(tracks):,} runs, {len(shapes):,} shapes")

    ox, oy = round(x0), round(y0)        # integer metre grid origin

    shape_idx, shape_out, shape_mode = {}, [], {}
    colours, colour_idx = [], {}
    patterns, pattern_idx = [], {}
    profiles, profile_idx = [], {}
    trips = []
    for tr in tracks:
        sid = tr["shape_id"]
        if sid not in shape_idx:
            sh = shapes[sid]
            xs = np.round(sh["x"] - ox).astype(int)
            ys = np.round(sh["y"] - oy).astype(int)
            flat = np.empty(2 * len(xs), dtype=int)
            flat[0::2] = np.diff(xs, prepend=0)
            flat[1::2] = np.diff(ys, prepend=0)
            shape_idx[sid] = len(shape_out)
            shape_out.append(flat.tolist())
        s = shape_idx[sid]
        if tr["color"] not in colour_idx:
            colour_idx[tr["color"]] = len(colours)
            colours.append(tr["color"])
        c = colour_idx[tr["color"]]
        e = 1 if tr["route_type"] in emph else 0
        shape_mode.setdefault(s, (c, e))
        if e:
            shape_mode[s] = (c, e)     # an emphasised line wins the shape
        # distances in whole metres along the geometric cumulative length
        ds = tuple(np.round(tr["ds"]).astype(int).tolist())
        pk = (s, c, e, ds)
        if pk not in pattern_idx:
            pattern_idx[pk] = len(patterns)
            patterns.append([s, c, e, list(ds)])
        ts = np.round(tr["ts"]).astype(int)
        start = int(ts[0])
        rel = tuple((ts - start).tolist())
        if rel not in profile_idx:
            profile_idx[rel] = len(profiles)
            profiles.append(list(rel))
        trips.append((start, pattern_idx[pk], profile_idx[rel],
                      str(rnames.get(tr["route_id"], ""))))

    trips.sort()
    # route names, deduped, for the hover/legend later
    names, name_idx = [], {}
    flat_trips = []
    for start, p, q, n in trips:
        if n not in name_idx:
            name_idx[n] = len(names)
            names.append(n)
        flat_trips += [start, p, q, name_idx[n]]

    # legend: each colour named by the mode most of its runs belong to,
    # grouped so Budapest's four metro hexes read as one "metro" row
    from collections import Counter
    by_col = {}
    for tr in tracks:
        by_col.setdefault(tr["color"], Counter())[
            tp.TYPE_NAMES.get(tr["route_type"], "other")] += 1
    groups = {}
    for col, cnt in by_col.items():
        name, n = cnt.most_common(1)[0]
        g = groups.setdefault(name, [0, []])
        g[0] += n
        g[1].append(col)
    legend = [[name, cols] for name, (n, cols) in
              sorted(groups.items(), key=lambda kv: -kv[1][0])]
    out = {
        "city": cfg["name"], "date": date, "t0": T0, "t1": T1,
        "origin": [ox, oy], "bbox": [x0, y0, x1, y1],
        "center": cfg["center"],
        "colours": colours,
        "shapes": shape_out,
        "shape_style": [list(shape_mode.get(i, (0, 0)))
                        for i in range(len(shape_out))],
        "patterns": patterns, "profiles": profiles,
        "trips": flat_trips, "names": names,
        "network_alpha": cfg.get("network_alpha", 0.55),
        "legend": legend,
    }
    path = os.path.join(OUT, f"{key}.json")
    with open(path, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    mb = os.path.getsize(path) / 1e6
    print(f"  wrote {path}: {mb:.1f} MB  ({len(patterns):,} patterns, "
          f"{len(profiles):,} profiles, {len(trips):,} trips)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "budapest")
