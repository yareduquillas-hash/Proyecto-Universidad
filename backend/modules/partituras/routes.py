import os
import re
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required, current_user
from werkzeug.utils import secure_filename

from backend.extensions.db import db
from backend.models import Partitura, Agrupacion, Instrumento
from backend.utils.auth import role_required, puede_gestionar_agrupacion

partituras_bp = Blueprint("partituras", __name__, url_prefix="/api/v1/partituras")

ALLOWED_EXTENSIONS = {"pdf"}
# Lectura amplia: admin/secretaria ven todas las agrupaciones (paridad con
# cronograma ROLES_LECTURA_AMPLIA). Profesor/alumno solo las suyas.
ROLES_LECTURA_AMPLIA = ["admin", "secretaria"]


def _agrupaciones_propias():
    return [a.id for a in getattr(current_user, "agrupaciones", []) or []]


def _puede_ver_agrupacion(agrupacion_id):
    if current_user.role in ROLES_LECTURA_AMPLIA:
        return True
    return agrupacion_id in _agrupaciones_propias()


def _max_pdf_bytes():
    try:
        return int(current_app.config.get("MAX_PDF_MB", 10)) * 1024 * 1024
    except Exception:
        return 10 * 1024 * 1024


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def is_valid_pdf(file_storage):
    """Valida magic bytes de PDF. Lee los primeros bytes sin consumir el stream."""
    try:
        pos = file_storage.tell()
    except Exception:
        pos = 0
    try:
        header = file_storage.read(5)
        file_storage.seek(pos)
        return header.startswith(b"%PDF")
    except Exception:
        try:
            file_storage.seek(pos)
        except Exception:
            pass
        return False


def _escape_like(s):
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _resolve_archivo(partitura):
    """Resuelve la ruta en disco: soporta filas legacy (absoluta) y nuevas (nombre único)."""
    ruta = partitura.archivo_ruta or ""
    if os.path.isabs(ruta) and os.path.exists(ruta):
        return ruta
    base = current_app.config.get("UPLOAD_FOLDER")
    candidatos = []
    if base:
        candidatos.append(os.path.join(base, os.path.basename(ruta)))
        candidatos.append(os.path.join(base, partitura.archivo_nombre or ""))
    for c in candidatos:
        if c and os.path.exists(c):
            return c
    return candidatos[0] if candidatos else ruta


def _slug(texto, default="partitura"):
    base = re.sub(r"[^A-Za-z0-9ÁÉÍÓÚáéíóúÑñ _-]+", "", texto or "").strip().replace(" ", "_")
    return (base or default)[:80]


def serialize_partitura(p):
    return {
        "id": p.id,
        "titulo": p.titulo,
        "obra": p.obra,
        "compositor": p.compositor,
        "catedra": p.catedra,
        "agrupacion_id": p.agrupacion_id,
        "agrupacion_nombre": p.agrupacion.nombre if p.agrupacion else None,
        "instrumento_id": p.instrumento_id,
        "instrumento_nombre": p.instrumento.nombre if p.instrumento else None,
        "archivo_nombre": p.archivo_nombre,
        "fecha_subida": p.fecha_subida.isoformat() if p.fecha_subida else None,
        "subido_por_nombre": (
            f"{p.uploader.nombre} {p.uploader.apellido}" if p.uploader else None
        ),
    }


@partituras_bp.get("/filtros")
@jwt_required()
def obtener_filtros():
    catedras = sorted(r[0] for r in db.session.query(Partitura.catedra).filter(
        Partitura.activo.is_(True), Partitura.catedra.isnot(None)).distinct().all() if r[0])
    obras = sorted(r[0] for r in db.session.query(Partitura.obra).filter(
        Partitura.activo.is_(True), Partitura.obra.isnot(None)).distinct().all() if r[0])
    compositores = sorted(r[0] for r in db.session.query(Partitura.compositor).filter(
        Partitura.activo.is_(True), Partitura.compositor.isnot(None)).distinct().all() if r[0])
    agrupaciones = [
        {"id": a.id, "nombre": a.nombre}
        for a in Agrupacion.query.filter_by(activa=True).order_by(Agrupacion.nombre).all()
    ]
    instrumentos = [
        {"id": i.id, "nombre": i.nombre}
        for i in Instrumento.query.order_by(Instrumento.nombre).all()
    ]
    return jsonify(
        {
            "catedras": catedras,
            "obras": obras,
            "compositores": compositores,
            "agrupaciones": agrupaciones,
            "instrumentos": instrumentos,
        }
    ), 200


@partituras_bp.post("/upload")
@jwt_required()
@role_required("profesor", "secretaria", "admin")
def upload_partitura():
    if "archivo" not in request.files:
        return jsonify({"error": "archivo es requerido"}), 400

    archivo = request.files["archivo"]
    if archivo.filename == "":
        return jsonify({"error": "archivo sin nombre"}), 400

    if not allowed_file(archivo.filename):
        return jsonify({"error": "Solo se permiten archivos PDF"}), 400

    if not is_valid_pdf(archivo.stream if hasattr(archivo, 'stream') else archivo):
        return jsonify({"error": "El archivo no es un PDF válido (cabecera %PDF no encontrada)"}), 400

    max_pdf = _max_pdf_bytes()
    try:
        archivo.seek(0, os.SEEK_END)
        size = archivo.tell()
        archivo.seek(0)
        if size > max_pdf:
            return jsonify({"error": f"PDF demasiado grande ({size//1024}KB). Máximo {max_pdf//1024//1024}MB"}), 400
        if size == 0:
            return jsonify({"error": "Archivo vacío"}), 400
    except Exception:
        pass

    titulo = (request.form.get("titulo") or "").strip()
    obra = (request.form.get("obra") or "").strip()
    compositor = (request.form.get("compositor") or "").strip()
    catedra = (request.form.get("catedra") or "").strip()
    agrupacion_id = request.form.get("agrupacion_id")
    instrumento_id = request.form.get("instrumento_id")

    if not titulo or len(titulo) < 3:
        return jsonify({"error": "titulo es requerido (mín 3 caracteres)"}), 400
    if not agrupacion_id:
        return jsonify({"error": "titulo y agrupacion_id son requeridos"}), 400

    try:
        agrupacion_id_int = int(agrupacion_id)
    except (ValueError, TypeError):
        return jsonify({"error": "agrupacion_id debe ser numérico"}), 400
    if not db.session.get(Agrupacion, agrupacion_id_int):
        return jsonify({"error": "Agrupación no encontrada"}), 404
    if not puede_gestionar_agrupacion(current_user, agrupacion_id_int):
        return jsonify({"error": "No perteneces a esa agrupación"}), 403

    instrumento_id_int = None
    if instrumento_id:
        try:
            instrumento_id_int = int(instrumento_id)
        except (ValueError, TypeError):
            return jsonify({"error": "instrumento_id debe ser numérico"}), 400
        if not db.session.get(Instrumento, instrumento_id_int):
            return jsonify({"error": "Instrumento no encontrado"}), 404

    nombre_seguro = secure_filename(archivo.filename)
    if not nombre_seguro:
        return jsonify({"error": "Nombre de archivo inválido"}), 400
    nombre_unico = f"{uuid.uuid4().hex}_{nombre_seguro}"

    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
        return jsonify({"error": "UPLOAD_FOLDER no configurado"}), 500

    os.makedirs(upload_folder, exist_ok=True)
    ruta_destino = os.path.join(upload_folder, nombre_unico)
    if not os.path.abspath(ruta_destino).startswith(os.path.abspath(upload_folder)):
        return jsonify({"error": "Ruta de archivo inválida"}), 400
    archivo.save(ruta_destino)

    partitura = Partitura(
        titulo=titulo[:150],
        obra=obra[:150] or None,
        compositor=compositor[:150] or None,
        catedra=catedra[:80] or None,
        agrupacion_id=agrupacion_id_int,
        instrumento_id=instrumento_id_int,
        archivo_nombre=nombre_unico,
        archivo_ruta=nombre_unico,  # relativa: se resuelve contra UPLOAD_FOLDER
        subido_por=int(current_user.id),
        fecha_subida=datetime.utcnow(),
        activo=True,
    )

    db.session.add(partitura)
    db.session.commit()

    return jsonify(serialize_partitura(partitura)), 201


@partituras_bp.get("/")
@jwt_required()
def listar_partituras():
    query = Partitura.query.filter_by(activo=True)

    agrupacion_id = request.args.get("agrupacion_id", type=int)
    if agrupacion_id:
        if not _puede_ver_agrupacion(agrupacion_id):
            return jsonify({"error": "No perteneces a esa agrupación"}), 403
        query = query.filter(Partitura.agrupacion_id == agrupacion_id)
    elif current_user.role not in ROLES_LECTURA_AMPLIA:
        mias = _agrupaciones_propias()
        if not mias:
            return jsonify([]), 200
        query = query.filter(Partitura.agrupacion_id.in_(mias))

    instrumento_id = request.args.get("instrumento_id", type=int)
    if instrumento_id:
        query = query.filter(Partitura.instrumento_id == instrumento_id)

    catedra = request.args.get("catedra")
    if catedra:
        query = query.filter(Partitura.catedra.ilike(f"%{_escape_like(catedra)}%", escape="\\"))

    obra = request.args.get("obra")
    if obra:
        query = query.filter(Partitura.obra.ilike(f"%{_escape_like(obra)}%", escape="\\"))

    compositor = request.args.get("compositor")
    if compositor:
        query = query.filter(Partitura.compositor.ilike(f"%{_escape_like(compositor)}%", escape="\\"))

    query = query.order_by(Partitura.fecha_subida.desc())
    from backend.utils.pagination import paginate_query
    result, is_paginated = paginate_query(query)
    if is_paginated:
        return jsonify({
            "items": [serialize_partitura(p) for p in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
            "pages": result["pages"],
            "truncated": result.get("truncated", False),
        }), 200
    return jsonify([serialize_partitura(p) for p in result]), 200


def _partitura_visible_o_error(id):
    """Devuelve (partitura, None) si existe y el rol puede verla; si no, (None, respuesta)."""
    partitura = Partitura.query.filter_by(id=id, activo=True).first()
    if not partitura:
        return None, (jsonify({"error": "Partitura no encontrada"}), 404)
    if not _puede_ver_agrupacion(partitura.agrupacion_id):
        return None, (jsonify({"error": "No perteneces a esa agrupación"}), 403)
    return partitura, None


@partituras_bp.get("/<int:id>")
@jwt_required()
def obtener_partitura(id):
    partitura, err = _partitura_visible_o_error(id)
    if err:
        return err
    return jsonify(serialize_partitura(partitura)), 200


@partituras_bp.get("/<int:id>/descargar")
@jwt_required()
def descargar_partitura(id):
    partitura, err = _partitura_visible_o_error(id)
    if err:
        return err

    ruta = _resolve_archivo(partitura)
    if not ruta or not os.path.exists(ruta):
        return jsonify({"error": "Archivo no encontrado en disco"}), 404

    resp = send_file(
        ruta,
        as_attachment=True,
        download_name=f"{_slug(partitura.titulo)}.pdf",
        mimetype="application/pdf",
    )
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


@partituras_bp.get("/<int:id>/preview")
@jwt_required()
def preview_partitura(id):
    partitura, err = _partitura_visible_o_error(id)
    if err:
        return err

    ruta = _resolve_archivo(partitura)
    if not ruta or not os.path.exists(ruta):
        return jsonify({"error": "Archivo no encontrado en disco"}), 404

    resp = send_file(
        ruta,
        as_attachment=False,
        download_name=f"{_slug(partitura.titulo)}.pdf",
        mimetype="application/pdf",
    )
    resp.headers["Cache-Control"] = "private, no-store"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    return resp


@partituras_bp.delete("/<int:id>")
@jwt_required()
@role_required("profesor", "secretaria", "admin")
def eliminar_partitura(id):
    partitura = Partitura.query.filter_by(id=id, activo=True).first()
    if not partitura:
        return jsonify({"error": "Partitura no encontrada"}), 404
    if not puede_gestionar_agrupacion(current_user, partitura.agrupacion_id):
        return jsonify({"error": "No perteneces a esa agrupación"}), 403

    partitura.activo = False
    db.session.commit()
    # El archivo se conserva para auditoría; programar limpieza con tarea cron.
    return jsonify({"mensaje": "Partitura eliminada (soft delete)", "id": id}), 200
