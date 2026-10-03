/* ─────────────────────────────────────────────────────────────
   4. ADMISIONES Y AUDICIONES
   ───────────────────────────────────────────────────────────── */
let aspirantesPage = 1;
let convocatoriasPage = 1;

async function renderAudiciones(){
    const html = `
    <div style="border-bottom:2px solid #edf2f7;margin-bottom:20px;display:flex;gap:10px;">
        <button class="tab-btn active" id="tabConvBtn" onclick="switchAudicionesTab('convocatorias')">Convocatorias de Admisión</button>
        <button class="tab-btn" id="tabAspBtn" onclick="switchAudicionesTab('aspirantes')">Aspirantes & Matriz de Evaluación</button>
    </div>
    <div id="tabAudicionesContent"></div>`;
    document.getElementById('contentBody').innerHTML = html;
    await switchAudicionesTab('convocatorias');
}

async function switchAudicionesTab(tab){
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    if(tab === 'convocatorias') document.getElementById('tabConvBtn')?.classList.add('active');
    if(tab === 'aspirantes') document.getElementById('tabAspBtn')?.classList.add('active');

    const container = document.getElementById('tabAudicionesContent');
    container.innerHTML = '<p>Cargando datos del módulo...</p>';

    if(tab === 'convocatorias'){
        await cargarConvocatoriasAudicion(1);
    } else if(tab === 'aspirantes'){
        const resConvs = await apiCall('/audiciones/convocatorias?page=1&per_page=50');
        const rawConvs = resConvs && resConvs.ok ? await resConvs.json() : [];
        const convs = _items(rawConvs);

        container.innerHTML = `
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:15px;">
            ${['admin','secretaria','profesor'].includes(USER_ROLE) ? `<button onclick="mostrarModalCrearAspirante()" style="padding:10px 18px;background:#009B77;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:bold;">+ Nuevo aspirante</button>` : ''}
            ${USER_ROLE==='admin' ? `<button onclick="mostrarModalProgramarAudicion()" style="padding:10px 18px;background:#1d4ed8;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:bold;">+ Programar audición</button>` : ''}
        </div>
        <div style="display:grid;grid-template-columns:300px 1fr;gap:20px;">
            <div>
                <h3>Lista de Aspirantes</h3>
                <div style="margin:10px 0;">
                    <select id="filtroConvAsp" class="login-input" onchange="filtrarAspirantesAudicion(1)">
                        <option value="">Todas las convocatorias</option>
                        ${convs.map(c => `<option value="${c.id}">${escapeHtml(c.titulo)}</option>`).join('')}
                    </select>
                </div>
                <div id="listaAspirantesSidebar" style="max-height:60vh;overflow-y:auto;">
                    <p>Cargando aspirantes…</p>
                </div>
            </div>
            <div id="expedienteAspiranteArea" style="background:var(--card-bg-subtle);padding:20px;border-radius:12px;border:1px solid var(--border);">
                <p style="text-align:center;padding:40px;color:var(--text-muted);">Selecciona un aspirante de la lista para ver su expediente y calificarlo.</p>
            </div>
        </div>`;
        await filtrarAspirantesAudicion(1);
    }
}

async function cargarConvocatoriasAudicion(page){
    convocatoriasPage = page || 1;
    const res = await apiCall(`/audiciones/convocatorias?page=${convocatoriasPage}&per_page=50`);
    const rawC = res && res.ok ? await res.json() : [];
    const convocatorias = _items(rawC);
    const isAdmin = USER_ROLE === 'admin';
    const container = document.getElementById('tabAudicionesContent');

    container.innerHTML = _avisoTruncado(rawC) + `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <h3>Convocatorias Registradas</h3>
            ${isAdmin ? `<button onclick="mostrarModalCrearConvocatoria()" style="padding:10px 20px;background:#D81B60;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:bold;">+ Nueva Convocatoria</button>` : ''}
        </div>
        <table class="members-table">
            <thead><tr><th>#</th><th>Título</th><th>Fechas</th><th>Estado</th><th>Acciones</th></tr></thead>
            <tbody>${convocatorias.length === 0 ? '<tr><td colspan="5">No hay convocatorias creadas.</td></tr>' :
                convocatorias.map(c => `
                <tr>
                    <td>${c.id}</td>
                    <td><strong>${escapeHtml(c.titulo)}</strong><br><small style="color:var(--text-muted);">${escapeHtml(c.descripcion)||''}</small></td>
                    <td>${escapeHtml(c.fecha_inicio)} al ${escapeHtml(c.fecha_fin)}</td>
                    <td>${c.activa ? '<span class="badge badge-success">ACTIVA</span>' : '<span class="badge badge-warning">CERRADA</span>'}</td>
                    <td>
                        ${isAdmin ? `<button onclick="toggleConvocatoria(${c.id})" style="background:none;border:none;color:#009B77;cursor:pointer;font-weight:bold;">${c.activa?'Cerrar':'Activar'}</button>` : '-'}
                    </td>
                </tr>`).join('')}
            </tbody>
        </table>` + _pagControls(rawC, 'cargarConvocatoriasAudicion');
}


async function mostrarModalCrearConvocatoria(){
    showModal(`
        <h3 style="margin-bottom:15px;color:var(--text);">Apertura de Convocatoria de Admisión</h3>
        <form id="formCrearConv" class="grid-2">
            <div class="grid-full">
                <label style="font-weight:600;">Título de la Convocatoria (*):</label>
                <input type="text" name="titulo" class="login-input" required placeholder="Ej. Convocatoria Orquestal 2026-I">
            </div>
            <div>
                <label style="font-weight:600;">Fecha Apertura (*):</label>
                <input type="date" name="fecha_inicio" class="login-input" required>
            </div>
            <div>
                <label style="font-weight:600;">Fecha Cierre (*):</label>
                <input type="date" name="fecha_fin" class="login-input" required>
            </div>
            <div class="grid-full">
                <label style="font-weight:600;">Descripción / Requisitos:</label>
                <textarea name="descripcion" class="login-input" style="height:70px;" placeholder="Edades permitidas, documentos necesarios..."></textarea>
            </div>
            <div class="grid-full" style="display:flex;justify-content:flex-end;gap:10px;margin-top:15px;">
                <button type="button" onclick="closeModal()" style="padding:10px 20px;border:none;background:var(--border-strong);color:var(--text);border-radius:6px;cursor:pointer;">Cancelar</button>
                <button type="submit" class="btn-submit" style="width:auto;margin:0;padding:10px 25px;">Abrir Convocatoria</button>
            </div>
        </form>
    `);

    document.getElementById('formCrearConv').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const body = Object.fromEntries(fd);
        const res = await apiCall('/audiciones/convocatorias', 'POST', body);
        if(res && res.ok){
            alert('Convocatoria creada.');
            closeModal();
            cargarConvocatoriasAudicion(1);
        } else {
            alert('Error al crear convocatoria.');
        }
    });
}

async function toggleConvocatoria(id){
    const res = await apiCall(`/audiciones/convocatorias/${id}/activar`, 'PUT');
    if(res && res.ok){ cargarConvocatoriasAudicion(convocatoriasPage); }
}

async function filtrarAspirantesAudicion(page){
    aspirantesPage = page || 1;
    const convId = document.getElementById('filtroConvAsp')?.value;
    const params = new URLSearchParams();
    if(convId) params.set('convocatoria_id', convId);
    params.set('page', String(aspirantesPage));
    params.set('per_page', '50');
    const res = await apiCall('/audiciones/aspirantes?' + params.toString());
    if(!res || !res.ok) return;
    const rawF = await res.json();
    const aspirantes = _items(rawF);
    const container = document.getElementById('listaAspirantesSidebar');
    if(!container) return;
    const listHtml = aspirantes.map(a => `
        <div onclick="cargarExpedienteAspirante(${a.id})" style="padding:12px;border:1px solid var(--border);border-radius:8px;margin-bottom:8px;cursor:pointer;background:var(--card-bg);">
            <strong>${escapeHtml(a.nombre)} ${escapeHtml(a.apellido)}</strong><br>
            <small style="color:var(--text-muted);">Inst: ${escapeHtml(a.instrumento_postulado) || 'Voz'}</small> - 
            <span class="badge badge-info">${escapeHtml(a.estado)}</span>
        </div>`).join('') || '<p style="padding:20px;text-align:center;">No hay aspirantes para esta convocatoria.</p>';
    container.innerHTML = listHtml + _pagControls(rawF, 'filtrarAspirantesAudicion');
}

async function cargarExpedienteAspirante(id){
    const res = await apiCall(`/audiciones/aspirantes/${id}`);
    if(!res || !res.ok) return;
    const a = await res.json();
    const canScore = ['jurado', 'admin'].includes(USER_ROLE) && (a.estado === 'pendiente');
    const canDecide = ['admin', 'secretaria'].includes(USER_ROLE);

    const html = `
    <h3 style="color:var(--text);margin-bottom:10px;">Expediente: ${escapeHtml(a.nombre)} ${escapeHtml(a.apellido)}</h3>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:0.95rem;margin-bottom:20px;">
        <div><strong>Cédula:</strong> ${escapeHtml(a.cedula)}</div>
        <div><strong>Teléfono:</strong> ${escapeHtml(a.telefono) || '-'}</div>
        <div><strong>Correo:</strong> ${escapeHtml(a.email) || '-'}</div>
        <div><strong>Instrumento Postulado:</strong> <span class="badge badge-info">${escapeHtml(a.instrumento_postulado) || 'Voz'}</span></div>
        <div><strong>Estado:</strong> <span class="badge badge-info">${escapeHtml(a.estado)}</span></div>
        <div style="grid-column:span 2;"><strong>Experiencia Previa:</strong> ${escapeHtml(a.experiencia_previa) || 'No registrada'}</div>
    </div>
    ${a.estado !== 'pendiente' ? `<div style="background:#fff8e1;padding:12px;border-radius:8px;margin-bottom:15px;font-weight:600;">Expediente con decisión final (${escapeHtml(a.estado)}): evaluación cerrada.</div>` : ''}

    ${canDecide ? `
    <div style="background:var(--card-bg);border:1px solid var(--border);padding:15px;border-radius:10px;margin-bottom:15px;">
        <h4 style="margin-bottom:10px;">Decisión final (se comunica al aspirante)</h4>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <button onclick="decidirAspirante(${a.id},'admitido')" style="padding:8px 14px;background:#2e7d32;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">Admitir</button>
            <button onclick="decidirAspirante(${a.id},'no_admitido')" style="padding:8px 14px;background:#c62828;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">No admitir</button>
            <button onclick="decidirAspirante(${a.id},'en_espera')" style="padding:8px 14px;background:#b45309;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">En espera</button>
            <button onclick="decidirAspirante(${a.id},'pendiente')" style="padding:8px 14px;background:var(--border-strong);color:var(--text);border:none;border-radius:6px;cursor:pointer;">Reabrir</button>
            <button onclick="eliminarAspirante(${a.id})" style="padding:8px 14px;background:#6b7280;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:bold;margin-left:auto;">Eliminar expediente</button>
        </div>
    </div>` : ''}

    ${canScore ? `
    <div style="background:var(--card-bg);border:1px solid var(--border);padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.05);">
        <h4 style="color:#009B77;margin-bottom:15px;"><i class="fa-solid fa-star-half-stroke"></i> Evaluación interna del jurado (no es nota académica)</h4>
        <form id="formMatrizEvaluacion">
            <div style="display:grid;grid-template-columns:repeat(5, 1fr);gap:10px;text-align:center;margin-bottom:15px;">
                <div>
                    <label style="font-size:0.85rem;font-weight:600;">Técnica (0-10)</label>
                    <input type="number" step="0.5" min="0" max="10" id="scoreTec" class="login-input" placeholder="0-10" onchange="calcTotalScore()" required>
                </div>
                <div>
                    <label style="font-size:0.85rem;font-weight:600;">Interpretación (0-10)</label>
                    <input type="number" step="0.5" min="0" max="10" id="scoreInt" class="login-input" placeholder="0-10" onchange="calcTotalScore()" required>
                </div>
                <div>
                    <label style="font-size:0.85rem;font-weight:600;">Afinación (0-10)</label>
                    <input type="number" step="0.5" min="0" max="10" id="scoreAfi" class="login-input" placeholder="0-10" onchange="calcTotalScore()" required>
                </div>
                <div>
                    <label style="font-size:0.85rem;font-weight:600;">Ritmo (0-10)</label>
                    <input type="number" step="0.5" min="0" max="10" id="scoreRit" class="login-input" placeholder="0-10" onchange="calcTotalScore()" required>
                </div>
                <div>
                    <label style="font-size:0.85rem;font-weight:600;">Presencia (0-10)</label>
                    <input type="number" step="0.5" min="0" max="10" id="scorePre" class="login-input" placeholder="0-10" onchange="calcTotalScore()" required>
                </div>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;background:var(--card-bg-subtle);padding:10px;border-radius:8px;">
                <strong>Puntaje interno acumulado (máx 50):</strong>
                <span id="scoreTotalVal" style="font-size:1.4rem;font-weight:bold;color:#D81B60;">0.0 pts</span>
            </div>
            <div>
                <label style="font-weight:600;">Observaciones del Jurado:</label>
                <textarea id="scoreObs" class="login-input" style="height:60px;" placeholder="Comentarios sobre la audición..."></textarea>
            </div>
            <button type="submit" class="btn-submit" style="margin-top:15px;">Guardar Evaluación</button>
        </form>
    </div>` : ''}`;

    document.getElementById('expedienteAspiranteArea').innerHTML = html;

    if(canScore){
        calcTotalScore();
        document.getElementById('formMatrizEvaluacion').addEventListener('submit', async (e) => {
            e.preventDefault();
            const body = {
                tecnica: parseFloat(document.getElementById('scoreTec').value),
                interpretacion: parseFloat(document.getElementById('scoreInt').value),
                afinacion: parseFloat(document.getElementById('scoreAfi').value),
                ritmo: parseFloat(document.getElementById('scoreRit').value),
                presencia: parseFloat(document.getElementById('scorePre').value),
                observaciones: document.getElementById('scoreObs').value,
            };
            const res = await apiCall(`/audiciones/aspirantes/${id}/puntuacion`, 'POST', body);
            if(res && res.ok){
                alert('Puntuación guardada exitosamente.');
                cargarExpedienteAspirante(id);
            } else {
                let msg = 'No se pudo guardar (expediente cerrado o datos inválidos).';
                try { const ej = await res.json(); msg = ej.error || msg; } catch(_){}
                alert(msg);
            }
        });
    }
}

async function decidirAspirante(id, estado){
    if(!confirm(`¿Confirmar decisión: ${estado}?`)) return;
    const res = await apiCall(`/audiciones/aspirantes/${id}/estado`, 'PUT', { estado });
    if(res && res.ok){ showToast('Decisión guardada.', 'success'); cargarExpedienteAspirante(id); filtrarAspirantesAudicion(aspirantesPage); }
    else { let m='Error al guardar decisión.'; try{ m=(await res.json()).error||m; }catch(e){} showToast(m,'error'); }
}

async function eliminarAspirante(id){
    if(!confirm('¿Eliminar este aspirante y sus puntuaciones de forma permanente?')) return;
    const res = await apiCall(`/audiciones/aspirantes/${id}`, 'DELETE');
    if(res && res.ok){
        showToast('Aspirante eliminado.', 'warning');
        const area = document.getElementById('expedienteAspiranteArea');
        if(area) area.innerHTML = '<p style="text-align:center;padding:40px;color:var(--text-muted);">Selecciona un aspirante de la lista para ver su expediente y calificarlo.</p>';
        filtrarAspirantesAudicion(aspirantesPage);
    } else {
        let m='Error al eliminar el aspirante.';
        try{ m=(await res.json()).error||m; }catch(e){}
        showToast(m, 'error');
    }
}

async function mostrarModalCrearAspirante(){
    const rc = await apiCall('/audiciones/convocatorias');
    const raw = rc && rc.ok ? await rc.json() : [];
    const convs = _items(raw).filter(c=>c.activa);
    showModal(`
        <h3 style="margin-bottom:15px;">Nuevo aspirante (interno)</h3>
        <form id="formCrearAsp" class="grid-2">
            <div class="grid-full"><label>Convocatoria activa (*):</label>
                <select name="convocatoria_id" class="login-input" required>
                    <option value="">Selecciona</option>
                    ${convs.map(c=>`<option value="${c.id}">${escapeHtml(c.titulo)}</option>`).join('')}
                </select></div>
            <div><label>Nombre (*):</label><input name="nombre" class="login-input" required></div>
            <div><label>Apellido (*):</label><input name="apellido" class="login-input" required></div>
            <div><label>Cédula (*):</label><input name="cedula" class="login-input" required placeholder="V-12345678"></div>
            <div><label>Email:</label><input name="email" type="email" class="login-input"></div>
            <div><label>Teléfono:</label><input name="telefono" class="login-input"></div>
            <div><label>Instrumento postulado:</label><input name="instrumento_postulado" class="login-input"></div>
            <div class="grid-full" style="display:flex;justify-content:flex-end;gap:10px;margin-top:12px;">
                <button type="button" onclick="closeModal()" style="padding:10px 18px;border:none;background:var(--border-strong);border-radius:6px;cursor:pointer;">Cancelar</button>
                <button class="btn-submit" style="width:auto;margin:0;padding:10px 22px;">Guardar</button>
            </div>
        </form>`);
    document.getElementById('formCrearAsp').addEventListener('submit', async (e)=>{
        e.preventDefault();
        const fd = new FormData(e.target);
        const res = await fetch(API + '/audiciones/aspirantes', { method:'POST', headers: authHeaders(), body: fd });
        if(res.ok){ closeModal(); showToast('Aspirante registrado.','success'); filtrarAspirantesAudicion(1); }
        else { let m='Error al registrar.'; try{ m=(await res.json()).error||m; }catch(e){} alert(m); }
    });
}

async function mostrarModalProgramarAudicion(){
    const rg = await apiCall('/usuarios/agrupaciones');
    const agrups = rg && rg.ok ? await rg.json() : [];
    showModal(`
        <h3 style="margin-bottom:15px;">Programar audición</h3>
        <form id="formProgAud" class="grid-2">
            <div><label>Agrupación (*):</label><select name="agrupacion_id" class="login-input" required>
                <option value="">Selecciona</option>${agrups.map(a=>`<option value="${a.id}">${escapeHtml(a.nombre)}</option>`).join('')}</select></div>
            <div><label>Lugar:</label><input name="lugar" class="login-input"></div>
            <div><label>Fecha (*):</label><input type="date" name="fecha" class="login-input" required value="${fechaLocalHoy()}"></div>
            <div><label>Hora (* HH:MM):</label><input name="hora" class="login-input" required placeholder="10:00"></div>
            <div class="grid-full" style="display:flex;justify-content:flex-end;gap:10px;margin-top:12px;">
                <button type="button" onclick="closeModal()" style="padding:10px 18px;border:none;background:var(--border-strong);border-radius:6px;cursor:pointer;">Cancelar</button>
                <button class="btn-submit" style="width:auto;margin:0;padding:10px 22px;">Programar</button>
            </div>
        </form>`);
    document.getElementById('formProgAud').addEventListener('submit', async (e)=>{
        e.preventDefault();
        const body = Object.fromEntries(new FormData(e.target));
        body.agrupacion_id = parseInt(body.agrupacion_id);
        const res = await apiCall('/audiciones/audiciones', 'POST', body);
        if(res && res.ok){ closeModal(); showToast('Audición programada.','success'); }
        else { let m='Error al programar.'; try{ m=(await res.json()).error||m; }catch(e){} alert(m); }
    });
}

function calcTotalScore(){
    const t = parseFloat(document.getElementById('scoreTec')?.value || 0);
    const i = parseFloat(document.getElementById('scoreInt')?.value || 0);
    const a = parseFloat(document.getElementById('scoreAfi')?.value || 0);
    const r = parseFloat(document.getElementById('scoreRit')?.value || 0);
    const p = parseFloat(document.getElementById('scorePre')?.value || 0);
    const total = (t + i + a + r + p).toFixed(1);
    const el = document.getElementById('scoreTotalVal');
    if(el) el.textContent = total + ' pts';
}
