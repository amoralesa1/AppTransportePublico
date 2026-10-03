#!/usr/bin/env python3
"""
Genera el JSON de una red de Renfe (Cercanias, Trambahia...) a partir del GTFS de Cercanias de Renfe.

Descarga oficial (un solo zip para toda Espana):
    https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip

Uso:
    python3 scripts/build_renfe.py ZIP_O_CARPETA NUCLEO FILTRO SALIDA

    NUCLEO  prefijo del route_id del nucleo (31T = Cadiz)
    FILTRO  el route_short_name debe empezar por esto (C = Cercanias, T = tranvia)

Ejemplos:
    python3 scripts/build_renfe.py fomento_transit.zip 31T C data/cercanias-cadiz.json
    python3 scripts/build_renfe.py fomento_transit.zip 31T T data/trambahia.json

Notas sobre el formato de Renfe: no trae direction_id; normalmente cada sentido tiene un shape_id
distinto, pero algunos servicios reutilizan el mismo shape_id. Se agrupan por línea, trazado y
route_id para conservar esos sentidos y variantes. El trazado no siempre está dibujado en el mismo
sentido que el tren que lo usa, así que se prueban ambas orientaciones. Si alguna parada queda a más
de 300 m del trazado, el sentido se guarda con distancias entre paradas y la app lo marca como
aproximado. Los ficheros vienen con espacios de relleno; la librería los recorta.
"""
import json, os, re, sys
from collections import defaultdict

from gtfs_lib import Fuente, hav, paradas_con_offset

if len(sys.argv) < 5:
    sys.exit(__doc__)
GTFS, NUCLEO, FILTRO, OUT = sys.argv[1:5]
fuente = Fuente(GTFS)

print("Leyendo routes/trips...")
routes = {r["route_id"]: r for r in fuente.filas("routes.txt")
          if r["route_id"].startswith(NUCLEO) and r["route_short_name"].upper().startswith(FILTRO.upper())}
trips = {t["trip_id"]: t for t in fuente.filas("trips.txt") if t["route_id"] in routes}
print(f"  {len(routes)} rutas, {len(trips)} viajes")
if not trips:
    sys.exit("No hay viajes para ese nucleo/filtro. Revisa los argumentos.")

print("Leyendo stop_times (puede tardar un minuto)...")
seqs = defaultdict(list)
for tid, n, sid in fuente.stop_times_de(set(trips)):
    seqs[tid].append((n, sid))
seqs = {tid: [s for _, s in sorted(l)] for tid, l in seqs.items()}

# Patron representativo de cada (linea, trazado): el viaje con mas paradas.
grupos = defaultdict(list)
for tid, t in trips.items():
    if tid in seqs and t["shape_id"]:
        grupos[(routes[t["route_id"]]["route_short_name"], t["shape_id"], t["route_id"])].append(tid)
mejor = {}
for k, lista in grupos.items():
    mejor[k] = max(lista, key=lambda tid: len(seqs[tid]))
    # aviso si algun viaje del grupo para en una parada que el patron elegido no tiene
    extra = {s for tid in lista for s in seqs[tid]} - set(seqs[mejor[k]])
    if extra:
        print(f"  Aviso: {k} tiene paradas fuera del patron principal: {sorted(extra)}")

stops_all = {s["stop_id"]: s for s in fuente.filas("stops.txt")}
shapes_necesarios = {k[1] for k in mejor}
pts_shape = defaultdict(list)
for sp in fuente.filas("shapes.txt"):
    if sp["shape_id"] in shapes_necesarios:
        pts_shape[sp["shape_id"]].append((int(sp["shape_pt_sequence"]), float(sp["shape_pt_lat"]), float(sp["shape_pt_lon"])))

print("Calculando distancias...")
salida_rutas, usadas = {}, set()
for linea in sorted({k[0] for k in mejor}):
    grupos_linea = sorted(k for k in mejor if k[0] == linea)  # también separa sentidos con shape_id compartido
    # nombre: el de la primera ruta de la linea que tenga viajes
    rid = min(t["route_id"] for t in trips.values() if routes[t["route_id"]]["route_short_name"] == linea)
    r = routes[rid]
    nombre = re.sub(r"\s+-\s*", " – ", re.sub(r"\s+", " ", r["route_long_name"]))
    entry = {"code": linea, "name": nombre, "color": r["route_color"] or "555555",
             "textColor": r.get("route_text_color") or "FFFFFF", "dirs": {}}
    secuencias_vistas = set()
    for i, clave in enumerate(grupos_linea):
        sid = clave[1]
        tid = mejor[clave]
        seq = [s for s in seqs[tid] if s in stops_all]
        if len(seq) < 2:
            print(f"  Aviso: se omite {linea} {sid}; el viaje solo tiene una parada")
            continue
        patron = tuple(seq)
        if patron in secuencias_vistas:
            continue
        secuencias_vistas.add(patron)
        pts = [(la, lo) for _, la, lo in sorted(pts_shape[sid])]
        lista, peor = paradas_con_offset(seq, stops_all, pts)
        inv, peor_inv = paradas_con_offset(seq, stops_all, pts[::-1])
        nota = ""
        if peor_inv < peor:          # el trazado esta dibujado al reves respecto a las paradas
            lista, peor, nota = inv, peor_inv, " [trazado invertido]"
        aproximado = peor is not None and peor > 300
        if aproximado:
            lista, _ = paradas_con_offset(seq, stops_all, [])
            nota += " [distancia aproximada]"
        sentido = {"headsign": "", "stops": lista}
        if aproximado:
            sentido["aprox"] = True
        entry["dirs"][str(i)] = sentido
        usadas.update(seq)
        a, b = stops_all[seq[0]], stops_all[seq[-1]]
        recta = hav(float(a["stop_lat"]), float(a["stop_lon"]), float(b["stop_lat"]), float(b["stop_lon"]))
        km = (lista[-1][1] - lista[0][1]) / 1000
        print(f"  {linea:4} sentido {i}: {len(seq):2} paradas | {a['stop_name']} -> {b['stop_name']} | "
              f"{km:5.1f} km (recta {recta/1000:4.1f}) | parada mas lejos del trazado: {('%.0f m' % peor) if peor is not None else 'sin trazado'}{nota}")
        if peor is not None and peor > 300:
            print("    !! Ajuste geométrico ambiguo; este sentido se guarda con distancias aproximadas entre paradas.")
    salida_rutas[linea] = entry

out = {
    "fuente": f"renfe:{NUCLEO}:{FILTRO}",
    "stops": {s: [stops_all[s]["stop_name"], round(float(stops_all[s]["stop_lat"]), 5), round(float(stops_all[s]["stop_lon"]), 5)]
              for s in sorted(usadas)},
    "routes": salida_rutas,
}
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"OK -> {OUT} ({os.path.getsize(OUT)/1024:.0f} KB) | {len(salida_rutas)} lineas, {len(usadas)} paradas")

