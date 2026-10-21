# Dashboard Fanpage Ferre Experto Pacasmayo

Sitio estático con las métricas del fanpage: comportamiento general, publicaciones y audiencia. No usa backend, cookies, trackers ni CDN en tiempo de ejecución.

## Contenido

- `data/`: exports normalizados de Meta Business Suite y `page.json` con el corte y los seguidores.
- `assets/posts/`: capturas originales de las publicaciones (`YYYY-MM-DD.png`).
- `src/`: HTML, CSS, JavaScript y Chart.js vendorizado.
- `dist/`: sitio generado. No se versiona; lo reconstruye el build o GitHub Actions.
- `build.py`: parsea los CSV, cruza publicaciones con videos, calcula agregados y genera `dist/`.
- `serve.py`: servidor local para previsualizar `dist/`.
- `tests/`: pruebas de ingestión, totales y reglas de negocio.

## Requisitos

- Python 3.9 o superior.
- macOS: `sips` (incluido) para optimizar las capturas a JPEG.
- Linux/CI: `Pillow` para el mismo paso. Instalar con:

```bash
python3 -m pip install -r requirements.txt
```

## Generar y ver en local

```bash
python3 build.py
python3 serve.py
```

Abre `http://127.0.0.1:8000/`. También puedes hacer doble clic en `Actualizar Dashboard.command`.

## Actualizar datos

1. Exporta desde Meta Business Suite: Results, Content y Audience.
2. Reemplaza los archivos correspondientes en `data/`:
   - `results-views.csv`, `results-viewers.csv`, `results-visits.csv`, `results-follows.csv`
   - `posts.csv`, `videos.csv`
   - `audience.csv`
3. Agrega o reemplaza las capturas en `assets/posts/` usando la fecha de publicación como nombre: `YYYY-MM-DD.png`. Si falta una captura se muestra un placeholder.
4. Si cambió el número de seguidores, edita `data/page.json` (`followers`). La fecha de corte también vive ahí (`cutoff`).
5. Ejecuta `python3 build.py` y revisa el sitio en local.
6. Haz commit y push a `main`; el workflow de GitHub Actions ejecuta tests, reconstruye y publica.

## Automatización con Meta API

`fetch_meta.py` descarga un mes cerrado desde la Graph API y lo guarda en `data/archive/YYYY-MM.json`. Usa solo la biblioteca estándar.

### Credenciales

1. Crea una app en https://developers.facebook.com/apps/ y un usuario del sistema en Business Manager.
2. Asígnale la app y el fanpage con tarea **Analizar**.
3. Genera un token con `read_insights`, `pages_read_engagement` y `pages_show_list`.
4. Guarda el token como secreto `META_PAGE_TOKEN` y el ID de la página como `META_PAGE_ID` en GitHub, o expórtalos en local. No los escribas en el repositorio ni en el chat.

### Comprobar permisos

```bash
export META_PAGE_TOKEN="..."
export META_PAGE_ID="..."
python3 fetch_meta.py --probe
```

El modo `--probe` solo informa qué métricas responden `OK` o `ERROR`; no guarda datos ni imprime el token.

### Descargar un mes

```bash
python3 fetch_meta.py --month 2026-10
```

Sin `--month` descarga el mes anterior. El archivo queda en `data/archive/2026-10.json`.

También puedes ejecutar el workflow manual **Fetch Meta insights** desde GitHub Actions, con los mismos secretos. El JSON se adjunta como artefacto durante 14 días.

La integración de estos archivos con `build.py` y la publicación mensual automática se activará después de validar la primera descarga real. Hasta entonces, el dashboard sigue usando los CSV de `data/`.

## Publicar en GitHub Pages

1. Crea un repositorio **público** y sube el contenido de esta carpeta (`fanpage-dashboard/`) como raíz del repositorio.
2. En GitHub, entra a **Settings → Pages → Build and deployment** y selecciona **Source: GitHub Actions**.
3. Empuja a `main`. El workflow `.github/workflows/pages.yml` corre los tests, genera `dist/` y lo despliega.
4. La URL queda como `https://<usuario>.github.io/<repositorio>/`.

Si el workflow falla con `Resource not accessible by integration`, habilita Pages manualmente en **Settings → Pages → Build and deployment → Source: GitHub Actions** y vuelve a ejecutar el workflow.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Criterios de datos

- Solo métricas orgánicas del fanpage; anuncios y campañas quedan fuera.
- Los KPIs mensuales suman los días del export. Octubre es un mes en curso: se compara contra septiembre completo y se marca en la interfaz.
- `Engagement = interacciones / alcance`. Se muestra `—` cuando el alcance es 0 o no hay Views, para no publicar tasas engañosas.
- La audiencia es una foto fija de los seguidores al corte; no cambia con el selector de mes.
- La publicación del 01/09 se cruza con su fila de video para no duplicarla. El video del 16/09 no tiene captura ni Views en el export; se muestra con placeholder.
