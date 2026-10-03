#!/usr/bin/env python3
"""Genera el JSON de Metro de Madrid desde la carpeta GTFS descomprimida.

Uso: python3 scripts/build_metro_gtfs.py RUTA_GTFS data/madrid-metro.json
"""
import json
import os
import re
import sys
from collections import defaultdict

from gtfs_lib import Fuente, hav, paradas_con_offset

if len(sys.argv) < 3:
    sys.exit(__doc__)

GTFS, OUT = sys.argv[1:3]
BASE = sys.argv[3] if len(sys.argv) > 3 else OUT
fuente = Fuente(GTFS)

routes = {r["route_id"]: r for r in fuente.filas("routes.txt")}
trips = {t["trip_id"]: t for t in fuente.filas("trips.txt") if t["route_id"] in routes}
print(f"{len(routes)} rutas, {len(trips)} viajes")

seqs = defaultdict(list)
for tid, n, sid in fuente.stop_times_de(set(trips)):
    seqs[tid].append((n, sid))
seqs = {tid: [sid for _, sid in sorted(rows)] for tid, rows in seqs.items()}

# Elegir el viaje con más paradas para cada (línea, trazado).
groups = defaultdict(list)
for tid, trip in trips.items():
    if tid in seqs and trip["shape_id"]:
        line = routes[trip["route_id"]]["route_short_name"]
        groups[(line, trip["shape_id"])].append(tid)
best = {key: max(ids, key=lambda tid: len(seqs[tid])) for key, ids in groups.items()}


def rotate_loop(points, lat, lon):
    """Rotate a closed shape so ordered matching starts beside its first stop."""
    start = min(range(len(points)), key=lambda i: hav(lat, lon, *points[i]))
    return points[start:] + points[1:start + 1]

stops_all = {s["stop_id"]: s for s in fuente.filas("stops.txt")}
needed_shapes = {shape_id for _, shape_id in best}
shape_points = defaultdict(list)
for p in fuente.filas("shapes.txt"):
    if p["shape_id"] in needed_shapes:
        shape_points[p["shape_id"]].append((int(p["shape_pt_sequence"]), float(p["shape_pt_lat"]), float(p["shape_pt_lon"])))

out_routes, used_stops = {}, set()
for line in sorted({line for line, _ in best}, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x)):
    shapes = sorted(shape_id for route_line, shape_id in best if route_line == line)
    route_id = min(t["route_id"] for t in trips.values() if routes[t["route_id"]]["route_short_name"] == line)
    route = routes[route_id]
    name = re.sub(r"\s*-\s*", " – ", re.sub(r"\s+", " ", route["route_long_name"]))
    entry = {"code": line, "name": name, "color": route["route_color"] or "555555",
             "textColor": route["route_text_color"] or "FFFFFF", "dirs": {}}

    for direction, shape_id in enumerate(shapes):
        trip_id = best[(line, shape_id)]
        sequence = [sid for sid in seqs[trip_id] if sid in stops_all]
        points = [(lat, lon) for _, lat, lon in sorted(shape_points[shape_id])]
        if len(sequence) < 2:
            print(f"Aviso: se omite {line}/{shape_id}, tiene menos de dos paradas")
            continue
        first = stops_all[sequence[0]]
        if len(points) > 2 and hav(*points[0], *points[-1]) < 30:
            points = rotate_loop(points, float(first["stop_lat"]), float(first["stop_lon"]))
        candidates = [paradas_con_offset(sequence, stops_all, points), paradas_con_offset(sequence, stops_all, points[::-1])]
        result, worst = min(candidates, key=lambda candidate: candidate[1])
        approximate = worst > 300
        if approximate:
            # Circular lines can overlap themselves; use ordered station geometry if the
            # shape cannot be matched monotonically with confidence.
            result, _ = paradas_con_offset(sequence, stops_all, [])

        direction_data = {"headsign": "", "stops": result}
        if approximate:
            direction_data["aprox"] = True
        entry["dirs"][str(direction)] = direction_data
        if sequence[0] == sequence[-1]:
            entry["circular"] = True
        used_stops.update(sequence)
        origin, destination = stops_all[sequence[0]], stops_all[sequence[-1]]
        print(f"{line:>2} sentido {direction}: {len(sequence)} paradas | {origin['stop_name']} → {destination['stop_name']} | "
              f"{(result[-1][1] - result[0][1]) / 1000:.1f} km | separación máx. {worst:.0f} m")
        if worst > 300:
            print("  !! Revisa: hay una parada a más de 300 m del trazado")

    # Una circular puede cruzarse consigo misma y hacer fallar el ajuste de un sentido.
    # Si el sentido opuesto sí encaja, invertir sus distancias conserva el trazado completo.
    if entry.get("circular"):
        good = next((d for d in entry["dirs"].values() if not d.get("aprox")), None)
        if good:
            good_stops = good["stops"]
            total = good_stops[-1][1]
            for direction_data in entry["dirs"].values():
                if not direction_data.get("aprox") or len(direction_data["stops"]) != len(good_stops):
                    continue
                if [sid for sid, _ in direction_data["stops"]] == [sid for sid, _ in reversed(good_stops)]:
                    direction_data["stops"] = [
                        [sid, total - good_stops[-1 - i][1]]
                        for i, (sid, _) in enumerate(direction_data["stops"])
                    ]
                    direction_data.pop("aprox", None)

    if entry["dirs"]:
        out_routes[line] = entry

out = {
    "fuente": "crtm-gtfs",
    "stops": {
        sid: [stops_all[sid]["stop_name"], round(float(stops_all[sid]["stop_lat"]), 5), round(float(stops_all[sid]["stop_lon"]), 5)]
        for sid in sorted(used_stops)
    },
    "routes": out_routes,
}
if os.path.isfile(BASE):
    with open(BASE, encoding="utf-8") as f:
        previous = json.load(f)
    for line, route in previous.get("routes", {}).items():
        if line not in out["routes"]:
            if previous.get("aprox"):
                for direction in route.get("dirs", {}).values():
                    direction["aprox"] = True
            if any(direction.get("stops") and direction["stops"][0][0] == direction["stops"][-1][0]
                   for direction in route.get("dirs", {}).values()):
                route["circular"] = True
            out["routes"][line] = route
            for direction in route.get("dirs", {}).values():
                used_stops.update(stop_id for stop_id, _ in direction.get("stops", []))
    for stop_id in used_stops:
        if stop_id not in out["stops"] and stop_id in previous.get("stops", {}):
            out["stops"][stop_id] = previous["stops"][stop_id]
    out["routes"] = dict(sorted(out["routes"].items(), key=lambda item: (not item[0].isdigit(), int(item[0]) if item[0].isdigit() else item[0])))
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"OK → {OUT} ({os.path.getsize(OUT) / 1024:.1f} KB) | {len(out_routes)} líneas, {len(used_stops)} paradas")

