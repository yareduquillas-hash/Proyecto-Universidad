#!/bin/sh
# Backup mínimo del piloto (Linux/macOS).
# Uso: sh scripts/backup.sh
set -eu
stamp=$(date +%Y%m%d-%H%M%S)
dest="backup/$stamp"
mkdir -p "$dest"
# BD (si cambiaste POSTGRES_USER/DB en .env, ajusta -U y el nombre al final)
# --clean --if-exists: el dump incluye DROP antes de CREATE para que restaurar
# con psql realmente sobrescriba la BD actual (sin esto falla con "already exists").
# pg_dump a fichero primero: en un pipeline `set -e` solo ve el exit del último
# comando (gzip), y un pg_dump fallido quedaba enmascarado con backup "OK".
if ! docker compose exec -T db pg_dump --clean --if-exists \
    -U "${POSTGRES_USER:-nucleo}" "${POSTGRES_DB:-nucleo}" > "$dest/db.sql"; then
  echo "pg_dump falló: backup abortado" >&2
  rm -f "$dest/db.sql"
  exit 1
fi
if [ ! -s "$dest/db.sql" ]; then
  echo "pg_dump devolvió un dump vacío: backup abortado" >&2
  rm -f "$dest/db.sql"
  exit 1
fi
gzip -f "$dest/db.sql"
tar -czf "$dest/uploads.tar.gz" uploads
echo "Backup OK en $dest (db.sql.gz + uploads.tar.gz). Guarda esa carpeta fuera del servidor."
