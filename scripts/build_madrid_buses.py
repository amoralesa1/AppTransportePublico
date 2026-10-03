#!/usr/bin/env python3
"""Build compact bus route/stops JSON from CRTM or EMT GTFS folders.

Usage: python build_madrid_buses.py GTFS_DIR OUTPUT [ROUTE_ID_PREFIX]
Examples:
  python build_madrid_buses.py gtfs_interurbanomadrid data/interurbanos-madrid.json
  python build_madrid_buses.py gtfs_urbanomadrid data/urbano-madrid.json 9__
  python build_madrid_buses.py gtfs_emtmadrid data/emt-madrid.json
"""
import json
import os
import re
import sys
from collections import defaultdict
from gtfs_lib import Fuente, paradas_con_offset

if len(sys.argv) not in (3, 4):
    sys.exit(__doc__)
GTFS, OUT = sys.argv[1:3]
PREFIX = sys.argv[3] if len(sys.argv) == 4 else ""
source = Fuente(GTFS)
routes = {r["route_id"]: r for r in source.filas("routes.txt")
          if r.get("route_type") == "3" and r["route_id"].startswith(PREFIX)}
trips = {t["trip_id"]: t for t in source.filas("trips.txt") if t["route_id"] in routes}
print(f"Routes: {len(routes)}; trips: {len(trips)}; prefix: {PREFIX or '(all)'}")
if not routes or not trips:
    sys.exit("No bus routes or trips matched the selected feed/prefix.")

# Use the fullest trip for every route, direction and shape, preserving branch variants.
seqs = defaultdict(list)
for trip_id, sequence, stop_id in source.stop_times_de(set(trips)):
    seqs[trip_id].append((sequence, stop_id))
seqs = {tid: [sid for _, sid in sorted(rows)] for tid, rows in seqs.items()}
groups = defaultdict(list)
for tid, trip in trips.items():
    if tid in seqs:
        groups[(trip["route_id"], trip.get("direction_id") or "0", trip.get("shape_id") or "")].append(tid)
best = {key: max(ids, key=lambda tid: len(seqs[tid])) for key, ids in groups.items()}
print(f"Patterns: {len(best)}")

stops_all = {s["stop_id"]: s for s in source.filas("stops.txt")}
needed_shapes = {key[2] for key in best if key[2]}
shape_points = defaultdict(list)
for row in source.filas("shapes.txt"):
    if row["shape_id"] in needed_shapes:
        shape_points[row["shape_id"]].append((int(row["shape_pt_sequence"]), float(row["shape_pt_lat"]), float(row["shape_pt_lon"])))
for points in shape_points.values():
    points.sort()

routes_by_id = defaultdict(list)
for key in sorted(best):
    routes_by_id[key[0]].append(key)
out_routes, used_stops = {}, set()
approx_count = 0
for route_id, route_groups in routes_by_id.items():
    route = routes[route_id]
    code = route.get("route_short_name", "").strip() or route_id
    long_name = re.sub(r"\s+", " ", route.get("route_long_name", "")).strip()
    entry = {"code": code, "name": re.sub(r"\s*-\s*", " – ", long_name),
             "color": route.get("route_color") or "555555",
             "textColor": route.get("route_text_color") or "FFFFFF", "dirs": {}}
    seen_sequences = {}
    for _, direction, shape_id in route_groups:
        tid = best[(route_id, direction, shape_id)]
        sequence = [sid for sid in seqs[tid] if sid in stops_all]
        if len(sequence) < 2:
            continue
        points = [(lat, lon) for _, lat, lon in shape_points.get(shape_id, [])]
        candidates = [paradas_con_offset(sequence, stops_all, points),
                     paradas_con_offset(sequence, stops_all, points[::-1])]
        result, worst = min(candidates, key=lambda item: item[1])
        approx = len(points) < 2 or worst > 300
        if approx:
            result, _ = paradas_con_offset(sequence, stops_all, [])
        signature = (direction, tuple(sequence))
        candidate = {"headsign": trips[tid].get("trip_headsign", ""), "stops": result}
        if approx:
            candidate["aprox"] = True
        # Duplicate shape variants with the same stops: keep the most reliable geometry.
        previous = seen_sequences.get(signature)
        if previous is not None:
            old_data, old_worst = previous
            if approx and not old_data.get("aprox") or approx == old_data.get("aprox", False) and worst >= old_worst:
                continue
            entry["dirs"].pop(old_data["key"], None)
        key = direction
        if key in entry["dirs"]:
            key = f"{direction}-{len(entry['dirs'])}"
        candidate["_key"] = key
        entry["dirs"][key] = {k: v for k, v in candidate.items() if k != "_key"}
        seen_sequences[signature] = (dict(candidate, key=key), worst)
        if approx:
            approx_count += 1
        if sequence[0] == sequence[-1]:
            entry["circular"] = True
        used_stops.update(sequence)
    if entry["dirs"]:
        out_routes[route_id] = entry

out = {
    "fuente": "crtm-gtfs" + (":" + PREFIX if PREFIX else "") if routes and next(iter(routes.values())).get("agency_id") == "CRTM" else "emt-gtfs",
    "stops": {sid: [stops_all[sid]["stop_name"], round(float(stops_all[sid]["stop_lat"]), 5), round(float(stops_all[sid]["stop_lon"]), 5)] for sid in sorted(used_stops)},
    "routes": dict(sorted(out_routes.items(), key=lambda item: (re.sub(r"\d+", lambda m: m.group().zfill(6), item[1]["code"].casefold()), item[0]))),
}
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"OK: {OUT} ({os.path.getsize(OUT)/1024:.0f} KB), {len(out_routes)} routes, {len(used_stops)} stops, {approx_count} approximate patterns")

