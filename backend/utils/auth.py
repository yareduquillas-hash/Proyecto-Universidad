from functools import wraps
from flask import jsonify
from flask_jwt_extended import current_user, verify_jwt_in_request


def role_required(*roles):
    """Decorador que restringe un endpoint a los roles indicados.
    Lee el rol desde la BD (current_user) no del token, para que
    cambios de rol se reflejen inmediatamente y no queden tokens viejos con privilegios.
    Debe usarse después de @jwt_required().
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Asegura que el JWT fue verificado y current_user está cargado
            verify_jwt_in_request()
            user = current_user
            if not user or not getattr(user, "activo", True):
                return jsonify({"error": "Usuario no encontrado o inactivo"}), 401
            user_role = getattr(user, "role", None)
            if user_role not in roles:
                return jsonify({"error": "Permisos insuficientes"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


def puede_gestionar_agrupacion(usuario, agrupacion_id):
    """True si el usuario puede operar (escribir) sobre la agrupación.

    admin/secretaria: todas (gestión del núcleo).
    profesor: solo las suyas (usuario_agrupacion).
    Otros roles: False.
    """
    if not usuario or not getattr(usuario, "activo", True):
        return False
    rol = getattr(usuario, "role", None)
    if rol in ("admin", "secretaria"):
        return True
    if rol != "profesor":
        return False
    try:
        gid = int(agrupacion_id)
    except (TypeError, ValueError):
        return False
    try:
        mias = {a.id for a in getattr(usuario, "agrupaciones", []) or []}
    except Exception:
        return False
    return gid in mias