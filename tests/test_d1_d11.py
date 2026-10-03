"""Regresión D1-D11: cada test falla antes de la corrección y pasa después."""
from datetime import date, datetime, timedelta


def _login(client, cedula, password):
    r = client.post("/api/v1/auth/login", json={"cedula": cedula, "password": password})
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


def _sec_h(client):
    tok = _login(client, "V-23456789", "prof123")["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _ventana():
    hoy = date.today()
    return (hoy - timedelta(days=1)).isoformat(), (hoy + timedelta(days=60)).isoformat()


class TestD1SecretariaLeeTodo:
    def test_secretaria_lee_coro(self, client):
        sh = _sec_h(client)
        r = client.get("/api/v1/cronograma/eventos?agrupacion_id=1", headers=sh)
        assert r.status_code == 200, r.get_json()

    def test_profesor_sigue_restringido(self, client, prof_h):
        # Profesor seed solo coro(1)/orquesta(2): banda(3) le es ajena.
        r = client.get("/api/v1/cronograma/eventos?agrupacion_id=3", headers=prof_h)
        assert r.status_code == 403


class TestD2LogoutExigeRefresh:
    def test_logout_sin_refresh_invalida_access_y_refresh_sigue_vivo(self, client):
        login = _login(client, "V-00000001", "admin123")
        h_acc = {"Authorization": f"Bearer {login['access_token']}"}
        h_ref = {"Authorization": f"Bearer {login['refresh_token']}"}
        # Sin refresh en body igual debe invalidar el access actual.
        assert client.post("/api/v1/auth/logout", headers=h_acc).status_code == 200
        assert client.get("/api/v1/auth/me", headers=h_acc).status_code == 401
        # Sin refresh en body el refresh no se puede invalidar (no se conoce su jti).
        assert client.post("/api/v1/auth/refresh", headers=h_ref).status_code == 200

    def test_logout_completo_invalida_refresh(self, client):
        login = _login(client, "V-00000001", "admin123")
        h_acc = {"Authorization": f"Bearer {login['access_token']}"}
        h_ref = {"Authorization": f"Bearer {login['refresh_token']}"}
        r = client.post("/api/v1/auth/logout", headers=h_acc,
                        json={"refresh_token": login["refresh_token"]})
        assert r.status_code == 200
        assert client.post("/api/v1/auth/refresh", headers=h_ref).status_code == 401


class TestD3AlertasSinPasados:
    def test_pasado_con_flag_no_aparece(self, client, admin_h):
        r = client.post("/api/v1/cronograma/eventos", headers=admin_h, json={
            "agrupacion_id": 1, "titulo": "D3 viejo con flag", "tipo": "ensayo",
            "fecha_inicio": "2020-01-01T10:00", "fecha_fin": "2020-01-01T12:00",
            "notificar_cambios": True, "mensaje_alerta": "viejo"})
        assert r.status_code == 201
        alertas = client.get("/api/v1/cronograma/eventos/alertas", headers=admin_h).get_json()
        assert all(a["titulo"] != "D3 viejo con flag" for a in alertas)


class TestD4MensajeCustom:
    def test_put_preserva_mensaje(self, client, admin_h):
        r = client.post("/api/v1/cronograma/eventos", headers=admin_h, json={
            "agrupacion_id": 1, "titulo": "D4 evt", "tipo": "ensayo",
            "fecha_inicio": "2026-11-01T10:00", "fecha_fin": "2026-11-01T12:00"})
        eid = r.get_json()["id"]
        ru = client.put(f"/api/v1/cronograma/eventos/{eid}", headers=admin_h, json={
            "fecha_inicio": "2026-11-02T10:00", "fecha_fin": "2026-11-02T12:00",
            "notificar_cambios": True, "mensaje_alerta": "MI MENSAJE D4"})
        assert ru.status_code == 200
        body = ru.get_json()
        assert body["mensaje_alerta"] == "MI MENSAJE D4"
        assert body["alerta_generada"] is True

    def test_solo_titulo_no_genera_alerta(self, client, admin_h):
        r = client.post("/api/v1/cronograma/eventos", headers=admin_h, json={
            "agrupacion_id": 1, "titulo": "D4 titulo A", "tipo": "ensayo",
            "fecha_inicio": "2026-12-01T10:00", "fecha_fin": "2026-12-01T12:00"})
        eid = r.get_json()["id"]
        ru = client.put(f"/api/v1/cronograma/eventos/{eid}", headers=admin_h, json={
            "titulo": "D4 titulo B", "notificar_cambios": True})
        assert ru.status_code == 200
        assert ru.get_json()["alerta_generada"] is False


class TestD5Ventana7Dias:
    def test_profesor_no_edita_historico_admin_si(self, client, prof_h, admin_h):
        vieja = (date.today() - timedelta(days=30)).isoformat()
        rp = client.post("/api/v1/asistencia/registrar", headers=prof_h, json={
            "agrupacion_id": 1, "fecha": vieja,
            "registros": [{"alumno_id": 1, "estado": "presente"}]})
        assert rp.status_code == 403
        ra = client.post("/api/v1/asistencia/registrar", headers=admin_h, json={
            "agrupacion_id": 1, "fecha": vieja,
            "registros": [{"alumno_id": 1, "estado": "presente"}]})
        assert ra.status_code == 201


class TestD6ProfesorSinAspirantes:
    def test_profesor_bloqueado_jurado_pasa(self, client, admin_h, jurado_h, prof_h):
        fi, ff = _ventana()
        conv = client.post("/api/v1/audiciones/convocatorias", headers=admin_h, json={
            "titulo": "D6 conv", "fecha_inicio": fi, "fecha_fin": ff}).get_json()
        asp = client.post("/api/v1/audiciones/aspirantes", headers=admin_h, data={
            "convocatoria_id": conv["id"], "nombre": "Ana", "apellido": "Bravo",
            "cedula": "V-66001122"}).get_json()
        aid = asp["id"]
        assert client.get("/api/v1/audiciones/aspirantes", headers=prof_h).status_code == 403
        assert client.get(f"/api/v1/audiciones/aspirantes/{aid}", headers=prof_h).status_code == 403
        client.post(f"/api/v1/audiciones/aspirantes/{aid}/puntuacion", headers=jurado_h, json={
            "tecnica": 8, "interpretacion": 8, "afinacion": 8, "ritmo": 8, "presencia": 8})
        assert client.get(f"/api/v1/audiciones/puntuaciones/aspirante/{aid}",
                          headers=prof_h).status_code == 403
        assert client.get(f"/api/v1/audiciones/aspirantes/{aid}",
                          headers=jurado_h).status_code == 200


class TestD7DashboardSoloActivos:
    def test_baja_no_cuenta(self, client, admin_h):
        antes = client.get("/api/v1/dashboard/stats", headers=admin_h).get_json()["total_usuarios"]
        u = client.post("/api/v1/usuarios/", headers=admin_h, json={
            "cedula": "V-70001001", "nombre": "Tmp", "apellido": "Baja",
            "email": "tmpbaja@test.com", "role": "alumno"}).get_json()
        medio = client.get("/api/v1/dashboard/stats", headers=admin_h).get_json()["total_usuarios"]
        assert medio == antes + 1
        assert client.delete(f"/api/v1/usuarios/{u['id']}", headers=admin_h).status_code == 200
        despues = client.get("/api/v1/dashboard/stats", headers=admin_h).get_json()["total_usuarios"]
        assert despues == antes


class TestD8JustificadosSuman:
    def test_justificado_da_100(self, client, admin_h):
        f1 = date.today().isoformat()
        f2 = (date.today() - timedelta(days=1)).isoformat()
        for f in (f1, f2):
            r = client.post("/api/v1/asistencia/registrar", headers=admin_h, json={
                "agrupacion_id": 1, "fecha": f,
                "registros": [{"alumno_id": 2, "estado": "justificado"}]})
            assert r.status_code == 201
        h = client.get("/api/v1/asistencia/alumno/2", headers=admin_h).get_json()
        assert h["justificados"] >= 2
        assert h["porcentaje_asistencia"] == 100.0
        assert h["porcentaje_inasistencias"] == 0.0


class TestD9Readmision:
    def test_cedula_usuario_puede_reaplicar(self, client, admin_h):
        u = client.post("/api/v1/usuarios/", headers=admin_h, json={
            "cedula": "V-71002002", "nombre": "Ex", "apellido": "Alumno",
            "email": "exd9@test.com", "role": "alumno"})
        assert u.status_code == 201
        fi, ff = _ventana()
        conv = client.post("/api/v1/audiciones/convocatorias", headers=admin_h, json={
            "titulo": "D9 conv", "fecha_inicio": fi, "fecha_fin": ff}).get_json()
        r = client.post("/api/v1/audiciones/aspirantes", headers=admin_h, data={
            "convocatoria_id": conv["id"], "nombre": "Ex", "apellido": "Alumno",
            "cedula": "V-71002002"})
        assert r.status_code == 201, r.get_json()
        dup = client.post("/api/v1/audiciones/aspirantes", headers=admin_h, data={
            "convocatoria_id": conv["id"], "nombre": "Ex", "apellido": "Alumno",
            "cedula": "V-71002002"})
        assert dup.status_code == 400


class TestD10TemporalObligaCambio:
    def test_temporal_bloquea_hasta_cambiar(self, client, admin_h):
        tmp = client.post("/api/v1/usuarios/2/reset-password", headers=admin_h).get_json()["temporal"]
        login = _login(client, "V-12345678", tmp)
        assert login["requiere_cambio_clave"] is True
        ht = {"Authorization": f"Bearer {login['access_token']}"}
        assert client.get("/api/v1/auth/me", headers=ht).status_code == 200
        r = client.get("/api/v1/partituras/", headers=ht)
        assert r.status_code == 403
        assert r.get_json().get("requiere_cambio_clave") is True
        rc = client.post("/api/v1/auth/change-password", headers=ht, json={
            "current_password": tmp, "password": "CambioD10_1",
            "confirm_password": "CambioD10_1"})
        assert rc.status_code == 200
        hn = {"Authorization": f"Bearer {rc.get_json()['access_token']}"}
        assert client.get("/api/v1/partituras/", headers=hn).status_code == 200


class TestD11AudicionHoyLocal:
    def test_hora_futura_local_pasa_y_pasada_falla(self, client, admin_h):
        ahora = datetime.now().replace(second=0, microsecond=0)
        futura = ahora + timedelta(hours=2)
        if futura.date() != ahora.date():
            futura = ahora  # al borde de medianoche no se prueba mismo-día
            assert True
            return
        hora_fut = futura.strftime("%H:%M")
        r = client.post("/api/v1/audiciones/audiciones", headers=admin_h, json={
            "agrupacion_id": 1, "fecha": ahora.date().isoformat(), "hora": hora_fut})
        assert r.status_code == 201, r.get_json()
        pasada_dt = ahora - timedelta(minutes=30)
        if pasada_dt.date() != ahora.date():
            return  # al borde de medianoche no se prueba hora pasada mismo-día
        r2 = client.post("/api/v1/audiciones/audiciones", headers=admin_h, json={
            "agrupacion_id": 1, "fecha": ahora.date().isoformat(),
            "hora": pasada_dt.strftime("%H:%M")})
        assert r2.status_code == 400
