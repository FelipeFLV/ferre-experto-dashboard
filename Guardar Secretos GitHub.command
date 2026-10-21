#!/bin/bash
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

if [ ! -f .env ]; then
  echo "No existe .env. Ejecuta primero Obtener Token Meta.command."
  read -r -p "Pulsa Enter para cerrar..." _
  exit 1
fi

set -a
source .env
set +a

if ! command -v gh >/dev/null 2>&1; then
  echo "No se encontró gh. Instálalo o avísame."
  read -r -p "Pulsa Enter para cerrar..." _
  exit 1
fi

printf '%s' "$META_PAGE_TOKEN" | gh secret set META_PAGE_TOKEN --repo FelipeFLV/ferre-experto-dashboard
token_status=$?

printf '%s' "$META_PAGE_ID" | gh secret set META_PAGE_ID --repo FelipeFLV/ferre-experto-dashboard
id_status=$?

if [ $token_status -eq 0 ] && [ $id_status -eq 0 ]; then
  rm .env
  echo
  echo "Secretos guardados y .env eliminado."
  gh secret list --repo FelipeFLV/ferre-experto-dashboard
else
  echo
  echo "No se pudieron guardar todos los secretos. .env se conserva."
fi

echo
read -r -p "Pulsa Enter para cerrar..." _
