from backend.extensions import db
from backend.models.common import _utcnow


class EventoCronograma(db.Model):
    __tablename__ = "eventos_cronograma"
    id = db.Column(db.Integer, primary_key=True)
    agrupacion_id = db.Column(db.Integer, db.ForeignKey("agrupaciones.id"), nullable=False, index=True)
    titulo = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    descripcion = db.Column(db.Text)
    fecha_inicio = db.Column(db.DateTime, nullable=False, index=True)
    fecha_fin = db.Column(db.DateTime, nullable=False)
    lugar = db.Column(db.String(200))
    creado_por = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    notificar_cambios = db.Column(db.Boolean, default=False, nullable=False, server_default="0")
    mensaje_alerta = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=_utcnow)
    activo = db.Column(db.Boolean, default=True, nullable=False, server_default="1")

    agrupacion = db.relationship("Agrupacion", back_populates="eventos")
    creador = db.relationship("Usuario")
