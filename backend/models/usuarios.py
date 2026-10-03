from backend.extensions import db
from backend.models.associations import usuario_agrupacion
from backend.models.common import _utcnow


class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    cedula = db.Column(db.String(20), unique=True, nullable=False, index=True)
    nombre = db.Column(db.String(80), nullable=False)
    apellido = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)
    password_set = db.Column(db.Boolean, default=True, nullable=False, server_default="1")
    role = db.Column(db.String(20), nullable=False, default="alumno")
    activo = db.Column(db.Boolean, default=True, nullable=False, server_default="1")
    creado_en = db.Column(db.DateTime, default=_utcnow)
    actualizado_en = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
    # Invalida JWT viejos al cambiar clave: se firma dentro del token y se compara en cada request.
    password_version = db.Column(db.Integer, default=0, nullable=False, server_default="0")
    # Reset asistido por secretaría: obliga a cambiar la temporal en el próximo login.
    requiere_cambio_clave = db.Column(db.Boolean, default=False, nullable=False, server_default="0")

    agrupaciones = db.relationship("Agrupacion", secondary=usuario_agrupacion, back_populates="usuarios")
    alumno = db.relationship("Alumno", back_populates="usuario", uselist=False, cascade="all, delete-orphan")
    profesor = db.relationship("Profesor", back_populates="usuario", uselist=False, cascade="all, delete-orphan")

    def has_role(self, role):
        return self.role == role

    def is_jurado(self):
        return self.role == "jurado"


class PasswordResetCode(db.Model):
    """Código de recuperación de 6 dígitos (hash SHA256, 1 uso, 15 min, máx intentos)."""

    __tablename__ = "password_reset_codes"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo_hash = db.Column(db.String(64), nullable=False, index=True)
    expira_en = db.Column(db.DateTime, nullable=False)
    intentos = db.Column(db.Integer, default=0, nullable=False, server_default="0")
    usado = db.Column(db.Boolean, default=False, nullable=False, server_default="0")
    creado_en = db.Column(db.DateTime, default=_utcnow)

    usuario = db.relationship("Usuario")


class TokenBloqueado(db.Model):
    """Blocklist de JWT (logout): se guarda el jti hasta su expiración."""

    __tablename__ = "tokens_bloqueados"
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expira_en = db.Column(db.DateTime, nullable=False)
    creado_en = db.Column(db.DateTime, default=_utcnow)
