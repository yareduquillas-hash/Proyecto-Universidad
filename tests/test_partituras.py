class TestPartituras:
    def test_list_empty(self, client, admin_h):
        r = client.get("/api/v1/partituras/", headers=admin_h)
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

    def test_alumno_cant_subir(self, client, alumno_h):
        import io
        data = {"archivo": (io.BytesIO(b"%PDF-1.4"), "test.pdf"), "titulo": "P", "agrupacion_id": "1"}
        r = client.post("/api/v1/partituras/upload", headers=alumno_h, data=data)
        assert r.status_code == 403

    def test_upload_then_list(self, client, admin_h):
        import io
        data = {"archivo": (io.BytesIO(b"%PDF-1.4 fake"), "test.pdf"), "titulo": "Part Test", "agrupacion_id": "1"}
        r = client.post("/api/v1/partituras/upload", headers=admin_h, data=data)
        assert r.status_code == 201

        r2 = client.get("/api/v1/partituras/", headers=admin_h)
        assert r2.status_code == 200
        assert len(r2.get_json()) == 1


class TestPartiturasAislamientoAgrupacion:
    """Un usuario no lista/ve/descarga/previsualiza partituras de otra agrupación."""

    @staticmethod
    def _subir(client, headers, agrupacion_id, titulo):
        import io
        r = client.post(
            "/api/v1/partituras/upload",
            headers=headers,
            data={
                "archivo": (io.BytesIO(b"%PDF-1.4 fake"), "x.pdf"),
                "titulo": titulo,
                "agrupacion_id": str(agrupacion_id),
            },
        )
        assert r.status_code == 201, r.get_json()
        return r.get_json()

    @staticmethod
    def _obtener_por_titulo(client, headers, titulo):
        r = client.get("/api/v1/partituras/", headers=headers)
        assert r.status_code == 200
        items = r.get_json()
        return next(p for p in items if p["titulo"] == titulo)

    def test_alumno_no_ve_partituras_de_otra_agrupacion(self, client, admin_h, alumno_h):
        # alumno_h (Andrea) pertenece al coro (agrupacion 1), no a la banda (3)
        p_coro = self._subir(client, admin_h, 1, "Aisl Coro")
        p_banda = self._subir(client, admin_h, 3, "Aisl Banda")

        r = client.get("/api/v1/partituras/", headers=alumno_h)
        assert r.status_code == 200
        titulos = {p["titulo"] for p in r.get_json()}
        assert "Aisl Coro" in titulos
        assert "Aisl Banda" not in titulos

        # ver
        assert client.get(f"/api/v1/partituras/{p_banda['id']}", headers=alumno_h).status_code == 403
        assert client.get(f"/api/v1/partituras/{p_coro['id']}", headers=alumno_h).status_code == 200
        # descargar / preview
        assert client.get(f"/api/v1/partituras/{p_banda['id']}/descargar", headers=alumno_h).status_code == 403
        assert client.get(f"/api/v1/partituras/{p_banda['id']}/preview", headers=alumno_h).status_code == 403
        # el de su agrupación sí pasa el chequeo (404 solo si falta el archivo en disco)
        assert client.get(f"/api/v1/partituras/{p_coro['id']}/descargar", headers=alumno_h).status_code in (200, 404)
        assert client.get(f"/api/v1/partituras/{p_coro['id']}/preview", headers=alumno_h).status_code in (200, 404)

        # filtro explícito por ajena agrupación → 403
        assert client.get(
            f"/api/v1/partituras/?agrupacion_id={p_banda['agrupacion_id']}", headers=alumno_h
        ).status_code == 403
        # el de la suya sí lista
        r_ok = client.get(
            f"/api/v1/partituras/?agrupacion_id={p_coro['agrupacion_id']}", headers=alumno_h
        )
        assert r_ok.status_code == 200

    def test_profesor_no_ve_partituras_de_agrupacion_ajena(self, client, admin_h, prof_h):
        # prof_h (Yared) está en coro/orquesta, no en banda (3)
        p_banda = self._subir(client, admin_h, 3, "Aisl Banda Prof")

        r = client.get("/api/v1/partituras/", headers=prof_h)
        assert r.status_code == 200
        assert "Aisl Banda Prof" not in {p["titulo"] for p in r.get_json()}

        assert client.get(f"/api/v1/partituras/{p_banda['id']}", headers=prof_h).status_code == 403
        assert client.get(f"/api/v1/partituras/{p_banda['id']}/descargar", headers=prof_h).status_code == 403
        assert client.get(f"/api/v1/partituras/{p_banda['id']}/preview", headers=prof_h).status_code == 403
        assert client.get(
            f"/api/v1/partituras/?agrupacion_id={p_banda['agrupacion_id']}", headers=prof_h
        ).status_code == 403

    def test_admin_secretaria_ven_todas(self, client, admin_h, prof_h):
        # secretaria (V-23456789) tiene lectura amplia: ve banda aunque su perfil esté en ella
        p_coro = self._subir(client, admin_h, 1, "Aisl Admin Coro")
        p_banda = self._subir(client, admin_h, 3, "Aisl Admin Banda")

        sec = client.post(
            "/api/v1/auth/login", json={"cedula": "V-23456789", "password": "prof123"}
        ).get_json()
        sh = {"Authorization": f"Bearer {sec['access_token']}"}

        r = client.get("/api/v1/partituras/", headers=sh)
        assert r.status_code == 200
        titulos = {p["titulo"] for p in r.get_json()}
        assert "Aisl Admin Coro" in titulos and "Aisl Admin Banda" in titulos
        assert client.get(f"/api/v1/partituras/{p_coro['id']}", headers=sh).status_code == 200
        assert client.get(f"/api/v1/partituras/{p_banda['id']}", headers=sh).status_code == 200

        r_admin = client.get("/api/v1/partituras/", headers=admin_h)
        titulos_admin = {p["titulo"] for p in r_admin.get_json()}
        assert "Aisl Admin Coro" in titulos_admin and "Aisl Admin Banda" in titulos_admin

    def test_rol_sin_agrupaciones_lista_vacia(self, client, admin_h, jurado_h):
        self._subir(client, admin_h, 1, "Aisl Jurado Test")
        r = client.get("/api/v1/partituras/", headers=jurado_h)
        assert r.status_code == 200
        assert r.get_json() == []