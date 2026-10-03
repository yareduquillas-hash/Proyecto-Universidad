import os
import secrets
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def _get_secret(env_name, default_dev=None):
    val = os.environ.get(env_name)
    if val:
        return val
    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError(f"{env_name} debe estar configurado en .env en producción (no se permite default)")
    if default_dev:
        return default_dev
    # En desarrollo sin .env, genera uno efímero y avisa
    generated = secrets.token_hex(32)
    print(f"⚠️  {env_name} no configurado — usando valor temporal generado (solo desarrollo): {generated[:8]}...")
    return generated


class Config:
    SECRET_KEY = _get_secret("SECRET_KEY", "dev-secret-key-solo-para-desarrollo-local-no-usar-en-prod")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'nucleo_los_teques.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Pool sensato para Postgres en prod (en SQLite se ignora)
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}

    JWT_SECRET_KEY = _get_secret("JWT_SECRET_KEY", "dev-jwt-secret-solo-para-desarrollo-local-no-usar-en-prod")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.environ.get("JWT_ACCESS_HOURS", "2")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", "7")))
    # Blocklist activa (logout invalida el token hasta su expiración)
    JWT_TOKEN_IN_BLOCKLIST_ENABLED = True
    JWT_BLOCKLIST_TOKEN_CHECKS = ["access", "refresh"]
    # Solo headers: usar cookies requiere CSRF y HTTPS. Si necesitas cookies, activa JWT_COOKIE_CSRF_PROTECT y HTTPS.
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_CSRF_PROTECT = False

    # CORS: lista separada por comas en env, ej: "https://conservatorio.gob.ve,https://nucleo.test"
    CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5000,http://127.0.0.1:5000").split(",") if o.strip()]

    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads", "partituras"))
    # Global: cubre el PDF más grande (10MB) + overhead multipart.
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH_MB", "15")) * 1024 * 1024
    MAX_PDF_MB = int(os.environ.get("MAX_PDF_MB", "10"))

    ALLOWED_PDF = {"pdf"}

    UMBRAL_INASISTENCIA_PERCENT = int(os.environ.get("UMBRAL_INASISTENCIA_PERCENT", "25"))

    # Recuperación por email (Gmail). Si no se configura, el código se loguea
    # (solo desarrollo) y en testing se devuelve para asserts.
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "no-reply@nucleoteques.local"))
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "1") == "1"

    PASSWORD_RESET_TTL_MIN = int(os.environ.get("PASSWORD_RESET_TTL_MIN", "15"))
    PASSWORD_RESET_MAX_INTENTOS = int(os.environ.get("PASSWORD_RESET_MAX_INTENTOS", "5"))


class DevelopmentConfig(Config):
    DEBUG = True
    SEND_FILE_MAX_AGE_DEFAULT = 0


class ProductionConfig(Config):
    DEBUG = False

    # Valores que nunca deben llegar a producción (placeholders, defaults de
    # dev/test y secretos débiles históricos del proyecto).
    _SECRETOS_PROHIBIDOS = {
        "dev-secret-key-solo-para-desarrollo-local-no-usar-en-prod",
        "dev-jwt-secret-solo-para-desarrollo-local-no-usar-en-prod",
        "cambia-esta-clave-por-una-generada-con-secrets-token_hex",
        "cambia-esta-otra-clave-jwt-con-secrets-token_hex",
        "test-secret-key-para-pytest-no-usar-en-prod",
        "test-jwt-secret-para-pytest-no-usar-en-prod",
        "nucleo-los-teques-clave-secreta-2025",
        "jwt-secreto-nucleo-los-teques",
        "cambia-esta-clave-postgres-en-produccion",
        "nucleo",
    }

    # Subcadenas típicas de secretos de desarrollo/test/placeholders.
    _PATRONES_DEBILES = (
        "cambia-esta-",
        "dev-secret",
        "dev-jwt",
        "test-secret",
        "test-jwt",
        "solo-para-desarrollo",
        "no-usar-en-prod",
        "para-pytest",
    )

    @classmethod
    def check_required_secrets(cls):
        valores = {}
        for k in ("SECRET_KEY", "JWT_SECRET_KEY"):
            v = os.environ.get(k) or ""
            if not v:
                raise RuntimeError(f"{k} es obligatorio en producción. Configúralo en .env")
            if v.strip() in cls._SECRETOS_PROHIBIDOS or "cambia-esta-" in v:
                raise RuntimeError(f"{k} tiene un valor placeholder/default en producción. Genera uno con: python -c \"import secrets; print(secrets.token_hex(32))\"")
            if len(v) < 32:
                raise RuntimeError(f"{k} es demasiado corto en producción (mín 32 caracteres). Genera uno con: python -c \"import secrets; print(secrets.token_hex(32))\"")
            low = v.lower()
            for pat in cls._PATRONES_DEBILES:
                if pat in low:
                    raise RuntimeError(f"{k} parece un secreto de desarrollo/test ('{pat}'). Genera uno con: python -c \"import secrets; print(secrets.token_hex(32))\"")
            # Heurística mínima de fortaleza: suficientes caracteres distintos
            # (un secreto real generado tiene alta entropía; frases débiles no).
            if len(set(v)) < 12:
                raise RuntimeError(f"{k} es demasiado predecible en producción (pocos caracteres distintos). Genera uno con: python -c \"import secrets; print(secrets.token_hex(32))\"")
            valores[k] = v
        if valores.get("SECRET_KEY") == valores.get("JWT_SECRET_KEY"):
            raise RuntimeError("SECRET_KEY y JWT_SECRET_KEY deben ser distintos en producción")


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key-para-pytest-no-usar-en-prod"
    JWT_SECRET_KEY = "test-jwt-secret-para-pytest-no-usar-en-prod"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_TOKEN_LOCATION = ["headers"]


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
