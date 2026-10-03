import os
from datetime import datetime
from flask import Flask, jsonify, send_from_directory
from backend.config.config import config_by_name
from backend.extensions import db, jwt, cors, migrate
from backend.modules.registry import module_registry

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app(config_name="default", config_override=None):
    # En producción exige secretos ANTES de arrancar (evita clave dev por typo de FLASK_ENV)
    if os.getenv("FLASK_ENV") == "production" and config_name == "production":
        config_by_name["production"].check_required_secrets()
    app = Flask(
        __name__,
        static_folder=os.path.join(PROJECT_ROOT, "frontend", "static"),
        template_folder=os.path.join(PROJECT_ROOT, "frontend", "templates"),
    )
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))
    if config_override:
        app.config.update(config_override)

    # Detrás de Caddy/nginx: confiar en X-Forwarded-* solo en producción
    # (para que rate-limit use la IP real del cliente y HSTS/HTTPS se vean bien).
    # En desarrollo/expuesto directo no se confía en esos headers.
    if config_name == "production" or os.getenv("FLASK_ENV") == "production":
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # La carpeta de uploads debe existir (clon fresco / prod). Falla suave si no hay permiso.
    folder = app.config.get("UPLOAD_FOLDER")
    if folder:
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            app.logger.warning("No se pudo crear UPLOAD_FOLDER=%s", folder)

    register_extensions(app)
    register_modules(app)
    register_error_handlers(app)
    register_password_guard(app)
    register_frontend_routes(app)

    return app


def register_password_guard(app):
    """Guard global de sesión en /api/*.

    1. Revocación efectiva: token de usuario inactivado o con password_version
    distinto (cambio de clave) recibe 401 en TODAS las rutas /api/, incluso en
    las que solo usan @jwt_required() sin current_user (p.ej. descarga de
    partituras, convocatorias). Antes solo los filtros por rol lo bloqueaban.
    2. Clave temporal (D10): con requiere_cambio_clave, solo pasan me,
    change-password, logout, refresh y menú (403 en el resto).
    """
    from flask import request
    ALLOW = {
        "/api/v1/auth/me",
        "/api/v1/auth/change-password",
        "/api/v1/auth/logout",
        "/api/v1/auth/refresh",
        "/api/v1/auth/menu",
    }
    _NO_SESSION = {"error": "Sesión inválida, inicie sesión de nuevo"}

    @app.before_request
    def _guard_clave_temporal():
        if not request.path.startswith("/api/"):
            return None
        try:
            from flask_jwt_extended import verify_jwt_in_request, get_jwt
            verify_jwt_in_request(optional=True)
            claims = get_jwt()
        except Exception:
            # Token ausente/malformado/repocado: lo decide la propia ruta.
            return None
        if not claims:
            return None
        try:
            from backend.models import Usuario
            try:
                uid = int(claims.get("sub"))
            except (TypeError, ValueError):
                return None
            user = db.session.get(Usuario, uid)
        except Exception:
            return None
        if user is None or not getattr(user, "activo", False):
            return jsonify(dict(_NO_SESSION)), 401
        try:
            token_pv = int(claims.get("pv", 0))
        except (TypeError, ValueError):
            token_pv = 0
        if token_pv != (user.password_version or 0):
            return jsonify(dict(_NO_SESSION)), 401
        if request.path in ALLOW:
            return None
        if bool(getattr(user, "requiere_cambio_clave", False)):
            return jsonify({
                "error": "Debe cambiar su contraseña temporal antes de continuar",
                "requiere_cambio_clave": True,
            }), 403
        return None


def register_extensions(app):
    db.init_app(app)
    jwt.init_app(app)
    # CORS seguro: solo orígenes configurados, sin wildcard con credenciales
    cors_origins = app.config.get("CORS_ORIGINS", ["http://localhost:5000"])
    cors.init_app(app, origins=cors_origins, supports_credentials=False)
    migrate.init_app(app, db)

    # Cabeceras de seguridad. X-Frame-Options SAMEORIGIN (no DENY) para permitir
    # el preview de partituras en <iframe> del mismo origen.
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # CSP mínima que no rompe el JS inline actual; endurecer cuando se extraiga a static/js.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; media-src 'self' blob:; frame-src 'self'; "
            "connect-src 'self'; font-src 'self' data:"
        )
        if os.getenv("FLASK_ENV") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


def register_modules(app):

    from backend.models import (  # noqa: F401
        Usuario, Agrupacion, Instrumento, Alumno, Profesor,
        Partitura, Asistencia, EventoCronograma,
        Convocatoria, Aspirante, Audicion, PuntuacionAudicion,
        PasswordResetCode, TokenBloqueado,
    )

    from backend.modules.auth.routes import auth_bp
    from backend.modules.usuarios.routes import usuarios_bp
    from backend.modules.asistencia.routes import asistencia_bp
    from backend.modules.partituras.routes import partituras_bp
    from backend.modules.cronograma.routes import cronograma_bp
    from backend.modules.audiciones.routes import audiciones_bp
    from backend.modules.dashboard.routes import dashboard_bp

    module_registry.register("auth", auth_bp, "Autenticación", "fa-sign-in-alt", ["*"], sidebar_visible=False)
    module_registry.register("inicio", dashboard_bp, "Dashboard Inicio", "fa-chart-pie", ["admin"], sidebar_visible=True)
    module_registry.register("usuarios", usuarios_bp, "Gestión de Usuarios", "fa-users-cog", ["admin", "secretaria"], sidebar_visible=True)
    module_registry.register("asistencia", asistencia_bp, "Control de Asistencia", "fa-calendar-check", ["profesor", "secretaria", "admin", "alumno"], sidebar_visible=True)
    module_registry.register("partituras", partituras_bp, "Biblioteca de Partituras", "fa-file-pdf", ["profesor", "alumno", "admin", "secretaria"], sidebar_visible=True)
    module_registry.register("cronograma", cronograma_bp, "Cronograma", "fa-calendar-alt", ["profesor", "alumno", "admin", "secretaria"], sidebar_visible=True)
    module_registry.register("audiciones", audiciones_bp, "Admisiones y Audiciones", "fa-clipboard-list", ["jurado", "admin", "secretaria"], sidebar_visible=True)

    module_registry.register_blueprints(app)


def register_error_handlers(app):

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        from backend.models import Usuario
        raw = jwt_data.get("sub")
        try:
            identity = int(raw)
        except (TypeError, ValueError):
            return None
        user = db.session.get(Usuario, identity)
        if not user or not user.activo:
            return None
        # Invalida tokens firmados antes de un cambio de clave (password_version)
        try:
            token_pv = int(jwt_data.get("pv", 0))
        except (TypeError, ValueError):
            token_pv = 0
        if token_pv != (user.password_version or 0):
            return None
        return user

    @jwt.token_in_blocklist_loader
    def check_blocklist(_jwt_header, jwt_payload):
        from backend.models import TokenBloqueado
        jti = jwt_payload.get("jti")
        if not jti:
            return True
        return db.session.query(TokenBloqueado.id).filter_by(jti=jti).first() is not None

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token expirado"}), 401

    @jwt.unauthorized_loader
    def unauthorized_callback(error_string):
        return jsonify({"error": "Acceso no autorizado"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error_string):
        return jsonify({"error": "Token inválido"}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Sesión cerrada, inicie sesión de nuevo"}), 401

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({"error": "Recurso no encontrado"}), 404

    @app.errorhandler(405)
    def handle_405(e):
        return jsonify({"error": "Método no permitido"}), 405

    @app.errorhandler(413)
    def handle_413(e):
        return jsonify({"error": "Archivo demasiado grande para el servidor"}), 413

    @app.errorhandler(500)
    def handle_500(e):
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"error": "Error interno del servidor"}), 500


def register_frontend_routes(app):
    FRONTEND = os.path.join(PROJECT_ROOT, "frontend", "templates")

    @app.route("/health")
    def health():
        # Liveness simple + check BD
        try:
            db.session.execute(db.text("SELECT 1"))
            return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()}), 200
        except Exception:
            return jsonify({"status": "degraded"}), 500

    @app.route("/")
    def index():
        return send_from_directory(FRONTEND, "index.html")

    @app.route("/login")
    def login_page():
        return send_from_directory(FRONTEND, "login.html")

    @app.route("/dashboard")
    def dashboard_page():
        return send_from_directory(FRONTEND, "dashboard.html")

    @app.route("/modulo/<name>")
    def modulo_page(name):
        template_map = {
            "asistencia": "asistencia.html",
            "partituras": "partituras.html",
            "cronograma": "cronograma.html",
            "audiciones": "audiciones.html",
            "usuarios": "usuarios.html",
        }
        filename = template_map.get(name, "dashboard.html")
        return send_from_directory(FRONTEND, filename)

    @app.route("/static/<path:filename>")
    def serve_static(filename):
        return send_from_directory(os.path.join(PROJECT_ROOT, "frontend", "static"), filename)
