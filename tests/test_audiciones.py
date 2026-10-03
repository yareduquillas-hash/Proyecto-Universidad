from datetime import date, timedelta
def _ventana():
    hoy = date.today()
    return (hoy - timedelta(days=1)).isoformat(), (hoy + timedelta(days=60)).isoformat()

class TestAudiciones:
    def test_convocatoria_crud(self, client, admin_h):
        fi, ff = _ventana()
        r = client.post("/api/v1/audiciones/convocatorias", headers=admin_h, json={
            "titulo": "C2025", "fecha_inicio": fi, "fecha_fin": ff
        })
        assert r.status_code == 201
        cid = r.get_json()["id"]

        r2 = client.get("/api/v1/audiciones/convocatorias", headers=admin_h)
        assert r2.status_code == 200

        r3 = client.put(f"/api/v1/audiciones/convocatorias/{cid}/activar", headers=admin_h)
        assert r3.status_code == 200

    def test_aspirante_puntuacion(self, client, admin_h, jurado_h):
        fi, ff = _ventana()
        conv = client.post("/api/v1/audiciones/convocatorias", headers=admin_h, json={
            "titulo": "C2025B", "fecha_inicio": fi, "fecha_fin": ff
        }).get_json()
        r = client.post("/api/v1/audiciones/aspirantes", headers=admin_h, data={
            "convocatoria_id": conv["id"], "nombre": "Ana", "apellido": "Bravo",
            "cedula": "V-88888888", "email": "ab@test.com"
        })
        assert r.status_code == 201
        aid = r.get_json()["id"]

        r2 = client.post(f"/api/v1/audiciones/aspirantes/{aid}/puntuacion", headers=jurado_h, json={
            "tecnica": 5, "interpretacion": 4, "afinacion": 3, "ritmo": 4, "presencia": 5
        })
        assert r2.status_code == 201

        r3 = client.get(f"/api/v1/audiciones/convocatoria/{conv['id']}/ranking", headers=admin_h)
        assert r3.status_code == 404  # ranking eliminado (pendiente definir con el conservatorio)

    def test_alumno_cant_crear(self, client, alumno_h):
        r = client.post("/api/v1/audiciones/convocatorias", headers=alumno_h, json={
            "titulo": "Hack", "fecha_inicio": "2025-01-01", "fecha_fin": "2025-12-31"
        })
        assert r.status_code == 403