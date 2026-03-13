let currentMode = 'filters';
let ws = null;
let sessionId = null;
let properties = [];

// Mode switching
function setMode(mode) {
    currentMode = mode;
    document.querySelectorAll('.mode-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.mode === mode);
    });
    document.getElementById('filtersPanel').classList.toggle('hidden', mode !== 'filters');
    document.getElementById('urlPanel').classList.toggle('hidden', mode !== 'url');
}

// URL validation
document.getElementById('customUrl')?.addEventListener('input', function () {
    const validation = document.getElementById('urlValidation');
    const url = this.value.trim();
    if (!url) {
        validation.textContent = '';
        return;
    }
    try {
        const parsed = new URL(url);
        if (parsed.hostname.includes('portalinmobiliario.com')) {
            validation.textContent = '✅';
        } else {
            validation.textContent = '❌';
        }
    } catch {
        validation.textContent = '❌';
    }
});

// Logging
function addLog(message, type = 'info') {
    const container = document.getElementById('logContainer');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const time = new Date().toLocaleTimeString('es-CL');
    entry.innerHTML = `<span class="timestamp">[${time}]</span> ${escapeHtml(message)}`;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateProgress(percent) {
    const bar = document.getElementById('progressBar');
    const text = document.getElementById('progressText');
    bar.style.width = `${Math.max(percent, 3)}%`;
    text.textContent = `${percent}%`;
}

function addPropertyRow(prop, index) {
    const tbody = document.getElementById('resultsBody');
    const tr = document.createElement('tr');
    const precio = prop.precio_clp || prop.precio_uf || '-';
    tr.innerHTML = `
        <td>${index}</td>
        <td title="${escapeHtml(prop.titulo)}">${escapeHtml(prop.titulo || '-')}</td>
        <td>${escapeHtml(precio)}</td>
        <td title="${escapeHtml(prop.ubicacion)}">${escapeHtml(prop.ubicacion || prop.comuna || '-')}</td>
        <td>${escapeHtml(prop.tipo_propiedad || '-')}</td>
        <td>${escapeHtml(prop.superficie_construida || '-')}</td>
        <td>${escapeHtml(prop.habitaciones || '-')}</td>
        <td>${escapeHtml(prop.banos || '-')}</td>
        <td>${prop.url ? `<a href="${escapeHtml(prop.url)}" target="_blank">Ver</a>` : '-'}</td>
    `;
    tbody.appendChild(tr);
}

// Start scraping
function startScraping() {
    // Reset
    properties = [];
    sessionId = null;
    document.getElementById('resultsBody').innerHTML = '';
    document.getElementById('logContainer').innerHTML = '';
    updateProgress(0);

    // Show/hide sections
    document.getElementById('progressSection').classList.remove('hidden');
    document.getElementById('resultsSection').classList.remove('hidden');
    document.getElementById('btnStart').classList.add('hidden');
    document.getElementById('btnCancel').classList.remove('hidden');
    document.getElementById('btnDownload').disabled = true;
    document.getElementById('resultsCount').textContent = '';

    // Build config
    const config = {
        mode: currentMode,
        max_pages: parseInt(document.getElementById('maxPages').value) || 5,
        max_properties: parseInt(document.getElementById('maxProperties').value) || 50,
    };

    if (currentMode === 'url') {
        config.url = document.getElementById('customUrl').value.trim();
        if (!config.url) {
            alert('Por favor ingresa una URL');
            resetControls();
            return;
        }
    } else {
        config.operacion = document.getElementById('operacion').value;
        config.tipo_propiedad = document.getElementById('tipoPropiedad').value;
        config.region = document.getElementById('region').value;
        config.comuna = document.getElementById('comuna').value;

        const precioMin = document.getElementById('precioMin').value;
        const precioMax = document.getElementById('precioMax').value;
        const supMin = document.getElementById('superficieMin').value;
        const supMax = document.getElementById('superficieMax').value;

        if (precioMin) config.precio_min = parseInt(precioMin);
        if (precioMax) config.precio_max = parseInt(precioMax);
        if (supMin) config.superficie_min = parseInt(supMin);
        if (supMax) config.superficie_max = parseInt(supMax);

        const hab = document.getElementById('habitaciones').value;
        const ban = document.getElementById('banos').value;
        if (hab) config.habitaciones = parseInt(hab);
        if (ban) config.banos = parseInt(ban);

        config.estacionamiento = document.getElementById('conEstacionamiento').checked;
        config.bodega = document.getElementById('conBodega').checked;
        config.amoblado = document.getElementById('amoblado').checked;
    }

    // Connect WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/scrape`;

    try {
        ws = new WebSocket(wsUrl);
    } catch (e) {
        addLog('Error al conectar con el servidor: ' + e.message, 'error');
        resetControls();
        return;
    }

    ws.onopen = () => {
        addLog('Conectado al servidor. Iniciando scraping...', 'success');
        ws.send(JSON.stringify(config));
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleMessage(data);
    };

    ws.onerror = () => {
        addLog('Error de conexión WebSocket', 'error');
        resetControls();
    };

    ws.onclose = () => {
        addLog('Conexión cerrada', 'info');
        resetControls();
    };
}

function handleMessage(data) {
    switch (data.type) {
        case 'status':
        case 'info':
            addLog(data.message, 'info');
            if (data.progress !== undefined) updateProgress(data.progress);
            break;

        case 'progress':
            addLog(data.message, 'info');
            if (data.progress !== undefined) updateProgress(data.progress);
            break;

        case 'property':
            properties.push(data.data);
            addPropertyRow(data.data, data.index);
            document.getElementById('resultsCount').textContent = `(${properties.length} propiedades)`;
            break;

        case 'warning':
            addLog(data.message, 'warning');
            break;

        case 'error':
            addLog(data.message, 'error');
            break;

        case 'complete':
            addLog(data.message, 'success');
            updateProgress(100);
            document.getElementById('btnDownload').disabled = false;
            break;

        case 'cancelled':
            addLog(data.message, 'warning');
            break;

        case 'session':
            sessionId = data.session_id;
            document.getElementById('btnDownload').disabled = false;
            break;
    }
}

function cancelScraping() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'cancel' }));
        addLog('Cancelando scraping...', 'warning');
    }
}

function resetControls() {
    document.getElementById('btnStart').classList.remove('hidden');
    document.getElementById('btnCancel').classList.add('hidden');
}

function downloadCSV() {
    if (!sessionId) {
        // Fallback: generate CSV client-side
        if (properties.length === 0) {
            alert('No hay datos para descargar');
            return;
        }
        downloadClientCSV();
        return;
    }
    window.open(`/api/download/${sessionId}`, '_blank');
}

function downloadClientCSV() {
    const headers = [
        'URL', 'Título', 'Precio CLP', 'Precio UF', 'Ubicación',
        'Región', 'Comuna', 'Barrio', 'Tipo Propiedad',
        'Superficie Construida', 'Superficie Total',
        'Habitaciones', 'Baños', 'Estacionamientos', 'Bodegas',
        'Gastos Comunes', 'Antigüedad', 'Fecha Publicación'
    ];

    const keys = [
        'url', 'titulo', 'precio_clp', 'precio_uf', 'ubicacion',
        'region', 'comuna', 'barrio', 'tipo_propiedad',
        'superficie_construida', 'superficie_total',
        'habitaciones', 'banos', 'estacionamientos', 'bodegas',
        'gastos_comunes', 'antiguedad', 'fecha_publicacion'
    ];

    let csv = '\uFEFF'; // BOM for UTF-8
    csv += headers.map(h => `"${h}"`).join(',') + '\n';

    properties.forEach(prop => {
        csv += keys.map(k => {
            const val = (prop[k] || '').toString().replace(/"/g, '""');
            return `"${val}"`;
        }).join(',') + '\n';
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'propiedades_portal_inmobiliario.csv';
    a.click();
    URL.revokeObjectURL(url);
}
