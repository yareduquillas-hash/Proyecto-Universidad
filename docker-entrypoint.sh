#!/bin/sh
# Arranque del contenedor de producción: garantiza esquema antes de servir.
# - BD vacía (instalación limpia): flask db upgrade crea todas las tablas.
# - BD legacy creada con create_all/seed y SIN alembic_version: stamp head
#   (no re-ejecuta la migración inicial sobre un esquema que ya existe).
# - BD con alembic_version: aplica migraciones pendientes.
set -e
export FLASK_APP="${FLASK_APP:-run.py}"

python - <<'PY'
import os
import sys

sys.path.insert(0, "/app")
os.chdir("/app")

from sqlalchemy import inspect

from backend.app import create_app
from backend.extensions import db
from flask_migrate import stamp, upgrade

app = create_app(os.getenv("FLASK_ENV", "development"))
with app.app_context():
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    has_version = "alembic_version" in tables
    user_tables = tables - {"alembic_version"}
    # directory absoluto: no depende del cwd del proceso gunicorn heredado.
    migrations = os.path.join("/app", "migrations")
    if user_tables and not has_version:
        stamp("head", directory=migrations)
    else:
        upgrade(directory=migrations)
PY

exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --timeout 60 run:app
