import csv
import io

from flask import Blueprint, request, jsonify, Response, current_app
from flask_jwt_extended import jwt_required, current_user
from backend.extensions.db import db
from backend.models import Alumno, Agrupacion, Asistencia, Usuario
from backend.utils.auth import role_required, puede_gestionar_agrupacion
from sqlalchemy.exc import IntegrityError
from datetime import datetime, date, timedelta

asistencia_bp = Blueprint("asistencia", __name__, url_prefix="/api/v1/asistencia")

ESTADOS_VALIDOS = ["presente", "ausente", "justificado", "retraso"]


def _umbral():
    try:
        return int(current_app.config.get("UMBRAL_INASISTENCIA_PERCENT", 25))
    except Exception:
        return 25


def serialize_asistencia(a):
    return {
        "id": a.id,
        "alumno_id": a.alumno_id,
        "agrupacion_id": a.agrupacion_id,
        "fecha": a.fecha.isoformat() if a.fecha else None,
        "estado": a.estado,
        "observaciones": a.observaciones,
        "registrado_por": a.registrado_por,
        "creado_en": a.creado_en.isoformat() if a.creado_en else None,
    }


def _alumnos_de_agrupacion(agrupacion_id):
    agrupacion = db.session.get(Agrupacion, agrupacion_id)
    if not agrupacion:
        return None, []
    alumnos = []
    for usuario in agrupacion.usuarios:
        if not usuario.activo:
            continue
        if usuario.role == "alumno" and getattr(usuario, "alumno", None):
            alumnos.append(usuario.alumno)
    return agrupacion, alumnos


def _agrupacion_ids_de_alumno(alumno):
    if not alumno or not alumno.usuario:
        return set()
    return {a.id for a in alumno.usuario.agrupaciones}


@asistencia_bp.post("/registrar")
@jwt_required()
@role_required("profesor", "secretaria", "admin")
def registrar_asistencia():
    data = request.get_json() or {}
    agrupacion_id = data.get("agrupacion_id")
    fecha_str = data.get("fecha")
    registros = data.get("registros") or []

    if not agrupacion_id or not fecha_str or not isinstance(registros, list):
        return jsonify({"error": "agrupacion_id, fecha y registros son requeridos"}), 400
    if len(registros) > 500:
        return jsonify({"error": "Máximo 500 registros por llamada"}), 400

    try:
        agrupacion_id = int(agrupacion_id)
    except (TypeError, ValueError):
        return jsonify({"error": "agrupacion_id debe ser numérico"}), 400

    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "fecha debe tener formato YYYY-MM-DD"}), 400

    if fecha > date.today():
        return jsonify({"error": "No se puede registrar asistencia en fecha futura"}), 400

    # Ventana de corrección: profesor/secretaria hasta 7 días atrás; histórico
    # más antiguo solo admin (decisión D5). Evita reescritura silenciosa del pasado.
    if fecha < date.today() - timedelta(days=7) and current_user.role != "admin":
        return jsonify({"error": "Solo un administrador puede modificar asistencias con más de 7 días"}), 403

    agrupacion = db.session.get(Agrupacion, agrupacion_id)
    if not agrupacion:
        return jsonify({"error": "Agrupación no encontrada"}), 400

    if not puede_gestionar_agrupacion(current_user, agrupacion_id):
        return jsonify({"error": "No perteneces a esa agrupación"}), 403

    usuario_id = current_user.id
    miembros = _agrupacion_ids_de_alumno
    _, alumnos_grupo = _alumnos_de_agrupacion(agrupacion_id)
    ids_validos = {a.id for a in alumnos_grupo}

    total = 0
    errores = []
    for idx, reg in enumerate(registros):
        if not isinstance(reg, dict):
            errores.append({"index": idx, "error": "registro inválido"})
            continue
        alumno_id_raw = reg.get("alumno_id")
        estado = reg.get("estado")
        observaciones = reg.get("observaciones")
        try:
            alumno_id = int(alumno_id_raw)
        except (TypeError, ValueError):
            errores.append({"index": idx, "alumno_id": alumno_id_raw, "error": "alumno_id y estado válido requeridos"})
            continue
        if observaciones and len(str(observaciones)) > 500:
            errores.append({"index": idx, "alumno_id": alumno_id, "error": "observaciones máx 500 caracteres"})
            continue
        if estado not in ESTADOS_VALIDOS:
            errores.append({"index": idx, "alumno_id": alumno_id, "error": "alumno_id y estado válido requeridos"})
            continue
        alumno = db.session.get(Alumno, alumno_id)
        if not alumno:
            errores.append({"index": idx, "alumno_id": alumno_id, "error": "Alumno no encontrado"})
            continue
        # Pertenencia: el alumno debe estar en la agrupación y activo
        if alumno_id not in ids_validos:
            errores.append({"index": idx, "alumno_id": alumno_id, "error": "El alumno no pertenece a la agrupación"})
            continue

        existente = Asistencia.query.filter_by(
            alumno_id=alumno_id, agrupacion_id=agrupacion_id, fecha=fecha
        ).first()
        if existente:
            existente.estado = estado
            existente.observaciones = observaciones
            existente.registrado_por = usuario_id
        else:
            db.session.add(
                Asistencia(
                    alumno_id=alumno_id,
                    agrupacion_id=agrupacion_id,
                    fecha=fecha,
                    estado=estado,
                    observaciones=observaciones,
                    registrado_por=usuario_id,
                )
            )
        total += 1

    if total == 0:
        db.session.rollback()
        return jsonify({"error": "Ningún registro válido", "errores": errores}), 400
    try:
        db.session.commit()
    except IntegrityError:
        # Doble clic / carrera: uq_asistencia_dia ya existía; tratar como éxito.
        db.session.rollback()
        return jsonify({"mensaje": "Asistencia registrada", "total": total, "errores": errores}), 200
    return jsonify({"mensaje": "Asistencia registrada", "total": total, "errores": errores}), 201


@asistencia_bp.get("/agrupacion/<int:agrupacion_id>/fecha/<fecha>")
@jwt_required()
@role_required("profesor", "secretaria", "admin")
def listar_por_fecha(agrupacion_id, fecha):
    try:
        fecha_dt = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "fecha debe tener formato YYYY-MM-DD"}), 400

    if not puede_gestionar_agrupacion(current_user, agrupacion_id):
        return jsonify({"error": "No perteneces a esa agrupación"}), 403

    agrupacion, alumnos = _alumnos_de_agrupacion(agrupacion_id)
    if agrupacion is None:
        return jsonify({"error": "Agrupación no encontrada"}), 404

    resultado = []
    for alumno in alumnos:
        registro = Asistencia.query.filter_by(
            alumno_id=alumno.id, agrupacion_id=agrupacion_id, fecha=fecha_dt
        ).first()
        resultado.append(
            {
                "id": alumno.id,
                "alumno_id": alumno.id,
                "nombre": f"{alumno.usuario.nombre} {alumno.usuario.apellido}" if alumno.usuario else "",
                "cedula": alumno.usuario.cedula if alumno.usuario else "",
                "estado": registro.estado if registro else "no_registrado",
                "observaciones": registro.observaciones if registro else None,
                "registro_id": registro.id if registro else None,
            }
        )
    return jsonify(resultado), 200


@asistencia_bp.get("/alumno/<int:alumno_id>")
@jwt_required()
def historial_alumno(alumno_id):
    current_u = current_user
    param = alumno_id
    # Resolución sin ambigüedad: se acepta Alumno.id (canónico) o Usuario.id
    # (compat). Si ambos existen y difieren, el canónico es Alumno.id, salvo
    # para el propio alumno que siempre resuelve a su ficha con cualquiera.
    alumno_by_id = db.session.get(Alumno, param)
    alumno_by_usuario = Alumno.query.filter_by(usuario_id=param).first()
    if current_u.role == "alumno":
        propio = current_u.alumno.id if getattr(current_u, "alumno", None) else None
        propio_usuario_id = current_u.id
        if propio is None:
            return jsonify({"error": "No tienes permisos para ver el historial de otro alumno"}), 403
        if param == propio:
            alumno = db.session.get(Alumno, propio)
            alumno_id = propio
        elif param == propio_usuario_id:
            alumno = db.session.get(Alumno, propio)
            alumno_id = propio
        else:
            return jsonify({"error": "No tienes permisos para ver el historial de otro alumno"}), 403
    elif current_u.role not in ("profesor", "secretaria", "admin"):
        return jsonify({"error": "Permisos insuficientes"}), 403
    else:
        if alumno_by_id is not None:
            alumno = alumno_by_id
            alumno_id = alumno.id
        elif alumno_by_usuario is not None:
            alumno = alumno_by_usuario
            alumno_id = alumno.id
        else:
            return jsonify({"error": "Alumno no encontrado"}), 404
        # Profesor solo sus agrupaciones (paridad con reporte/exportar/por-fecha)
        if current_u.role == "profesor":
            mias = {a.id for a in getattr(current_u, "agrupaciones", []) or []}
            suyas = _agrupacion_ids_de_alumno(alumno)
            if not (mias & suyas):
                return jsonify({"error": "No perteneces a esa agrupación"}), 403

    if alumno is None:
        alumno = db.session.get(Alumno, alumno_id)
    if not alumno:
        return jsonify({"error": "Alumno no encontrado"}), 404

    registros = (
        Asistencia.query.filter_by(alumno_id=alumno_id)
        .order_by(Asistencia.fecha.desc())
        .limit(500)
        .all()
    )
    total_reales = Asistencia.query.filter_by(alumno_id=alumno_id).count()
    truncado = total_reales > len(registros)
    total = len(registros)
    inasistencias = sum(1 for r in registros if r.estado == "ausente")
    presentes = sum(1 for r in registros if r.estado == "presente")
    justificados = sum(1 for r in registros if r.estado == "justificado")
    retrasos = sum(1 for r in registros if r.estado == "retraso")

    # Asistencia efectiva incluye justificados y retrasos (decisión D8).
    asistencias_efectivas = presentes + justificados + retrasos
    porcentaje_inasistencias = (inasistencias / total * 100) if total else 0.0
    porcentaje_asistencia = (asistencias_efectivas / total * 100) if total else 0.0

    en_riesgo = porcentaje_inasistencias >= _umbral()

    return jsonify(
        {
            "alumno_id": alumno.id,
            "nombre": f"{alumno.usuario.nombre} {alumno.usuario.apellido}" if alumno.usuario else None,
            "historial": [serialize_asistencia(r) for r in registros],
            "total_registros": total,
            "total_reales": total_reales,
            "truncado": truncado,
            "inasistencias_acumuladas": inasistencias,
            "presentes": presentes,
            "justificados": justificados,
            "retrasos": retrasos,
            "porcentaje_asistencia": round(porcentaje_asistencia, 2),
            "porcentaje_inasistencias": round(porcentaje_inasistencias, 2),
            "en_riesgo": en_riesgo,
        }
    ), 200


def _celda_csv(valor):
    """Neutraliza formula injection en Excel/Sheets (=, +, -, @ al inicio)."""
    s = "" if valor is None else str(valor)
    if s.startswith(("=", "+", "-", "@")):
        return "'" + s
    return s


def _aplicar_filtro_fechas(query):
    fd = request.args.get("fecha_desde")
    fh = request.args.get("fecha_hasta")
    if fd:
        try:
            query = query.filter(Asistencia.fecha >= datetime.strptime(fd, "%Y-%m-%d").date())
        except ValueError:
            return None, "fecha_desde debe tener formato YYYY-MM-DD"
    if fh:
        try:
            query = query.filter(Asistencia.fecha <= datetime.strptime(fh, "%Y-%m-%d").date())
        except ValueError:
            return None, "fecha_hasta debe tener formato YYYY-MM-DD"
    return query, None


@asistencia_bp.get("/reporte/<int:agrupacion_id>")
@jwt_required()
@role_required("profesor", "secretaria", "admin")
def reporte_agrupacion(agrupacion_id):
    if not puede_gestionar_agrupacion(current_user, agrupacion_id):
        return jsonify({"error": "No perteneces a esa agrupación"}), 403
    agrupacion, alumnos = _alumnos_de_agrupacion(agrupacion_id)
    if agrupacion is None:
        return jsonify({"error": "Agrupación no encontrada"}), 404

    query, err = _aplicar_filtro_fechas(Asistencia.query.filter_by(agrupacion_id=agrupacion_id))
    if err:
        return jsonify({"error": err}), 400
    todas = query.all()
    from collections import defaultdict
    agrupadas = defaultdict(list)
    for r in todas:
        agrupadas[r.alumno_id].append(r)

    reporte = []
    for alumno in alumnos:
        registros = agrupadas.get(alumno.id, [])
        total = len(registros)
        inasistencias = sum(1 for r in registros if r.estado == "ausente")
        presentes = sum(1 for r in registros if r.estado == "presente")
        justificados_rep = sum(1 for r in registros if r.estado == "justificado")
        retrasos_rep = sum(1 for r in registros if r.estado == "retraso")
        porcentaje_asistencia = ((presentes + justificados_rep + retrasos_rep) / total * 100) if total else 0.0
        porcentaje_inasistencias = (inasistencias / total * 100) if total else 0.0
        en_riesgo = porcentaje_inasistencias >= _umbral()

        reporte.append(
            {
                "id": alumno.id,
                "nombre": f"{alumno.usuario.nombre} {alumno.usuario.apellido}" if alumno.usuario else None,
                "cedula": alumno.usuario.cedula if alumno.usuario else None,
                "total_registros": total,
                "porcentaje_asistencia": round(porcentaje_asistencia, 2),
                "porcentaje_inasistencias": round(porcentaje_inasistencias, 2),
                "en_riesgo": en_riesgo,
            }
        )
    return jsonify(reporte), 200


@asistencia_bp.get("/exportar/<int:agrupacion_id>")
@jwt_required()
@role_required("profesor", "secretaria", "admin")
def exportar_csv(agrupacion_id):
    if not puede_gestionar_agrupacion(current_user, agrupacion_id):
        return jsonify({"error": "No perteneces a esa agrupación"}), 403
    agrupacion = db.session.get(Agrupacion, agrupacion_id)
    if not agrupacion:
        return jsonify({"error": "Agrupación no encontrada"}), 404

    query, err = _aplicar_filtro_fechas(
        Asistencia.query.filter_by(agrupacion_id=agrupacion_id).order_by(Asistencia.fecha.asc())
    )
    if err:
        return jsonify({"error": err}), 400
    registros = query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "alumno_id", "nombre", "cedula", "agrupacion_id", "fecha", "estado", "observaciones"])
    for r in registros:
        nombre = f"{r.alumno.usuario.nombre} {r.alumno.usuario.apellido}" if r.alumno and r.alumno.usuario else ""
        cedula = r.alumno.usuario.cedula if r.alumno and r.alumno.usuario else ""
        writer.writerow(
            [
                r.id,
                r.alumno_id,
                _celda_csv(nombre),
                _celda_csv(cedula),
                r.agrupacion_id,
                r.fecha.isoformat() if r.fecha else "",
                _celda_csv(r.estado),
                _celda_csv(r.observaciones or ""),
            ]
        )

    csv_data = output.getvalue()
    output.close()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=asistencia_agrupacion_{agrupacion_id}.csv",
            "Cache-Control": "private, no-store",
        },
    )
