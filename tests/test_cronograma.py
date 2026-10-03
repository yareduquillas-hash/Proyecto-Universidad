class TestCronograma:
    def test_create_evento(self, client, prof_h):
        r = client.post("/api/v1/cronograma/eventos", headers=prof_h, json={
            "agrupacion_id": 1, "titulo": "Test", "tipo": "ensayo",
            "fecha_inicio": "2025-07-15T14:00", "fecha_fin": "2025-07-15T17:00"
        })
        assert r.status_code == 201

    def test_list_eventos(self, client, alumno_h):
        r = client.get("/api/v1/cronograma/eventos", headers=alumno_h)
        assert r.status_code == 200

    def test_proximos(self, client, alumno_h):
        r = client.get("/api/v1/cronograma/eventos/proximos", headers=alumno_h)
        assert r.status_code == 200

    def test_alumno_cant_crear(self, client, alumno_h):
        r = client.post("/api/v1/cronograma/eventos", headers=alumno_h, json={
            "agrupacion_id": 1, "titulo": "Hack", "tipo": "ensayo",
            "fecha_inicio": "2025-07-15T14:00", "fecha_fin": "2025-07-15T17:00"
        })
        assert r.status_code == 403