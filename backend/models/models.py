# Compatibilidad: los modelos ahora están organizados por dominio en este
# paquete (usuarios, academico, partituras, cronograma, admisiones).
# Importa desde `backend.models` en el código nuevo.
from backend.models import (  # noqa: F401
    usuario_agrupacion,
    alumno_instrumento,
    profesor_agrupacion,
    audicion_jurado,
    _utcnow,
    Usuario,
    PasswordResetCode,
    TokenBloqueado,
    Agrupacion,
    Instrumento,
    Alumno,
    Profesor,
    Asistencia,
    Partitura,
    EventoCronograma,
    Convocatoria,
    Aspirante,
    Audicion,
    PuntuacionAudicion,
    ESTADOS_ASPIRANTE,
    ESTADOS_ASPIRANTE_LEGACY,
)
