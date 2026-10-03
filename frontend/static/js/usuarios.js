/* ─────────────────────────────────────────────────────────────
   5. GESTIÓN Y PRE-REGISTRO DE USUARIOS (ADMIN Y SECRETARÍA)
   ───────────────────────────────────────────────────────────── */
let usuariosGlobalCache = [];
let usuariosTotal = 0;
const PAGE_SIZE_USUARIOS = 50;

async function renderUsuarios(){
    // El shell (filtros) se renderiza UNA vez; loadUsuariosPage solo actualiza
    // tbody/paginación para no destruir el input mientras se escribe.
    document.getElementById('contentBody').innerHTML = `
    <div id="avisoUsuarios"></div>
    <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:15px;margin-bottom:20px;">
        <div>
            <h3 style="margin:0;font-size:1.4rem;"><i class="fa-solid fa-users-gear" style="color:#009B77;"></i> Gestión y Pre-Registro de Usuarios</h3>
            <span style="color:var(--text-muted);font-size:0.9rem;">Total Registrados: <strong id="conteoUsuarios">… usuarios</strong></span>
        </div>
        <div style="display:flex;gap:10px;">
            <button onclick="mostrarModalCrearUsuario()" style="padding:10px 18px;background:linear-gradient(135deg,#009B77,#00b894);color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:bold;box-shadow:0 4px 12px rgba(0,155,119,0.25);">
                <i class="fa-solid fa-id-card"></i> Pre-Registrar por Cédula
            </button>
        </div>
    </div>

    <div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:20px;background:var(--card-bg, #f8fafc);padding:14px;border-radius:10px;border:1px solid var(--border-color, #e2e8f0);">
        <div style="flex:1;min-width:200px;">
            <input type="text" id="busquedaUsuarioInput" class="login-input" placeholder="🔍 Buscar por Cédula, Nombre o Email..." oninput="debouncedLoadUsuarios()" style="margin:0;">
        </div>
        <div style="width:180px;">
            <select id="filtroRolUsuario" class="login-input" onchange="loadUsuariosPage(1)" style="margin:0;">
                <option value="">-- Todos los Roles --</option>
                <option value="alumno">Alumnos</option>
                <option value="profesor">Profesores</option>
                <option value="secretaria">Secretaría</option>
                <option value="jurado">Jurados</option>
                <option value="admin">Administradores</option>
            </select>
        </div>
        <div style="width:200px;">
            <select id="filtroEstadoActivacion" class="login-input" onchange="loadUsuariosPage(1)" style="margin:0;">
                <option value="">-- Estado Contraseña --</option>
                <option value="pendiente">⏳ Pendiente Activación</option>
                <option value="activo">✅ Clave Configurada</option>
            </select>
        </div>
    </div>

    <div style="overflow-x:auto;">
    <table class="members-table">
        <thead>
            <tr>
                <th>Cédula</th>
                <th>Nombre y Apellido</th>
                <th>Correo</th>
                <th>Rol</th>
                <th>Estado Clave</th>
                <th>Cuenta</th>
                <th>Acciones</th>
            </tr>
        </thead>
        <tbody id="tablaUsuariosBody"></tbody>
    </table>
    </div>
    <div id="pagUsuarios"></div>`;
    await loadUsuariosPage(1);
}

async function loadUsuariosPage(page){
    const p = page || 1;
    const q = (document.getElementById('busquedaUsuarioInput')?.value || '').trim();
    const role = document.getElementById('filtroRolUsuario')?.value || '';
    const estado = document.getElementById('filtroEstadoActivacion')?.value || '';
    const params = new URLSearchParams();
    params.set('incluir_inactivos', 'true');
    params.set('page', String(p));
    params.set('per_page', String(PAGE_SIZE_USUARIOS));
    if(q) params.set('q', q);
    if(role) params.set('role', role);
    if(estado) params.set('estado_activacion', estado);

    const res = await apiCall('/usuarios/?' + params.toString());
    if(!res || !res.ok) return;
    const raw = await res.json();
    usuariosGlobalCache = _items(raw);
    usuariosTotal = (!Array.isArray(raw) && raw.total != null) ? raw.total : usuariosGlobalCache.length;
    window._usuariosAviso = _avisoTruncado(raw);
    const aviso = document.getElementById('avisoUsuarios');
    if(aviso) aviso.innerHTML = window._usuariosAviso || '';
    const pag = document.getElementById('pagUsuarios');
    if(pag) pag.innerHTML = _pagControls(raw, 'loadUsuariosPage');
    filtrarUsuariosRows();
}

const debouncedLoadUsuarios = debounce(() => loadUsuariosPage(1), 350);

function filtrarUsuariosRows(){
    // El filtrado q/role/estado lo hace el servidor (page + q + role...);
    // aquí solo se pintan los items de la página actual.
    const list = usuariosGlobalCache;

    const conteo = document.getElementById('conteoUsuarios');
    if(conteo) conteo.textContent = `${list.length} de ${usuariosTotal} usuarios`;

    const tbody = document.getElementById('tablaUsuariosBody');
    if(!tbody) return;
    tbody.innerHTML = list.length === 0
        ? '<tr><td colspan="7" style="text-align:center;padding:20px;">No se encontraron usuarios.</td></tr>'
        : list.map(u => `
            <tr>
                <td><strong>${escapeHtml(u.cedula)}</strong></td>
                <td>${escapeHtml(u.nombre)} ${escapeHtml(u.apellido)}</td>
                <td>${escapeHtml(u.email)}</td>
                <td><span class="badge ${u.role==='admin'?'badge-danger':u.role==='profesor'?'badge-info':u.role==='jurado'?'badge-warning':'badge-success'}">${escapeHtml(u.role).toUpperCase()}</span></td>
                <td>
                    ${u.requiere_activacion ?
                    '<span class="badge badge-warning" title="El usuario debe ingresar su cédula al sistema para crear su contraseña"><i class="fa-solid fa-clock-rotate-left"></i> Pendiente Activación</span>' :
                    '<span class="badge badge-success"><i class="fa-solid fa-circle-check"></i> Clave Configurada</span>'}
                </td>
                <td>${u.activo ? '<span class="badge badge-success">Activo</span>' : '<span class="badge badge-danger">Inactivo</span>'}</td>
                <td>
                    <button onclick="mostrarModalAsignarAgrupacion(${u.id})" style="background:none;border:none;color:#009B77;cursor:pointer;font-weight:bold;margin-right:8px;" title="Asignar a Agrupación">
                        <i class="fa-solid fa-link"></i> Agrupación
                    </button>
                    ${u.activo ? `
                    <button onclick="toggleActivoUsuario(${u.id}, false)" style="background:none;border:none;color:#D81B60;cursor:pointer;">
                        <i class="fa-solid fa-user-slash"></i> Desactivar
                    </button>` : `
                    <button onclick="toggleActivoUsuario(${u.id}, true)" style="background:none;border:none;color:#2e7d32;cursor:pointer;">
                        <i class="fa-solid fa-user-check"></i> Activar
                    </button>`}
                </td>
            </tr>`).join('');
}

// Compat: recarga la página actual del servidor (antes re-filtraba en cliente)
function filtrarYRenderizarUsuarios(){
    if(!document.getElementById('tablaUsuariosBody')){ renderUsuarios(); return; }
    loadUsuariosPage(1);
}

async function mostrarModalCrearUsuario(){
    showModal(`
        <h3 style="margin-bottom:15px;color:var(--text-color, #2c3e50);"><i class="fa-solid fa-user-plus" style="color:#009B77;"></i> Pre-Registro / Nuevo Usuario por Cédula</h3>
        <p style="font-size:0.88rem;color:#64748b;margin-bottom:15px;">
            Al pre-registrar un usuario (alumno, profesor, secretaria, jurado o admin) con su Cédula, no es necesario asignarle clave inicial. El usuario podrá ingresar su Cédula para registrar su contraseña privada con confirmación doble.
        </p>
        <form id="formCrearUsuarioModal" class="grid-2">
            <div>
                <label style="font-weight:600;">Cédula de Identidad (*):</label>
                <input type="text" name="cedula" class="login-input" required placeholder="V-12345678">
            </div>
            <div>
                <label style="font-weight:600;">Rol del Usuario (*):</label>
                <select name="role" class="login-input" required id="modalUserRoleSelect" onchange="toggleModalUserFields()">
                    <option value="alumno">Alumno / Músico</option>
                    <option value="profesor">Profesor</option>
                    <option value="secretaria">Secretaría</option>
                    <option value="jurado">Jurado Audición</option>
                    <option value="admin">Administrador General</option>
                </select>
            </div>
            <div>
                <label style="font-weight:600;">Nombre (*):</label>
                <input type="text" name="nombre" class="login-input" required placeholder="Ej. Andrea">
            </div>
            <div>
                <label style="font-weight:600;">Apellido (*):</label>
                <input type="text" name="apellido" class="login-input" required placeholder="Ej. Fernández">
            </div>
            <div class="grid-full">
                <label style="font-weight:600;">Correo Electrónico (*):</label>
                <input type="email" name="email" class="login-input" required placeholder="andrea@correo.com">
            </div>

            <!-- Campos Opcionales para Alumnos -->
            <div class="grid-full" id="modalAlumnoFields" style="background:rgba(0,155,119,0.05);padding:12px;border-radius:8px;border:1px dashed #009B77;">
                <h4 style="margin:0 0 10px 0;font-size:0.9rem;color:#009B77;"><i class="fa-solid fa-graduation-cap"></i> Datos Adicionales del Alumno (Opcional)</h4>
                <div class="grid-2">
                    <div>
                        <label style="font-size:0.85rem;">Teléfono:</label>
                        <input type="text" name="telefono" class="login-input" placeholder="0412-1234567">
                    </div>
                    <div>
                        <label style="font-size:0.85rem;">Nombre Representante:</label>
                        <input type="text" name="nombre_representante" class="login-input" placeholder="Sra. Fernández">
                    </div>
                </div>
            </div>

            <!-- Opción de Contraseña -->
            <div class="grid-full" style="margin-top:10px;">
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-weight:600;">
                    <input type="checkbox" id="chkDefinirPasswordModal" onchange="toggleModalPasswordInput()">
                    Definir contraseña inicial en este momento (de lo contrario, el usuario la creará con su Cédula)
                </label>
            </div>

            <div class="grid-full" id="areaPasswordModal" style="display:none;background:var(--card-bg-subtle);padding:12px;border-radius:8px;margin-top:5px;">
                <div class="grid-2">
                    <div>
                        <label style="font-size:0.85rem;font-weight:600;">Contraseña:</label>
                        <input type="password" name="password" id="modalPasswordInput" class="login-input" placeholder="••••••••">
                    </div>
                    <div>
                        <label style="font-size:0.85rem;font-weight:600;">Confirmar Contraseña:</label>
                        <input type="password" name="confirm_password" id="modalConfirmPasswordInput" class="login-input" placeholder="••••••••">
                    </div>
                </div>
            </div>

            <div class="grid-full" style="display:flex;justify-content:flex-end;gap:10px;margin-top:15px;">
                <button type="button" onclick="closeModal()" style="padding:10px 20px;border:none;background:var(--border-strong);color:var(--text);border-radius:6px;cursor:pointer;">Cancelar</button>
                <button type="submit" class="btn-submit" style="width:auto;margin:0;padding:10px 25px;">
                    <i class="fa-solid fa-user-check"></i> Completar Registro
                </button>
            </div>
        </form>
    `);

    document.getElementById('formCrearUsuarioModal').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const body = Object.fromEntries(fd);

        const chk = document.getElementById('chkDefinirPasswordModal');
        if(!chk.checked){
            delete body.password;
            delete body.confirm_password;
        } else {
            if(body.password !== body.confirm_password){
                alert('Las contraseñas ingresadas no coinciden.');
                return;
            }
        }

        const res = await apiCall('/usuarios/', 'POST', body);
        if(res && res.ok){
            showToast('Usuario registrado exitosamente', 'success');
            closeModal();
            renderUsuarios();
        } else {
            const err = await res.json();
            showToast(err.error || 'Error al registrar usuario.', 'error');
        }
    });
}

function toggleModalUserFields(){
    const role = document.getElementById('modalUserRoleSelect')?.value;
    const alumnoFields = document.getElementById('modalAlumnoFields');
    if(alumnoFields){
        alumnoFields.style.display = role === 'alumno' ? 'block' : 'none';
    }
}

function toggleModalPasswordInput(){
    const chk = document.getElementById('chkDefinirPasswordModal');
    const area = document.getElementById('areaPasswordModal');
    if(area){
        area.style.display = chk.checked ? 'block' : 'none';
    }
}

async function mostrarModalAsignarAgrupacion(userId){
    // El nombre NO se inyecta en onclick (escapeAttr se decodifica en contexto
    // JS → XSS). Se resuelve desde la caché de la página actual por id.
    const u = usuariosGlobalCache.find(x => x.id === userId);
    const userName = u ? `${u.nombre} ${u.apellido}` : `#${userId}`;
    const res = await apiCall('/usuarios/agrupaciones');
    const agrups = res && res.ok ? await res.json() : [];

    showModal(`
        <h3 style="margin-bottom:15px;color:var(--text);">Asignar Agrupación</h3>
        <p style="margin-bottom:15px;">Usuario: <strong>${escapeHtml(userName)}</strong></p>
        <form id="formAsignarAgrup">
            <label style="font-weight:600;">Selecciona Agrupación:</label>
            <select id="selAsignarAgrupId" class="login-input" required style="margin-top:5px;">
                <option value="">-- Selecciona --</option>
                ${agrups.map(a => `<option value="${a.id}">${escapeHtml(a.nombre)}</option>`).join('')}
            </select>
            <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px;">
                <button type="button" onclick="closeModal()" style="padding:10px 20px;border:none;background:var(--border-strong);color:var(--text);border-radius:6px;cursor:pointer;">Cancelar</button>
                <button type="submit" class="btn-submit" style="width:auto;margin:0;padding:10px 25px;">Asignar</button>
            </div>
        </form>
    `);

    document.getElementById('formAsignarAgrup').addEventListener('submit', async (e) => {
        e.preventDefault();
        const agrupId = parseInt(document.getElementById('selAsignarAgrupId').value);
        const res = await apiCall('/usuarios/asignar-agrupacion', 'POST', {
            usuario_id: userId, agrupacion_id: agrupId
        });
        if(res && res.ok){
            alert('Agrupación asignada exitosamente.');
            closeModal();
            renderUsuarios();
        } else {
            alert('Error asignando agrupación.');
        }
    });
}

async function toggleActivoUsuario(id, activo){
    const res = await apiCall(`/usuarios/${id}`, 'PUT', { activo });
    if(res && res.ok){ renderUsuarios(); }
}
