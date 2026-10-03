"""Tests de la auditoría de cierre: rate-limit acotado, paginación, export
sin tope, revocación de sesión, IntegrityError, TZ Caracas, DELETE aspirante,
CSV antifórmula y upgrade de esquema (instalación limpia / BD legacy)."""
import os
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from backend.extensions import db
from backend.models import Asistencia, Usuario
from backend.utils import rate_limit as rl


class TestRateLimitAcotado:
    def test_claves_no_crecen_sin_limite(self, app):
        # Simula rotación masiva de identidad (hallazgo 2): el dict debe quedar
        # acotado a _MAX_KEYS y las claves vencidas deben poder eliminarse.
        original = rl._MAX_KEYS
        rl._MAX_KEYS = 50
        try:
            rl.clear_rate_limits()
            now = time.time()
            with app.test_request_context("/", environ_base={"REMOTE_ADDR": "10.0.0.9"}):
                for i in range(200):
                    key = f"forgot:10.0.0.9:ced{i}"
                    rl._is_rate_limited(key, 5, 300, record=True)
            assert len(rl._attempts) <= 50
        finally:
            rl._MAX_KEYS = original
            rl.clear_rate_limits()

    def test_inscribir_publico_key_solo_ip(self, app):
        # Rotar cédula no debe crear claves distintas para inscribir-publico.
        with app.test_request_context(
            "/", method="POST", data={"cedula": "V-1"},
            environ_base={"REMOTE_ADDR": "10.1.1.1"},
        ):
            k1 = rl._key_for("inscribir-publico")
        with app.test_request_context(
            "/", method="POST", data={"cedula": "V-2"},
            environ_base={"REMOTE_ADDR": "10.1.1.1"},
        ):
            k2 = rl._key_for("inscribir-publico")
        assert k1 == k2 == "inscribir-publico:10.1.1.1"

    def test_claves_expiradas_se_borran(self, app):
        rl.clear_rate_limits()
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "10.2.2.2"}):
            key = rl._key_for("login")
            rl._is_rate_limited(key, 5, 60, record=True)
        assert key in rl._attempts
        # Simula ventana vencida
        rl._attempts[key][0] = time.time() - 999
        rl._sweep(time.time())
        assert key not in rl._attempts


class TestPaginacionServer:
    def test_usuarios_mas_de_100_page(self, client, admin_h, app):
        with app.app_context():
            base = Usuario.query.count()
            for i in range(110):
                db.session.add(Usuario(
                    cedula=f"V-9{base + i:07d}",
                    nombre=f"Tmp{i}", apellido="Pag",
                    email=f"pag{base + i}@test.com",
                    password_hash="x", password_set=True,
                    role="alumno", activo=True,
                ))
            db.session.commit()

        r1 = client.get("/api/v1/usuarios/?incluir_inactivos=true&page=1&per_page=50", headers=admin_h)
        assert r1.status_code == 200
        j1 = r1.get_json()
        assert isinstance(j1, dict) and j1["page"] == 1
        assert len(j1["items"]) == 50
        assert j1["total"] >= 110

        r2 = client.get("/api/v1/usuarios/?incluir_inactivos=true&page=3&per_page=50", headers=admin_h)
        j2 = r2.get_json()
        assert j2["page"] == 3
        assert j2["items"]
        ids1 = {u["id"] for u in j1["items"]}
        ids2 = {u["id"] for u in j2["items"]}
        assert not (ids1 & ids2)

    def test_aspirantes_page(self, client, admin_h):
        from datetime import date
        fi = (date.today() - timedelta(days=1)).isoformat()
        ff = (date.today() + timedelta(days=60)).isoformat()
        conv = client.post("/api/v1/audiciones/convocatorias", headers=admin_h, json={
            "titulo": "C-Pag", "fecha_inicio": fi, "fecha_fin": ff}).get_json()
        for i in range(55):
            r = client.post("/api/v1/audiciones/aspirantes", headers=admin_h, data={
                "convocatoria_id": conv["id"], "nombre": "Asg", "apellido": f"N{i}",
                "cedula": f"V-7{i:07d}"})
            assert r.status_code == 201, r.get_json()
        r = client.get(f"/api/v1/audiciones/aspirantes?convocatoria_id={conv['id']}&page=2&per_page=50",
                       headers=admin_h)
        j = r.get_json()
        assert j["page"] == 2
        assert 1 <= len(j["items"]) <= 50
        assert j["total"] == 55


class TestExportSinTope:
    def test_export_mas_de_5000(self, client, prof_h, app):
        from datetime import date
        with app.app_context():
            agrup = 1
            alumno_id = 1
            Asistencia.query.filter_by(alumno_id=alumno_id, agrupacion_id=agrup).delete()
            # Fechas distintas: uq_asistencia_dia impide repetir (alumno, agrupación, fecha)
            for i in range(5001):
                db.session.add(Asistencia(
                    alumno_id=alumno_id, agrupacion_id=agrup,
                    fecha=date(2000, 1, 1) + timedelta(days=i),
                    estado="presente", registrado_por=1,
                ))
            db.session.commit()

        r = client.get(f"/api/v1/asistencia/exportar/{agrup}", headers=prof_h)
        assert r.status_code == 200, r.get_json()
        lines = r.get_data(as_text=True).strip().splitlines()
        assert len(lines) > 5000


class TestCsvAntiFormula:
    def test_observacion_formula_neutralizada(self, client, prof_h, app):
        # Fecha relativa: la ventana de corrección del profesor es de 7 días.
        hoy = (date.today() - timedelta(days=1)).isoformat()
        r = client.post("/api/v1/asistencia/registrar", headers=prof_h, json={
            "agrupacion_id": 1, "fecha": hoy,
            "registros": [{"alumno_id": 1, "estado": "presente",
                           "observaciones": "=cmd|'/c calc'!A1"}]})
        assert r.status_code in (200, 201), r.get_json()
        exp = client.get("/api/v1/asistencia/exportar/1", headers=prof_h)
        assert exp.status_code == 200
        body = exp.get_data(as_text=True)
        assert "'=cmd|'/c calc'!A1" in body


class TestRevocacionSesion:
    def test_token_usuario_desactivado_401_ruta_sin_current_user(self, client, admin_h):
        # /api/v1/partituras/filtros es solo @jwt_required (sin current_user/rol):
        # antes el token de un desactivado seguía operando.
        login = client.post("/api/v1/auth/login", json={
            "cedula": "V-29555333", "password": "alumno123"}).get_json()
        tok = {"Authorization": f"Bearer {login['access_token']}"}
        assert client.get("/api/v1/partituras/filtros", headers=tok).status_code == 200

        me = client.get("/api/v1/auth/me", headers=tok).get_json()
        r = client.put(f"/api/v1/usuarios/{me['id']}", headers=admin_h, json={"activo": False})
        assert r.status_code == 200

        assert client.get("/api/v1/partituras/filtros", headers=tok).status_code == 401

    def test_token_pv_desactualizado_401_ruta_sin_current_user(self, client, app):
        login = client.post("/api/v1/auth/login", json={
            "cedula": "V-29555333", "password": "alumno123"}).get_json()
        tok = {"Authorization": f"Bearer {login['access_token']}"}
        assert client.get("/api/v1/partituras/filtros", headers=tok).status_code == 200
        with app.app_context():
            u = Usuario.query.filter_by(cedula="V-29555333").first()
            u.password_version = (u.password_version or 0) + 1
            db.session.commit()
        assert client.get("/api/v1/partituras/filtros", headers=tok).status_code == 401


class TestIntegrityErrorManejado:
    def test_asignar_agrupacion_doble_no_500(self, client, admin_h, app, monkeypatch):
        r = client.post("/api/v1/usuarios/asignar-agrupacion", headers=admin_h, json={
            "usuario_id": 2, "agrupacion_id": 1})
        assert r.status_code == 200

        real_commit = db.session.commit

        def boom(*a, **k):
            raise IntegrityError("stmt", {}, Exception("dup"))

        monkeypatch.setattr(db.session, "commit", boom)
        r2 = client.post("/api/v1/usuarios/asignar-agrupacion", headers=admin_h, json={
            "usuario_id": 3, "agrupacion_id": 1})
        assert r2.status_code == 200  # ya asignada o carrera: no 500
        monkeypatch.setattr(db.session, "commit", real_commit)

    def test_registrar_asistencia_integrity_200(self, client, prof_h, monkeypatch):
        def boom(*a, **k):
            raise IntegrityError("stmt", {}, Exception("uq_asistencia_dia"))
        monkeypatch.setattr(db.session, "commit", boom)
        r = client.post("/api/v1/asistencia/registrar", headers=prof_h, json={
            "agrupacion_id": 1, "fecha": (date.today() - timedelta(days=1)).isoformat(),
            "registros": [{"alumno_id": 1, "estado": "presente"}]})
        assert r.status_code == 200


class TestTZAudiciones:
    def test_slot_futuro_hoy_caracas_aceptado(self, client, admin_h, app):
        from backend.modules.audiciones.routes import _ahora_ven_naive, VEN_TZ
        ahora = _ahora_ven_naive()
        futuro = ahora + timedelta(hours=3)
        if futuro.date() != ahora.date():
            pytest.skip("Cruza de medianoche Caracas: sin slot 'hoy' futuro")
        r = client.post("/api/v1/audiciones/audiciones", headers=admin_h, json={
            "agrupacion_id": 1,
            "fecha": futuro.date().isoformat(),
            "hora": futuro.strftime("%H:%M"),
        })
        assert r.status_code == 201, r.get_json()

    def test_slot_pasado_hoy_caracas_rechazado(self, client, admin_h):
        from backend.modules.audiciones.routes import _ahora_ven_naive
        ahora = _ahora_ven_naive()
        pasado = ahora - timedelta(hours=2)
        if pasado.date() != ahora.date():
            pytest.skip("Cruza de medianoche Caracas")
        r = client.post("/api/v1/audiciones/audiciones", headers=admin_h, json={
            "agrupacion_id": 1,
            "fecha": pasado.date().isoformat(),
            "hora": pasado.strftime("%H:%M"),
        })
        assert r.status_code == 400


class TestDeleteAspirante:
    def test_delete_admin(self, client, admin_h):
        from datetime import date
        fi = (date.today() - timedelta(days=1)).isoformat()
        ff = (date.today() + timedelta(days=60)).isoformat()
        conv = client.post("/api/v1/audiciones/convocatorias", headers=admin_h, json={
            "titulo": "C-Del", "fecha_inicio": fi, "fecha_fin": ff}).get_json()
        asp = client.post("/api/v1/audiciones/aspirantes", headers=admin_h, data={
            "convocatoria_id": conv["id"], "nombre": "Bor", "apellido": "Rarme",
            "cedula": "V-66666666"}).get_json()
        aid = asp["id"]
        r = client.delete(f"/api/v1/audiciones/aspirantes/{aid}", headers=admin_h)
        assert r.status_code == 200, r.get_json()
        assert client.get(f"/api/v1/audiciones/aspirantes/{aid}", headers=admin_h).status_code == 404

    def test_delete_alumno_403(self, client, admin_h, alumno_h):
        from datetime import date
        fi = (date.today() - timedelta(days=1)).isoformat()
        ff = (date.today() + timedelta(days=60)).isoformat()
        conv = client.post("/api/v1/audiciones/convocatorias", headers=admin_h, json={
            "titulo": "C-Del2", "fecha_inicio": fi, "fecha_fin": ff}).get_json()
        asp = client.post("/api/v1/audiciones/aspirantes", headers=admin_h, data={
            "convocatoria_id": conv["id"], "nombre": "Xx", "apellido": "Yy",
            "cedula": "V-66666667"}).get_json()
        assert client.delete(f"/api/v1/audiciones/aspirantes/{asp['id']}",
                             headers=alumno_h).status_code in (401, 403)


class TestSchemaUpgrade:
    def test_flask_db_upgrade_bd_limpia(self):
        """Instalación limpia: upgrade crea el esquema completo (entrypoint Docker)."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(path)
        url = f"sqlite:///{path}"
        env = dict(os.environ)
        env["FLASK_APP"] = "run.py"
        env["DATABASE_URL"] = url
        env.pop("FLASK_ENV", None)
        try:
            r = subprocess.run(
                [sys.executable, "-m", "flask", "db", "upgrade"],
                cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
                env=env, capture_output=True, text=True, timeout=120,
            )
            assert r.returncode == 0, r.stderr + r.stdout
            import sqlite3
            conn = sqlite3.connect(path)
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            conn.close()
            for t in ("usuarios", "asistencias", "aspirantes", "alembic_version",
                      "puntuaciones_audicion", "eventos_cronograma"):
                assert t in tables, f"falta tabla {t}"
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_bd_legacy_sin_alembic_stamp_head(self, app):
        """BD creada con create_all y sin alembic_version: stamp no debe fallar
        (es lo que hace docker-entrypoint.sh antes de servir)."""
        from flask_migrate import stamp
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        migrations_dir = os.path.join(root, "migrations")
        with app.app_context():
            # El fixture usa seed (create_all): no hay alembic_version
            has = db.session.execute(db.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
            )).first()
            assert has is None
            stamp(directory=migrations_dir)
            row = db.session.execute(db.text(
                "SELECT version_num FROM alembic_version"
            )).first()
            assert row is not None and row[0] == "737d9a85a650"
