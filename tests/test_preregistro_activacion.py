import pytest

class TestPreregistroActivacion:

    def test_preregistro_secretaria_sin_password(self, client):
        # Secretaria logs in and pre-registers a student
        sec_login = client.post("/api/v1/auth/login", json={"cedula": "V-23456789", "password": "prof123"})
        assert sec_login.status_code == 200
        sec_h = {"Authorization": f"Bearer {sec_login.get_json()['access_token']}"}

        res = client.post("/api/v1/usuarios/", headers=sec_h, json={
            "cedula": "V-55555555",
            "nombre": "Mariana",
            "apellido": "López",
            "email": "mariana@correo.com",
            "role": "alumno",
            "telefono": "0414-9998877"
        })
        assert res.status_code == 201
        data = res.get_json()
        assert data["cedula"] == "V-55555555"
        assert data["password_set"] is False
        assert data["requiere_activacion"] is True

    def test_login_usuario_sin_activar_falla(self, client):
        # Trying to login with pre-registered user (V-99999999 from seed) before setting password
        res = client.post("/api/v1/auth/login", json={
            "cedula": "V-99999999",
            "password": "cualquiercosa"
        })
        assert res.status_code == 401
        assert res.get_json()["requiere_activacion"] is True

    def test_verificar_cedula(self, client):
        # Non-existent: siempre 200 para no distinguir por código HTTP
        r1 = client.post("/api/v1/auth/verificar-cedula", json={"cedula": "V-00000000"})
        assert r1.status_code == 200
        assert r1.get_json()["status"] == "no_encontrado"

        # Pre-registered (V-99999999)
        r2 = client.post("/api/v1/auth/verificar-cedula", json={"cedula": "V-99999999"})
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "requiere_activacion"
        # Anti-enumeración: no expone PII
        assert "nombre" not in r2.get_json()
        assert "email" not in r2.get_json()

        # Already active
        r3 = client.post("/api/v1/auth/verificar-cedula", json={"cedula": "V-00000001"})
        assert r3.status_code == 200
        assert r3.get_json()["status"] == "activo"

    def test_activacion_password_no_coincide(self, client):
        res = client.post("/api/v1/auth/activar-cuenta", json={
            "cedula": "V-99999999",
            "email": "carlos.mendoza@correo.com",
            "password": "Password123",
            "confirm_password": "Password456"
        })
        assert res.status_code == 400
        assert "no coinciden" in res.get_json()["error"]

    def test_activacion_password_corta(self, client):
        res = client.post("/api/v1/auth/activar-cuenta", json={
            "cedula": "V-99999999",
            "email": "carlos.mendoza@correo.com",
            "password": "123",
            "confirm_password": "123"
        })
        assert res.status_code == 400
        assert "al menos 8 caracteres" in res.get_json()["error"]

    def test_activacion_exitosa_y_login(self, client):
        # Activate account V-99999999
        res = client.post("/api/v1/auth/activar-cuenta", json={
            "cedula": "V-99999999",
            "email": "carlos.mendoza@correo.com",
            "password": "NuevaPassword123",
            "confirm_password": "NuevaPassword123"
        })
        assert res.status_code == 200
        data = res.get_json()
        assert "access_token" in data
        assert data["role"] == "alumno"

        # Now login with the newly registered password
        res_login = client.post("/api/v1/auth/login", json={
            "cedula": "V-99999999",
            "password": "NuevaPassword123"
        })
        assert res_login.status_code == 200
        assert "access_token" in res_login.get_json()

    def test_pre_registro_todos_los_roles(self, client, admin_h):
        roles = ["alumno", "profesor", "secretaria", "jurado", "admin"]
        for idx, role in enumerate(roles):
            res = client.post("/api/v1/usuarios/pre-registrar", headers=admin_h, json={
                "cedula": f"V-7777000{idx}",
                "nombre": f"Test{role}",
                "apellido": "User",
                "email": f"test_{role}@correo.com",
                "role": role
            })
            assert res.status_code == 201, res.get_json()
            assert res.get_json()["requiere_activacion"] is True
