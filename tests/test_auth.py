class TestAuth:
    def test_login_ok(self, client):
        r = client.post("/api/v1/auth/login", json={"cedula": "V-00000001", "password": "admin123"})
        assert r.status_code == 200
        data = r.get_json()
        assert "access_token" in data
        assert data["role"] == "admin"

    def test_login_bad(self, client):
        r = client.post("/api/v1/auth/login", json={"cedula": "V-00000001", "password": "mal"})
        assert r.status_code == 401

    def test_me(self, client, admin_h):
        r = client.get("/api/v1/auth/me", headers=admin_h)
        assert r.status_code == 200
        assert r.get_json()["role"] == "admin"

    def test_menu_admin(self, client, admin_h):
        r = client.get("/api/v1/auth/menu", headers=admin_h)
        assert r.status_code == 200
        menus = r.get_json()
        assert any(m["name"] == "usuarios" for m in menus)

    def test_menu_alumno(self, client, alumno_h):
        r = client.get("/api/v1/auth/menu", headers=alumno_h)
        menus = r.get_json()
        assert all(m["name"] != "usuarios" for m in menus)
        assert len(menus) == 3