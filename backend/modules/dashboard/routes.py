from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from backend.extensions.db import db
from backend.models import Usuario, Agrupacion, Asistencia, Aspirante, PuntuacionAudicion
from backend.utils.auth import role_required

dashboard_bp = Blueprint("inicio", __name__, url_prefix="/api/v1/dashboard")


@dashboard_bp.get("/stats")
@jwt_required()
@role_required("admin")
def dashboard_stats():
    from sqlalchemy import func
    total_usuarios = Usuario.query.filter_by(activo=True).count()
    total_agrupaciones = Agrupacion.query.filter_by(activa=True).count()

    total_asistencias = db.session.query(func.count(Asistencia.id)).scalar() or 0
    presentes = db.session.query(func.count(Asistencia.id)).filter(
        Asistencia.estado.in_(["presente", "justificado", "retraso"])
    ).scalar() or 0
    pct_asistencia = round(presentes / total_asistencias * 100, 1) if total_asistencias else 0.0

    # Pendientes sin evaluar con una sola query (evita N+1)
    pendientes_sin_evaluar = db.session.query(func.count(Aspirante.id)).outerjoin(
        PuntuacionAudicion, PuntuacionAudicion.aspirante_id == Aspirante.id
    ).filter(Aspirante.estado == "pendiente", PuntuacionAudicion.id.is_(None)).scalar() or 0

    return jsonify({
        "total_usuarios": total_usuarios,
        "total_agrupaciones": total_agrupaciones,
        "porcentaje_asistencia_global": pct_asistencia,
        "postulaciones_pendientes": pendientes_sin_evaluar,
    }), 200
