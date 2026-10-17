// Lógica para el formulario de registro dinámico según tipo de negocio
function updateRequiredDocuments() {
    const type = document.getElementById('businessType')?.value;
    const container = document.getElementById('dynamicDocuments');
    if (!container) return;

    let html = '';

    if (type === 'handyman') {
        html = `
            <div class="doc-requirement">
                <h4>Requisitos para Handyman / Emprendedor Pequeño:</h4>
                <label>Identificación Oficial (Driver's License / ITIN):</label>
                <input type="file" required style="margin-bottom:10px; display:block;">
                <label>Póliza de Seguro de Responsabilidad Civil (Opcional):</label>
                <input type="file" style="display:block;">
            </div>
        `;
    } else if (type === 'taxi') {
        html = `
            <div class="doc-requirement">
                <h4>Requisitos para Taxi / Chofer Independiente:</h4>
                <label>Licencia de Conducir Válida en EE. UU. *:</label>
                <input type="file" required style="margin-bottom:10px; display:block;">
                <label>Registro del Vehículo (Vehicle Registration) *:</label>
                <input type="file" required style="margin-bottom:10px; display:block;">
                <label>Seguro de Auto Comercial o Endoso Rideshare *:</label>
                <input type="file" required style="display:block;">
            </div>
        `;
    } else if (type === 'contractor') {
        html = `
            <div class="doc-requirement">
                <h4>Requisitos para Contratistas Licenciados:</h4>
                <label>Número de Licencia Estatal / Condal *:</label>
                <input type="text" placeholder="Ej. CRC123456" required style="margin-bottom:10px; display:block; width:100%; padding:8px;">
                <label>Certificado de Seguro de Responsabilidad Civil *:</label>
                <input type="file" required style="display:block;">
            </div>
        `;
    } else if (type === 'llc') {
        html = `
            <div class="doc-requirement">
                <h4>Requisitos para Compañías Registradas (LLC / Inc):</h4>
                <label>Número EIN (Employer Identification Number) *:</label>
                <input type="text" placeholder="XX-XXXXXXX" required style="margin-bottom:10px; display:block; width:100%; padding:8px;">
                <label>Artículos de Organización y Licencia Comercial *:</label>
                <input type="file" required style="display:block;">
            </div>
        `;
    } else {
        html = '<p class="placeholder-text">Selecciona un tipo de negocio arriba para ver los requisitos de registro.</p>';
    }

    container.innerHTML = html;
}

// Filtro de búsqueda en la página principal
function filterBusinesses() {
    const query = document.getElementById('searchInput').value.toLowerCase();
    const selectedLang = document.getElementById('langSelect').value;
    const cards = document.querySelectorAll('.business-card');

    cards.forEach(card => {
        const text = card.innerText.toLowerCase();
        const lang = card.getAttribute('data-lang');
        
        const matchesQuery = text.includes(query);
        const matchesLang = !selectedLang || lang === selectedLang;

        if (matchesQuery && matchesLang) {
            card.style.display = 'flex';
        } else {
            card.style.display = 'none';
        }
    });
}
