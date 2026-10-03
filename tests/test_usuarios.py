class TestUsuarios:
    def test_list_usuarios(self, client, admin_h):
        r = client.get("/api/v1/usuarios/", headers=admin_h)
        assert r.status_code == 200
        assert len(r.get_json()) >= 8

    def test_alumno_cant_listar(self, client, alumno_h):
        r = client.get("/api/v1/usuarios/", headers=alumno_h)
        assert r.status_code == 403

    def test_crud_usuario(self, client, admin_h):
        u = client.post("/api/v1/usuarios/", headers=admin_h, json={
            "cedula": "V-77777777", "nombre": "Test", "apellido": "User",
            "email": "t1@test.com", "password": "Test1234", "role": "alumno"
        })
        assert u.status_code == 201
        uid = u.get_json()["id"]

        d = client.delete(f"/api/v1/usuarios/{uid}", headers=admin_h)
        assert d.status_code == 200
        assert d.get_json()["activo"] == False

    def test_alumno_cant_crear(self, client, alumno_h):
        r = client.post("/api/v1/usuarios/", headers=alumno_h, json={
            "nombre": "H", "apellido": "X", "cedula": "x", "email": "x@x", "password": "x", "role": "alumno"
        })
        assert r.status_code == 403

    def test_listar_agrupaciones(self, client, admin_h):
        r = client.get("/api/v1/usuarios/agrupaciones", headers=admin_h)
        assert r.status_code == 200
        assert len(r.get_json()) == 3


class TestCambioRolCreaPerfil:
    """Cambio de rol: el perfil correspondiente debe existir tras el PUT."""

    def test_alumno_a_profesor_crea_ficha_profesor(self, client, admin_h, app):
        from backend.extensions import db
        from backend.models import Usuario

        me = client.get("/api/v1/auth/me", headers=admin_h).get_json()
        # alumno seed id=1 (Andrea, cédula V-28765432) → profesor
        r = client.put("/api/v1/usuarios/5", headers=admin_h, json={"role": "profesor"})
        # el id del alumno seed puede variar; buscar por cédula si hace falta
        if r.status_code == 404:
            with app.app_context():
                u = Usuario.query.filter_by(cedula="V-28765432").first()
                uid = u.id
            r = client.put(f"/api/v1/usuarios/{uid}", headers=admin_h, json={"role": "profesor"})
        assert r.status_code == 200, r.get_json()
        assert r.get_json()["role"] == "profesor"

        uid = r.get_json()["id"]
        with app.app_context():
            u = db.session.get(Usuario, uid)
            assert u is not None
            assert u.role == "profesor"
            assert u.profesor is not None, "cambio alumno→profesor dejó sin ficha Profesor"
            # historial: la ficha Alumno se conserva
            assert u.alumno is not None

    def test_profesor_a_alumno_crea_ficha_alumno(self, client, admin_h, app):
        from backend.extensions import db
        from backend.models import Usuario

        with app.app_context():
            u = Usuario.query.filter_by(cedula="V-12345678").first()
            uid = u.id
            assert u.profesor is not None

        r = client.put(f"/api/v1/usuarios/{uid}", headers=admin_h, json={"role": "alumno"})
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            u = db.session.get(Usuario, uid)
            assert u.role == "alumno"
            assert u.alumno is not None, "cambio profesor→alumno dejó sin ficha Alumno"
            # historial: la ficha Profesor se conserva
            assert u.profesor is not None

    def test_fallo_al_crear_perfil_revuye_cambio_de_rol(self, client, admin_h, app, monkeypatch):
        """Si falla la creación del perfil, el cambio de rol NO debe persistir."""
        from sqlalchemy.exc import IntegrityError
        from backend.extensions import db
        from backend.models import Usuario

        with app.app_context():
            u = Usuario.query.filter_by(cedula="V-29555333").first()
            uid = u.id
            rol_antes = u.role

        real_add = db.session.add

        def add_con_fallo(obj):
            # Solo truena al crear el perfil nuevo, no el resto de la sesión
            if type(obj).__name__ in ("Profesor", "Alumno"):
                raise IntegrityError("stmt", {}, Exception("perfil"))
            return real_add(obj)

        monkeypatch.setattr(db.session, "add", add_con_fallo)
        r = client.put(f"/api/v1/usuarios/{uid}", headers=admin_h, json={"role": "profesor"})
        monkeypatch.undo()

        # o bien 400 (IntegrityError capturado) o 500 (rollback global); nunca 200 con rol nuevo sin ficha
        assert r.status_code in (400, 500), r.get_json()
        with app.app_context():
            u = db.session.get(Usuario, uid)
            db.session.rollback()
            u = db.session.get(Usuario, uid)
            assert u.role == rol_antes, "el cambio de rol persistió a pesar de fallar el perfil"