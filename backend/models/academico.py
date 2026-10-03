from backend.extensions import db
from backend.models.associations import alumno_instrumento, profesor_agrupacion, usuario_agrupacion
from backend.models.common import _utcnow


class Agrupacion(db.Model):
    __tablename__ = "agrupaciones"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False, unique=True)
    tipo = db.Column(db.String(30), nullable=False)
    descripcion = db.Column(db.Text)
    activa = db.Column(db.Boolean, default=True, nullable=False, server_default="1")

    usuarios = db.relationship("Usuario", secondary=usuario_agrupacion, back_populates="agrupaciones")
    profesores = db.relationship("Profesor", secondary=profesor_agrupacion, back_populates="agrupaciones")
    asistencias = db.relationship("Asistencia", back_populates="agrupacion", lazy="dynamic")
    partituras = db.relationship("Partitura", back_populates="agrupacion", lazy="dynamic")
    eventos = db.relationship("EventoCronograma", back_populates="agrupacion", lazy="dynamic")
    audiciones = db.relationship("Audicion", back_populates="agrupacion", lazy="dynamic")


class Instrumento(db.Model):
    __tablename__ = "instrumentos"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False, unique=True)
    familia = db.Column(db.String(50))

    alumnos = db.relationship("Alumno", secondary=alumno_instrumento, back_populates="instrumentos")
    partituras = db.relationship("Partitura", back_populates="instrumento", lazy="dynamic")


class Alumno(db.Model):
    __tablename__ = "alumnos"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), unique=True, nullable=False)
    fecha_nacimiento = db.Column(db.Date)
    direccion = db.Column(db.String(200))
    telefono = db.Column(db.String(20))
    nombre_representante = db.Column(db.String(160))
    telefono_representante = db.Column(db.String(20))
    nivel_academico = db.Column(db.String(80))
    fecha_ingreso = db.Column(db.Date)

    usuario = db.relationship("Usuario", back_populates="alumno")
    instrumentos = db.relationship("Instrumento", secondary=alumno_instrumento, back_populates="alumnos")
    asistencias = db.relationship("Asistencia", back_populates="alumno", lazy="dynamic")


class Profesor(db.Model):
    __tablename__ = "profesores"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), unique=True, nullable=False)
    especialidad = db.Column(db.String(100))
    telefono = db.Column(db.String(20))

    usuario = db.relationship("Usuario", back_populates="profesor")
    agrupaciones = db.relationship("Agrupacion", secondary=profesor_agrupacion, back_populates="profesores")


class Asistencia(db.Model):
    __tablename__ = "asistencias"
    id = db.Column(db.Integer, primary_key=True)
    alumno_id = db.Column(db.Integer, db.ForeignKey("alumnos.id"), nullable=False, index=True)
    agrupacion_id = db.Column(db.Integer, db.ForeignKey("agrupaciones.id"), nullable=False, index=True)
    fecha = db.Column(db.Date, nullable=False, index=True)
    estado = db.Column(db.String(20), nullable=False, default="presente")
    observaciones = db.Column(db.Text)
    registrado_por = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    creado_en = db.Column(db.DateTime, default=_utcnow)

    alumno = db.relationship("Alumno", back_populates="asistencias")
    agrupacion = db.relationship("Agrupacion", back_populates="asistencias")
    registrador = db.relationship("Usuario")

    __table_args__ = (
        db.UniqueConstraint("alumno_id", "agrupacion_id", "fecha", name="uq_asistencia_dia"),
        db.CheckConstraint(
            "estado IN ('presente','ausente','justificado','retraso')",
            name="ck_asistencia_estado",
        ),
    )
