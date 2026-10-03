from backend.extensions import db

usuario_agrupacion = db.Table(
    "usuario_agrupacion",
    db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id"), primary_key=True),
    db.Column("agrupacion_id", db.Integer, db.ForeignKey("agrupaciones.id"), primary_key=True),
)

alumno_instrumento = db.Table(
    "alumno_instrumento",
    db.Column("alumno_id", db.Integer, db.ForeignKey("alumnos.id"), primary_key=True),
    db.Column("instrumento_id", db.Integer, db.ForeignKey("instrumentos.id"), primary_key=True),
)

profesor_agrupacion = db.Table(
    "profesor_agrupacion",
    db.Column("profesor_id", db.Integer, db.ForeignKey("profesores.id"), primary_key=True),
    db.Column("agrupacion_id", db.Integer, db.ForeignKey("agrupaciones.id"), primary_key=True),
)

# Tabla M2M para audiciones <-> jurados (reemplaza el String jurado_ids)
audicion_jurado = db.Table(
    "audicion_jurado",
    db.Column("audicion_id", db.Integer, db.ForeignKey("audiciones.id", ondelete="CASCADE"), primary_key=True),
    db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
)
