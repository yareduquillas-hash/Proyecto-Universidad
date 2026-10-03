#!/bin/sh
# Restauración mínima del piloto (Linux/macOS).
# Sobreescribe la BD y uploads con el contenido de un backup.
# Uso: sh scripts/restore.sh backup/<fecha>
set -eu
dir="${1:?Uso: sh scripts/restore.sh backup/<fecha>}"
[ -d "$dir" ] || { echo "No existe el directorio de backup: $dir" >&2; exit 1; }
pg_user="${POSTGRES_USER:-nucleo}"
pg_db="${POSTGRES_DB:-nucleo}"

db_file="$dir/db.sql.gz"
[ -f "$db_file" ] || { echo "Falta $db_file" >&2; exit 1; }
echo "Restaurando BD desde $db_file ..."
# Descomprimir a fichero primero: en un pipeline `set -e` solo reporta el exit
# de psql y un gunzip fallido dejaba SQL truncado con "restauración OK".
tmp="$dir/.db.restore.sql"
gunzip -c "$db_file" > "$tmp"
# ON_ERROR_STOP=1: psql devuelve distinto de 0 ante el primer error SQL.
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "$pg_user" "$pg_db" < "$tmp"
rm -f "$tmp"

if [ -f "$dir/uploads.tar.gz" ]; then
  echo "Restaurando uploads desde $dir/uploads.tar.gz ..."
  tar -xzf "$dir/uploads.tar.gz"
fi
echo "Restauración completada ($dir)."
