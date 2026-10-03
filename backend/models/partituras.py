from backend.extensions import db
from backend.models.common import _utcnow


class Partitura(db.Model):
    __tablename__ = "partituras"
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    obra = db.Column(db.String(150))
    compositor = db.Column(db.String(150))
    catedra = db.Column(db.String(80))
    agrupacion_id = db.Column(db.Integer, db.ForeignKey("agrupaciones.id"), nullable=False)
    instrumento_id = db.Column(db.Integer, db.ForeignKey("instrumentos.id"))
    archivo_nombre = db.Column(db.String(300), nullable=False)
    # Ruta: se guarda relativa si es posible (solo nombre único); filas legacy
    # pueden tener ruta absoluta y se resuelven con fallback en las rutas.
    archivo_ruta = db.Column(db.String(500), nullable=False)
    subido_por = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    fecha_subida = db.Column(db.DateTime, default=_utcnow)
    activo = db.Column(db.Boolean, default=True, nullable=False, server_default="1")

    agrupacion = db.relationship("Agrupacion", back_populates="partituras")
    instrumento = db.relationship("Instrumento", back_populates="partituras")
    uploader = db.relationship("Usuario")
