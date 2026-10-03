#!/usr/bin/env python3
"""Build compact route-and-stop distance JSON files from the TMB Barcelona GTFS.

Usage: python build_barcelona_gtfs.py GTFS_DIR ROUTE_TYPES OUTPUT
Example: python build_barcelona_gtfs.py gtfs_barcelona 1,7 data/tmb-barcelona-metro.json
"""
import json
import os
import re
import sys
from collections import defaultdict
from gtfs_lib import Fuente, hav, paradas_con_offset

if len(sys.argv) != 4:
    sys.exit(__doc__)
GTFS, TYPE_LIST, OUT = sys.argv[1:4]
route_types = {value.strip() for value in TYPE_LIST.split(",")}
source = Fuente(GTFS)
routes = {r["route_id"]: r for r in source.filas("routes.txt") if r["route_type"] in route_types}
trips = {t["trip_id"]: t for t in source.filas("trips.txt") if t["route_id"] in routes}
print(f"{len(routes)} rutas, {len(trips)} viajes; route_type={','.join(sorted(route_types))}")

seqs = defaultdict(list)
for tid, seq, sid in source.stop_times_de(set(trips)):
    seqs[tid].append((seq, sid))
seqs = {tid: [sid for _, sid in sorted(rows)] for tid, rows in seqs.items()}

# Keep the fullest trip for each displayed line and shape (a shape represents one direction).
groups = defaultdict(list)
for tid, trip in trips.items():
    route = routes[trip["route_id"]]
    if tid in seqs and trip.get("shape_id"):
        groups[(route["route_short_name"], trip["shape_id"])].append(tid)
best = {key: max(ids, key=lambda tid: len(seqs[tid])) for key, ids in groups.items()}
stops_all = {s["stop_id"]: s for s in source.filas("stops.txt")}
needed_shapes = {shape for _, shape in best}
shape_points = defaultdict(list)
for point in source.filas("shapes.txt"):
    if point["shape_id"] in needed_shapes:
        shape_points[point["shape_id"]].append((int(point["shape_pt_sequence"]), float(point["shape_pt_lat"]), float(point["shape_pt_lon"])))

def line_key(code):
    return (0, int(code)) if code.isdigit() else (1, code.casefold())

out_routes, used_stops = {}, set()
for line in sorted({key[0] for key in best}, key=line_key):
    shapes = sorted(shape for route_line, shape in best if route_line == line)
    representative = min((routes[trips[best[(line, shape)]]['route_id']] for shape in shapes), key=lambda r: r['route_id'])
    long_name = re.sub(r"\s+", " ", representative.get("route_long_name", "")).strip()
    name = re.sub(r"\s*-\s*", " – ", long_name)
    entry = {"code": line, "name": name, "color": representative.get("route_color") or "555555",
             "textColor": representative.get("route_text_color") or "FFFFFF", "dirs": {}}
    for direction, shape in enumerate(shapes):
        sequence = [sid for sid in seqs[best[(line, shape)]] if sid in stops_all]
        if len(sequence) < 2:
            print(f"Aviso: se omite {line}/{shape}, menos de dos paradas")
            continue
        points = [(lat, lon) for _, lat, lon in sorted(shape_points[shape])]
        candidates = [paradas_con_offset(sequence, stops_all, points), paradas_con_offset(sequence, stops_all, points[::-1])]
        result, worst = min(candidates, key=lambda c: c[1])
        approx = worst > 300
        if approx:
            result, _ = paradas_con_offset(sequence, stops_all, [])
        direction_data = {"headsign": "", "stops": result}
        if approx:
            direction_data["aprox"] = True
        entry["dirs"][str(direction)] = direction_data
        used_stops.update(sequence)
        origin, destination = stops_all[sequence[0]], stops_all[sequence[-1]]
        print(f"{line:>8} sentido {direction}: {len(sequence):3} paradas | {origin['stop_name']} → {destination['stop_name']} | {(result[-1][1]-result[0][1])/1000:.1f} km | separación máx. {worst:.0f} m")
    if entry["dirs"]:
        out_routes[line] = entry

out = {
    "fuente": "tmb-barcelona-gtfs:" + ",".join(sorted(route_types)),
    "stops": {sid: [stops_all[sid]["stop_name"], round(float(stops_all[sid]["stop_lat"]), 5), round(float(stops_all[sid]["stop_lon"]), 5)] for sid in sorted(used_stops)},
    "routes": out_routes,
}
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"OK -> {OUT} ({os.path.getsize(OUT)/1024:.1f} KB) | {len(out_routes)} líneas, {len(used_stops)} paradas")
