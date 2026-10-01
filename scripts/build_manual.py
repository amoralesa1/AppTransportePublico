#!/usr/bin/env python3
"""
Genera el JSON de un operador SIN GTFS a partir de un fichero de texto con paradas y coordenadas
tomadas a mano (ver manual/urbano-cadiz.txt para el formato).

Uso:
    python3 scripts/build_manual.py manual/urbano-cadiz.txt data/urbano-cadiz.json

Los km se calculan encadenando la distancia en linea recta entre paradas consecutivas de cada
sentido. En avenidas rectas queda ~1 % por debajo del trazado real; en tramos con curvas hasta
~6-10 %. Por eso el JSON lleva "aprox": true y la app marca esos km como aproximados.

Para un sentido cuyo nombre visible en la app no deba coincidir con su primera/última parada real
(p. ej. la cabecera de la línea se llama distinto a la primera parada), se puede fijar a mano con
una fila "cabecera":
    cabecera | codigo_linea | numero_sentido | Texto a mostrar
Si no se indica, la app sigue mostrando "primera parada → última parada" como hasta ahora.

Para un tramo concreto donde la linea recta se aleje mucho de la realidad (curvas, rodeos), se
puede fijar su distancia a mano con una fila "tramo":
    tramo | id_parada_origen | id_parada_destino | metros
Esa distancia sustituye al calculo por coordenadas solo para ese par de paradas consecutivas,
en cualquier sentido en que aparezcan juntas.
"""
import json, os, re, sys
from gtfs_lib import hav

if len(sys.argv) < 3:
    sys.exit(__doc__)
ENTRADA, SALIDA = sys.argv[1:3]
SALTO_MAX_M, SALTO_MIN_M = 3000, 40


def coord(s):
    s = s.strip()
    m = re.fullmatch(r"(\d+)°(\d+)'([\d.]+)\"?\s*([NSEWO])", s)
    if m:
        v = int(m[1]) + int(m[2]) / 60 + float(m[3]) / 3600
        return -v if m[4] in "SWO" else v
    return float(s.replace(",", "."))


stops, lineas, sentidos, tramos_fijos, cabeceras, fuente = {}, {}, {}, {}, {}, ""
for n, raw in enumerate(open(ENTRADA, encoding="utf-8"), 1):
    linea = raw.split("#", 1)[0].strip()
    if not linea:
        continue
    c = [x.strip() for x in linea.split("|")]
    try:
        if c[0] == "fuente":
            fuente = c[1]
        elif c[0] == "parada":
            stops[c[1]] = (c[2], coord(c[3]), coord(c[4]))
        elif c[0] == "linea":
            lineas[c[1]] = {"code": c[1], "name": c[2], "color": c[3] if len(c) > 3 else "555555", "dirs": {}}
        elif c[0] == "sentido":
            sentidos[(c[1], c[2])] = c[3].split()
        elif c[0] == "tramo":
            tramos_fijos[frozenset((c[1], c[2]))] = float(c[3])
        elif c[0] == "cabecera":
            cabeceras[(c[1], c[2])] = c[3]
        else:
            raise ValueError("tipo de fila desconocido: " + c[0])
    except (IndexError, ValueError) as e:
        sys.exit(f"Linea {n}: no se pudo leer ({e}): {raw.strip()}")

usadas, avisos = set(), 0
for (cod, num), ids in sorted(sentidos.items()):
    if cod not in lineas:
        sys.exit(f"Sentido de una linea no declarada: {cod}")
    falta = [i for i in ids if i not in stops]
    if falta:
        sys.exit(f"Linea {cod} sentido {num}: paradas no definidas: {falta}")
    if len(set(ids)) != len(ids):
        print(f"  Aviso: la linea {cod} sentido {num} repite alguna parada")
    acc, prev, lista = 0.0, None, []
    for i in ids:
        _, la, lo = stops[i]
        if prev is not None:
            fijo = tramos_fijos.get(frozenset((prev[2], i)))
            salto = fijo if fijo is not None else hav(prev[0], prev[1], la, lo)
            if fijo is None and (salto > SALTO_MAX_M or salto < SALTO_MIN_M):
                avisos += 1
                print(f"  !! Linea {cod} sentido {num}: salto de {salto:.0f} m entre '{stops[prev[2]][0]}' y '{stops[i][0]}': revisa las coordenadas")
            acc += salto
        prev = (la, lo, i)
        lista.append([i, round(acc)])
        usadas.add(i)
    lineas[cod]["dirs"][num] = {"headsign": cabeceras.get((cod, num), ""), "stops": lista}
    print(f"Linea {cod} sentido {num}: {len(ids):2} paradas | {stops[ids[0]][0]} -> {stops[ids[-1]][0]} | {acc/1000:.2f} km")

out = {
    "fuente": fuente,
    "aprox": True,
    "stops": {i: [stops[i][0], round(stops[i][1], 5), round(stops[i][2], 5)] for i in sorted(usadas)},
    "routes": dict(sorted(lineas.items(), key=lambda kv: kv[0].zfill(4))),
}
os.makedirs(os.path.dirname(SALIDA) or ".", exist_ok=True)
with open(SALIDA, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"OK -> {SALIDA} ({os.path.getsize(SALIDA)/1024:.1f} KB) | {len(out['routes'])} lineas, {len(usadas)} paradas" + (f" | {avisos} avisos" if avisos else ""))
