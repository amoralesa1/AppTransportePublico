#!/usr/bin/env python3
"""Build app JSON (routes, directions, stops and distances) from a GTFS folder or zip.

Usage: python build_gtfs_routes.py GTFS_DIR ROUTE_TYPE OUTPUT
Examples:
  python build_gtfs_routes.py gtfs-autobus-sevilla 3 data/tussam-sevilla.json
  python build_gtfs_routes.py gtfs-autobus-sevilla 0 data/metrocentro-sevilla.json
  python build_gtfs_routes.py gtfs-metroligero 0 data/metro-ligero-madrid.json
"""
import json
import os
import re
import sys
from collections import defaultdict
from gtfs_lib import Fuente, paradas_con_offset

if len(sys.argv) != 4:
    sys.exit(__doc__)
GTFS, ROUTE_TYPE, OUT = sys.argv[1:4]
source = Fuente(GTFS)
routes = {r["route_id"]: r for r in source.filas("routes.txt") if r.get("route_type") == ROUTE_TYPE}
trips = {t["trip_id"]: t for t in source.filas("trips.txt") if t["route_id"] in routes}
print(f"Routes: {len(routes)}; trips: {len(trips)}; route_type: {ROUTE_TYPE}")
if not routes or not trips:
    sys.exit("No routes or trips matched this route type.")

sequences = defaultdict(list)
for trip_id, number, stop_id in source.stop_times_de(set(trips)):
    sequences[trip_id].append((number, stop_id))
sequences = {tid: [sid for _, sid in sorted(rows)] for tid, rows in sequences.items()}
# Keep the fullest trip for each route/direction/shape so that shape variants survive.
groups = defaultdict(list)
for tid, trip in trips.items():
    if tid in sequences:
        groups[(trip["route_id"], trip.get("direction_id") or "0", trip.get("shape_id") or "")].append(tid)
best = {key: max(ids, key=lambda tid: len(sequences[tid])) for key, ids in groups.items()}
print(f"Patterns: {len(best)}")

stops_all = {s["stop_id"]: s for s in source.filas("stops.txt")}
if source.zip:
    has_shapes = "shapes.txt" in source.zip.namelist()
else:
    has_shapes = os.path.isfile(os.path.join(GTFS, "shapes.txt"))
needed_shapes = {key[2] for key in best if key[2]}
shape_points = defaultdict(list)
if has_shapes:
    for row in source.filas("shapes.txt"):
        if row["shape_id"] in needed_shapes:
            shape_points[row["shape_id"]].append((int(row["shape_pt_sequence"]), float(row["shape_pt_lat"]), float(row["shape_pt_lon"])))
    for points in shape_points.values():
        points.sort()

by_route = defaultdict(list)
for (route_id, direction, shape_id), tid in sorted(best.items()):
    by_route[route_id].append((direction, shape_id, tid))
out_routes, used_stops = {}, set()
approx_count = 0
for route_id, patterns in by_route.items():
    route = routes[route_id]
    code = route.get("route_short_name", "").strip() or route_id
    name = re.sub(r"\s+", " ", route.get("route_long_name", "")).strip()
    entry = {"code": code, "name": re.sub(r"\s*-\s*", " – ", name),
             "color": route.get("route_color") or "555555",
             "textColor": route.get("route_text_color") or "FFFFFF", "dirs": {}}
    selected = {}
    for direction, shape_id, tid in patterns:
        sequence = [sid for sid in sequences[tid] if sid in stops_all]
        if len(sequence) < 2:
            continue
        points = [(lat, lon) for _, lat, lon in shape_points.get(shape_id, [])]
        if len(points) >= 2:
            options = [paradas_con_offset(sequence, stops_all, points),
                       paradas_con_offset(sequence, stops_all, points[::-1])]
            result, worst = min(options, key=lambda item: item[1])
            approximate = worst > 300
        else:
            result, worst = paradas_con_offset(sequence, stops_all, [])
            approximate = True
        if approximate:
            result, _ = paradas_con_offset(sequence, stops_all, [])
        signature = (direction, tuple(sequence))
        previous = selected.get(signature)
        if previous and previous[0] <= worst:
            continue
        data = {"headsign": trips[tid].get("trip_headsign", ""), "stops": result}
        if approximate:
            data["aprox"] = True
        selected[signature] = (worst, shape_id, data)
        used_stops.update(sequence)
        if sequence[0] == sequence[-1]:
            entry["circular"] = True
    # Use distinct IDs for branches that share the same direction_id.
    counts = defaultdict(int)
    for (direction, _), (_, _, data) in sorted(selected.items(), key=lambda item: (item[0][0], item[1][1])):
        key = direction if counts[direction] == 0 else f"{direction}-{counts[direction]}"
        entry["dirs"][key] = data
        counts[direction] += 1
        approx_count += bool(data.get("aprox"))
    if entry["dirs"]:
        out_routes[route_id] = entry

agencies = {r.get("agency_id") for r in routes.values()}
if "TUSSAM" in agencies:
    source_name = "metrocentro-sevilla" if ROUTE_TYPE == "0" else "tussam-sevilla"
elif "CRTM" in agencies and ROUTE_TYPE == "0":
    source_name = "crtm-metro-ligero"
else:
    source_name = "gtfs-route-type:" + ROUTE_TYPE
out = {
    "fuente": source_name,
    "stops": {sid: [stops_all[sid]["stop_name"], round(float(stops_all[sid]["stop_lat"]), 5), round(float(stops_all[sid]["stop_lon"]), 5)] for sid in sorted(used_stops)},
    "routes": dict(sorted(out_routes.items(), key=lambda item: (re.sub(r"\d+", lambda m: m.group().zfill(6), item[1]["code"].casefold()), item[0]))),
}
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"OK: {OUT} ({os.path.getsize(OUT)/1024:.1f} KB), {len(out_routes)} routes, {len(used_stops)} stops, {approx_count} approximate directions")


