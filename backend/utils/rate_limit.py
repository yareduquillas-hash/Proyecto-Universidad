import time
from functools import wraps
from collections import deque
from flask import request, jsonify, g

# Almacenamiento en memoria: key -> deque de timestamps.
# Acotado: claves expiradas se eliminan y hay tope _MAX_KEYS con barrido para
# que un atacante que rote identidad no crezca el dict sin límite (OOM).
# NOTA prod: con múltiples workers/procesos no se comparte. Para alta concurrencia
# usar Redis (Flask-Limiter). Para el núcleo con 1 réplica gunicorn es suficiente.
_attempts = {}
_MAX_KEYS = 10000
# Configuración por endpoint: (max_intentos, ventana_segundos)
LIMITS = {
    "login": (5, 60),  # 5 intentos por 60 segundos
    "verificar-cedula": (10, 60),
    "activar-cuenta": (5, 300),
    "forgot": (5, 300),
    "verify-code": (5, 300),
    "reset": (5, 300),
    # Inscripción pública: cubo propio (no comparte con forgot). La key es solo
    # IP: incluir la cédula permitiría rotar identidad y evadir el límite.
    "inscribir-publico": (10, 600),
}
_IP_ONLY_ENDPOINTS = {"inscribir-publico"}
_MAX_WINDOW = max(w for _, w in LIMITS.values())


def _key_for(endpoint_key):
    ip = request.remote_addr or "unknown"
    if endpoint_key in _IP_ONLY_ENDPOINTS:
        return f"{endpoint_key}:{ip}"
    try:
        cedula = ""
        try:
            data = request.get_json(silent=True) or {}
            cedula = (data.get("cedula") or data.get("email") or "").strip()
        except Exception:
            cedula = ""
        if not cedula:
            try:
                form = request.form or {}
                cedula = (form.get("cedula") or form.get("email") or "").strip()
            except Exception:
                cedula = ""
        if not cedula:
            try:
                args = request.args or {}
                cedula = (args.get("cedula") or args.get("email") or "").strip()
            except Exception:
                cedula = ""
        if cedula:
            return f"{endpoint_key}:{ip}:{cedula.lower()}"
        return f"{endpoint_key}:{ip}"
    except Exception:
        return f"{endpoint_key}:{ip}"


def _sweep(now):
    """Elimina claves cuyo último intento ya venció (o vacías)."""
    dead = [
        k for k, dq in _attempts.items()
        if not dq or now - dq[-1] > _MAX_WINDOW
    ]
    for k in dead:
        del _attempts[k]


def _enforce_max_keys(now):
    if len(_attempts) < _MAX_KEYS // 2:
        return
    _sweep(now)
    while len(_attempts) >= _MAX_KEYS:
        oldest = min(_attempts, key=lambda k: _attempts[k][-1] if _attempts[k] else 0.0)
        del _attempts[oldest]


def _is_rate_limited(key, max_attempts, window_seconds, record=True):
    now = time.time()
    dq = _attempts.get(key)
    if dq is None:
        if not record:
            return False, 0
        _enforce_max_keys(now)
        dq = deque()
        _attempts[key] = dq
    while dq and now - dq[0] > window_seconds:
        dq.popleft()
    if not dq and key in _attempts and not record:
        # Solo lectura de una clave ya vencida: no conservarla.
        del _attempts[key]
        return False, 0
    if len(dq) >= max_attempts:
        return True, int(dq[0] + window_seconds - now) + 1
    if record:
        dq.append(now)
    return False, 0


def rate_limit(endpoint_key):
    max_attempts, window = LIMITS.get(endpoint_key, (5, 60))

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = _key_for(endpoint_key)
            limited, retry_after = _is_rate_limited(key, max_attempts, window, record=True)
            if limited:
                resp = jsonify({"error": "Demasiados intentos. Por favor espere e intente de nuevo."})
                resp.headers["Retry-After"] = str(retry_after)
                return resp, 429
            g.rate_limit_key = key
            return f(*args, **kwargs)

        return wrapper

    return decorator


def rate_limit_record_failure(endpoint_key=None):
    """Registra UN intento fallido (para endpoints que solo cuentan fallos, ej. login).

    Debe llamarse solo cuando la autenticación falla. En éxito, llamar
    rate_limit_clear_current() para no bloquear logins legítimos seguidos.
    """
    key = getattr(g, "rate_limit_key", None) or _key_for(endpoint_key or "login")
    max_attempts, window = LIMITS.get(endpoint_key or "login", (5, 60))
    limited, retry_after = _is_rate_limited(key, max_attempts, window, record=True)
    return limited, retry_after


def rate_limit_check_only(endpoint_key):
    """Revisa sin registrar (útil cuando el registro se hace manual en fallo)."""
    key = _key_for(endpoint_key)
    max_attempts, window = LIMITS.get(endpoint_key, (5, 60))
    limited, retry_after = _is_rate_limited(key, max_attempts, window, record=False)
    if limited:
        resp = jsonify({"error": "Demasiados intentos. Por favor espere e intente de nuevo."})
        resp.headers["Retry-After"] = str(retry_after)
        return resp
    g.rate_limit_key = key
    return None


def rate_limit_clear_current():
    key = getattr(g, "rate_limit_key", None)
    if key and key in _attempts:
        _attempts[key].clear()
        if not _attempts[key]:
            del _attempts[key]


def clear_rate_limits():
    """Solo para tests: limpia el estado en memoria."""
    _attempts.clear()
