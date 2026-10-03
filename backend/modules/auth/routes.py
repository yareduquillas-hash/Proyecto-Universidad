import hashlib
import os
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    jwt_required, create_access_token, create_refresh_token,
    get_jwt_identity, get_jwt, current_user,
)
from backend.extensions.db import db
from backend.models import Usuario, PasswordResetCode, TokenBloqueado
from werkzeug.security import generate_password_hash, check_password_hash
from backend.utils.rate_limit import (
    rate_limit, rate_limit_check_only, rate_limit_record_failure, rate_limit_clear_current,
)
from backend.utils.validators import validate_password

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


def _tokens_for(usuario):
    claims = {
        "role": usuario.role,
        "nombre": f"{usuario.nombre} {usuario.apellido}",
        "pv": usuario.password_version or 0,
    }
    return (
        create_access_token(identity=str(usuario.id), additional_claims=claims),
        create_refresh_token(identity=str(usuario.id), additional_claims={"pv": usuario.password_version or 0}),
    )


def _find_user_by_login(value):
    # Coerce a str: si el cliente envía cedula/codigo numérico en JSON,
    # (int or "").strip() lanzaba AttributeError -> 500. Con str() devuelve
    # 400/200 genérico según corresponda, sin cambiar anti-enumeración.
    value = str(value or "").strip()
    if not value:
        return None
    u = Usuario.query.filter_by(cedula=value).first()
    if u:
        return u
    return Usuario.query.filter(db.func.lower(Usuario.email) == value.lower()).first()


def _send_reset_code(email, codigo):
    """Envía el código por SMTP si está configurado; si no, lo loguea (solo dev)."""
    subject = "Recuperación de contraseña — Núcleo Los Teques"
    body = (
        f"Tu código de recuperación es: {codigo}\n"
        f"Vence en {current_app.config.get('PASSWORD_RESET_TTL_MIN', 15)} minutos. "
        "Si no lo solicitaste, ignora este mensaje."
    )
    host = current_app.config.get("SMTP_HOST")
    if not host:
        # En producción NUNCA loguear el código: quedaría en docker logs y
        # cualquiera con acceso a logs podría resetear cuentas. Solo desarrollo.
        if os.getenv("FLASK_ENV") == "production":
            current_app.logger.error(
                "SMTP no configurado en producción — recuperación por email inoperativa "
                "(el usuario recibe 200 genérico pero nunca llega código). "
                "Configura SMTP_* o usa reset asistido presencial."
            )
            return False
        current_app.logger.warning("SMTP no configurado — código de reset (solo desarrollo): %s -> %s", email, codigo)
        print(f"[DEV] Código de recuperación para {email}: {codigo}")
        return False
    try:
        import smtplib
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = current_app.config.get("SMTP_FROM")
        msg["To"] = email
        msg.set_content(body)
        with smtplib.SMTP(host, current_app.config.get("SMTP_PORT", 587), timeout=10) as s:
            if current_app.config.get("SMTP_USE_TLS"):
                s.starttls()
            if current_app.config.get("SMTP_USER"):
                s.login(current_app.config.get("SMTP_USER"), current_app.config.get("SMTP_PASSWORD", ""))
            s.send_message(msg)
        return True
    except Exception as e:
        current_app.logger.error("Fallo envío SMTP: %s", e)
        return False


@auth_bp.route("/login", methods=["POST"])
def login():
    # Solo cuenta fallos: revisa sin registrar, registra en cada fallo, limpia en éxito.
    blocked = rate_limit_check_only("login")
    if blocked is not None:
        return blocked
    data = request.get_json() or {}
    cedula = (data.get("cedula") or "").strip()
    password = data.get("password") or ""

    if not cedula or not password:
        rate_limit_record_failure("login")
        return jsonify({"error": "Cédula y contraseña son requeridas"}), 400

    usuario = Usuario.query.filter_by(cedula=cedula).first()
    if not usuario or not usuario.activo:
        rate_limit_record_failure("login")
        return jsonify({"error": "Cédula o contraseña incorrectos"}), 401

    if not usuario.password_set or not usuario.password_hash:
        rate_limit_record_failure("login")
        return jsonify({
            "error": "Su usuario está registrado por Cédula pero aún no ha creado su contraseña. Por favor use la opción 'Activar Cuenta' para registrar su clave de acceso.",
            "requiere_activacion": True,
            "cedula": usuario.cedula,
        }), 401

    if not check_password_hash(usuario.password_hash, password):
        rate_limit_record_failure("login")
        return jsonify({"error": "Cédula o contraseña incorrectos"}), 401

    rate_limit_clear_current()
    access_token, refresh_token = _tokens_for(usuario)
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "role": usuario.role,
        "nombre": f"{usuario.nombre} {usuario.apellido}",
        "id": usuario.id,
        "requiere_cambio_clave": bool(usuario.requiere_cambio_clave),
    }), 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    user = current_user
    if not user:
        return jsonify({"error": "Sesión inválida"}), 401
    access_token, _ = _tokens_for(user)
    # _tokens_for genera también refresh; aquí solo rotamos access
    return jsonify({"access_token": access_token}), 200


@auth_bp.route("/verificar-cedula", methods=["POST"])
@rate_limit("verificar-cedula")
def verificar_cedula():
    # Respuesta mínima anti-enumeración: no devuelve nombre/email/rol.
    # Siempre 200 (nunca 404) para no distinguir por código HTTP.
    data = request.get_json() or {}
    cedula = (data.get("cedula") or "").strip()
    if not cedula:
        return jsonify({"error": "La Cédula de Identidad es requerida"}), 400

    usuario = Usuario.query.filter_by(cedula=cedula).first()
    if not usuario or not usuario.activo:
        return jsonify({
            "status": "no_encontrado",
            "mensaje": "Si la cédula está registrada recibirás instrucciones.",
        }), 200

    if not usuario.password_set or not usuario.password_hash:
        return jsonify({
            "status": "requiere_activacion",
            "mensaje": "Tu cédula está pre-registrada. Puedes proceder a crear tu contraseña.",
        }), 200
    return jsonify({
        "status": "activo",
        "mensaje": "Su cuenta ya tiene contraseña configurada. Puede iniciar sesión directamente.",
    }), 200


@auth_bp.route("/activar-cuenta", methods=["POST"])
@rate_limit("activar-cuenta")
def activar_cuenta():
    data = request.get_json() or {}
    cedula = (data.get("cedula") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or ""

    if not cedula or not email or not password or not confirm_password:
        return jsonify({"error": "Cédula, email, contraseña y confirmación son obligatorios"}), 400

    if password != confirm_password:
        return jsonify({"error": "Las contraseñas no coinciden. Por favor verifíquelas."}), 400

    ok, err = validate_password(password)
    if not ok:
        return jsonify({"error": err}), 400

    usuario = Usuario.query.filter_by(cedula=cedula).first()
    # Anti-enumeración: mismo mensaje si no existe o email no coincide
    if not usuario or not usuario.activo or (usuario.email or "").strip().lower() != email.lower():
        return jsonify({"error": "No se pudo activar. Verifique cédula y email de pre-registro."}), 404

    if usuario.password_set and usuario.password_hash:
        return jsonify({"error": "Esta cuenta ya posee contraseña activa. Use recuperación si la olvidó."}), 400

    usuario.password_hash = generate_password_hash(password)
    usuario.password_set = True
    usuario.password_version = (usuario.password_version or 0) + 1
    db.session.commit()

    access_token, refresh_token = _tokens_for(usuario)
    return jsonify({
        "mensaje": "¡Contraseña creada con éxito! Su cuenta ha sido activada.",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "role": usuario.role,
        "nombre": f"{usuario.nombre} {usuario.apellido}",
        "id": usuario.id,
    }), 200


def _issue_reset_code(usuario):
    # Invalida códigos previos sin usar
    PasswordResetCode.query.filter_by(usuario_id=usuario.id, usado=False).update({"usado": True})
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    ttl = int(current_app.config.get("PASSWORD_RESET_TTL_MIN", 15))
    rec = PasswordResetCode(
        usuario_id=usuario.id,
        codigo_hash=hashlib.sha256(codigo.encode()).hexdigest(),
        expira_en=datetime.utcnow() + timedelta(minutes=ttl),
        intentos=0,
        usado=False,
    )
    db.session.add(rec)
    db.session.commit()
    return codigo


def _get_valid_reset_record(usuario, codigo):
    h = hashlib.sha256(str(codigo or "").encode()).hexdigest()
    rec = PasswordResetCode.query.filter_by(usuario_id=usuario.id, codigo_hash=h, usado=False).first()
    if not rec:
        return None
    if rec.expira_en < datetime.utcnow():
        return None
    if (rec.intentos or 0) >= int(current_app.config.get("PASSWORD_RESET_MAX_INTENTOS", 5)):
        return None
    return rec


def _registrar_intento_fallido(usuario, codigo):
    """Cuenta un intento fallido para enforcing de PASSWORD_RESET_MAX_INTENTOS.

    Si el hash coincide con un registro (expirado o bloqueado), lo incrementa.
    Si es un código erróneo distinto, incrementa el código activo más reciente
    para que el brute-force con códigos distintos también bloquee el código.
    """
    h = hashlib.sha256(str(codigo or "").encode()).hexdigest()
    cand = PasswordResetCode.query.filter_by(usuario_id=usuario.id, codigo_hash=h, usado=False).first()
    if cand:
        cand.intentos = (cand.intentos or 0) + 1
        db.session.commit()
        return
    rec = (
        PasswordResetCode.query.filter_by(usuario_id=usuario.id, usado=False)
        .order_by(PasswordResetCode.creado_en.desc())
        .first()
    )
    if rec and rec.expira_en >= datetime.utcnow():
        rec.intentos = (rec.intentos or 0) + 1
        db.session.commit()


@auth_bp.route("/forgot", methods=["POST"])
@rate_limit("forgot")
def forgot_password():
    # Siempre 200 genérico (anti-enumeración). Supuesto v1: usuarios mayores de edad,
    # el código va al email propio del usuario.
    data = request.get_json() or {}
    login_value = str(data.get("cedula") or data.get("email") or "").strip()
    usuario = _find_user_by_login(login_value)
    code_debug = None
    if usuario and usuario.activo and usuario.email:
        try:
            codigo = _issue_reset_code(usuario)
            _send_reset_code(usuario.email, codigo)
            if current_app.config.get("TESTING"):
                code_debug = codigo
        except Exception as e:
            current_app.logger.error("Error generando código reset: %s", e)
    resp = {"mensaje": "Si los datos corresponden a una cuenta activa, recibirás un código en tu email."}
    if code_debug:
        resp["code_debug"] = code_debug  # solo TESTING, jamás en prod
    return jsonify(resp), 200


@auth_bp.route("/verify-code", methods=["POST"])
@rate_limit("verify-code")
def verify_code():
    data = request.get_json() or {}
    usuario = _find_user_by_login(data.get("cedula") or data.get("email") or "")
    codigo = str(data.get("codigo") or "").strip()
    if not usuario or not codigo:
        return jsonify({"error": "Código inválido"}), 400
    rec = _get_valid_reset_record(usuario, codigo)
    if not rec:
        _registrar_intento_fallido(usuario, codigo)
        return jsonify({"error": "Código inválido o vencido"}), 400
    return jsonify({"ok": True}), 200


@auth_bp.route("/reset", methods=["POST"])
@rate_limit("reset")
def reset_password():
    data = request.get_json() or {}
    usuario = _find_user_by_login(data.get("cedula") or data.get("email") or "")
    codigo = str(data.get("codigo") or "").strip()
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or data.get("password_confirm") or ""
    if not usuario or not codigo or not password:
        return jsonify({"error": "Datos incompletos"}), 400
    if confirm and password != confirm:
        return jsonify({"error": "Las contraseñas no coinciden"}), 400
    ok, err = validate_password(password)
    if not ok:
        return jsonify({"error": err}), 400
    rec = _get_valid_reset_record(usuario, codigo)
    if not rec:
        _registrar_intento_fallido(usuario, codigo)
        return jsonify({"error": "Código inválido o vencido"}), 400
    usuario.password_hash = generate_password_hash(password)
    usuario.password_set = True
    usuario.password_version = (usuario.password_version or 0) + 1
    usuario.requiere_cambio_clave = False
    rec.usado = True
    # Invalida el resto de códigos vivos
    PasswordResetCode.query.filter_by(usuario_id=usuario.id, usado=False).update({"usado": True})
    db.session.commit()
    return jsonify({"mensaje": "Contraseña actualizada. Ya puedes iniciar sesión."}), 200


@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    user = current_user
    data = request.get_json() or {}
    current = data.get("current_password") or ""
    new = data.get("password") or ""
    confirm = data.get("confirm_password") or ""
    if not current or not new:
        return jsonify({"error": "Contraseña actual y nueva son requeridas"}), 400
    if confirm and new != confirm:
        return jsonify({"error": "Las contraseñas no coinciden"}), 400
    if not check_password_hash(user.password_hash or "", current):
        return jsonify({"error": "La contraseña actual es incorrecta"}), 401
    ok, err = validate_password(new)
    if not ok:
        return jsonify({"error": err}), 400
    user.password_hash = generate_password_hash(new)
    user.password_set = True
    user.password_version = (user.password_version or 0) + 1
    user.requiere_cambio_clave = False
    db.session.commit()
    access_token, refresh_token = _tokens_for(user)
    return jsonify({
        "mensaje": "Contraseña cambiada",
        "access_token": access_token,
        "refresh_token": refresh_token,
    }), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user = current_user
    alumno_id = user.alumno.id if getattr(user, "alumno", None) else None
    profesor_id = user.profesor.id if getattr(user, "profesor", None) else None
    return jsonify({
        "id": user.id,
        "cedula": user.cedula,
        "nombre": user.nombre,
        "apellido": user.apellido,
        "email": user.email,
        "role": user.role,
        "password_set": user.password_set,
        "requiere_cambio_clave": bool(user.requiere_cambio_clave),
        "agrupaciones": [a.id for a in user.agrupaciones],
        "alumno_id": alumno_id,
        "profesor_id": profesor_id,
    }), 200


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    # Blocklist real: siempre invalida el access actual; si el cliente envía su
    # refresh_token en el body, también lo invalida.
    from flask_jwt_extended import decode_token
    bloqueados = 0

    def _bloquear(jti, exp_ts, fallback_horas=2):
        nonlocal bloqueados
        if not jti:
            return
        try:
            expira = datetime.utcfromtimestamp(exp_ts) if exp_ts else datetime.utcnow() + timedelta(hours=fallback_horas)
        except Exception:
            expira = datetime.utcnow() + timedelta(hours=fallback_horas)
        if not TokenBloqueado.query.filter_by(jti=jti).first():
            db.session.add(TokenBloqueado(jti=jti, expira_en=expira))
            bloqueados += 1

    try:
        body = request.get_json(silent=True) or {}
        refresh_token = body.get("refresh_token") or body.get("refresh")
    except Exception:
        refresh_token = None

    payload = get_jwt()
    _bloquear(payload.get("jti"), payload.get("exp"), 2)
    refresh_bloqueado = False
    if refresh_token:
        try:
            dec = decode_token(refresh_token)
            _bloquear(dec.get("jti"), dec.get("exp"), 24 * 7)
            refresh_bloqueado = True
        except Exception:
            pass
    db.session.commit()
    if refresh_token and not refresh_bloqueado:
        return jsonify({"mensaje": "Sesión cerrada", "advertencia": "refresh_token no válido, solo se invalidó el access actual"}), 200
    if not refresh_token:
        return jsonify({"mensaje": "Sesión cerrada", "advertencia": "sin refresh_token solo se invalidó el access actual"}), 200
    return jsonify({"mensaje": "Sesión cerrada"}), 200


@auth_bp.route("/menu", methods=["GET"])
@jwt_required()
def menu():
    from backend.modules.registry import module_registry

    role = current_user.role
    items = module_registry.get_sidebar_items(role)
    return jsonify(items), 200
