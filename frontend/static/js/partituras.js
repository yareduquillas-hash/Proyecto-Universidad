/* ─────────────────────────────────────────────────────────────
   2. BIBLIOTECA VIRTUAL DE PARTITURAS
   ───────────────────────────────────────────────────────────── */
let partiturasPage = 1;

async function renderPartituras(){
    const canUpload = ['profesor', 'secretaria', 'admin'].includes(USER_ROLE);
    const html = `
    <div style="display:flex;gap:15px;flex-wrap:wrap;margin-bottom:20px;align-items:flex-end;">
        <div>
            <label style="display:block;margin-bottom:5px;font-weight:600;">Agrupación:</label>
            <select id="filtroAgrupPart" class="login-input" style="width:160px;" onchange="actualizarListaPartituras()"><option value="">Todas</option></select>
        </div>
        <div>
            <label style="display:block;margin-bottom:5px;font-weight:600;">Instrumento:</label>
            <select id="filtroInstPart" class="login-input" style="width:160px;" onchange="actualizarListaPartituras()"><option value="">Todos</option></select>
        </div>
        <div>
            <label style="display:block;margin-bottom:5px;font-weight:600;">Cátedra:</label>
            <input type="text" id="filtroCatPart" class="login-input" placeholder="Ej. Cuerdas" style="width:140px;" onkeyup="debouncedActualizarListaPartituras()">
        </div>
        <div>
            <label style="display:block;margin-bottom:5px;font-weight:600;">Obra:</label>
            <input type="text" id="filtroObraPart" class="login-input" placeholder="Nombre de obra" style="width:150px;" onkeyup="debouncedActualizarListaPartituras()">
        </div>
        <div>
            <label style="display:block;margin-bottom:5px;font-weight:600;">Compositor:</label>
            <input type="text" id="filtroCompPart" class="login-input" placeholder="Ej. Beethoven" style="width:150px;" onkeyup="debouncedActualizarListaPartituras()">
        </div>
        ${canUpload ? `
        <div style="margin-left:auto;">
            <button onclick="mostrarModalSubirPartitura()" style="padding:12px 20px;background:#D81B60;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:bold;">
                <i class="fa-solid fa-cloud-arrow-up"></i> Subir PDF
            </button>
        </div>` : ''}
    </div>
    <div id="listaPartituras"></div>`;
    document.getElementById('contentBody').innerHTML = html;
    await cargarSelectoresPartituras();
    await actualizarListaPartituras();
}

async function cargarSelectoresPartituras(){
    const agrupRes = await apiCall('/usuarios/agrupaciones');
    if(agrupRes && agrupRes.ok){
        const data = await agrupRes.json();
        const sel = document.getElementById('filtroAgrupPart');
        if(sel) sel.innerHTML += data.map(a=>`<option value="${a.id}">${escapeHtml(a.nombre)}</option>`).join('');
    }
    const instrRes = await apiCall('/usuarios/instrumentos');
    if(instrRes && instrRes.ok){
        const data = await instrRes.json();
        const sel = document.getElementById('filtroInstPart');
        if(sel) sel.innerHTML += data.map(i=>`<option value="${i.id}">${escapeHtml(i.nombre)}</option>`).join('');
    }
}

async function actualizarListaPartituras(page){
    partiturasPage = page || 1;
    const agrupId = document.getElementById('filtroAgrupPart')?.value;
    const instId = document.getElementById('filtroInstPart')?.value;
    const catedra = document.getElementById('filtroCatPart')?.value;
    const obra = document.getElementById('filtroObraPart')?.value;
    const compositor = document.getElementById('filtroCompPart')?.value;
    const params = new URLSearchParams();
    if(agrupId) params.set('agrupacion_id', agrupId);
    if(instId) params.set('instrumento_id', instId);
    if(catedra) params.set('catedra', catedra);
    if(obra) params.set('obra', obra);
    if(compositor) params.set('compositor', compositor);
    params.set('page', String(partiturasPage));
    params.set('per_page', '50');

    const res = await apiCall('/partituras/?' + params.toString());
    if(!res || !res.ok) return;
    const rawP = await res.json();
    const items = _items(rawP);
    const canManage = ['profesor', 'secretaria', 'admin'].includes(USER_ROLE);
    
    document.getElementById('listaPartituras').innerHTML = _avisoTruncado(rawP) + (items.length === 0
        ? '<p style="padding:20px;text-align:center;">No hay partituras registradas con esos filtros.</p>'
        : `<table class="members-table">
            <thead><tr><th>Título</th><th>Obra</th><th>Compositor</th><th>Cátedra</th><th>Agrupación</th><th>Instrumento</th><th>Acciones</th></tr></thead>
            <tbody>${items.map(p => `
                <tr>
                    <td><strong>${escapeHtml(p.titulo)}</strong></td>
                    <td>${escapeHtml(p.obra) || '-'}</td>
                    <td>${escapeHtml(p.compositor) || '-'}</td>
                    <td>${escapeHtml(p.catedra) || '-'}</td>
                    <td>${escapeHtml(p.agrupacion_nombre)}</td>
                    <td>${escapeHtml(p.instrumento_nombre) || 'General'}</td>
                    <td>
                        <button onclick="descargarPartitura(${p.id})" style="background:none;border:none;color:#009B77;cursor:pointer;font-weight:bold;margin-right:10px;">
                            <i class="fa-solid fa-download"></i> Descargar
                        </button>
                        <button onclick="previsualizarPartitura(${p.id})" style="background:none;border:none;color:var(--text);cursor:pointer;font-weight:bold;">
                            <i class="fa-solid fa-eye"></i> Previsualizar
                        </button>
                        ${canManage ? `
                        <button onclick="eliminarPartitura(${p.id})" style="background:none;border:none;color:#D81B60;cursor:pointer;margin-left:10px;">
                            <i class="fa-solid fa-trash"></i>
                        </button>` : ''}
                    </td>
                </tr>`).join('')}
            </tbody>
        </table>`) + _pagControls(rawP, 'actualizarListaPartituras');
}

const debouncedActualizarListaPartituras = debounce(actualizarListaPartituras, 350);

async function descargarPartitura(id){
    const res = await apiCall(`/partituras/${id}/descargar`);
    if(!res || !res.ok) return alert('Error al descargar la partitura.');
    const blob = await res.blob();
    let filename = `partitura_${id}.pdf`;
    const disp = res.headers.get('Content-Disposition') || '';
    const m = disp.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
    if(m && m[1]) filename = decodeURIComponent(m[1]);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
}

async function previsualizarPartitura(id){
    const res = await apiCall('/partituras/' + id);
    const titulo = res && res.ok ? (await res.json()).titulo : 'Partitura';
    showModal(`
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <h3>Previsualización: ${escapeHtml(titulo)}</h3>
            <button onclick="closeModal()" style="border:none;background:none;font-size:1.2rem;cursor:pointer;">✖</button>
        </div>
        <div id="previewPartBody" style="text-align:center;padding:20px;">Cargando PDF…</div>
    `);
    const pdfRes = await apiCall(`/partituras/${encodeURIComponent(id)}/preview`);
    const box = document.getElementById('previewPartBody');
    if(!box) return;
    if(!pdfRes || !pdfRes.ok){ box.innerHTML = '<p>Error al cargar la previsualización.</p>'; return; }
    const blob = await pdfRes.blob();
    const url = URL.createObjectURL(blob);
    box.innerHTML = `<iframe src="${url}" style="width:100%;height:70vh;border:none;border-radius:8px;"></iframe>`;
}

async function eliminarPartitura(id){
    if(!confirm('¿Estás seguro de eliminar esta partitura?')) return;
    const res = await apiCall(`/partituras/${id}`, 'DELETE');
    if(res && res.ok){
        alert('Partitura eliminada.');
        actualizarListaPartituras();
    }
}

async function mostrarModalSubirPartitura(){
    const agrupRes = await apiCall('/usuarios/agrupaciones');
    const instrRes = await apiCall('/usuarios/instrumentos');
    const agrups = agrupRes && agrupRes.ok ? await agrupRes.json() : [];
    const instrs = instrRes && instrRes.ok ? await instrRes.json() : [];

    showModal(`
        <h3 style="margin-bottom:15px;color:var(--text);">Subir Nueva Partitura (PDF)</h3>
        <form id="formSubirPartitura" enctype="multipart/form-data" class="grid-2">
            <div class="grid-full">
                <label style="font-weight:600;">Archivo PDF (*):</label>
                <input type="file" name="archivo" accept=".pdf" class="login-input" required>
            </div>
            <div class="grid-full">
                <label style="font-weight:600;">Título (*):</label>
                <input type="text" name="titulo" class="login-input" required placeholder="Ej. Violín I - Quinta Sinfonía">
            </div>
            <div>
                <label style="font-weight:600;">Obra:</label>
                <input type="text" name="obra" class="login-input" placeholder="Ej. 5ta Sinfonía Op. 67">
            </div>
            <div>
                <label style="font-weight:600;">Compositor:</label>
                <input type="text" name="compositor" class="login-input" placeholder="Ej. L. v. Beethoven">
            </div>
            <div>
                <label style="font-weight:600;">Cátedra:</label>
                <input type="text" name="catedra" class="login-input" placeholder="Ej. Cuerdas / Violín">
            </div>
            <div>
                <label style="font-weight:600;">Agrupación (*):</label>
                <select name="agrupacion_id" class="login-input" required>
                    <option value="">Selecciona Agrupación</option>
                    ${agrups.map(a => `<option value="${a.id}">${escapeHtml(a.nombre)}</option>`).join('')}
                </select>
            </div>
            <div class="grid-full">
                <label style="font-weight:600;">Instrumento Destino (opcional):</label>
                <select name="instrumento_id" class="login-input">
                    <option value="">Todos los instrumentos</option>
                    ${instrs.map(i => `<option value="${i.id}">${escapeHtml(i.nombre)}</option>`).join('')}
                </select>
            </div>
            <div class="grid-full" style="display:flex;justify-content:flex-end;gap:10px;margin-top:15px;">
                <button type="button" onclick="closeModal()" style="padding:10px 20px;border:none;background:var(--border-strong);color:var(--text);border-radius:6px;cursor:pointer;">Cancelar</button>
                <button type="submit" class="btn-submit" style="width:auto;margin:0;padding:10px 25px;">Subir Partitura</button>
            </div>
        </form>
    `);

    document.getElementById('formSubirPartitura').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const res = await fetch(API + '/partituras/upload', {
            method: 'POST',
            headers: authHeaders(),
            body: fd
        });
        if(res.ok){
            alert('Partitura subida exitosamente.');
            closeModal();
            actualizarListaPartituras();
        } else {
            const err = await res.json();
            alert(err.error || 'Error al subir partitura.');
        }
    });
}
