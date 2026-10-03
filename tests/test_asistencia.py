from datetime import date


class TestAsistencia:
    def test_list_alumnos_by_fecha(self, client, prof_h):
        hoy = date.today().isoformat()
        r = client.get(f"/api/v1/asistencia/agrupacion/1/fecha/{hoy}", headers=prof_h)
        assert r.status_code == 200
        alumnos = r.get_json()
        assert len(alumnos) >= 1

    def test_registrar_asistencia(self, client, prof_h):
        hoy = date.today().isoformat()
        alumnos = client.get(f"/api/v1/asistencia/agrupacion/1/fecha/{hoy}", headers=prof_h).get_json()
        r = client.post("/api/v1/asistencia/registrar", headers=prof_h, json={
            "agrupacion_id": 1, "fecha": hoy,
            "registros": [{"alumno_id": a["alumno_id"], "estado": "presente", "observaciones": ""} for a in alumnos]
        })
        assert r.status_code == 201

    def test_historial_alumno(self, client, prof_h):
        r = client.get("/api/v1/asistencia/alumno/1", headers=prof_h)
        assert r.status_code == 200
        assert "porcentaje_inasistencias" in r.get_json()

    def test_reporte_agrupacion(self, client, prof_h):
        r = client.get("/api/v1/asistencia/reporte/1", headers=prof_h)
        assert r.status_code == 200
        assert len(r.get_json()) >= 1

    def test_exportar_csv(self, client, prof_h):
        r = client.get("/api/v1/asistencia/exportar/1", headers=prof_h)
        assert r.status_code == 200
        assert "text/csv" in r.content_type