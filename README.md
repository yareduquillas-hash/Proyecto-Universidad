# Núcleo Los Teques — Sistema de Gestión

Aplicación web para el **Núcleo Los Teques** del Sistema Nacional de Orquestas y Coros Juveniles e Infantiles de Venezuela.

Gestión administrativa, control de asistencia, biblioteca de partituras, cronograma interactivo y proceso completo de admisiones / audiciones.

> **Supuestos v1 (acordados con el conservatorio):**
> - Los usuarios se tratan como mayores de edad: la recuperación de clave va al **email propio** del usuario. El manejo de niños (email del representante) queda para v2.
> - **No hay sistema de calificaciones académicas.** Solo clases + examen de admisión sin nota pública. Las puntuaciones del jurado son un **insumo interno de admisión** (máx 50) y al aspirante solo se le comunica `pendiente / admitido / no_admitido / en_espera`.

---

## Stack

| Capa        | Tecnología                           |
|-------------|--------------------------------------|
| Backend     | Python 3.11 + Flask 3               |
| Base de datos | SQLite (desarrollo) / PostgreSQL   |
| ORM         | SQLAlchemy 2 + Flask-Migrate        |
| Auth        | JWT (Flask-JWT-Extended)           |
| Frontend    | HTML5 + CSS3 + JS vanilla (SPA)    |
| Devops      | Docker + docker-compose            |
| Tests       | pytest + Flask test client         |
| Validación  | Marshmallow schemas                |

---

## Instalación

```bash
git clone <repo>
cd Proyecto-Universidad-experimental

# Crear entorno virtual
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
# Windows: copy .env.example .env
# Linux:   cp .env.example .env
# Editar .env con tus valores locales (genera SECRET_KEY y JWT_SECRET_KEY)

# Inicializar base de datos (crea tablas y carga datos de prueba)
python -m backend.seed.seed

# Migraciones (la estructura migrations/ ya existe en el repo)
$env:FLASK_APP = "run.py"   # Windows PowerShell (Linux: export FLASK_APP=run.py)
flask db migrate -m "descripcion"   # tras cambiar modelos
flask db upgrade

# Levantar servidor
python run.py
```

El servidor arranca en `http://localhost:5000` (desarrollo). Con docker compose, en `http://localhost` vía Caddy.

---

## Credenciales de prueba (seed)

| Rol         | Cédula       | Password    |
|-------------|--------------|-------------|
| Admin       | V-00000001   | admin123    |
| Profesor    | V-12345678   | prof123     |
| Secretaria  | V-23456789   | prof123     |
| Jurado      | V-34567890   | jurado123   |
| Alumno 1    | V-28765432   | alumno123   |
| Alumno 2    | V-29555333   | alumno123   |
| Alumno 3    | V-30444444   | alumno123   |
| Alumno 4    | V-31111111   | alumno123   |

---

## Estructura del proyecto

```
Proyecto-Universidad/
├── backend/
│   ├── app.py                  # app factory (create_app)
│   ├── config/config.py        # Config por entorno
│   ├── extensions/             # db, jwt, cors, migrate
│   ├── models/models.py        # Modelos SQLAlchemy (3FN)
│   ├── modules/
│   │   ├── registry.py         # Registro centralizado de módulos
│   │   ├── auth/routes.py      # Login, JWT, menú dinámico
│   │   ├── usuarios/routes.py  # CRUD de usuarios
│   │   ├── asistencia/routes.py# Asistencia masiva + reportes
│   │   ├── partituras/routes.py# Biblioteca PDF
│   │   ├── cronograma/routes.py# Eventos y cronograma
│   │   └── audiciones/routes.py# Convocatorias, aspirantes, puntuaciones
│   ├── seed/seed.py            # Carga datos de prueba
│   └── utils/auth.py           # Decorator role_required()
├── frontend/
│   ├── templates/              # HTML (login, dashboard)
│   └── static/                # CSS, JS, imágenes
├── tests/                     # Suite pytest
├── .env                       # Variables de entorno
├── run.py                     # Entrypoint del servidor
├── Dockerfile / docker-compose.yaml
└── requirements.txt
```

---

## Roles y permisos (RBAC)

| Rol        | Permisos                                                                 |
|------------|--------------------------------------------------------------------------|
| **alumno**    | Ver partituras, cronograma, menú reducido                             |
| **profesor**  | Tomar asistencia masiva, subir partituras, crear eventos              |
| **secretaria**| Igual que profesor                                                   |
| **jurado**    | Puntuar aspirantes, ver expedientes                         |
| **admin**     | Todo: usuarios, convocatorias, agrupaciones, reportes, apertura/cierre |

---

## Endpoints principales

### Auth
```
POST   /api/v1/auth/login           # Login (cedula, password) -> access (2h) + refresh (7d)
POST   /api/v1/auth/refresh         # Rota access con refresh_token
GET    /api/v1/auth/me              # Datos del usuario actual
POST   /api/v1/auth/logout          # Cierra sesión (invalida el token)
GET    /api/v1/auth/menu            # Menú dinámico según rol
POST   /api/v1/auth/verificar-cedula# Solo estado (sin PII): requiere_activacion | activo
POST   /api/v1/auth/activar-cuenta  # Requiere cedula + email de pre-registro
POST   /api/v1/auth/forgot          # Solicita código de 6 dígitos al email (siempre 200)
POST   /api/v1/auth/verify-code     # Verifica el código
POST   /api/v1/auth/reset           # Cambia la clave con código válido (1 uso, 15 min)
POST   /api/v1/auth/change-password # Cambio autenticado (rota sesión)
```

### Usuarios
```
POST   /api/v1/usuarios/                   # Crear usuario (admin/secretaria)
POST   /api/v1/usuarios/pre-registrar      # Pre-registro sin clave (fuerza passwordless)
GET    /api/v1/usuarios/                   # Listar (admin/secretaria, ?q=&role=&estado_activacion=&page=)
GET    /api/v1/usuarios/<id>              # Obtener (admin/secretaria o propio)
PUT    /api/v1/usuarios/<id>              # Actualizar (admin/secretaria, protege último admin)
DELETE /api/v1/usuarios/<id>              # Soft delete (admin/secretaria, no auto-borrado)
POST   /api/v1/usuarios/<id>/reset-password # Temporal de 1 uso + cambio obligado (presencial)
POST   /api/v1/usuarios/asignar-agrupacion  # Many-to-many (admin/secretaria)
POST   /api/v1/usuarios/desasignar-agrupacion
GET    /api/v1/usuarios/agrupaciones       # Listar agrupaciones activas
GET    /api/v1/usuarios/instrumentos       # Listar instrumentos
```

### Asistencia
```
POST   /api/v1/asistencia/registrar         # Carga masiva (prof+)
GET    /api/v1/asistencia/agrupacion/<id>/fecha/<date>
GET    /api/v1/asistencia/alumno/<id>      # Historial + % riesgos
GET    /api/v1/asistencia/reporte/<agrup_id>
GET    /api/v1/asistencia/exportar/<agrup_id>  # CSV
```

### Partituras
```
POST   /api/v1/partituras/upload            # Multipart (prof+)
GET    /api/v1/partituras/                 # Listar + filtros
GET    /api/v1/partituras/<id>             # Obtener
GET    /api/v1/partituras/<id>/descargar
GET    /api/v1/partituras/<id>/preview
DELETE /api/v1/partituras/<id>             # (prof+)
GET    /api/v1/partituras/filtros          # Filtros disponibles
```

### Cronograma
```
POST   /api/v1/cronograma/eventos           # Crear (prof+)
GET    /api/v1/cronograma/eventos           # Listar + filtros
GET    /api/v1/cronograma/eventos/proximos
GET    /api/v1/cronograma/eventos/alertas
GET/PUT/DELETE /api/v1/cronograma/eventos/<id>
```

### Audiciones (puntajes = insumo interno, nunca nota pública)
```
POST   /api/v1/audiciones/convocatorias      # Admin
GET    /api/v1/audiciones/convocatorias
PUT    /api/v1/audiciones/convocatorias/<id>/activar
POST   /api/v1/audiciones/aspirantes         # Crear aspirante (admin/secretaria/profesor)
POST   /api/v1/audiciones/inscribir-publico  # Inscripción pública con rate-limit
GET    /api/v1/audiciones/aspirantes         # Filtrar (jurado/admin/secretaria)
GET    /api/v1/audiciones/aspirantes/<id>    # Detalle + puntuaciones (jurado/admin/secretaria)
PUT    /api/v1/audiciones/aspirantes/<id>/estado  # Decisión: admitido/no_admitido/en_espera (admin/secretaria)
POST   /api/v1/audiciones/aspirantes/<id>/puntuacion  # Jurado/admin (convocatoria activa)
POST   /api/v1/audiciones/audiciones         # Programar audición (admin)
GET    /api/v1/audiciones/audiciones         # (jurado/admin/secretaria)
```
> Ranking de aspirantes: **eliminado del alcance v1** (pendiente definir con el conservatorio si lo quieren).

### Ops
```
GET    /health                            # Liveness + check BD
```

### Público (sin JWT, con rate-limit anti-spam)
```
POST   /api/v1/audiciones/inscribir-publico  # Inscripción pública de aspirantes
```

---

## Cómo agregar un nuevo módulo

1. Crea la carpeta `backend/modules/<nombre>/` con `__init__.py` y `routes.py`.
2. Define el Blueprint.
3. Registra en `backend/app.py`:

```python
from backend.modules.<nombre>.routes import <nombre>_bp
module_registry.register(
    "nombre", <nombre>_bp, "Nombre Módulo", "fa-icon",
    roles_allowed=["admin", "profesor"], sidebar_visible=True
)
```

4. Agrega el template HTML en `frontend/templates/<nombre>.html`.
5. La barra lateral se renderiza automáticamente para los roles autorizados.

---

## Tests

```bash
pytest                             # todos los tests
pytest tests/ -v                    # verbose
pytest tests/test_auth.py    # un archivo específico
```

Coverage:
```bash
pip install pytest-cov
pytest --cov=backend tests/
```

---

## Docker (producción) + HTTPS

```bash
# Configura en .env (bloque PRODUCCIÓN de .env.example):
#   SECRET_KEY, JWT_SECRET_KEY  (genera cada uno con secrets.token_hex(32))
#   POSTGRES_PASSWORD           (fuerte; obligatoria para levantar compose)
#   SITE_ADDRESS=tudominio.example.com  # opcional: HTTPS automático con Caddy
docker compose up --build
```

Topología: **Internet → Caddy (HTTPS) → Gunicorn (`app:5000`) → PostgreSQL**.
El contenedor `app` **no** publica puerto en el host; solo lo consume Caddy.

- Local (`SITE_ADDRESS=localhost`): `http://localhost` (puerto 80) y `http://localhost/health`.
- Producción con dominio: Caddy obtiene certificado Let's Encrypt y sirve en 80/443.
- **Esquema al arrancar:** `docker-entrypoint.sh` ejecuta `flask db upgrade` antes
  de Gunicorn. Instalación limpia → crea todas las tablas; BD legacy sin
  `alembic_version` → `flask db stamp head` (no re-ejecuta la migración inicial).
  No hace falta correr `flask db upgrade` a mano para levantar compose.

Los secretos de desarrollo del `.env` local **no** sirven para producción: el arranque falla si son placeholder, débiles o < 32 caracteres.

---

## Backup y restauración (piloto, mínimo)

**Crear backup:**

```powershell
# Windows (en la carpeta del proyecto):
powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
# Linux/macOS:
sh scripts/backup.sh
```

Genera `backup/<fecha>/` con la BD (`db.sql[.gz]`) + `uploads` (`uploads.zip` / `uploads.tar.gz`).
Guarda esa carpeta **fuera del servidor** (USB / Drive). Recomendado: semanal + antes de cada actualización.

**Restaurar** (sobreescribe lo actual):

```powershell
# Windows:
powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 -Dir backup\<fecha>
# Linux/macOS:
sh scripts/restore.sh backup/<fecha>
```

> ⚠️ `docker compose down -v` **borra** la BD (`pgdata`). En el servidor del conservatorio usa siempre `docker compose down` sin `-v`.
> Si cambiaste `POSTGRES_USER/DB` en `.env`, usa esos valores (los scripts leen el `.env` del entorno o asumen `nucleo`).

---

## Migraciones de esquema (Flask-Migrate / Alembic)

El proyecto tiene `migrations/` con una migración inicial. Para **cambiar modelos en el futuro sin `drop_all()`**:

```powershell
$env:FLASK_APP = "run.py"   # Linux: export FLASK_APP=run.py
flask db migrate -m "descripcion_del_cambio"   # genera el script (autogenerate)
flask db upgrade                                 # aplica
```

- En una BD ya creada con el esquema actual y **sin** `alembic_version`, una sola vez:
  `flask db stamp head` (marca que ya está al día; no borra datos).
  En Docker esto lo hace automáticamente `docker-entrypoint.sh` al arrancar.
- `python -m backend.seed.seed` sigue siendo **solo para desarrollo/bootstrap** (hace `drop_all`). No se usa para migrar producción.

---

## Puesta en marcha en producción (checklist mínimo)

1. `.env` con secretos fuertes (genera con `python -c "import secrets; print(secrets.token_hex(32))"`):
   `SECRET_KEY` y `JWT_SECRET_KEY` de 64 hex **distintos** (el arranque falla si son
   placeholder/débiles, < 32 chars o iguales entre sí),
   `POSTGRES_PASSWORD` fuerte (obligatoria en compose; + `DATABASE_URL` con la misma clave si la defines).
2. `SITE_ADDRESS=tudominio.example.com` para HTTPS vía Caddy (puertos 80/443).
3. `SMTP_*` real si quieres recuperación por email. Sin SMTP la app arranca igual pero el
   "Olvidé mi clave" **no envía nada** (el usuario ve éxito genérico y nunca llega código);
   alternativa operativa: reset asistido presencial en `Usuarios -> reset-password`.
4. `docker compose up --build -d` y verifica `http://localhost/health` (o vía el dominio).
   El entrypoint aplica las migraciones solo; si el contenedor entra en crash-loop
   revisa `docker compose logs app` (secretos faltantes o BD inaccesible).
5. Si el bootstrap inicial usó seed (`ALLOW_SEED_PROD=1`): cambia **inmediatamente**
   `admin123 / prof123 / alumno123 / jurado123` (las del README son solo dev) y elimina
   usuarios de prueba. A partir de ahí, cambios de esquema con `flask db migrate/upgrade`.

---

## Licencia

Sistema Nacional de Orquestas y Coros Juveniles e Infantiles de Venezuela - Núcleo Los Teques.