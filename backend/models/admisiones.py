from backend.extensions import db
from backend.models.associations import audicion_jurado
from backend.models.common import _utcnow


class Convocatoria(db.Model):
    __tablename__ = "convocatorias"
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    activa = db.Column(db.Boolean, default=True, nullable=False, server_default="1")
    creada_por = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)

    creador = db.relationship("Usuario")
    aspirantes = db.relationship("Aspirante", back_populates="convocatoria", lazy="dynamic")


# NOTA DE DOMINIO (decisión con el conservatorio): no hay sistema de calificaciones
# académicas. Solo clases + examen de admisión sin nota pública. Las puntuaciones
# de jurado son un insumo INTERNO de admisión y nunca se exponen como "nota" al
# aspirante; al aspirante solo se le comunica pendiente/admitido/no_admitido/en_espera.
ESTADOS_ASPIRANTE = ("pendiente", "admitido", "no_admitido", "en_espera")
# Legacy (compatibilidad con filas viejas): aprobado -> admitido, rechazado -> no_admitido.
ESTADOS_ASPIRANTE_LEGACY = ("aprobado", "rechazado")


class Aspirante(db.Model):
    __tablename__ = "aspirantes"
    id = db.Column(db.Integer, primary_key=True)
    convocatoria_id = db.Column(db.Integer, db.ForeignKey("convocatorias.id"), nullable=False, index=True)
    nombre = db.Column(db.String(80), nullable=False)
    apellido = db.Column(db.String(80), nullable=False)
    # Un aspirante puede reinscribirse en otra convocatoria: unicidad compuesta.
    cedula = db.Column(db.String(20), nullable=False, index=True)
    email = db.Column(db.String(120))
    telefono = db.Column(db.String(20))
    fecha_nacimiento = db.Column(db.Date)
    direccion = db.Column(db.String(200))
    instrumento_postulado = db.Column(db.String(80))
    experiencia_previa = db.Column(db.Text)
    # Dormidos (fuera del alcance v1): video de audición no pedido por el conservatorio.
    # Se conservan las columnas por compatibilidad con BD existentes.
    video_nombre = db.Column(db.String(300))
    video_ruta = db.Column(db.String(500))
    estado = db.Column(db.String(30), default="pendiente", nullable=False, server_default="pendiente")
    inscrito_en = db.Column(db.DateTime, default=_utcnow)

    convocatoria = db.relationship("Convocatoria", back_populates="aspirantes")
    puntuaciones = db.relationship("PuntuacionAudicion", back_populates="aspirante", lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("convocatoria_id", "cedula", name="uq_aspirante_convocatoria_cedula"),
    )


class Audicion(db.Model):
    __tablename__ = "audiciones"
    id = db.Column(db.Integer, primary_key=True)
    convocatoria_id = db.Column(db.Integer, db.ForeignKey("convocatorias.id"))
    agrupacion_id = db.Column(db.Integer, db.ForeignKey("agrupaciones.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)
    lugar = db.Column(db.String(200))
    # Deprecated: mantener por compatibilidad con BD existente, usar relación jurados en código nuevo
    jurado_ids = db.Column(db.String(300))
    jurados = db.relationship("Usuario", secondary=audicion_jurado, backref=db.backref("audiciones_jurado", lazy="dynamic"))

    agrupacion = db.relationship("Agrupacion", back_populates="audiciones")
    convocatoria = db.relationship("Convocatoria")


class PuntuacionAudicion(db.Model):
    # Puntuación INTERNA de admisión (no es nota académica, no se publica).
    __tablename__ = "puntuaciones_audicion"
    id = db.Column(db.Integer, primary_key=True)
    aspirante_id = db.Column(db.Integer, db.ForeignKey("aspirantes.id"), nullable=False, index=True)
    jurado_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    tecnica = db.Column(db.Float, default=0.0)
    interpretacion = db.Column(db.Float, default=0.0)
    afinacion = db.Column(db.Float, default=0.0)
    ritmo = db.Column(db.Float, default=0.0)
    presencia = db.Column(db.Float, default=0.0)
    observaciones = db.Column(db.Text)
    puntuacion_total = db.Column(db.Float, default=0.0)
    creado_en = db.Column(db.DateTime, default=_utcnow)

    aspirante = db.relationship("Aspirante", back_populates="puntuaciones")
    jurado = db.relationship("Usuario")

    __table_args__ = (
        db.UniqueConstraint("aspirante_id", "jurado_id", name="uq_puntuacion_jurado"),
        db.CheckConstraint("tecnica >= 0 AND tecnica <= 10", name="ck_punt_tecnica"),
        db.CheckConstraint("interpretacion >= 0 AND interpretacion <= 10", name="ck_punt_interpretacion"),
        db.CheckConstraint("afinacion >= 0 AND afinacion <= 10", name="ck_punt_afinacion"),
        db.CheckConstraint("ritmo >= 0 AND ritmo <= 10", name="ck_punt_ritmo"),
        db.CheckConstraint("presencia >= 0 AND presencia <= 10", name="ck_punt_presencia"),
    )
