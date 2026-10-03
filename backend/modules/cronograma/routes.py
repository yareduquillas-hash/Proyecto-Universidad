from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, current_user
from sqlalchemy.exc import IntegrityError

from backend.extensions.db import db
from backend.models import EventoCronograma, Agrupacion, Usuario
from backend.utils.auth import role_required, puede_gestionar_agrupacion

cronograma_bp = Blueprint("cronograma", __name__, url_prefix="/api/v1/cronograma")

TIPOS_VALIDOS = ["ensayo", "concierto", "pauta_extra", "clase", "taller"]
# Lectura amplia: admin/secretaria gestionan todo el núcleo (igual que en
# escritura via puede_gestionar_agrupacion). Profesor/alumno solo lo suyo.
ROLES_LECTURA_AMPLIA = ["admin", "secretaria"]

# Hora operativa del conservatorio: Venezuela UTC-4 fijo (sin DST).
# Los datetime-local del navegador llegan naive en hora Caracas y se guardan
# así; el "ahora" debe ser Caracas aunque el servidor corra en UTC (Docker).
VEN_TZ = timezone(timedelta(hours=-4), "America/Caracas")


def _ahora_local_naive():
    return datetime.now(VEN_TZ).replace(tzinfo=None)


def get_user_agrupaciones(user_id):
    usuario = db.session.get(Usuario, user_id)
    if not usuario:
        return []
    return [a.id for a in usuario.agrupaciones]


def serialize_evento(e):
    creador = e.creador
    creado_por_nombre = None
    if creador:
        creado_por_nombre = f"{creador.nombre} {creador.apellido}".strip()
    return {
        "id": e.id,
        "titulo": e.titulo,
        "tipo": e.tipo,
        "descripcion": e.descripcion,
        "fecha_inicio": e.fecha_inicio.isoformat() if e.fecha_inicio else None,
        "fecha_fin": e.fecha_fin.isoformat() if e.fecha_fin else None,
        "lugar": e.lugar,
        "agrupacion_id": e.agrupacion_id,
        "agrupacion_nombre": e.agrupacion.nombre if e.agrupacion else None,
        "notificar_cambios": e.notificar_cambios,
        "mensaje_alerta": e.mensaje_alerta,
        "creado_por_nombre": creado_por_nombre,
    }


def _parse_iso(value):
    """Acepta ISO con o sin tz y normaliza a naive en hora Caracas.

    Los inputs naive (datetime-local) ya vienen en hora local del
    conservatorio y se guardan tal cual. Los inputs con tz se convierten
    a Caracas para comparar con la misma base que _ahora_local_naive().
    """
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone(VEN_TZ).replace(tzinfo=None)
    return dt


def _parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d")


def _hay_solape(agrupacion_id, inicio, fin, excluir_id=None):
    q = EventoCronograma.query.filter(
        EventoCronograma.agrupacion_id == agrupacion_id,
        EventoCronograma.activo.is_(True),
        EventoCronograma.fecha_inicio < fin,
        EventoCronograma.fecha_fin > inicio,
    )
    if excluir_id:
        q = q.filter(EventoCronograma.id != excluir_id)
    return q.first() is not None


@cronograma_bp.post("/eventos")
@jwt_required()
@role_required("profesor", "secretaria", "admin")
def crear_evento():
    data = request.get_json() or {}

    required = ["agrupacion_id", "titulo", "tipo", "fecha_inicio", "fecha_fin"]
    if not all(data.get(k) for k in required):
        return jsonify({"error": "Faltan campos requeridos: agrupacion_id, titulo, tipo, fecha_inicio, fecha_fin"}), 400

    titulo = (data.get("titulo") or "").strip()
    if len(titulo) < 3:
        return jsonify({"error": "titulo es requerido (mín 3 caracteres)"}), 400
    if len(titulo) > 150:
        return jsonify({"error": "titulo demasiado largo (máx 150)"}), 400

    tipo = data["tipo"]
    if tipo not in TIPOS_VALIDOS:
        return jsonify({"error": f"tipo inválido. Debe ser uno de {TIPOS_VALIDOS}"}), 400

    try:
        agrupacion_id = int(data["agrupacion_id"])
    except (TypeError, ValueError):
        return jsonify({"error": "agrupacion_id debe ser numérico"}), 400
    if not db.session.get(Agrupacion, agrupacion_id):
        return jsonify({"error": "Agrupación no encontrada"}), 404
    if not puede_gestionar_agrupacion(current_user, agrupacion_id):
        return jsonify({"error": "No perteneces a esa agrupación"}), 403

    try:
        fecha_inicio = _parse_iso(data["fecha_inicio"])
        fecha_fin = _parse_iso(data["fecha_fin"])
    except (ValueError, TypeError):
        return jsonify({"error": "fecha_inicio y fecha_fin deben tener formato ISO (YYYY-MM-DDTHH:MM)"}), 400

    if fecha_fin <= fecha_inicio:
        return jsonify({"error": "fecha_fin debe ser posterior a fecha_inicio"}), 400

    lugar = (data.get("lugar") or "").strip() or None
    if lugar and len(lugar) > 200:
        return jsonify({"error": "lugar demasiado largo (máx 200)"}), 400

    if _hay_solape(agrupacion_id, fecha_inicio, fecha_fin):
        return jsonify({"error": "La agrupación ya tiene un evento en ese horario"}), 409

    evento = EventoCronograma(
        agrupacion_id=agrupacion_id,
        titulo=titulo,
        tipo=tipo,
        descripcion=(data.get("descripcion") or "").strip()[:2000] or None,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        lugar=lugar,
        notificar_cambios=bool(data.get("notificar_cambios", False)),
        mensaje_alerta=(data.get("mensaje_alerta") or "").strip()[:2000] or None,
        creado_por=int(current_user.id),
        activo=True,
    )
    db.session.add(evento)
    try:
        db.session.commit()
    except IntegrityError:
        # Doble clic / carrera frente a _hay_solape: no dejar 500 al usuario.
        db.session.rollback()
        if _hay_solape(agrupacion_id, fecha_inicio, fecha_fin):
            return jsonify({"error": "La agrupación ya tiene un evento en ese horario"}), 409
        return jsonify({"error": "No se pudo crear el evento (posible duplicado)"}), 409
    return jsonify(serialize_evento(evento)), 201


@cronograma_bp.get("/eventos")
@jwt_required()
def listar_eventos():
    query = EventoCronograma.query

    agrupacion_id = request.args.get("agrupacion_id", type=int)
    if agrupacion_id:
        query = query.filter(EventoCronograma.agrupacion_id == agrupacion_id)

    # Solo lectura propia salvo admin/secretaria (consistente con proximos/alertas)
    if current_user.role not in ROLES_LECTURA_AMPLIA:
        mias = get_user_agrupaciones(current_user.id)
        if agrupacion_id and agrupacion_id not in mias:
            return jsonify({"error": "No perteneces a esa agrupación"}), 403
        if not mias:
            return jsonify([]), 200
        if not agrupacion_id:
            query = query.filter(EventoCronograma.agrupacion_id.in_(mias))

    tipo = request.args.get("tipo")
    if tipo:
        if tipo not in TIPOS_VALIDOS:
            return jsonify({"error": f"tipo inválido. Debe ser uno de {TIPOS_VALIDOS}"}), 400
        query = query.filter(EventoCronograma.tipo == tipo)

    fecha_desde = request.args.get("fecha_desde")
    if fecha_desde:
        try:
            fd = _parse_date(fecha_desde)
            query = query.filter(EventoCronograma.fecha_inicio >= fd)
        except ValueError:
            return jsonify({"error": "fecha_desde debe tener formato YYYY-MM-DD"}), 400

    fecha_hasta = request.args.get("fecha_hasta")
    if fecha_hasta:
        try:
            fh = _parse_date(fecha_hasta)
            # Inclusivo: todo el día fecha_hasta
            query = query.filter(EventoCronograma.fecha_inicio < fh + timedelta(days=1))
        except ValueError:
            return jsonify({"error": "fecha_hasta debe tener formato YYYY-MM-DD"}), 400

    # Por defecto solo activos; ?activos_only=false solo admin/secretaría.
    # Otros roles siempre ven solo activos (consistente con detalle/proximos/alertas).
    activos_param = request.args.get("activos_only", "true").lower()
    if current_user.role not in ROLES_LECTURA_AMPLIA:
        query = query.filter(EventoCronograma.activo.is_(True))
    elif activos_param != "false":
        query = query.filter(EventoCronograma.activo.is_(True))

    query = query.order_by(EventoCronograma.fecha_inicio.asc())
    from backend.utils.pagination import paginate_query
    result, is_paginated = paginate_query(query)
    if is_paginated:
        return jsonify({
            "items": [serialize_evento(e) for e in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
            "pages": result["pages"],
            "truncated": result.get("truncated", False),
        }), 200
    return jsonify([serialize_evento(e) for e in result]), 200


@cronograma_bp.get("/eventos/proximos")
@jwt_required()
def eventos_proximos():
    usuario = db.session.get(Usuario, int(current_user.id))

    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404

    ahora = _ahora_local_naive()

    query = EventoCronograma.query.filter(
        EventoCronograma.fecha_inicio >= ahora,
        EventoCronograma.activo.is_(True),
    )

    if usuario.role not in ROLES_LECTURA_AMPLIA:
        agrupacion_ids = get_user_agrupaciones(usuario.id)
        if not agrupacion_ids:
            return jsonify([]), 200
        query = query.filter(EventoCronograma.agrupacion_id.in_(agrupacion_ids))

    eventos = query.order_by(EventoCronograma.fecha_inicio.asc()).limit(10).all()
    return jsonify([serialize_evento(e) for e in eventos]), 200


@cronograma_bp.get("/eventos/alertas")
@jwt_required()
def eventos_alertas():
    usuario = db.session.get(Usuario, int(current_user.id))
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404

    ahora = _ahora_local_naive()
    limite_48h = ahora + timedelta(hours=48)

    # Solo futuros: el flag notificar_cambios no rescata eventos pasados.
    query = EventoCronograma.query.filter(
        EventoCronograma.activo.is_(True),
        EventoCronograma.fecha_inicio >= ahora,
        (
            EventoCronograma.notificar_cambios.is_(True)
        ) | (
            (EventoCronograma.fecha_inicio >= ahora)
            & (EventoCronograma.fecha_inicio <= limite_48h)
        ),
    )

    if usuario.role not in ROLES_LECTURA_AMPLIA:
        agrupacion_ids = get_user_agrupaciones(usuario.id)
        if not agrupacion_ids:
            return jsonify([]), 200
        query = query.filter(EventoCronograma.agrupacion_id.in_(agrupacion_ids))

    eventos = query.order_by(EventoCronograma.fecha_inicio.asc()).all()
    return jsonify([serialize_evento(e) for e in eventos]), 200


@cronograma_bp.get("/eventos/<int:id>")
@jwt_required()
def detalle_evento(id):
    evento = db.session.get(EventoCronograma, id)
    if not evento:
        return jsonify({"error": "Evento no encontrado"}), 404
    if current_user.role not in ROLES_LECTURA_AMPLIA:
        if not evento.activo:
            return jsonify({"error": "Evento no encontrado"}), 404
        if evento.agrupacion_id not in get_user_agrupaciones(current_user.id):
            return jsonify({"error": "No perteneces a esa agrupación"}), 403
    return jsonify(serialize_evento(evento)), 200


@cronograma_bp.put("/eventos/<int:id>")
@jwt_required()
@role_required("profesor", "secretaria", "admin")
def actualizar_evento(id):
    evento = db.session.get(EventoCronograma, id)
    if not evento:
        return jsonify({"error": "Evento no encontrado"}), 404
    if not puede_gestionar_agrupacion(current_user, evento.agrupacion_id):
        return jsonify({"error": "No perteneces a esa agrupación"}), 403

    data = request.get_json() or {}

    # Validar TODO antes de mutar (evita sesión dirty en 400)
    nuevo_agrupacion = evento.agrupacion_id
    nuevo_titulo = evento.titulo
    nuevo_tipo = evento.tipo
    nueva_desc = evento.descripcion
    nuevo_inicio = evento.fecha_inicio
    nuevo_fin = evento.fecha_fin
    nuevo_lugar = evento.lugar
    nuevo_notificar = evento.notificar_cambios
    nuevo_msg = evento.mensaje_alerta

    if "agrupacion_id" in data:
        try:
            nuevo_agrupacion = int(data["agrupacion_id"])
        except (TypeError, ValueError):
            return jsonify({"error": "agrupacion_id debe ser numérico"}), 400
        if not db.session.get(Agrupacion, nuevo_agrupacion):
            return jsonify({"error": "Agrupación no encontrada"}), 404

    if "titulo" in data:
        nuevo_titulo = (data["titulo"] or "").strip()
        if len(nuevo_titulo) < 3:
            return jsonify({"error": "titulo es requerido (mín 3 caracteres)"}), 400
        if len(nuevo_titulo) > 150:
            return jsonify({"error": "titulo demasiado largo (máx 150)"}), 400

    if "tipo" in data:
        if data["tipo"] not in TIPOS_VALIDOS:
            return jsonify({"error": f"tipo inválido. Debe ser uno de {TIPOS_VALIDOS}"}), 400
        nuevo_tipo = data["tipo"]

    if "descripcion" in data:
        nueva_desc = (data["descripcion"] or "").strip()[:2000] or None

    if "fecha_inicio" in data:
        try:
            nuevo_inicio = _parse_iso(data["fecha_inicio"])
        except (ValueError, TypeError):
            return jsonify({"error": "fecha_inicio debe tener formato ISO (YYYY-MM-DDTHH:MM)"}), 400

    if "fecha_fin" in data:
        try:
            nuevo_fin = _parse_iso(data["fecha_fin"])
        except (ValueError, TypeError):
            return jsonify({"error": "fecha_fin debe tener formato ISO (YYYY-MM-DDTHH:MM)"}), 400

    if nuevo_fin <= nuevo_inicio:
        return jsonify({"error": "fecha_fin debe ser posterior a fecha_inicio"}), 400

    if "lugar" in data:
        nuevo_lugar = (data["lugar"] or "").strip() or None
        if nuevo_lugar and len(nuevo_lugar) > 200:
            return jsonify({"error": "lugar demasiado largo (máx 200)"}), 400

    if "notificar_cambios" in data:
        nuevo_notificar = bool(data["notificar_cambios"])

    if "mensaje_alerta" in data:
        nuevo_msg = (data["mensaje_alerta"] or "").strip()[:2000] or None

    if not puede_gestionar_agrupacion(current_user, nuevo_agrupacion):
        return jsonify({"error": "No perteneces a esa agrupación"}), 403

    if _hay_solape(nuevo_agrupacion, nuevo_inicio, nuevo_fin, excluir_id=evento.id):
        return jsonify({"error": "La agrupación ya tiene un evento en ese horario"}), 409

    alerta_generada = False
    fecha_inicio_anterior = evento.fecha_inicio.isoformat() if evento.fecha_inicio else None
    lugar_anterior = evento.lugar
    titulo_anterior = evento.titulo
    mensaje_enviado = "mensaje_alerta" in data

    evento.agrupacion_id = nuevo_agrupacion
    evento.titulo = nuevo_titulo
    evento.tipo = nuevo_tipo
    evento.descripcion = nueva_desc
    evento.fecha_inicio = nuevo_inicio
    evento.fecha_fin = nuevo_fin
    evento.lugar = nuevo_lugar
    evento.notificar_cambios = nuevo_notificar
    evento.mensaje_alerta = nuevo_msg

    if evento.notificar_cambios:
        fecha_nueva_str = evento.fecha_inicio.isoformat() if evento.fecha_inicio else None
        # Título solo no dispara alerta (decisión existente); se compara con el
        # valor previo a la asignación (no post-asignación).
        _cambio_titulo = (titulo_anterior != nuevo_titulo)
        cambios_significativos = (
            (fecha_nueva_str != fecha_inicio_anterior)
            or (evento.lugar != lugar_anterior)
            or (_cambio_titulo and False)
        )
        if cambios_significativos:
            alerta_generada = True
            if not mensaje_enviado:
                evento.mensaje_alerta = (
                    f"Actualización: {evento.titulo} - "
                    f"fecha: {evento.fecha_inicio.isoformat()} - "
                    f"lugar: {evento.lugar}"
                )

    db.session.commit()
    return jsonify({**serialize_evento(evento), "alerta_generada": alerta_generada}), 200


@cronograma_bp.delete("/eventos/<int:id>")
@jwt_required()
@role_required("profesor", "secretaria", "admin")
def eliminar_evento(id):
    evento = db.session.get(EventoCronograma, id)
    if not evento:
        return jsonify({"error": "Evento no encontrado"}), 404
    if not puede_gestionar_agrupacion(current_user, evento.agrupacion_id):
        return jsonify({"error": "No perteneces a esa agrupación"}), 403
    evento.activo = False
    db.session.commit()
    return jsonify(serialize_evento(evento)), 200
