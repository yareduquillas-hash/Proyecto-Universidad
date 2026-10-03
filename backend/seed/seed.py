from backend.app import create_app
from backend.extensions import db
from backend.models import (
    Usuario, Alumno, Profesor, Agrupacion, Instrumento,
)
from werkzeug.security import generate_password_hash
from datetime import date
import os


def seed(app=None, drop=True):
    # Guard anti-borrado: en producción un `python -m backend.seed.seed`
    # accidental con DATABASE_URL real haría drop_all() y vaciaría el núcleo.
    # Se exige override explícito para el bootstrap inicial.
    if os.getenv("FLASK_ENV") == "production" and os.getenv("ALLOW_SEED_PROD") != "1":
        raise RuntimeError(
            "seed bloqueado en producción (haría drop_all). "
            "Si es el bootstrap inicial, re-ejecuta con ALLOW_SEED_PROD=1"
        )
    if app is None:
        app = create_app()
    with app.app_context():
        db.session.remove()
        if drop:
            db.drop_all()
        db.create_all()
        db.session.commit()
        print("BD recreada.")

        # ── Roles ──
        admin = Usuario(
            cedula="V-00000001",
            nombre="Administrador",
            apellido="General",
            email="admin@nucleoteques.gob.ve",
            password_hash=generate_password_hash("admin123"),
            password_set=True,
            role="admin",
        )
        profesor1 = Usuario(
            cedula="V-12345678",
            nombre="Yared",
            apellido="Martínez",
            email="yared@nucleoteques.gob.ve",
            password_hash=generate_password_hash("prof123"),
            password_set=True,
            role="profesor",
        )
        profesor2 = Usuario(
            cedula="V-23456789",
            nombre="María",
            apellido="González",
            email="maria@nucleoteques.gob.ve",
            password_hash=generate_password_hash("prof123"),
            password_set=True,
            role="secretaria",
        )
        jurado1 = Usuario(
            cedula="V-34567890",
            nombre="Carlos",
            apellido="Juez",
            email="carlos@nucleoteques.gob.ve",
            password_hash=generate_password_hash("jurado123"),
            password_set=True,
            role="jurado",
        )
        alumno1 = Usuario(
            cedula="V-28765432",
            nombre="Andrea",
            apellido="Fernández",
            email="andrea@correo.com",
            password_hash=generate_password_hash("alumno123"),
            password_set=True,
            role="alumno",
        )
        alumno2 = Usuario(
            cedula="V-29555333",
            nombre="José",
            apellido="Rivas",
            email="jose@correo.com",
            password_hash=generate_password_hash("alumno123"),
            password_set=True,
            role="alumno",
        )
        alumno3 = Usuario(
            cedula="V-30444444",
            nombre="Diana",
            apellido="Torres",
            email="diana@correo.com",
            password_hash=generate_password_hash("alumno123"),
            password_set=True,
            role="alumno",
        )
        alumno4 = Usuario(
            cedula="V-31111111",
            nombre="Luis",
            apellido="Peña",
            email="luis@correo.com",
            password_hash=generate_password_hash("alumno123"),
            password_set=True,
            role="alumno",
        )
        alumno_pending = Usuario(
            cedula="V-99999999",
            nombre="Carlos",
            apellido="Mendoza",
            email="carlos.mendoza@correo.com",
            password_hash=None,
            password_set=False,
            role="alumno",
        )

        db.session.add_all([admin, profesor1, profesor2, jurado1, alumno1, alumno2, alumno3, alumno4, alumno_pending])
        db.session.flush()

        # ── Agrupaciones ──
        coro = Agrupacion(nombre="Coro Juvenil Los Teques", tipo="coral", descripcion="Coro principal del núcleo")
        orquesta = Agrupacion(nombre="Orquesta Sinfónica Infantil", tipo="orquestal", descripcion="Orquesta de iniciación")
        banda = Agrupacion(nombre="Banda Show Municipal", tipo="orquestal", descripcion="Banda de concierto")
        db.session.add_all([coro, orquesta, banda])
        db.session.flush()

        # ── Instrumentos ──
        instrumentos = [
            Instrumento(nombre="Violín", familia="Cuerdas"),
            Instrumento(nombre="Viola", familia="Cuerdas"),
            Instrumento(nombre="Violonchelo", familia="Cuerdas"),
            Instrumento(nombre="Contrabajo", familia="Cuerdas"),
            Instrumento(nombre="Flauta Traversa", familia="Vientos"),
            Instrumento(nombre="Clarinete", familia="Vientos"),
            Instrumento(nombre="Oboe", familia="Vientos"),
            Instrumento(nombre="Trompeta", familia="Vientos"),
            Instrumento(nombre="Trombón", familia="Vientos"),
            Instrumento(nombre="Corno", familia="Vientos"),
            Instrumento(nombre="Percusión", familia="Percusión"),
            Instrumento(nombre="Voz", familia="Vocal"),
        ]
        db.session.add_all(instrumentos)
        db.session.flush()

        # ── Asociaciones ──
        # Profesores ↔ Agrupaciones
        profesor1.agrupaciones.append(coro)
        profesor1.agrupaciones.append(orquesta)
        profesor2.agrupaciones.append(banda)

        # Alumnos ↔ Agrupaciones
        alumno1.agrupaciones.append(coro)
        alumno2.agrupaciones.append(coro)
        alumno3.agrupaciones.append(banda)
        alumno4.agrupaciones.append(orquesta)

        # Admin ve todas
        ADMIN_GROUPS = [coro, orquesta, banda]
        admin.agrupaciones.extend(ADMIN_GROUPS)

        # ── Alumno profiles ──
        db.session.add_all([
            Alumno(usuario_id=alumno1.id, fecha_nacimiento=date(2010,5,12), telefono="0412-5550101",
                   nombre_representante="Sra. Fernández", fecha_ingreso=date(2022,9,1)),
            Alumno(usuario_id=alumno2.id, fecha_nacimiento=date(2009,10,22), telefono="0412-5550202",
                   nombre_representante="Sr. Rivas", fecha_ingreso=date(2021,1,15)),
            Alumno(usuario_id=alumno3.id, fecha_nacimiento=date(2011,7,5), telefono="0412-5550303",
                   nombre_representante="Sra. Torres", fecha_ingreso=date(2023,3,10)),
            Alumno(usuario_id=alumno4.id, fecha_nacimiento=date(2013,4,9), telefono="0412-5550404",
                   nombre_representante="Sra. Díaz", fecha_ingreso=date(2022,1,20)),
            Alumno(usuario_id=alumno_pending.id, fecha_nacimiento=date(2012,8,15), telefono="0412-5550909",
                   nombre_representante="Sr. Mendoza", fecha_ingreso=date(2024,1,10)),
        ])

        # Profesor profiles
        db.session.add_all([
            Profesor(usuario_id=profesor1.id, especialidad="Música - Dirección Coral", telefono="0412-1111111"),
            Profesor(usuario_id=profesor2.id, especialidad="Música - Administración", telefono="0412-2222222"),
        ])

        # Asignar instrumentos a alumnos
        d_alumno1 = Alumno.query.filter_by(usuario_id=alumno1.id).first()
        d_alumno2 = Alumno.query.filter_by(usuario_id=alumno2.id).first()
        d_alumno3 = Alumno.query.filter_by(usuario_id=alumno3.id).first()
        d_alumno4 = Alumno.query.filter_by(usuario_id=alumno4.id).first()

        voces = Instrumento.query.filter_by(nombre="Voz").first()
        violin = Instrumento.query.filter_by(nombre="Violín").first()
        perc = Instrumento.query.filter_by(nombre="Percusión").first()
        flauta = Instrumento.query.filter_by(nombre="Flauta Traversa").first()

        if voces:
            d_alumno1.instrumentos.append(voces)
            d_alumno2.instrumentos.append(voces)
        if perc:
            d_alumno3.instrumentos.append(perc)
        if violin:
            d_alumno4.instrumentos.append(violin)
            d_alumno4.instrumentos.append(flauta)

        db.session.commit()
        print("Seed completado:")
        print("   admin     / V-00000001 / admin123")
        print("   Prof Yared / V-12345678 / prof123")
        print("   Secretaria / V-23456789 / prof123")
        print("   Jurado     / V-34567890 / jurado123")
    print("   Alumno 1   / V-28765432 / alumno123")
    print("   Alumno 2   / V-29555333 / alumno123")
    print("   Alumno 3   / V-30444444 / alumno123")
    print("   Alumno 4   / V-31111111 / alumno123")


if __name__ == "__main__":
    seed()