const API = '/api/v1';
const USER_ROLE = localStorage.getItem('role') || 'alumno';
const USER_ID = localStorage.getItem('userId');

const getToken = () => localStorage.getItem('token');
const authHeaders = () => ({"Authorization": "Bearer " + getToken()});

// Sanitización XSS: escapa datos de usuario antes de insertar en innerHTML
function escapeHtml(str){
    if(str == null) return '';
    return String(str).replace(/[&<>"']/g, function(m){
        return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m];
    });
}
function escapeAttr(str){ return escapeHtml(str).replace(/`/g, '&#96;'); }
function _items(d){ return Array.isArray(d) ? d : ((d && d.items) ? d.items : []); }
function _avisoTruncado(d){
    if(d && !Array.isArray(d) && (d.truncated || (d.total && d.items && d.total > d.items.length))){
        const total = d.total || '?';
        const n = (d.items || []).length;
        return `<div style="background:#fff8e1;padding:10px;border-radius:8px;margin-bottom:12px;font-weight:600;">Mostrando ${n} de ${total}. Use la paginación o filtros para ver el resto.</div>`;
    }
    return '';
}
// Controles de paginación para respuestas {items,total,page,pages}.
// fnName: función global que recibe el número de página (1-based).
function _pagControls(d, fnName){
    if(!d || Array.isArray(d) || !d.pages || d.pages <= 1) return '';
    const page = d.page || 1;
    const total = (d.total != null) ? d.total : '?';
    const btn = 'padding:8px 14px;border:1px solid var(--border-color,#e2e8f0);background:var(--card-bg,#fff);color:var(--text,#1e293b);border-radius:6px;cursor:pointer;font-weight:600;';
    const prev = page > 1 ? `<button type="button" style="${btn}" onclick="${fnName}(${page-1})">◀ Anterior</button>` : '';
    const next = page < d.pages ? `<button type="button" style="${btn}" onclick="${fnName}(${page+1})">Siguiente ▶</button>` : '';
    return `<div style="display:flex;gap:10px;justify-content:center;align-items:center;margin:14px 0;font-weight:600;">
        ${prev}<span>Página ${page} de ${d.pages} · ${total} en total</span>${next}
    </div>`;
}

function checkAuth(){
    if(!getToken()){ window.location.href = '/login'; return false; }
    document.getElementById('userName').textContent = localStorage.getItem('nombre') || 'Usuario';
    const roleBadge = document.getElementById('userRoleBadge');
    if(roleBadge) roleBadge.textContent = USER_ROLE.toUpperCase();
    return true;
}

async function apiCall(path, method='GET', body, _retried){
    const opts = { method, headers: authHeaders() };
    if(body && !(body instanceof FormData)){
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    } else if(body instanceof FormData){
        opts.body = body;
    }
    try {
        const res = await fetch(API + path, opts);
        if(res.status === 403){
            try {
                const clone = res.clone();
                const ej = await clone.json().catch(()=>null);
                if(ej && ej.requiere_cambio_clave){
                    mostrarModalCambioClave(true);
                    return res;
                }
            } catch(e){}
        }
        if(res.status === 401 && !_retried && localStorage.getItem('refresh_token')){
            // Intenta rotar access con refresh (access ahora dura 2h)
            try {
                const rr = await fetch(API + '/auth/refresh', {
                    method: 'POST',
                    headers: {"Authorization": "Bearer " + localStorage.getItem('refresh_token')}
                });
                if(rr.ok){
                    const dj = await rr.json();
                    localStorage.setItem('token', dj.access_token);
                    return apiCall(path, method, body, true);
                }
            } catch(e){ /* cae a logout */ }
            localStorage.clear(); window.location.href='/login'; return null;
        }
        if(res.status === 401){ localStorage.clear(); window.location.href='/login'; return null; }
        return res;
    } catch(e) {
        console.error('API call failed', e);
        return null;
    }
}

function debounce(fn, ms){
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

function fechaLocalHoy(){
    // Fecha local del navegador (evita el desfase UTC de toISOString en Venezuela UTC-4)
    const d = new Date();
    const m = String(d.getMonth()+1).padStart(2,'0');
    const day = String(d.getDate()).padStart(2,'0');
    return `${d.getFullYear()}-${m}-${day}`;
}

async function loadSidebar(){
    const res = await apiCall('/auth/menu');
    if(!res) return;
    const items = await res.json();
    const sidebar = document.getElementById('sidebarContent');
    sidebar.innerHTML = items.map((it, i) =>
        `<button class="side-btn ${i===0 ? 'active':''}" data-module="${it.name}" onclick="navigateTo('${it.name}')">
            <i class="fa-solid ${it.icon}"></i> ${it.label}
        </button>`
    ).join('') + `
    <hr class="sidebar-divider">
    <a href="/" class="side-btn"><i class="fa-solid fa-house"></i> Inicio Portal</a>`;
    
    if(items.length > 0) navigateTo(items[0].name);
}

async function navigateTo(module){
    const titles = {
        inicio: 'Dashboard de Administración',
        asistencia: 'Control de Asistencia',
        partituras: 'Biblioteca Virtual de Partituras',
        cronograma: 'Cronograma Activo',
        audiciones: 'Admisiones y Audiciones',
        usuarios: 'Gestión Integral de Usuarios',
    };
    document.getElementById('contentTitle').textContent = titles[module] || module;
    const body = document.getElementById('contentBody');
    body.classList.remove('fade-enter');
    body.innerHTML = '<div class="spinner"></div>';
    document.querySelectorAll('.side-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`[data-module="${module}"]`);
    if(btn) btn.classList.add('active');

    if(window.innerWidth <= 640){
        const sidebar = document.getElementById('mainSidebar');
        const overlay = document.getElementById('sidebarOverlay');
        sidebar.classList.remove('open');
        overlay.classList.remove('show');
    }
    try {
        if(module === 'inicio') await renderInicio();
        else if(module === 'asistencia') await renderAsistencia();
        else if(module === 'partituras') await renderPartituras();
        else if(module === 'cronograma') await renderCronograma();
        else if(module === 'audiciones') await renderAudiciones();
        else if(module === 'usuarios') await renderUsuarios();
        document.getElementById('contentBody').classList.add('fade-enter');
    } catch(e){
        document.getElementById('contentBody').innerHTML = '<p style="color:#c62828;padding:20px;text-align:center;">Error al cargar el módulo.</p>';
        console.error(e);
    }
}

function showModal(html){
    const el = document.getElementById('modalContainer');
    // html aquí es generado internamente, no datos de usuario directo; si contiene datos, ya vienen escapados con escapeHtml
    el.innerHTML = `<div class="modal-overlay" onclick="closeModal(event)"><div class="modal-box" onclick="event.stopPropagation()">${html}</div></div>`;
    el.style.display = 'block';
}

function closeModal(e){
    if(e) e.stopPropagation();
    document.getElementById('modalContainer').style.display = 'none';
}

function showToast(msg, type='success'){
    const container = document.getElementById('toastContainer');
    if(!container) return;
    const icons = {success:'fa-check-circle', error:'fa-exclamation-circle', warning:'fa-exclamation-triangle', info:'fa-info-circle'};
    const icon = icons[type] || icons.info;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> ${escapeHtml(msg)}`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 400);
    }, 3000);
}

function initTheme(){
    const theme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeUI(theme);
}

function toggleTheme(){
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    updateThemeUI(next);
}

function updateThemeUI(theme){
    const icon = document.getElementById('themeIcon');
    const label = document.getElementById('themeLabel');
    if(!icon || !label) return;
    if(theme === 'dark'){
        icon.className = 'fa-solid fa-sun';
        label.textContent = 'Claro';
    } else {
        icon.className = 'fa-solid fa-moon';
        label.textContent = 'Oscuro';
    }
}

/* ─────────────────────────────────────────────────────────────
   0. DASHBOARD DE ADMINISTRACIÓN (ESTADÍSTICAS)
   ───────────────────────────────────────────────────────────── */
async function renderInicio(){
    const res = await apiCall('/dashboard/stats');
    if(!res || !res.ok){
        document.getElementById('contentBody').innerHTML = '<p>Error al cargar estadísticas.</p>';
        return;
    }
    const s = await res.json();
    const html = `
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-icon"><i class="fa-solid fa-users"></i></div>
            <div class="stat-info">
                <div class="stat-number">${s.total_usuarios}</div>
                <div class="stat-label">Usuarios Registrados</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon"><i class="fa-solid fa-music"></i></div>
            <div class="stat-info">
                <div class="stat-number">${s.total_agrupaciones}</div>
                <div class="stat-label">Agrupaciones Activas</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon"><i class="fa-solid fa-calendar-check"></i></div>
            <div class="stat-info">
                <div class="stat-number">${s.porcentaje_asistencia_global}%</div>
                <div class="stat-label">Asistencia Global</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon"><i class="fa-solid fa-clipboard-list"></i></div>
            <div class="stat-info">
                <div class="stat-number">${s.postulaciones_pendientes}</div>
                <div class="stat-label">Postulaciones Pendientes</div>
            </div>
        </div>
    </div>
    <div style="background:var(--green-subtle);padding:22px;border-radius:12px;border:1px solid var(--border);border-left:4px solid var(--primary);margin-top:10px;">
        <p style="color:var(--text);margin-bottom:6px;font-weight:600;"><i class="fa-solid fa-circle-info" style="color:var(--primary);margin-right:8px;"></i> Bienvenido al panel de administración del <strong>Núcleo Los Teques</strong>.</p>
        <p style="color:var(--text-muted);font-size:0.9rem;">Utiliza el menú lateral para gestionar usuarios, asistencia, partituras, cronograma y audiciones.</p>
    </div>`;
    document.getElementById('contentBody').innerHTML = html;
}

function mostrarModalCambioClave(obligatorio=false){
    if(document.getElementById('formCambioClave')) return;
    showModal(`
        <h3 style="margin-bottom:10px;">${obligatorio ? 'Cambio de contraseña temporal obligatorio' : 'Cambiar contraseña'}</h3>
        ${obligatorio ? '<p style="color:#b45309;font-weight:600;">Tu clave temporal no permite operar hasta cambiarla.</p>' : ''}
        <form id="formCambioClave" class="grid-2">
            <div class="grid-full"><label>Contraseña actual / temporal (*):</label>
                <input type="password" id="ccActual" class="login-input" required></div>
            <div><label>Nueva (mín 8, letra y número) (*):</label>
                <input type="password" id="ccNueva" class="login-input" required></div>
            <div><label>Confirmar nueva (*):</label>
                <input type="password" id="ccConf" class="login-input" required></div>
            <div class="grid-full" style="display:flex;justify-content:flex-end;gap:10px;margin-top:12px;">
                ${obligatorio ? '' : '<button type="button" onclick="closeModal()" style="padding:10px 18px;border:none;background:var(--border-strong);border-radius:6px;cursor:pointer;">Cancelar</button>'}
                <button class="btn-submit" style="width:auto;margin:0;padding:10px 22px;">Guardar</button>
            </div>
        </form>`);
    document.getElementById('formCambioClave').addEventListener('submit', async (e)=>{
        e.preventDefault();
        const cur = document.getElementById('ccActual').value;
        const nw = document.getElementById('ccNueva').value;
        const cf = document.getElementById('ccConf').value;
        if(nw !== cf){ showToast('Las contraseñas no coinciden.','error'); return; }
        const res = await apiCall('/auth/change-password', 'POST', { current_password: cur, password: nw, confirm_password: cf });
        if(res && res.ok){
            const dj = await res.json().catch(()=>null);
            if(dj && dj.access_token){ localStorage.setItem('token', dj.access_token); }
            if(dj && dj.refresh_token){ localStorage.setItem('refresh_token', dj.refresh_token); }
            closeModal(); showToast('Contraseña cambiada.','success');
        } else { let m='Error al cambiar.'; try{ m=(await res.json()).error||m; }catch(e){} showToast(m,'error'); }
    });
}

async function forzarCambioClaveSiRequerido(){
    const res = await apiCall('/auth/me');
    if(!res || !res.ok) return;
    const me = await res.json().catch(()=>null);
    if(me && me.alumno_id) localStorage.setItem('alumnoId', me.alumno_id);
    if(me && me.requiere_cambio_clave) mostrarModalCambioClave(true);
}

function toggleSidebar(){
    const sidebar = document.getElementById('mainSidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('show');
}

document.addEventListener('click', function(e){
    const sidebar = document.getElementById('mainSidebar');
    const hamburger = document.getElementById('hamburgerBtn');
    if(window.innerWidth <= 640 && sidebar.classList.contains('open') && 
       !sidebar.contains(e.target) && !hamburger.contains(e.target)){
        toggleSidebar();
    }
});

// Cerrar modal con ESC
document.addEventListener('keydown', function(e){
    if(e.key === 'Escape'){
        const mc = document.getElementById('modalContainer');
        if(mc && mc.style.display === 'block') closeModal();
    }
});

document.getElementById('btnChangePass')?.addEventListener('click', (e)=>{ e.preventDefault(); mostrarModalCambioClave(false); });

document.getElementById('btnLogout').addEventListener('click', async (e) => {
    e.preventDefault();
    try {
        const headers = authHeaders();
        headers['Content-Type'] = 'application/json';
        await fetch(API + '/auth/logout', { method: 'POST', headers, body: JSON.stringify({ refresh_token: localStorage.getItem('refresh_token') }) });
    } catch(err){}
    localStorage.clear();
    window.location.href = '/login';
});
