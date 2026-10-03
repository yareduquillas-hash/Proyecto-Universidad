"""Tests de endurecimiento prod: autorización PII, reset seguro, sesiones, reglas negocio."""
from datetime import date, timedelta

def _ventana():
    hoy = date.today()
    return (hoy - timedelta(days=1)).isoformat(), (hoy + timedelta(days=60)).isoformat()


class TestAuthzPII:
    def test_alumno_no_ve_reporte_ni_exporta(self, client, alumno_h):
        assert client.get("/api/v1/asistencia/reporte/1", headers=alumno_h).status_code == 403
        assert client.get("/api/v1/asistencia/exportar/1", headers=alumno_h).status_code == 403

    def test_alumno_no_ve_historial_ajeno(self, client, alumno_h):
        # alumno fixture es Alumno id 1; el 2 es de otro alumno
        r = client.get("/api/v1/asistencia/alumno/2", headers=alumno_h)
        assert r.status_code == 403

    def test_jurado_no_ve_historial_alumno(self, client, jurado_h):
        assert client.get("/api/v1/asistencia/alumno/1", headers=jurado_h).status_code == 403

    def test_alumno_no_ve_otro_usuario(self, client, alumno_h):
        assert client.get("/api/v1/usuarios/1", headers=alumno_h).status_code == 403

    def test_audiciones_internas_solo_jurado_admin(self, client, admin_h, jurado_h, alumno_h):
        fi, ff = _ventana()
        conv = client.post("/api/v1/audiciones/convocatorias", headers=admin_h, json={
            "titulo": "PII", "fecha_inicio": fi, "fecha_fin": ff}).get_json()
        asp = client.post("/api/v1/audiciones/aspirantes", headers=admin_h, data={
            "convocatoria_id": conv["id"], "nombre": "Ana", "apellido": "Bravo",
            "cedula": "V-88112233"}).get_json()
        aid = asp["id"]
        assert client.get(f"/api/v1/audiciones/aspirantes/{aid}", headers=alumno_h).status_code == 403
        assert client.get(f"/api/v1/audiciones/aspirantes/{aid}", headers=jurado_h).status_code == 200
        # Ranking eliminado: 404 para cualquier rol (pendiente definir con el conservatorio)
        assert client.get(f"/api/v1/audiciones/convocatoria/{conv['id']}/ranking", headers=alumno_h).status_code == 404
        assert client.get(f"/api/v1/audiciones/convocatoria/{conv['id']}/ranking", headers=jurado_h).status_code == 404


class TestActivacionSegura:
    def test_activar_sin_email_falla(self, client):
        r = client.post("/api/v1/auth/activar-cuenta", json={
            "cedula": "V-99999999", "password": "Xx123456", "confirm_password": "Xx123456"})
        assert r.status_code == 400

    def test_activar_email_incorrecto_no_enumera(self, client):
        r = client.post("/api/v1/auth/activar-cuenta", json={
            "cedula": "V-99999999", "email": "otro@x.com",
            "password": "Xx123456", "confirm_password": "Xx123456"})
        assert r.status_code == 404


class TestPasswordReset:
    def _resetear(self, client, cedula, nueva="NuevaClave123"):
        f = client.post("/api/v1/auth/forgot", json={"cedula": cedula})
        assert f.status_code == 200
        codigo = f.get_json().get("code_debug")
        assert codigo, "en TESTING forgot debe devolver code_debug"
        v = client.post("/api/v1/auth/verify-code", json={"cedula": cedula, "codigo": codigo})
        assert v.status_code == 200
        r = client.post("/api/v1/auth/reset", json={
            "cedula": cedula, "codigo": codigo,
            "password": nueva, "confirm_password": nueva})
        assert r.status_code == 200
        # Un solo uso
        r2 = client.post("/api/v1/auth/reset", json={
            "cedula": cedula, "codigo": codigo,
            "password": "OtraClave123", "confirm_password": "OtraClave123"})
        assert r2.status_code == 400
        return nueva

    def test_forgot_no_enumera(self, client):
        r = client.post("/api/v1/auth/forgot", json={"cedula": "V-00000000"})
        assert r.status_code == 200
        assert "code_debug" not in r.get_json()

    def test_reset_completo_y_login(self, client):
        nueva = self._resetear(client, "V-28765432")
        ok = client.post("/api/v1/auth/login", json={"cedula": "V-28765432", "password": nueva})
        assert ok.status_code == 200

    def test_reset_invalida_jwt_viejo(self, client, alumno_h):
        # token viejo de alumno_h debe morir tras el reset (password_version)
        self._resetear(client, "V-28765432", "ClaveNueva999")
        assert client.get("/api/v1/auth/me", headers=alumno_h).status_code == 401


class TestSesiones:
    def test_logout_invalida_token(self, client):
        login = client.post("/api/v1/auth/login", json={"cedula": "V-00000001", "password": "admin123"}).get_json()
        h = {"Authorization": f"Bearer {login['access_token']}"}
        assert client.get("/api/v1/auth/me", headers=h).status_code == 200
        assert client.post("/api/v1/auth/logout", headers=h, json={"refresh_token": login["refresh_token"]}).status_code == 200
        assert client.get("/api/v1/auth/me", headers=h).status_code == 401

    def test_refresh_emite_access(self, client):
        login = client.post("/api/v1/auth/login", json={"cedula": "V-00000001", "password": "admin123"}).get_json()
        rh = {"Authorization": f"Bearer {login['refresh_token']}"}
        r = client.post("/api/v1/auth/refresh", headers=rh)
        assert r.status_code == 200
        assert "access_token" in r.get_json()

    def test_change_password_rota_sesion(self, client):
        login = client.post("/api/v1/auth/login", json={"cedula": "V-29555333", "password": "alumno123"}).get_json()
        h = {"Authorization": f"Bearer {login['access_token']}"}
        r = client.post("/api/v1/auth/change-password", headers=h, json={
            "current_password": "alumno123", "password": "Cambio1234", "confirm_password": "Cambio1234"})
        assert r.status_code == 200
        # token viejo muere
        assert client.get("/api/v1/auth/me", headers=h).status_code == 401
        # el nuevo sirve
        nh = {"Authorization": f"Bearer {r.get_json()['access_token']}"}
        assert client.get("/api/v1/auth/me", headers=nh).status_code == 200


class TestReglasNegocio:
    def test_no_desactivar_ultimo_admin(self, client, admin_h):
        me = client.get("/api/v1/auth/me", headers=admin_h).get_json()
        r = client.delete(f"/api/v1/usuarios/{me['id']}", headers=admin_h)
        assert r.status_code == 400

    def test_asistencia_rechaza_otra_agrupacion_y_futura(self, client, prof_h):
        # Alumno 3 está en banda (id 3), no en coro (id 1). Fecha reciente para
        # no activar la ventana de 7 días (D5) y probar pertenencia.
        hoy = date.today().isoformat()
        r = client.post("/api/v1/asistencia/registrar", headers=prof_h, json={
            "agrupacion_id": 1, "fecha": hoy,
            "registros": [{"alumno_id": 3, "estado": "presente"}]})
        assert r.status_code == 400
        r2 = client.post("/api/v1/asistencia/registrar", headers=prof_h, json={
            "agrupacion_id": 1, "fecha": "2999-01-01",
            "registros": [{"alumno_id": 1, "estado": "presente"}]})
        assert r2.status_code == 400

    def test_cronograma_solape_409(self, client, prof_h):
        body = {"agrupacion_id": 1, "titulo": "Solape A", "tipo": "ensayo",
                "fecha_inicio": "2025-08-01T10:00", "fecha_fin": "2025-08-01T12:00"}
        assert client.post("/api/v1/cronograma/eventos", headers=prof_h, json=body).status_code == 201
        body2 = dict(body, titulo="Solape B")
        assert client.post("/api/v1/cronograma/eventos", headers=prof_h, json=body2).status_code == 409

    def test_aspirante_reinscripcion_otra_convocatoria_ok(self, client, admin_h):
        fi, ff = _ventana()
        c1 = client.post("/api/v1/audiciones/convocatorias", headers=admin_h, json={
            "titulo": "C-A", "fecha_inicio": fi, "fecha_fin": ff}).get_json()
        c2 = client.post("/api/v1/audiciones/convocatorias", headers=admin_h, json={
            "titulo": "C-B", "fecha_inicio": fi, "fecha_fin": ff}).get_json()
        d = {"convocatoria_id": c1["id"], "nombre": "Re", "apellido": "Inscrito", "cedula": "V-55556666"}
        assert client.post("/api/v1/audiciones/aspirantes", headers=admin_h, data=d).status_code == 201
        d2 = dict(d, convocatoria_id=c2["id"])
        assert client.post("/api/v1/audiciones/aspirantes", headers=admin_h, data=d2).status_code == 201
        # duplicada en la MISMA convocatoria sí falla
        assert client.post("/api/v1/audiciones/aspirantes", headers=admin_h, data=d2).status_code == 400
