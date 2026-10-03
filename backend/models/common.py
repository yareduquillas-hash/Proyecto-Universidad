from datetime import datetime


def _utcnow():
    # Fechas naive en UTC en toda la app (consistente con fromisoformat sin tz
    # y datetime.utcnow usado en cronograma). No mezclar aware/naive.
    return datetime.utcnow()
