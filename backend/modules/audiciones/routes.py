from datetime import datetime, date, timedelta, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, current_user
from sqlalchemy.exc import IntegrityError
from backend.extensions.db import db
from backend.models import (
    Convocatoria, Aspirante, Audicion, PuntuacionAudicion, Agrupacion, Usuario,
    ESTADOS_ASPIRANTE, ESTADOS_ASPIRANTE_LEGACY,
)
from backend.utils.auth import role_required
from backend.utils.rate_limit import rate_limit

ESTADOS_VALIDOS = set(ESTADOS_ASPIRANTE) | set(ESTADOS_ASPIRANTE_LEGACY)

audiciones_bp = Blueprint("audiciones", __name__, url_prefix="/api/v1/audiciones")

# Hora operativa del conservatorio: Venezuela UTC-4 fijo (sin DST), igual que
# cronograma. datetime-local y date del navegador llegan en hora Caracas; el
# servidor en Docker corre en UTC y date.today()/now() desfasaban la validación.
VEN_TZ = timezone(timedelta(hours=-4), "America/Caracas")


def _ahora_ven_naive():
    return datetime.now(VEN_TZ).replace(tzinfo=None)


def serialize_convocatoria(c):
    return {
        "id": c.id, "titulo": c.titulo, "descripcion": c.descripcion,
        "fecha_inicio": str(c.fecha_inicio), "fecha_fin": str(c.fecha_fin),
        "activa": c.activa,
    }


def serialize_aspirante(a):
    return {
        "id": a.id, "convocatoria_id": a.convocatoria_id,
        "nombre": a.nombre, "apellido": a.apellido, "cedula": a.cedula,
        "email": a.email, "telefono": a.telefono,
        "fecha_nacimiento": str(a.fecha_nacimiento) if a.fecha_nacimiento else None,
        "direccion": a.direccion,
        "instrumento_postulado": a.instrumento_postulado,
        "experiencia_previa": a.experiencia_previa,
        "estado": a.estado,
        "inscrito_en": str(a.inscrito_en),
    }


def serialize_puntuacion(p):
    return {
        "id": p.id, "aspirante_id": p.aspirante_id,
        "jurado_id": p.jurado_id,
        "jurado_nombre": f"{p.jurado.nombre} {p.jurado.apellido}" if p.jurado else None,
        "tecnica": p.tecnica, "interpretacion": p.interpretacion,
        "afinacion": p.afinacion, "ritmo": p.ritmo,
        "presencia": p.presencia, "observaciones": p.observaciones,
        "puntuacion_total": p.puntuacion_total,
        "creado_en": str(p.creado_en),
    }


@audiciones_bp.route("/convocatorias", methods=["POST"])
@jwt_required()
@role_required("admin")
def crear_convocatoria():
    data = request.get_json() or {}
    titulo = (data.get("titulo") or "").strip()
    if not titulo or len(titulo) < 3:
        return jsonify({"error": "titulo es requerido (mín 3 caracteres)"}), 400
    if len(titulo) > 150:
        return jsonify({"error": "titulo demasiado largo (máx 150)"}), 400
    try:
        fecha_inicio = datetime.strptime(data["fecha_inicio"], "%Y-%m-%d").date()
        fecha_fin = datetime.strptime(data["fecha_fin"], "%Y-%m-%d").date()
    except (ValueError, KeyError, TypeError):
        return jsonify({"error": "fecha_inicio y fecha_fin deben tener formato YYYY-MM-DD"}), 400
    if fecha_fin < fecha_inicio:
        return jsonify({"error": "fecha_fin no puede ser anterior a fecha_inicio"}), 400
    c = Convocatoria(
        titulo=titulo,
        descripcion=(data.get("descripcion") or "").strip()[:2000],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        activa=bool(data.get("activa", True)),
        creada_por=int(current_user.id),
    )
    db.session.add(c)
    db.session.commit()
    return jsonify(serialize_convocatoria(c)), 201


@audiciones_bp.route("/convocatorias", methods=["GET"])
@jwt_required()
def listar_convocatorias():
    from backend.utils.pagination import paginate_query
    activa = request.args.get("activa")
    q = Convocatoria.query
    if activa is not None:
        q = q.filter_by(activa=activa.lower() == "true")
    q = q.order_by(Convocatoria.fecha_inicio.desc())
    result, is_paginated = paginate_query(q)
    if is_paginated:
        return jsonify({
            "items": [serialize_convocatoria(c) for c in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
            "pages": result["pages"],
            "truncated": result.get("truncated", False),
        }), 200
    return jsonify([serialize_convocatoria(c) for c in result]), 200


@audiciones_bp.route("/convocatorias-publicas", methods=["GET"])
def convocatorias_publicas():
    """Lista pública mínima de convocatorias activas y vigentes (para inscripción)."""
    # Fecha en hora Caracas: en UTC el día cambiaba 4 h antes y cerraba/abría
    # convocatorias fuera de hora del conservatorio.
    hoy = _ahora_ven_naive().date()
    q = Convocatoria.query.filter_by(activa=True).filter(
        Convocatoria.fecha_inicio <= hoy, Convocatoria.fecha_fin >= hoy
    ).order_by(Convocatoria.fecha_fin.asc())
    items = [{"id": c.id, "titulo": c.titulo, "descripcion": c.descripcion,
              "fecha_inicio": str(c.fecha_inicio), "fecha_fin": str(c.fecha_fin)} for c in q.limit(50).all()]
    return jsonify(items), 200


@audiciones_bp.route("/convocatorias/<int:id>/activar", methods=["PUT"])
@jwt_required()
@role_required("admin")
def toggle_convocatoria(id):
    c = db.session.get(Convocatoria, id)
    if not c:
        return jsonify({"error": "Convocatoria no encontrada"}), 404
    c.activa = not c.activa
    db.session.commit()
    return jsonify(serialize_convocatoria(c)), 200


def _validar_y_crear_aspirante(form, files):
    convocatoria_id = form.get("convocatoria_id")
    nombre = (form.get("nombre") or "").strip()
    apellido = (form.get("apellido") or "").strip()
    cedula = (form.get("cedula") or "").strip()
    email = (form.get("email") or "").strip().lower()
    telefono = (form.get("telefono") or "").strip()
    fecha_nacimiento_str = form.get("fecha_nacimiento")
    fecha_nacimiento = None
    if fecha_nacimiento_str:
        try:
            fecha_nacimiento = datetime.strptime(fecha_nacimiento_str, "%Y-%m-%d").date()
        except ValueError:
            return None, ({"error": "fecha_nacimiento debe tener formato YYYY-MM-DD"}, 400)
    direccion = (form.get("direccion") or "").strip() or None
    instrumento_postulado = (form.get("instrumento_postulado") or "").strip() or None
    experiencia_previa = (form.get("experiencia_previa") or "").strip() or None

    if not convocatoria_id or not nombre or not apellido or not cedula:
        return None, ({"error": "convocatoria_id, nombre, apellido y cedula son obligatorios"}, 400)
    if len(nombre) < 2 or len(apellido) < 2:
        return None, ({"error": "Nombre y apellido deben tener al menos 2 caracteres"}, 400)
    from backend.utils.validators import validate_cedula
    ok_ced, err_ced = validate_cedula(cedula)
    if not ok_ced:
        return None, ({"error": err_ced}, 400)
    if email:
        from backend.utils.validators import validate_email_format
        ok, err = validate_email_format(email)
        if not ok:
            return None, ({"error": f"Email inválido: {err}"}, 400)

    try:
        convocatoria_id_int = int(convocatoria_id)
    except (TypeError, ValueError):
        return None, ({"error": "convocatoria_id debe ser numérico"}, 400)

    conv = db.session.get(Convocatoria, convocatoria_id_int)
    if not conv or not conv.activa:
        return None, ({"error": "La convocatoria indicada no existe o se encuentra inactiva"}, 400)
    hoy = _ahora_ven_naive().date()
    if conv.fecha_inicio and hoy < conv.fecha_inicio:
        return None, ({"error": "La convocatoria aún no abre inscripciones"}, 400)
    if conv.fecha_fin and hoy > conv.fecha_fin:
        return None, ({"error": "La convocatoria ya cerró inscripciones"}, 400)

    # Unicidad por convocatoria (permite reinscripción en otra convocatoria,
    # incluso si la cédula ya existe como usuario —readmisión, decisión D9—).
    if Aspirante.query.filter_by(convocatoria_id=convocatoria_id_int, cedula=cedula).first():
        return None, ({"error": "Ya existe un aspirante con esa cédula en esta convocatoria"}, 400)

    aspirante = Aspirante(
        convocatoria_id=convocatoria_id_int,
        nombre=nombre[:80], apellido=apellido[:80], cedula=cedula[:20],
        email=email[:120] if email else None, telefono=telefono[:20] if telefono else None,
        fecha_nacimiento=fecha_nacimiento,
        direccion=direccion[:200] if direccion else None,
        instrumento_postulado=instrumento_postulado[:80] if instrumento_postulado else None,
        experiencia_previa=experiencia_previa[:2000] if experiencia_previa else None,
        estado="pendiente",
    )

    # NOTA: sin video de audición (fuera del alcance v1, pendiente con el conservatorio).
    # Los campos video_nombre/video_ruta quedan dormidos en BD por compatibilidad.
    db.session.add(aspirante)
    return aspirante, None


@audiciones_bp.route("/aspirantes", methods=["POST"])
@jwt_required()
@role_required("admin", "secretaria", "profesor")
def crear_aspirante():
    aspirante, error = _validar_y_crear_aspirante(request.form, request.files)
    if error:
        return jsonify(error[0]), error[1]
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Ya existe un aspirante con esa cédula en esta convocatoria"}), 409
    return jsonify(serialize_aspirante(aspirante)), 201


@audiciones_bp.route("/inscribir-publico", methods=["POST"])
@rate_limit("inscribir-publico")
def inscribir_publico():
    """Inscripción pública de aspirantes (sin JWT), con rate-limit anti-spam."""
    aspirante, error = _validar_y_crear_aspirante(request.form, request.files)
    if error:
        return jsonify(error[0]), error[1]
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Ya existe un aspirante con esa cédula en esta convocatoria"}), 409
    return jsonify({"mensaje": "Inscripción recibida. Te contactaremos.", "id": aspirante.id}), 201


@audiciones_bp.route("/aspirantes", methods=["GET"])
@jwt_required()
@role_required("jurado", "admin", "secretaria")
def listar_aspirantes():
    from backend.utils.pagination import paginate_query
    q = Aspirante.query
    conv = request.args.get("convocatoria_id")
    estado = request.args.get("estado")
    cedula = request.args.get("cedula")
    if conv:
        try:
            q = q.filter_by(convocatoria_id=int(conv))
        except ValueError:
            return jsonify({"error": "convocatoria_id debe ser numérico"}), 400
    if estado:
        if estado not in ESTADOS_VALIDOS:
            return jsonify({"error": f"estado inválido. Válidos: {sorted(ESTADOS_VALIDOS)}"}), 400
        q = q.filter_by(estado=estado)
    if cedula:
        q = q.filter_by(cedula=cedula)
    q = q.order_by(Aspirante.inscrito_en.desc())
    result, is_paginated = paginate_query(q)
    if is_paginated:
        return jsonify({
            "items": [serialize_aspirante(a) for a in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
            "pages": result["pages"],
            "truncated": result.get("truncated", False),
        }), 200
    return jsonify([serialize_aspirante(a) for a in result]), 200


@audiciones_bp.route("/aspirantes/<int:id>", methods=["GET"])
@jwt_required()
@role_required("jurado", "admin", "secretaria")
def detalle_aspirante(id):
    a = db.session.get(Aspirante, id)
    if not a:
        return jsonify({"error": "Aspirante no encontrado"}), 404
    result = serialize_aspirante(a)
    result["puntuaciones"] = [serialize_puntuacion(p) for p in a.puntuaciones.all()]
    return jsonify(result), 200


@audiciones_bp.route("/aspirantes/<int:id>", methods=["DELETE"])
@jwt_required()
@role_required("admin", "secretaria")
def eliminar_aspirante(id):
    """Borra el expediente (y sus puntuaciones en cascada). Sin endpoint de
    borrado, el rate-limit de inscripción pública obligaba a acumular basura."""
    a = db.session.get(Aspirante, id)
    if not a:
        return jsonify({"error": "Aspirante no encontrado"}), 404
    db.session.delete(a)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "No se pudo eliminar el aspirante"}), 409
    return jsonify({"mensaje": "Aspirante eliminado"}), 200


@audiciones_bp.route("/aspirantes/<int:id>/estado", methods=["PUT"])
@jwt_required()
@role_required("admin", "secretaria")
def decidir_aspirante(id):
    """Decisión de admisión (lo único que se comunica al aspirante).

    Incluye 'pendiente' para reabrir un expediente con decisión errónea
    y permitir nueva evaluación del jurado.
    """
    DECISIONES_VALIDAS = ("pendiente", "admitido", "no_admitido", "en_espera")
    a = db.session.get(Aspirante, id)
    if not a:
        return jsonify({"error": "Aspirante no encontrado"}), 404
    data = request.get_json() or {}
    estado = (data.get("estado") or "").strip()
    if estado not in DECISIONES_VALIDAS:
        return jsonify({"error": f"estado inválido. Válidos: {list(DECISIONES_VALIDAS)}"}), 400
    a.estado = estado
    db.session.commit()
    return jsonify(serialize_aspirante(a)), 200


@audiciones_bp.route("/aspirantes/<int:id>/puntuacion", methods=["POST"])
@jwt_required()
@role_required("jurado", "admin")
def puntuar_aspirante(id):
    jurado_id = int(current_user.id)
    data = request.get_json() or {}
    aspirante = db.session.get(Aspirante, id)
    if not aspirante:
        return jsonify({"error": "Aspirante no encontrado"}), 404
    conv = db.session.get(Convocatoria, aspirante.convocatoria_id)
    if not conv or not conv.activa:
        return jsonify({"error": "La convocatoria ya está cerrada, no se puede puntuar"}), 400
    if (aspirante.estado or "pendiente") != "pendiente":
        return jsonify({"error": "El aspirante ya tiene decisión final, no se puede puntuar"}), 400

    def check_score(v, name):
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return None, f"{name} debe ser un número"
        if not (0 <= fv <= 10):
            return None, f"{name} debe estar entre 0 y 10"
        return round(fv, 2), None
    for campo in ("tecnica", "interpretacion", "afinacion", "ritmo", "presencia"):
        if campo not in data or data.get(campo) is None:
            return jsonify({"error": f"{campo} es requerido (0-10)"}), 400
    tecnica, err = check_score(data.get("tecnica"), "tecnica")
    if err: return jsonify({"error": err}), 400
    interpretacion, err = check_score(data.get("interpretacion"), "interpretacion")
    if err: return jsonify({"error": err}), 400
    afinacion, err = check_score(data.get("afinacion"), "afinacion")
    if err: return jsonify({"error": err}), 400
    ritmo, err = check_score(data.get("ritmo"), "ritmo")
    if err: return jsonify({"error": err}), 400
    presencia, err = check_score(data.get("presencia"), "presencia")
    if err: return jsonify({"error": err}), 400
    puntuacion_total = round(tecnica + interpretacion + afinacion + ritmo + presencia, 2)
    if puntuacion_total > 50:
        return jsonify({"error": "Puntuación total no puede exceder 50 (5 criterios x 10)"}), 400
    if data.get("observaciones") and len(str(data["observaciones"])) > 2000:
        return jsonify({"error": "observaciones demasiado largas (máx 2000)"}), 400

    existente = PuntuacionAudicion.query.filter_by(
        aspirante_id=id, jurado_id=jurado_id
    ).first()

    if existente:
        existente.tecnica = tecnica
        existente.interpretacion = interpretacion
        existente.afinacion = afinacion
        existente.ritmo = ritmo
        existente.presencia = presencia
        existente.observaciones = (data.get("observaciones") or "")[:2000]
        existente.puntuacion_total = puntuacion_total
        puntuacion = existente
        code = 200
    else:
        puntuacion = PuntuacionAudicion(
            aspirante_id=id,
            jurado_id=jurado_id,
            tecnica=tecnica,
            interpretacion=interpretacion,
            afinacion=afinacion,
            ritmo=ritmo,
            presencia=presencia,
            observaciones=(data.get("observaciones") or "")[:2000],
            puntuacion_total=puntuacion_total,
        )
        db.session.add(puntuacion)
        code = 201

    try:
        db.session.commit()
    except IntegrityError:
        # Doble clic: otro jurado/guard concurrente ya insertó uq_puntuacion_jurado.
        db.session.rollback()
        existente = PuntuacionAudicion.query.filter_by(aspirante_id=id, jurado_id=jurado_id).first()
        if existente:
            return jsonify(serialize_puntuacion(existente)), 200
        return jsonify({"error": "No se pudo guardar la puntuación"}), 409
    return jsonify(serialize_puntuacion(puntuacion)), code


@audiciones_bp.route("/puntuaciones/aspirante/<int:aspirante_id>", methods=["GET"])
@jwt_required()
@role_required("jurado", "admin", "secretaria")
def puntuaciones_aspirante(aspirante_id):
    puntuaciones = PuntuacionAudicion.query.filter_by(
        aspirante_id=aspirante_id
    ).all()
    return jsonify([serialize_puntuacion(p) for p in puntuaciones]), 200


@audiciones_bp.route("/audiciones", methods=["POST"])
@jwt_required()
@role_required("admin")
def programar_audicion():
    data = request.get_json() or {}
    try:
        fecha = datetime.strptime(data["fecha"], "%Y-%m-%d").date()
        hora = datetime.strptime(data["hora"], "%H:%M").time()
    except (ValueError, KeyError, TypeError):
        return jsonify({"error": "fecha (YYYY-MM-DD) y hora (HH:MM) requeridos"}), 400
    # Comparar en hora Caracas (misma base naive que envía el navegador), no en
    # UTC del contenedor: rechazaba slots válidos de las próximas 4 h y "hoy"
    # después de las 20:00 Caracas.
    ahora = _ahora_ven_naive()
    if fecha < ahora.date():
        return jsonify({"error": "No se puede programar una audición en el pasado"}), 400
    if fecha == ahora.date():
        if datetime.combine(fecha, hora) <= ahora:
            return jsonify({"error": "No se puede programar una audición en hora pasada"}), 400
    try:
        agrupacion_id = int(data.get("agrupacion_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "agrupacion_id debe ser numérico"}), 400
    if not db.session.get(Agrupacion, agrupacion_id):
        return jsonify({"error": "Agrupación no encontrada"}), 404
    convocatoria_id = data.get("convocatoria_id")
    if convocatoria_id is not None:
        try:
            convocatoria_id = int(convocatoria_id)
        except (TypeError, ValueError):
            return jsonify({"error": "convocatoria_id debe ser numérico"}), 400
        conv = db.session.get(Convocatoria, convocatoria_id)
        if not conv:
            return jsonify({"error": "Convocatoria no encontrada"}), 404
        if not conv.activa:
            return jsonify({"error": "La convocatoria está inactiva"}), 400
    # Normalizar jurados: acepta lista [1,2], string "1,2", o jurados
    jurado_ids_raw = data.get("jurado_ids", data.get("jurados_ids", data.get("jurados", "")))
    jurado_ids_str = ""
    jurados_objs = []
    if isinstance(jurado_ids_raw, list):
        ids = []
        for x in jurado_ids_raw:
            try:
                ids.append(int(x))
            except (TypeError, ValueError):
                return jsonify({"error": "jurado_ids debe contener IDs numéricos"}), 400
        jurado_ids_str = ",".join(str(i) for i in ids)
        if ids:
            jurados_objs = Usuario.query.filter(
                Usuario.id.in_(ids), Usuario.role.in_(["jurado", "admin"])
            ).all()
            if len(jurados_objs) != len(set(ids)):
                return jsonify({"error": "Uno o más jurados no existen o no tienen rol válido (jurado/admin)"}), 400
    elif isinstance(jurado_ids_raw, str) and jurado_ids_raw.strip():
        jurado_ids_str = jurado_ids_raw
        ids = [s.strip() for s in jurado_ids_raw.split(",") if s.strip()]
        try:
            ids = [int(i) for i in ids]
        except ValueError:
            return jsonify({"error": "jurado_ids debe contener IDs numéricos"}), 400
        if ids:
            jurados_objs = Usuario.query.filter(
                Usuario.id.in_(ids), Usuario.role.in_(["jurado", "admin"])
            ).all()
            if len(jurados_objs) != len(set(ids)):
                return jsonify({"error": "Uno o más jurados no existen o no tienen rol válido (jurado/admin)"}), 400
    audicion = Audicion(
        convocatoria_id=convocatoria_id,
        agrupacion_id=agrupacion_id,
        fecha=fecha,
        hora=hora,
        lugar=(data.get("lugar") or "")[:200],
        jurado_ids=jurado_ids_str,
    )
    for j in jurados_objs:
        audicion.jurados.append(j)
    db.session.add(audicion)
    db.session.commit()
    return jsonify({"id": audicion.id, "mensaje": "Audición programada", "jurados": [j.id for j in audicion.jurados]}), 201


@audiciones_bp.route("/audiciones", methods=["GET"])
@jwt_required()
@role_required("jurado", "admin", "secretaria", "profesor")
def listar_audiciones():
    from backend.utils.pagination import paginate_query
    q = Audicion.query
    agrupacion_id = request.args.get("agrupacion_id", type=int)
    if agrupacion_id:
        q = q.filter_by(agrupacion_id=agrupacion_id)
    convocatoria_id = request.args.get("convocatoria_id", type=int)
    if convocatoria_id:
        q = q.filter_by(convocatoria_id=convocatoria_id)
    q = q.order_by(Audicion.fecha.desc())
    result, is_paginated = paginate_query(q)
    items = result["items"] if is_paginated else result

    def _ser(a):
        jurados_ids = [j.id for j in a.jurados] if hasattr(a, 'jurados') and a.jurados else []
        if not jurados_ids and a.jurado_ids:
            jurados_ids = [int(x) for x in a.jurado_ids.split(",") if x.strip().isdigit()]
        return {
            "id": a.id,
            "convocatoria_id": a.convocatoria_id,
            "agrupacion_id": a.agrupacion_id,
            "agrupacion_nombre": a.agrupacion.nombre if a.agrupacion else None,
            "fecha": str(a.fecha),
            "hora": str(a.hora),
            "lugar": a.lugar,
            "jurado_ids": a.jurado_ids,
            "jurados": jurados_ids,
        }

    if is_paginated:
        return jsonify({
            "items": [_ser(a) for a in items],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
            "pages": result["pages"],
            "truncated": result.get("truncated", False),
        }), 200
    return jsonify([_ser(a) for a in items]), 200
