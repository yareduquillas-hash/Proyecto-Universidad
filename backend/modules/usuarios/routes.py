import secrets
import string

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, current_user
from sqlalchemy.exc import IntegrityError
from backend.extensions.db import db
from backend.models import Usuario, Alumno, Profesor, Agrupacion, Instrumento
from werkzeug.security import generate_password_hash
from backend.utils.auth import role_required
from backend.utils.validators import validate_password, validate_email_format, validate_cedula
from datetime import datetime

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/api/v1/usuarios")

ROLES_VALIDOS = ["alumno", "profesor", "secretaria", "jurado", "admin"]


def serialize_usuario(u):
    data = {
        "id": u.id,
        "cedula": u.cedula,
        "nombre": u.nombre,
        "apellido": u.apellido,
        "email": u.email,
        "role": u.role,
        "activo": u.activo,
        "password_set": getattr(u, "password_set", True),
        "requiere_activacion": not getattr(u, "password_set", True) or not u.password_hash,
        "requiere_cambio_clave": bool(getattr(u, "requiere_cambio_clave", False)),
        "agrupaciones": [a.id for a in u.agrupaciones],
        "creado_en": u.creado_en.isoformat() if u.creado_en else None,
    }
    if u.role == "alumno" and getattr(u, "alumno", None):
        data["instrumentos_ids"] = [i.id for i in u.alumno.instrumentos]
        data["fecha_nacimiento"] = (
            u.alumno.fecha_nacimiento.isoformat() if u.alumno.fecha_nacimiento else None
        )
        data["telefono"] = u.alumno.telefono
        data["direccion"] = u.alumno.direccion
        data["nombre_representante"] = u.alumno.nombre_representante
        data["telefono_representante"] = u.alumno.telefono_representante
        data["nivel_academico"] = u.alumno.nivel_academico
        data["fecha_ingreso"] = (
            u.alumno.fecha_ingreso.isoformat() if u.alumno.fecha_ingreso else None
        )
    if u.role in ("profesor", "secretaria") and getattr(u, "profesor", None):
        data["especialidad"] = u.profesor.especialidad
        data["telefono"] = u.profesor.telefono
    return data


def _parse_fecha_or_400(value, campo):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _hay_otro_admin_activo(excluir_id=None):
    q = Usuario.query.filter_by(role="admin", activo=True)
    if excluir_id is not None:
        q = q.filter(Usuario.id != excluir_id)
    return q.first() is not None


@usuarios_bp.post("/")
@jwt_required()
@role_required("admin", "secretaria")
def crear_usuario():
    return _do_crear_usuario(request.get_json() or {})


def _do_crear_usuario(data):
    required = ["cedula", "nombre", "apellido", "email", "role"]
    if not all(data.get(k) for k in required):
        return jsonify({"error": "Faltan campos requeridos: cedula, nombre, apellido, email, role"}), 400

    if data["role"] not in ROLES_VALIDOS:
        return jsonify({"error": f"Role inválido. Debe ser uno de {ROLES_VALIDOS}"}), 400
    if data["role"] == "admin" and current_user.role != "admin":
        return jsonify({"error": "Solo un administrador puede asignar rol admin"}), 403

    cedula = (data["cedula"] or "").strip()
    email = (data["email"] or "").strip().lower()

    ok_ced, err_ced = validate_cedula(cedula)
    if not ok_ced:
        return jsonify({"error": err_ced}), 400
    ok_email, err_email = validate_email_format(email)
    if not ok_email:
        return jsonify({"error": f"Email inválido: {err_email}"}), 400

    if Usuario.query.filter_by(cedula=cedula).first():
        existente = Usuario.query.filter_by(cedula=cedula).first()
        if existente and not existente.activo:
            return jsonify({"error": "Cédula ya registrada como inactiva. Reactive la cuenta existente.", "usuario_id": existente.id, "activo": False}), 409
        return jsonify({"error": "Cédula ya registrada en la base de datos"}), 400
    dup_email = Usuario.query.filter(db.func.lower(Usuario.email) == email).first()
    if dup_email:
        if not dup_email.activo:
            return jsonify({"error": "Email ya registrado como inactivo. Reactive la cuenta existente.", "usuario_id": dup_email.id, "activo": False}), 409
        return jsonify({"error": "Email ya registrado en la base de datos"}), 400

    password = data.get("password")
    confirm_password = data.get("confirm_password")

    if password:
        if confirm_password and password != confirm_password:
            return jsonify({"error": "Las contraseñas no coinciden. Por favor verifíquelas."}), 400
        ok, err = validate_password(password)
        if not ok:
            return jsonify({"error": err}), 400
        password_hash = generate_password_hash(password)
        password_set = True
    else:
        password_hash = None
        password_set = False

    usuario = Usuario(
        cedula=cedula,
        nombre=(data["nombre"] or "").strip(),
        apellido=(data["apellido"] or "").strip(),
        email=email,
        password_hash=password_hash,
        password_set=password_set,
        role=data["role"],
        activo=True,
    )
    if not usuario.nombre or not usuario.apellido:
        return jsonify({"error": "nombre y apellido son requeridos"}), 400
    db.session.add(usuario)
    db.session.flush()

    if data["role"] == "alumno":
        alumno_profile = Alumno(
            usuario_id=usuario.id,
            telefono=data.get("telefono"),
            direccion=data.get("direccion"),
            nombre_representante=data.get("nombre_representante"),
            telefono_representante=data.get("telefono_representante"),
            nivel_academico=data.get("nivel_academico"),
        )
        if data.get("fecha_nacimiento"):
            fn = _parse_fecha_or_400(data["fecha_nacimiento"], "fecha_nacimiento")
            if fn is None:
                db.session.rollback()
                return jsonify({"error": "fecha_nacimiento debe tener formato YYYY-MM-DD"}), 400
            alumno_profile.fecha_nacimiento = fn
        if data.get("fecha_ingreso"):
            fi = _parse_fecha_or_400(data["fecha_ingreso"], "fecha_ingreso")
            if fi is None:
                db.session.rollback()
                return jsonify({"error": "fecha_ingreso debe tener formato YYYY-MM-DD"}), 400
            alumno_profile.fecha_ingreso = fi
        db.session.add(alumno_profile)

        if data.get("instrumentos_ids"):
            if not isinstance(data["instrumentos_ids"], list):
                db.session.rollback()
                return jsonify({"error": "instrumentos_ids debe ser una lista"}), 400
            try:
                ids = [int(x) for x in data["instrumentos_ids"]]
            except (TypeError, ValueError):
                db.session.rollback()
                return jsonify({"error": "instrumentos_ids debe contener IDs numéricos"}), 400
            insts = Instrumento.query.filter(Instrumento.id.in_(ids)).all() if ids else []
            faltantes = set(ids) - {i.id for i in insts}
            if faltantes:
                db.session.rollback()
                return jsonify({"error": f"Instrumentos no encontrados: {sorted(faltantes)}"}), 400
            alumno_profile.instrumentos.extend(insts)

    elif data["role"] in ("profesor", "secretaria"):
        profesor_profile = Profesor(
            usuario_id=usuario.id,
            especialidad=data.get("especialidad"),
            telefono=data.get("telefono"),
        )
        db.session.add(profesor_profile)

    if data.get("agrupaciones_ids"):
        if not isinstance(data["agrupaciones_ids"], list):
            db.session.rollback()
            return jsonify({"error": "agrupaciones_ids debe ser una lista"}), 400
        try:
            gids = [int(x) for x in data["agrupaciones_ids"]]
        except (TypeError, ValueError):
            db.session.rollback()
            return jsonify({"error": "agrupaciones_ids debe contener IDs numéricos"}), 400
        agrups = Agrupacion.query.filter(Agrupacion.id.in_(gids)).all() if gids else []
        falt = set(gids) - {a.id for a in agrups}
        if falt:
            db.session.rollback()
            return jsonify({"error": f"Agrupaciones no encontradas: {sorted(falt)}"}), 400
        usuario.agrupaciones.extend(agrups)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Cédula o email duplicados"}), 400
    return jsonify(serialize_usuario(usuario)), 201


@usuarios_bp.post("/pre-registrar")
@jwt_required()
@role_required("admin", "secretaria")
def pre_registrar_usuario():
    """Pre-registra por cédula sin contraseña inicial (flujo activación).

    Ignora cualquier password enviado: la cuenta nace sin clave y el usuario la
    crea con /api/v1/auth/activar-cuenta validando cédula+email.
    """
    data = dict(request.get_json() or {})
    data.pop("password", None)
    data.pop("confirm_password", None)
    return _do_crear_usuario(data)


@usuarios_bp.get("/")
@jwt_required()
@role_required("admin", "secretaria")
def listar_usuarios():
    from backend.utils.pagination import paginate_query
    query = Usuario.query
    role = request.args.get("role")
    if role:
        if role not in ROLES_VALIDOS:
            return jsonify({"error": f"Role inválido. Debe ser uno de {ROLES_VALIDOS}"}), 400
        query = query.filter_by(role=role)

    estado_activacion = request.args.get("estado_activacion")
    if estado_activacion == "pendiente":
        query = query.filter((Usuario.password_set.is_(False)) | (Usuario.password_hash.is_(None)))
    elif estado_activacion == "activo":
        query = query.filter(Usuario.password_set.is_(True), Usuario.password_hash.isnot(None))

    incluir_inactivos = (request.args.get("incluir_inactivos") or "").lower() == "true"
    filtro_activo = request.args.get("activo")
    if filtro_activo is not None:
        query = query.filter_by(activo=filtro_activo.lower() == "true")
    elif not incluir_inactivos:
        query = query.filter_by(activo=True)

    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Usuario.nombre.ilike(like),
                Usuario.apellido.ilike(like),
                Usuario.cedula.ilike(like),
                Usuario.email.ilike(like),
            )
        )

    query = query.order_by(Usuario.creado_en.desc())
    result, is_paginated = paginate_query(query)
    if is_paginated:
        return jsonify({
            "items": [serialize_usuario(u) for u in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
            "pages": result["pages"],
            "truncated": result.get("truncated", False),
        }), 200
    return jsonify([serialize_usuario(u) for u in result]), 200


@usuarios_bp.get("/<int:id>")
@jwt_required()
def obtener_usuario(id):
    # Admin/secretaría ven a cualquiera; el resto solo su propio perfil.
    if current_user.role not in ("admin", "secretaria") and current_user.id != id:
        return jsonify({"error": "Permisos insuficientes"}), 403
    usuario = db.session.get(Usuario, id)
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404
    return jsonify(serialize_usuario(usuario)), 200


@usuarios_bp.put("/<int:id>")
@jwt_required()
@role_required("admin", "secretaria")
def actualizar_usuario(id):
    usuario = db.session.get(Usuario, id)
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404

    data = request.get_json() or {}
    # Secretaria no puede crear/escalar a admin ni tocar cuentas admin
    if usuario.role == "admin" and current_user.role != "admin":
        return jsonify({"error": "Solo un administrador puede modificar cuentas admin"}), 403
    if data.get("role") == "admin" and current_user.role != "admin":
        return jsonify({"error": "Solo un administrador puede asignar rol admin"}), 403

    nuevo_rol = data.get("role", usuario.role)
    nuevo_activo = data.get("activo", usuario.activo)
    # not nuevo_activo cubre False, 0 y otros falsy: evita bypass con {"activo": 0}
    if usuario.role == "admin" and (nuevo_rol != "admin" or not nuevo_activo):
        if not _hay_otro_admin_activo(excluir_id=usuario.id):
            return jsonify({"error": "No se puede degradar/desactivar al último administrador activo"}), 400
    # Paridad con DELETE: nadie puede desactivar su propia cuenta por PUT
    if usuario.id == current_user.id and "activo" in data and not data["activo"]:
        return jsonify({"error": "No puedes desactivar tu propia cuenta"}), 400

    for campo in ("nombre", "apellido", "email", "role", "activo"):
        if campo in data:
            if campo == "role" and data["role"] not in ROLES_VALIDOS:
                return jsonify({"error": f"Role inválido. Debe ser uno de {ROLES_VALIDOS}"}), 400
            if campo == "email":
                email = (data["email"] or "").strip().lower()
                ok, err = validate_email_format(email)
                if not ok:
                    return jsonify({"error": f"Email inválido: {err}"}), 400
                dup = Usuario.query.filter(
                    db.func.lower(Usuario.email) == email, Usuario.id != usuario.id
                ).first()
                if dup:
                    return jsonify({"error": "Email ya registrado por otro usuario"}), 400
                usuario.email = email
                continue
            if campo in ("nombre", "apellido"):
                val = (data[campo] or "").strip()
                if not val:
                    return jsonify({"error": f"{campo} no puede estar vacío"}), 400
                setattr(usuario, campo, val)
                continue
            setattr(usuario, campo, data[campo])

    if "password" in data and data["password"]:
        if data.get("confirm_password") and data["password"] != data["confirm_password"]:
            return jsonify({"error": "Las contraseñas no coinciden"}), 400
        ok, err = validate_password(data["password"])
        if not ok:
            return jsonify({"error": err}), 400
        usuario.password_hash = generate_password_hash(data["password"])
        usuario.password_set = True
        usuario.password_version = (usuario.password_version or 0) + 1
        usuario.requiere_cambio_clave = False

    if usuario.role == "alumno" and getattr(usuario, "alumno", None):
        for campo in ("telefono", "direccion", "nombre_representante", "telefono_representante", "nivel_academico"):
            if campo in data:
                setattr(usuario.alumno, campo, data[campo])
        if "fecha_nacimiento" in data and data["fecha_nacimiento"]:
            fn = _parse_fecha_or_400(data["fecha_nacimiento"], "fecha_nacimiento")
            if fn is None:
                return jsonify({"error": "fecha_nacimiento debe tener formato YYYY-MM-DD"}), 400
            usuario.alumno.fecha_nacimiento = fn
    elif usuario.role in ("profesor", "secretaria") and getattr(usuario, "profesor", None):
        if "especialidad" in data:
            usuario.profesor.especialidad = data["especialidad"]
        if "telefono" in data:
            usuario.profesor.telefono = data["telefono"]

    # Al cambiar de rol, crear el perfil que falte (no se borra el anterior
    # para conservar historial de asistencia). Sin esto el usuario quedaba
    # sin ficha (profesor sin Profesor, alumno sin Alumno).
    # flush + commit en el mismo try: si falla la creación del perfil, se
    # revierte TODO (incluido el cambio de rol) — nunca rol nuevo sin ficha.
    try:
        db.session.flush()
        if usuario.role == "alumno" and not getattr(usuario, "alumno", None):
            db.session.add(Alumno(usuario_id=usuario.id))
        elif usuario.role in ("profesor", "secretaria") and not getattr(usuario, "profesor", None):
            db.session.add(Profesor(usuario_id=usuario.id))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Conflicto de unicidad (cédula/email)"}), 400
    return jsonify(serialize_usuario(usuario)), 200


@usuarios_bp.delete("/<int:id>")
@jwt_required()
@role_required("admin", "secretaria")
def eliminar_usuario(id):
    usuario = db.session.get(Usuario, id)
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404
    if usuario.id == current_user.id:
        return jsonify({"error": "No puedes desactivar tu propia cuenta"}), 400
    if usuario.role == "admin":
        if current_user.role != "admin":
            return jsonify({"error": "Solo un administrador puede desactivar cuentas admin"}), 403
        if not _hay_otro_admin_activo(excluir_id=usuario.id):
            return jsonify({"error": "No se puede desactivar al último administrador activo"}), 400
    usuario.activo = False
    db.session.commit()
    return jsonify(serialize_usuario(usuario)), 200


@usuarios_bp.post("/<int:id>/reset-password")
@jwt_required()
@role_required("admin", "secretaria")
def reset_password_asistido(id):
    """Reset asistido: genera temporal de 1 uso y obliga a cambiarla.

    Solo por secretaría/admin en persona. La temporal se muestra UNA vez.
    """
    usuario = db.session.get(Usuario, id)
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404
    if usuario.role == "admin" and current_user.role != "admin":
        return jsonify({"error": "Solo un administrador puede resetear cuentas admin"}), 403
    alfabeto = string.ascii_letters + string.digits
    temporal = "T-" + "".join(secrets.choice(alfabeto) for _ in range(10)) + "9a"
    usuario.password_hash = generate_password_hash(temporal)
    usuario.password_set = True
    usuario.password_version = (usuario.password_version or 0) + 1
    usuario.requiere_cambio_clave = True
    db.session.commit()
    current_app_logger = db.session.bind  # noqa: F841 (mantiene sesión viva para audit)
    return jsonify({
        "mensaje": "Clave temporal generada. Entrégala en persona y pide cambio inmediato.",
        "usuario_id": usuario.id,
        "temporal": temporal,
    }), 200


@usuarios_bp.post("/asignar-agrupacion")
@jwt_required()
@role_required("admin", "secretaria")
def asignar_agrupacion():
    data = request.get_json() or {}
    usuario_id = data.get("usuario_id")
    agrupacion_id = data.get("agrupacion_id")
    if not usuario_id or not agrupacion_id:
        return jsonify({"error": "usuario_id y agrupacion_id son requeridos"}), 400

    usuario = db.session.get(Usuario, usuario_id)
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404

    agrupacion = db.session.get(Agrupacion, agrupacion_id)
    if not agrupacion:
        return jsonify({"error": "Agrupación no encontrada"}), 404

    if agrupacion not in usuario.agrupaciones:
        usuario.agrupaciones.append(agrupacion)
        try:
            db.session.commit()
        except IntegrityError:
            # Doble clic: usuario_agrupacion es PK compuesta (ya asignada).
            db.session.rollback()

    return jsonify(serialize_usuario(usuario)), 200


@usuarios_bp.post("/desasignar-agrupacion")
@jwt_required()
@role_required("admin", "secretaria")
def desasignar_agrupacion():
    data = request.get_json() or {}
    usuario_id = data.get("usuario_id")
    agrupacion_id = data.get("agrupacion_id")
    if not usuario_id or not agrupacion_id:
        return jsonify({"error": "usuario_id y agrupacion_id son requeridos"}), 400
    usuario = db.session.get(Usuario, usuario_id)
    agrupacion = db.session.get(Agrupacion, agrupacion_id)
    if not usuario or not agrupacion:
        return jsonify({"error": "Usuario o agrupación no encontrados"}), 404
    if agrupacion in usuario.agrupaciones:
        usuario.agrupaciones.remove(agrupacion)
        db.session.commit()
    return jsonify(serialize_usuario(usuario)), 200


@usuarios_bp.get("/agrupaciones")
@jwt_required()
def listar_agrupaciones():
    grupos = Agrupacion.query.filter_by(activa=True).all()
    return jsonify([{"id": g.id, "nombre": g.nombre, "tipo": g.tipo} for g in grupos]), 200


@usuarios_bp.get("/instrumentos")
@jwt_required()
def listar_instrumentos():
    instrumentos = Instrumento.query.all()
    return jsonify([{"id": i.id, "nombre": i.nombre, "familia": i.familia} for i in instrumentos]), 200
