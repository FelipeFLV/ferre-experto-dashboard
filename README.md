# Dashboard Fanpage Ferre Experto Pacasmayo

Sitio estático con las métricas del fanpage: comportamiento general, publicaciones y audiencia. No usa backend, cookies, trackers ni CDN en tiempo de ejecución.

## Contenido

- `data/archive/`: JSON mensual descargado de Meta Graph API. Es la fuente del dashboard.
- `data/*.csv`: exports históricos de Meta Business Suite, conservados solo como referencia.
- `assets/posts/`: capturas originales de las publicaciones (`YYYY-MM-DD.png`).
- `src/`: HTML, CSS, JavaScript y Chart.js vendorizado.
- `dist/`: sitio generado. No se versiona; lo reconstruye el build o GitHub Actions.
- `build.py`: lee `data/archive/*.json`, calcula agregados, meses dinámicos y genera `dist/`.
- `serve.py`: servidor local para previsualizar `dist/`.
- `fetch_meta.py`: descarga un mes cerrado desde la Graph API y lo guarda en `data/archive/YYYY-MM.json`.
- `meta_page_token.py`: asistente local para obtener un Page Access Token de larga duración sin Business Portfolio.
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

1. Ejecuta el workflow **Fetch Meta insights** desde GitHub Actions. Si dejas el mes vacío, descarga el mes anterior.
2. El workflow guarda `data/archive/YYYY-MM.json`, lo commitea y el push reconstruye y publica el dashboard.
3. Para backfill o correcciones, ejecuta el workflow con un mes explícito (`YYYY-MM`).
4. Las capturas viven en `assets/posts/` con el nombre `YYYY-MM-DD.png`; si falta una, se muestra un placeholder.
5. En local: `python3 build.py` y `python3 serve.py`.

## Automatización con Meta API

`fetch_meta.py` descarga un mes cerrado desde la Graph API y lo guarda en `data/archive/YYYY-MM.json`. Usa solo la biblioteca estándar.

### Credenciales

La vía recomendada para este proyecto es un **Page Access Token de larga duración**. No requiere Business Portfolio, System User ni App Review; la app puede quedar en Development mode.

Requisitos:

- Ser administrador de la página.
- Tener una app creada con el caso de uso **Manage everything on your Page** en https://developers.facebook.com/apps/. El caso de uso **Facebook Login** es incompatible con Pages; si la app se creó así, hay que crear otra.
- Tener a mano **App ID** y **App Secret** (App settings → Basic).
- Permisos: `pages_show_list`, `pages_read_engagement`, `pages_read_user_content` y `read_insights`.

1. Abre https://developers.facebook.com/tools/explorer/ y selecciona la app con el caso de uso Pages.
2. Genera un token de usuario con la cuenta que administra la página y agrega los permisos indicados.
3. Copia el token corto y ejecuta el asistente:

```bash
python3 meta_page_token.py
```

El asistente pide App ID, App Secret y el token corto. No imprime el token; crea `.env` con `META_PAGE_ID` y `META_PAGE_TOKEN`, le da permisos `600` y comprueba la expiración. `.env` está en `.gitignore`.

4. Prueba el token contra Meta:

```bash
set -a; source .env; set +a
python3 fetch_meta.py --probe --month 2026-10
```

5. Guarda los secretos en GitHub y borra `.env`:

```bash
printf '%s' "$META_PAGE_TOKEN" | gh secret set META_PAGE_TOKEN --repo FelipeFLV/ferre-experto-dashboard
printf '%s' "$META_PAGE_ID" | gh secret set META_PAGE_ID --repo FelipeFLV/ferre-experto-dashboard
rm .env
```

Si el token se invalida por un cambio de contraseña, por revocar la app o por perder el rol de administrador de la página, vuelve a ejecutar `python3 meta_page_token.py --force` y actualiza el secreto. El `META_PAGE_ID` no cambia. Los Page Access Tokens de larga duración normalmente no expiran por tiempo, pero sí pueden ser invalidados.

No compartas el App Secret ni el token; no los pegues en el chat ni en el repositorio.

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

El dashboard consume directamente esos archivos. El workflow corre automáticamente el día 1 a las **08:00 Perú (13:00 UTC)**, descarga el mes anterior, commitea el archivo y publica el sitio. También puedes ejecutarlo manualmente para backfill.

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
- Los KPIs mensuales suman los días del archivo hasta la fecha de corte. El mes en curso se marca como parcial y no se compara como mes cerrado.
- `Engagement = interacciones / alcance`; si Meta no expone alcance por publicación, se usa Views como denominador. Se muestra `—` cuando no hay base comparable.
- Meta puede no devolver edad, género, ciudad o país; en ese caso el panel lo indica.
- Las métricas por publicación son acumuladas (`lifetime`) hasta el corte, no solo del mes de publicación.
- El alcance por publicación no está disponible vía API; se muestra Viewers cuando existe.
- La serie diaria se corta en la fecha de corte; no se publican días futuros con ceros.
