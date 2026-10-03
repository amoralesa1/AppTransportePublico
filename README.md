# Mis trayectos

PWA para registrar trayectos en transporte público (fecha, operador, línea, sentido,
paradas, km reales, tiempo de espera y de trayecto). Funciona offline y guarda los
datos solo en tu iPhone (localStorage).

## Publicar en GitHub Pages

1. Crea un repositorio nuevo en GitHub (por ejemplo `mis-trayectos`), público.
2. Sube todo el contenido de esta carpeta a la raíz del repositorio.
3. En el repositorio: **Settings → Pages → Build and deployment**
   - Source: *Deploy from a branch*
   - Branch: `main`, carpeta `/ (root)` → Save
4. Espera 1-2 minutos. La app quedará en `https://TU_USUARIO.github.io/mis-trayectos/`

## Instalar en el iPhone

1. Abre esa URL **con Safari** (no funciona desde otros navegadores en iOS).
2. Botón Compartir → **Añadir a pantalla de inicio**.

## Guardar los trayectos en Google Sheets

Cada trayecto se guarda primero en el iPhone y después se envía a tu hoja. Si no hay
conexión queda como «pendiente» y se reenvía solo al abrir la app o al volver la red.
Cada trayecto lleva un ID único, así que un reintento nunca duplica filas.
Los trayectos guardados antes de activar esto no se suben.

**1. Crear la hoja y el script**
1. Crea una hoja de cálculo nueva en Google Sheets (el nombre da igual).
2. Menú **Extensiones → Apps Script**. Borra lo que haya y pega el contenido de
   `google-apps-script/Code.gs`.
3. Cambia `CAMBIA-ESTE-TEXTO` por un token tuyo (largo y aleatorio). Guarda.
4. Engranaje **Configuración del proyecto** → zona horaria `Europe/Madrid`.

**2. Publicarlo**
1. **Implementar → Nueva implementación** → tipo **Aplicación web**.
2. *Ejecutar como*: **Yo**. *Quién tiene acceso*: **Cualquier persona**. → Implementar.
3. Autoriza los permisos. Si sale «Google no ha verificado esta aplicación»:
   *Configuración avanzada → Ir a (nombre del proyecto)*. Es tu propio script.
4. Copia la **URL de la aplicación web** (termina en `/exec`).

**3. Conectar la app**
1. Abre la app **desde el icono de la pantalla de inicio** (no desde Safari: en iOS la app
   instalada tiene su propio almacenamiento, aparte del de Safari).
2. Sección **Google Sheets → Configuración**: pega la URL y el token → **Probar conexión**.

La URL y el token se guardan solo en tu iPhone. No los subas a GitHub.

Si cambias `Code.gs` más adelante: **Implementar → Gestionar implementaciones → editar →
Versión nueva**. Si no, Google sigue sirviendo la versión anterior.

**Columnas de la hoja:** `id, fecha, anio, mes, dia_semana, tipo, ciudad, linea, linea_nombre,
origen, destino, km, espera_min, trayecto_min, registrado_en`. Las columnas `anio`, `mes`
y `dia_semana` están para facilitar las tablas dinámicas del análisis anual.

**Borrar en la app no borra en la hoja.** La hoja es el registro histórico; si quieres quitar
una fila, hazlo en la propia hoja.

## De dónde salen los datos de cada operador

| Opción en la app | Fichero | Fuente | Estado |
|---|---|---|---|
| Autobús → Consorcio Bahía de Cádiz | `data/bahia-cadiz.json` | GTFS del Consorcio de Transportes de Andalucía | ✅ |
| Tranvía → Trambahía (T1) | `data/trambahia.json` | GTFS de Cercanías de Renfe (núcleo 31, líneas T) | ✅ |
| Tren → Cercanías de Cádiz (C1, C1a) | `data/cercanias-cadiz.json` | GTFS de Cercanías de Renfe (núcleo 31, líneas C) | ✅ |
| Tren → Cercanías de Madrid | `data/cercanias-madrid.json` | GTFS de Cercanías de Renfe (núcleo 10T) | ✅ C1–C5, C7–C10; variantes C4a/b y C8a/b |
| Autobús → Autobús de Cádiz (urbano) | `data/urbano-cadiz.json` | Coordenadas tomadas a mano (`manual/urbano-cadiz.txt`); no hay GTFS público | ✅ línea 1 · km aprox.; líneas 2, 3, 5 y 7 pendientes |
| Metro → Metro de Madrid | `data/madrid-metro.json` | GTFS del CRTM; la línea 3 se conserva del conjunto manual anterior porque el feed no contiene viajes para ella | ✅ líneas 1–12 y R |
| Metro → TMB Barcelona | `data/tmb-barcelona-metro.json` | GTFS de TMB, tipos de ruta 1 (metro) y 7 (funicular) | ✅ 10 líneas de metro y funicular FM |
| Autobús → TMB Barcelona | `data/tmb-barcelona-bus.json` | GTFS de TMB, tipo de ruta 3 | ✅ 104 líneas |
| Resto de operadores | — | Sin datos todavía | km manuales |

Los km se calculan siguiendo el trazado real de la línea cuando el GTFS permite ajustarlo. Los datos manuales o los sentidos con un trazado ambiguo se marcan como aproximados.

### Regenerar Consorcio Bahía de Cádiz

```bash
# GTFS unificado: https://api.ctan.es/v1/datos/UNIFICADO/gtfs.zip  (carpeta o .zip)
python3 scripts/build_gtfs.py RUTA_GTFS 2_ data/bahia-cadiz.json
# Prefijos: 1_ Sevilla, 2_ Bahía de Cádiz, 3_ Granada, 4_ Málaga, 5_ Campo de Gibraltar,
#           6_ Almería, 7_ Jaén, 8_ Córdoba, 9_ Huelva
```

### Regenerar Trambahía y Cercanías de Cádiz

```bash
# Descarga el zip oficial de Renfe (toda España, ~2 MB):
#   https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip
# No hace falta descomprimirlo (de hecho, algunos descompresores fallan con él):
python3 scripts/build_renfe.py fomento_transit.zip 31T C data/cercanias-cadiz.json
python3 scripts/build_renfe.py fomento_transit.zip 31T T data/trambahia.json
python3 scripts/build_renfe.py fomento_transit.zip 10T C data/cercanias-madrid.json
```

`31T` es el núcleo de Cádiz y la última letra filtra por tipo (`C` cercanías, `T` tranvía).
Otros núcleos de Renfe se generan igual cambiando el prefijo (por ejemplo `10T` Madrid).
El script puede tardar alrededor de un minuto porque el zip contiene un `stop_times.txt` muy
voluminoso. Si una parada queda a más de 300 m del trazado, usa distancias entre paradas y marca
ese sentido como aproximado en la app.

> Nota: el feed de Renfe dibuja algunos trazados en sentido contrario al del tren que los
> usa. El script lo detecta solo (prueba ambas orientaciones y se queda con la que encaja).

### Regenerar Metro de Madrid

```bash
# Carpeta descomprimida con routes, trips, stop_times, stops y shapes:
python3 scripts/build_metro_gtfs.py RUTA_GTFS data/madrid-metro.json
```

El script ajusta las paradas a los trazados del GTFS y calcula los km siguiendo la línea. Conserva
las rutas que ya existan en el JSON cuando el feed no trae viajes para ellas; en el feed recibido,
la línea 3 no tiene viajes y se mantiene desde los datos manuales anteriores.

### Regenerar Metro y autobús de Barcelona (TMB)

```bash
# Carpeta descomprimida con los ficheros GTFS de TMB:
python3 scripts/build_barcelona_gtfs.py RUTA_GTFS 1,7 data/tmb-barcelona-metro.json
python3 scripts/build_barcelona_gtfs.py RUTA_GTFS 3 data/tmb-barcelona-bus.json
```

El tipo 1 incluye el metro y el tipo 7 el funicular FM; el tipo 3 corresponde a autobuses.
El generador sigue los trazados de `shapes.txt` y guarda cada variante de sentido con sus paradas.

### Operadores sin GTFS: paradas a mano (autobús urbano de Cádiz)

`manual/urbano-cadiz.txt` lista las paradas con sus coordenadas y el orden de cada sentido
(el formato está explicado en la cabecera del fichero). Para añadir o modificar una línea:
edita sus paradas y sus filas `sentido`, y ejecuta:

```bash
python3 scripts/build_manual.py manual/urbano-cadiz.txt data/urbano-cadiz.json
```

Los km se calculan encadenando la distancia en línea recta entre paradas consecutivas: en una
avenida recta queda ~1 % por debajo del trazado real, y en tramos con curvas, hasta ~6-10 %. La
app los marca como «≈» y el CSV lleva la columna `km_aprox`. (En Google Sheets no hay columna
de aproximado: se distinguen por la columna `ciudad`.)
El script avisa con «!!» si dos paradas consecutivas quedan a menos de 40 m o a más de 3 km,
que casi siempre es una errata en una coordenada.

Dos filas opcionales para casos puntuales:
- `tramo | id_origen | id_destino | metros` — fija a mano la distancia real entre dos paradas
  consecutivas concretas, para cuando el autobús rodea una manzana o un polideportivo y la
  línea recta se queda muy corta (ejemplo: tramo Cortadura–Complejo Deportivo en Cádiz).
- `cabecera | linea | sentido | Texto` — fija el texto que ve el usuario en el desplegable de
  sentido, para cuando la cabecera real de la línea no coincide con el nombre de la primera o
  última parada de ese sentido (ejemplo: la línea 1 de Cádiz se llama «Cortadura», aunque esa
  parada no sea ni la primera del sentido de ida ni la última del de vuelta).

## Añadir otro operador

1. Genera su JSON con el script que corresponda y guárdalo en `data/`.
2. En `app.js`, dentro de `CIUDADES`, añade `data: "data/su-archivo.json"` a la entrada.
3. Añade el archivo a `ARCHIVOS` en `sw.js` y sube `VERSION`.

## Actualizar la app tras cambios

Cada vez que cambies cualquier archivo, sube `VERSION` en `sw.js`; si no, el iPhone
seguirá mostrando la versión cacheada.
