/* ─────────────────────────────────────────────────────────────
   1. CONTROL DE ASISTENCIA
   ───────────────────────────────────────────────────────────── */
async function renderAsistencia(){
    if(USER_ROLE === 'alumno'){
        await renderAsistenciaAlumno();
        return;
    }
    const html = `
<div style="display:flex;gap:15px;flex-wrap:wrap;margin-bottom:25px;align-items:flex-end;">
    <div>
        <label style="display:block;margin-bottom:5px;font-weight:600;">Agrupación:</label>
        <select id="selAgrupAsist" class="login-input" style="width:250px;"></select>
    </div>
    <div>
        <label style="display:block;margin-bottom:5px;font-weight:600;">Fecha:</label>
        <input type="date" id="fechaAsist" class="login-input" style="width:200px;">
    </div>
    <button onclick="cargarListaAsistencia()" style="padding:12px 20px;background:#009B77;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:bold;">
        <i class="fa-solid fa-search"></i> Cargar Lista
    </button>
    <button onclick="guardarAsistencia()" style="padding:12px 20px;background:#D81B60;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:bold;">
        <i class="fa-solid fa-floppy-disk"></i> Guardar Asistencia
    </button>
    <button onclick="verReporteAsist()" style="padding:12px 20px;background:var(--card-bg-subtle);color:var(--text);border:1px solid var(--border);border:none;border-radius:8px;cursor:pointer;font-weight:bold;">
        <i class="fa-solid fa-chart-bar"></i> Reporte Agrupación
    </button>
    <button onclick="exportarCSVAsist()" style="padding:12px 20px;background:#f2c94c;color:#333;border:none;border-radius:8px;cursor:pointer;font-weight:bold;">
        <i class="fa-solid fa-file-csv"></i> Exportar CSV
    </button>
</div>
<div id="tablaAsistencia"></div>
<div id="reporteAsistencia" style="margin-top:25px;"></div>`;
    document.getElementById('contentBody').innerHTML = html;
    
    const res = await apiCall('/usuarios/agrupaciones');
    if(res && res.ok){
        const data = await res.json();
        const sel = document.getElementById('selAgrupAsist');
        sel.innerHTML = '<option value="">-- Selecciona Agrupación --</option>' +
            data.map(a => `<option value="${a.id}">${escapeHtml(a.nombre)}</option>`).join('');
    }
    document.getElementById('fechaAsist').value = fechaLocalHoy();
}

async function renderAsistenciaAlumno(){
    let alumnoId = localStorage.getItem('alumnoId');
    if(!alumnoId){
        const meRes = await apiCall('/auth/me');
        if(meRes && meRes.ok){
            const me = await meRes.json().catch(()=>null);
            if(me && me.alumno_id) { alumnoId = me.alumno_id; localStorage.setItem('alumnoId', alumnoId); }
            else if(me && me.id) { alumnoId = me.id; }
        }
    }
    if(!alumnoId) alumnoId = USER_ID;
    const res = await apiCall(`/asistencia/alumno/${alumnoId}`);
    if(!res || !res.ok){
        document.getElementById('contentBody').innerHTML = '<p>No se encontraron registros de asistencia personales.</p>';
        return;
    }
    const d = await res.json();
    const html = `
    ${d.truncado ? `<div style="background:#fff8e1;padding:10px;border-radius:8px;margin-bottom:12px;font-weight:600;">Historial parcial: mostrando ${d.total_registros} de ${d.total_reales}. Solicite reporte completo a secretaría.</div>` : ''}
    <div style="background:var(--card-bg-subtle);padding:20px;border-radius:12px;margin-bottom:25px;border:1px solid var(--border);">
        <h3 style="margin-bottom:15px;color:var(--text);">Mi Récord Personal de Asistencia</h3>
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(140px, 1fr));gap:15px;text-align:center;">
            <div style="background:var(--card-bg);border:1px solid var(--border);padding:15px;border-radius:10px;box-shadow:0 2px 5px rgba(0,0,0,0.05);">
                <div style="font-size:1.8rem;font-weight:bold;color:var(--text);">${d.total_registros}</div>
                <div style="font-size:0.85rem;color:var(--text-muted);">Total Clases</div>
            </div>
            <div style="background:var(--card-bg);border:1px solid var(--border);padding:15px;border-radius:10px;box-shadow:0 2px 5px rgba(0,0,0,0.05);">
                <div style="font-size:1.8rem;font-weight:bold;color:#2e7d32;">${d.presentes}</div>
                <div style="font-size:0.85rem;color:var(--text-muted);">Presente</div>
            </div>
            <div style="background:var(--card-bg);border:1px solid var(--border);padding:15px;border-radius:10px;box-shadow:0 2px 5px rgba(0,0,0,0.05);">
                <div style="font-size:1.8rem;font-weight:bold;color:#c62828;">${d.inasistencias_acumuladas}</div>
                <div style="font-size:0.85rem;color:var(--text-muted);">Ausente</div>
            </div>
            <div style="background:var(--card-bg);border:1px solid var(--border);padding:15px;border-radius:10px;box-shadow:0 2px 5px rgba(0,0,0,0.05);">
                <div style="font-size:1.8rem;font-weight:bold;color:#1565c0;">${d.justificados}</div>
                <div style="font-size:0.85rem;color:var(--text-muted);">Justificados</div>
            </div>
            <div style="background:var(--card-bg);border:1px solid var(--border);padding:15px;border-radius:10px;box-shadow:0 2px 5px rgba(0,0,0,0.05);">
                <div style="font-size:1.8rem;font-weight:bold;color:#f57f17;">${d.porcentaje_inasistencias}%</div>
                <div style="font-size:0.85rem;color:var(--text-muted);">% Inasistencias</div>
            </div>
        </div>
        ${d.en_riesgo ? `
        <div style="margin-top:20px;background:#ffebee;color:#c62828;padding:15px;border-radius:8px;font-weight:bold;display:flex;align-items:center;gap:10px;">
            <i class="fa-solid fa-triangle-exclamation fa-lg"></i>
            ATENCIÓN: Tu porcentaje de inasistencias (${d.porcentaje_inasistencias}%) ha superado el umbral permitido (25%). Estás en riesgo de exclusión de la agrupación. Contacta al profesor.
        </div>` : ''}
    </div>
    <h3>Historial de Fechas</h3>
    <table class="members-table">
        <thead><tr><th>Fecha</th><th>Estado</th><th>Observaciones</th></tr></thead>
        <tbody>
            ${d.historial.length === 0 ? '<tr><td colspan="3">Sin registros aún.</td></tr>' :
                d.historial.map(r => `
                    <tr>
                        <td>${escapeHtml(r.fecha) || '-'}</td>
                        <td><span class="badge ${r.estado==='presente'?'badge-success':r.estado==='ausente'?'badge-danger':'badge-warning'}">${escapeHtml(r.estado)}</span></td>
                        <td>${escapeHtml(r.observaciones) || '-'}</td>
                    </tr>`).join('')}
        </tbody>
    </table>`;
    document.getElementById('contentBody').innerHTML = html;
}

async function cargarListaAsistencia(){
    const agrupId = document.getElementById('selAgrupAsist').value;
    const fecha = document.getElementById('fechaAsist').value;
    if(!agrupId || !fecha) return alert('Por favor selecciona la agrupación y la fecha.');
    const res = await apiCall(`/asistencia/agrupacion/${agrupId}/fecha/${fecha}`);
    if(!res || !res.ok) return;
    const alumnos = await res.json();
    window._asistenciaAlumnos = alumnos;
    const html = `<table class="members-table">
        <thead><tr><th>#</th><th>Alumno</th><th>Cédula</th><th>Presente</th><th>Ausente</th><th>Justificado</th><th>Retraso</th><th>Motivo / Observación</th></tr></thead>
        <tbody>${alumnos.length === 0 ? '<tr><td colspan="8">No se encontraron alumnos asignados a esta agrupación.</td></tr>' :
            alumnos.map((a,i)=>`
            <tr>
                <td>${i+1}</td>
                <td><strong>${escapeHtml(a.nombre)}</strong></td>
                <td>${escapeHtml(a.cedula) || '-'}</td>
                <td><input type="radio" name="asist_${a.alumno_id}" value="presente" ${a.estado==='presente'||a.estado==='no_registrado'?'checked':''}></td>
                <td><input type="radio" name="asist_${a.alumno_id}" value="ausente" ${a.estado==='ausente'?'checked':''}></td>
                <td><input type="radio" name="asist_${a.alumno_id}" value="justificado" ${a.estado==='justificado'?'checked':''}></td>
                <td><input type="radio" name="asist_${a.alumno_id}" value="retraso" ${a.estado==='retraso'?'checked':''}></td>
                <td><input type="text" id="obs_${a.alumno_id}" class="login-input" style="min-width:140px;margin:0;" maxlength="500" placeholder="Motivo…" value="${escapeAttr(a.observaciones || '')}"></td>
            </tr>`).join('')}
        </tbody></table>`;
    document.getElementById('tablaAsistencia').innerHTML = html;
}

async function guardarAsistencia(){
    const agrupId = document.getElementById('selAgrupAsist').value;
    const fecha = document.getElementById('fechaAsist').value;
    const alumnos = window._asistenciaAlumnos || [];
    if(!agrupId || !fecha || alumnos.length === 0){ showToast('Primero selecciona agrupación y carga la lista.', 'warning'); return; }

    const registros = alumnos.map(a => {
        const radios = document.getElementsByName(`asist_${a.alumno_id}`);
        let estado = 'presente';
        radios.forEach(r => { if(r.checked) estado = r.value; });
        const obsEl = document.getElementById(`obs_${a.alumno_id}`);
        return { alumno_id: a.alumno_id, estado, observaciones: obsEl ? obsEl.value.trim().slice(0,500) : '' };
    });

    const res = await apiCall('/asistencia/registrar', 'POST', {
        agrupacion_id: parseInt(agrupId), fecha, registros
    });
    if(res && res.ok){
        const dj = await res.json().catch(() => ({}));
        showToast(`Asistencia guardada (${dj.total || registros.length} registros).`, 'success');
        await cargarListaAsistencia();
    } else {
        let msg = 'Error al guardar asistencia.';
        try { const ej = await res.json(); msg = ej.error || msg; } catch(e){}
        showToast(msg, 'error');
    }
}

async function verReporteAsist(){
    const agrupId = document.getElementById('selAgrupAsist').value;
    if(!agrupId) return alert('Selecciona una agrupación.');
    const res = await apiCall(`/asistencia/reporte/${agrupId}`);
    if(!res || !res.ok) return;
    const data = await res.json();
    const html = `<h3>Reporte de Inasistencias de la Agrupación</h3>
    <table class="members-table" style="margin-top:15px;">
        <thead><tr><th>#</th><th>Nombre Alumno</th><th>Clases Totales</th><th>% Asistencia</th><th>% Inasistencias</th><th>Estado de Riesgo</th></tr></thead>
        <tbody>${data.map((r,i)=>`
            <tr style="${r.en_riesgo ? 'background:#ffebee;font-weight:bold;' : ''}">
                <td>${i+1}</td>
                <td>${escapeHtml(r.nombre)}</td>
                <td>${r.total_registros}</td>
                <td>${r.porcentaje_asistencia}%</td>
                <td>${r.porcentaje_inasistencias}%</td>
                <td>${r.en_riesgo ? '<span class="badge badge-danger">⚠️ EN RIESGO DE EXCLUSIÓN</span>' : '<span class="badge badge-success">Normal</span>'}</td>
            </tr>`).join('')}
        </tbody></table>`;
    document.getElementById('reporteAsistencia').innerHTML = html;
}

async function exportarCSVAsist(){
    const agrupId = document.getElementById('selAgrupAsist').value;
    if(!agrupId) return alert('Selecciona una agrupación para exportar.');
    const res = await apiCall(`/asistencia/exportar/${agrupId}`);
    if(!res || !res.ok) return alert('Error exportando CSV.');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `reporte_asistencia_agrupacion_${agrupId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}
