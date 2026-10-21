#!/bin/bash
cd "$(dirname "$0")" || exit 1

python3 meta_page_token.py "$@"
status=$?

if [ $status -eq 0 ] && [ -f .env ]; then
  echo
  echo "Probando el token contra Meta..."
  set -a
  source .env
  set +a
  python3 fetch_meta.py --probe --month 2026-10
fi

echo
echo "Puedes cerrar esta ventana."
read -r -p "Pulsa Enter para cerrar..." _
