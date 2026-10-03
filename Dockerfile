FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FLASK_APP=run.py
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# sh explícito: el bit de ejecución puede perderse al clonar en Windows.
RUN chmod +x docker-entrypoint.sh || true

RUN mkdir -p uploads/partituras uploads/videos instance

EXPOSE 5000

# Prod: 1 worker (el rate-limit es en memoria por proceso, ver backend/utils/rate_limit.py).
# No subir workers sin pasar el rate-limit a Redis. Health en /health.
# El entrypoint ejecuta `flask db upgrade` (o stamp en BD legacy) ANTES de
# gunicorn: sin esto una instalación limpia arranca con la BD vacía.
CMD ["sh", "docker-entrypoint.sh"]
