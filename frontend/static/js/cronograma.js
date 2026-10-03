/* ─────────────────────────────────────────────────────────────
   3. CRONOGRAMA INTERACTIVO
   ───────────────────────────────────────────────────────────── */
let cronogramaPage = 1;

async function renderCronograma(){
    const canCreate = ['profesor', 'secretaria', 'admin'].includes(USER_ROLE);
    const html = `
    <div id="bannerAlertasCronograma" style="margin-bottom:20px;"></div>
    <div style="display:flex;gap:15px;flex-wrap:wrap;margin-bottom:20px;align-items:flex-end;">
        <div>
            <label style="display:block;margin-bottom:5px;font-weight:600;">Agrupación:</label>
            <select id="filtroAgrupCrono" class="login-input" style="width:200px;" onchange="cargarEventosCronograma()"><option value="">Todas</option></select>
        </div>
        <div>
            <label style="display:block;margin-bottom:5px;font-weight:600;">Tipo de Actividad:</label>
            <select id="filtroTipoCrono" class="login-input" style="width:180px;" onchange="cargarEventosCronograma()">
                <option value="">Todos los tipos</option>
                <option value="ensayo">Ensayo</option>
                <option value="concierto">Concierto</option>
                <option value="clase">Clase</option>
                <option value="taller">Taller</option>
                <option value="pauta_extra">Pauta Extra</option>
            </select>
        </div>
        ${canCreate ? `
        <div style="margin-left:auto;">
            <button onclick="mostrarModalCrearEvento()" style="padding:12px 20px;background:#D81B60;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:bold;">
                <i class="fa-solid fa-plus"></i> Programar Evento
            </button>
        </div>` : ''}
    </div>
    <div id="listaEventosCronograma"></div>`;
    document.getElementById('contentBody').innerHTML = html;
    await cargarSelectoresCronograma();
    await cargarAlertasCronograma();
    await cargarEventosCronograma();
}

async function cargarSelectoresCronograma(){
    const res = await apiCall('/usuarios/agrupaciones');
    if(res && res.ok){
        const data = await res.json();
        const sel = document.getElementById('filtroAgrupCrono');
        if(sel) sel.innerHTML += data.map(a => `<option value="${a.id}">${escapeHtml(a.nombre)}</option>`).join('');
    }
}

async function cargarAlertasCronograma(){
    const res = await apiCall('/cronograma/eventos/alertas');
    if(!res || !res.ok) return;
    const alertas = await res.json();
    if(alertas.length > 0){
        const html = `<div class="cronograma-alert-banner">
            <h4><i class="fa-solid fa-bell"></i> Avisos Destacados y Próximos Eventos (48h)</h4>
            ${alertas.map(a => `
                <div class="crono-alert-item">
                    <strong>[${escapeHtml(a.tipo).toUpperCase()}] ${escapeHtml(a.titulo)}</strong> - ${escapeHtml(a.agrupacion_nombre)} | 
                    <span><i class="fa-solid fa-calendar-days"></i> ${escapeHtml((a.fecha_inicio||'').replace('T',' '))}</span> | 
                    <span><i class="fa-solid fa-location-dot"></i> ${escapeHtml(a.lugar)||'Por definir'}</span>
                    ${a.mensaje_alerta ? `<div class="crono-alert-msg"><i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(a.mensaje_alerta)}</div>` : ''}
                </div>`).join('')}
        </div>`;
        document.getElementById('bannerAlertasCronograma').innerHTML = html;
    }
}

async function cargarEventosCronograma(page){
    cronogramaPage = page || 1;
    const agrupId = document.getElementById('filtroAgrupCrono')?.value;
    const tipo = document.getElementById('filtroTipoCrono')?.value;
    const params = new URLSearchParams();
    if(agrupId) params.set('agrupacion_id', agrupId);
    if(tipo) params.set('tipo', tipo);
    params.set('page', String(cronogramaPage));
    params.set('per_page', '50');

    const res = await apiCall('/cronograma/eventos?' + params.toString());
    if(!res || !res.ok) return;
    const rawE = await res.json();
    const eventos = _items(rawE);

    const canManage = ['profesor', 'secretaria', 'admin'].includes(USER_ROLE);
    document.getElementById('listaEventosCronograma').innerHTML = _avisoTruncado(rawE) + (eventos.length === 0
        ? '<p style="padding:20px;text-align:center;">No hay actividades programadas con los criterios seleccionados.</p>'
        : `<table class="members-table">
            <thead><tr><th>Título</th><th>Tipo</th><th>Agrupación</th><th>Inicio</th><th>Fin</th><th>Lugar</th><th>Creado por</th>${canManage?'<th>Acciones</th>':''}</tr></thead>
            <tbody>${eventos.map(e => `
                <tr>
                    <td><strong>${escapeHtml(e.titulo)}</strong></td>
                    <td><span class="badge ${e.tipo==='concierto'?'badge-danger':e.tipo==='ensayo'?'badge-info':'badge-warning'}">${escapeHtml(e.tipo)}</span></td>
                    <td>${escapeHtml(e.agrupacion_nombre)}</td>
                    <td>${escapeHtml((e.fecha_inicio||'').replace('T',' '))}</td>
                    <td>${escapeHtml((e.fecha_fin||'').replace('T',' '))}</td>
                    <td>${escapeHtml(e.lugar) || '-'}</td>
                    <td>${escapeHtml(e.creado_por_nombre) || 'Sistema'}</td>
                    ${canManage ? `
                    <td>
                        <button onclick="mostrarModalEditarEvento(${e.id})" class="btn-action edit">
                            <i class="fa-solid fa-pen-to-square"></i> Editar
                        </button>
                        <button onclick="eliminarEventoCronograma(${e.id})" class="btn-action delete" style="margin-left:4px;">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </td>` : ''}
                </tr>`).join('')}
            </tbody>
        </table>`) + _pagControls(rawE, 'cargarEventosCronograma');
}

async function mostrarModalEditarEvento(id){
    const evtRes = await apiCall('/cronograma/eventos/' + id);
    if(!evtRes || !evtRes.ok) return showToast('Error al obtener datos del evento.', 'error');
    const evt = await evtRes.json();
    
    const agrupRes = await apiCall('/usuarios/agrupaciones');
    const agrups = agrupRes && agrupRes.ok ? await agrupRes.json() : [];

    showModal(`
        <h3 style="margin-bottom:15px;">Editar Actividad Programada</h3>
        <form id="formEditarEventoModal" class="grid-2">
            <div class="grid-full">
                <label>Título del Evento (*):</label>
                <input type="text" name="titulo" class="login-input" required value="${escapeAttr(evt.titulo || '')}">
            </div>
            <div>
                <label>Tipo (*):</label>
                <select name="tipo" class="login-input" required>
                    <option value="ensayo" ${evt.tipo==='ensayo'?'selected':''}>Ensayo</option>
                    <option value="concierto" ${evt.tipo==='concierto'?'selected':''}>Concierto</option>
                    <option value="clase" ${evt.tipo==='clase'?'selected':''}>Clase</option>
                    <option value="taller" ${evt.tipo==='taller'?'selected':''}>Taller</option>
                    <option value="pauta_extra" ${evt.tipo==='pauta_extra'?'selected':''}>Pauta Extra</option>
                </select>
            </div>
            <div>
                <label>Agrupación (*):</label>
                <select name="agrupacion_id" class="login-input" required>
                    ${agrups.map(a => `<option value="${a.id}" ${a.id===evt.agrupacion_id?'selected':''}>${escapeHtml(a.nombre)}</option>`).join('')}
                </select>
            </div>
            <div>
                <label>Fecha / Hora Inicio (*):</label>
                <input type="datetime-local" name="fecha_inicio" class="login-input" required value="${(evt.fecha_inicio||'').substring(0,16)}">
            </div>
            <div>
                <label>Fecha / Hora Fin (*):</label>
                <input type="datetime-local" name="fecha_fin" class="login-input" required value="${(evt.fecha_fin||'').substring(0,16)}">
            </div>
            <div class="grid-full">
                <label>Lugar / Aula:</label>
                <input type="text" name="lugar" class="login-input" value="${escapeAttr(evt.lugar || '')}">
            </div>
            <div class="grid-full">
                <label>Descripción:</label>
                <textarea name="descripcion" class="login-input" style="height:60px;">${escapeHtml(evt.descripcion || '')}</textarea>
            </div>
            <div class="grid-full" style="display:flex;align-items:center;gap:10px;">
                <input type="checkbox" id="notifEditCheck" name="notificar_cambios" ${evt.notificar_cambios?'checked':''}>
                <label for="notifEditCheck">Notificar cambios de hora/lugar en cartelera activa</label>
            </div>
            <div class="grid-full" style="display:flex;justify-content:flex-end;gap:10px;margin-top:15px;">
                <button type="button" onclick="closeModal()" style="padding:10px 20px;border:none;background:var(--border-strong);color:var(--text);border-radius:6px;cursor:pointer;">Cancelar</button>
                <button type="submit" class="btn-submit" style="width:auto;margin:0;padding:10px 25px;">Guardar Cambios</button>
            </div>
        </form>
    `);

    document.getElementById('formEditarEventoModal').addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.target));
        data.notificar_cambios = document.getElementById('notifEditCheck').checked;
        const res = await apiCall('/cronograma/eventos/' + id, 'PUT', data);
        if(res && res.ok){
            showToast('Evento actualizado con éxito.', 'success');
            closeModal();
            cargarEventosCronograma();
        } else {
            const err = await res.json();
            showToast(err.error || 'Error al actualizar evento.', 'error');
        }
    });
}

async function eliminarEventoCronograma(id){
    if(!confirm('¿Estás seguro de eliminar esta actividad del cronograma?')) return;
    const res = await apiCall('/cronograma/eventos/' + id, 'DELETE');
    if(res && res.ok){
        showToast('Actividad eliminada del cronograma.', 'warning');
        cargarEventosCronograma();
    } else {
        showToast('Error al eliminar la actividad.', 'error');
    }
}

async function mostrarModalCrearEvento(){
    const res = await apiCall('/usuarios/agrupaciones');
    const agrups = res && res.ok ? await res.json() : [];

    showModal(`
        <h3 style="margin-bottom:15px;color:var(--text);">Programar Nueva Actividad</h3>
        <form id="formCrearEventoModal" class="grid-2">
            <div class="grid-full">
                <label style="font-weight:600;">Título del Evento (*):</label>
                <input type="text" name="titulo" class="login-input" required placeholder="Ej. Ensayo General de Cuerdas">
            </div>
            <div>
                <label style="font-weight:600;">Tipo (*):</label>
                <select name="tipo" class="login-input" required>
                    <option value="ensayo">Ensayo</option>
                    <option value="concierto">Concierto</option>
                    <option value="clase">Clase</option>
                    <option value="taller">Taller</option>
                    <option value="pauta_extra">Pauta Extra</option>
                </select>
            </div>
            <div>
                <label style="font-weight:600;">Agrupación (*):</label>
                <select name="agrupacion_id" class="login-input" required>
                    <option value="">Selecciona Agrupación</option>
                    ${agrups.map(a => `<option value="${a.id}">${escapeHtml(a.nombre)}</option>`).join('')}
                </select>
            </div>
            <div>
                <label style="font-weight:600;">Fecha / Hora Inicio (*):</label>
                <input type="datetime-local" name="fecha_inicio" class="login-input" required>
            </div>
            <div>
                <label style="font-weight:600;">Fecha / Hora Fin (*):</label>
                <input type="datetime-local" name="fecha_fin" class="login-input" required>
            </div>
            <div class="grid-full">
                <label style="font-weight:600;">Lugar / Aula:</label>
                <input type="text" name="lugar" class="login-input" placeholder="Ej. Auditorio Principal / Sala B">
            </div>
            <div class="grid-full">
                <label style="font-weight:600;">Descripción:</label>
                <textarea name="descripcion" class="login-input" style="height:60px;" placeholder="Detalles o repertorio a ensayar..."></textarea>
            </div>
            <div class="grid-full" style="display:flex;align-items:center;gap:10px;">
                <input type="checkbox" id="notifCheck" name="notificar_cambios">
                <label for="notifCheck" style="font-weight:600;">Notificar cambios de hora/lugar en cartelera activa</label>
            </div>
            <div class="grid-full" style="display:flex;justify-content:flex-end;gap:10px;margin-top:15px;">
                <button type="button" onclick="closeModal()" style="padding:10px 20px;border:none;background:var(--border-strong);color:var(--text);border-radius:6px;cursor:pointer;">Cancelar</button>
                <button type="submit" class="btn-submit" style="width:auto;margin:0;padding:10px 25px;">Crear Evento</button>
            </div>
        </form>
    `);

    document.getElementById('formCrearEventoModal').addEventListener('submit', async (e) => {
        e.preventDefault();
        // Antidual-click: un segundo submit concurrente no debe reenviar el evento.
        if(e.target.dataset.enviando === '1') return;
        e.target.dataset.enviando = '1';
        const btnSubmit = e.target.querySelector('button[type="submit"]');
        if(btnSubmit) btnSubmit.disabled = true;
        try {
            const fd = new FormData(e.target);
            const body = Object.fromEntries(fd);
            body.agrupacion_id = parseInt(body.agrupacion_id);
            body.notificar_cambios = document.getElementById('notifCheck').checked;

            const res = await apiCall('/cronograma/eventos', 'POST', body);
            if(res && res.ok){
                alert('Evento creado exitosamente.');
                closeModal();
                cargarEventosCronograma();
                cargarAlertasCronograma();
            } else {
                const err = await res.json();
                alert(err.error || 'Error al crear evento.');
            }
        } finally {
            e.target.dataset.enviando = '';
            if(btnSubmit) btnSubmit.disabled = false;
        }
    });
}
