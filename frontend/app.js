const API_BASE = 'http://localhost:8000/api';

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

let geofenceMap;
let draw;

async function initializeApp() {
    checkConnection();
    setupNavigation();
    setupFileUpload();
    setupTabs();
    loadSuspects();
    setupGeofencing();
    setupWebSocket();

    // Refresh suspects list every 30 seconds
    setInterval(loadSuspects, 30000);
}

// Connection Status
async function checkConnection() {
    try {
        const response = await fetch('http://localhost:8000/health');
        const data = await response.json();
        const statusEl = document.getElementById('connectionStatus');
        const dot = statusEl.querySelector('.status-dot');

        if (data.status === 'healthy' && data.database === 'connected') {
            dot.classList.add('connected');
            statusEl.innerHTML = '<span class="status-dot connected"></span><span>Connected</span>';
        } else {
            dot.classList.remove('connected');
            statusEl.innerHTML = '<span class="status-dot"></span><span>Disconnected</span>';
        }
    } catch (error) {
        const statusEl = document.getElementById('connectionStatus');
        statusEl.innerHTML = '<span class="status-dot"></span><span>Connection Error</span>';
    }
}

// Convert kebab-case to camelCase
function toCamelCase(str) {
    return str.replace(/-([a-z])/g, (g) => g[1].toUpperCase());
}

// Navigation
function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const viewName = item.dataset.view;
            const viewId = toCamelCase(viewName) + 'View'; // Convert single-analysis to singleAnalysisView

            // Update active nav
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            // Show corresponding view
            views.forEach(view => view.style.display = 'none');
            const targetView = document.getElementById(viewId);
            if (targetView) {
                targetView.style.display = 'block';
            } else {
                console.error(`View not found: ${viewId}`);
            }

            // Load data for the view
            if (viewName === 'single-analysis' || viewName === 'multiple-analysis' || viewName === 'utils') {
                loadSuspects();
            }
        });
    });
}

// File Upload
function setupFileUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');

    if (!uploadArea || !fileInput) {
        console.error('Upload elements not found');
        return;
    }

    // Make upload area clickable
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });

    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFiles(files);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFiles(e.target.files);
        }
    });
}

async function handleFiles(files) {
    console.log('Handling files:', files.length);

    const progressDiv = document.getElementById('uploadProgress');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const resultsDiv = document.getElementById('uploadResults');

    if (!progressDiv || !progressFill || !progressText || !resultsDiv) {
        console.error('Upload UI elements not found');
        return;
    }

    progressDiv.style.display = 'block';
    progressFill.style.width = '0%';
    resultsDiv.innerHTML = '';

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        progressText.textContent = `Processing ${file.name}...`;
        progressFill.style.width = `${((i + 1) / files.length) * 100}%`;

        const formData = new FormData();
        formData.append('file', file);

        const inputSuspectName = document.getElementById('suspectName').value || null;
        const autoDetect = document.getElementById('autoDetect').checked;

        try {
            const response = await fetch(`${API_BASE}/upload?auto_detect=${autoDetect}${inputSuspectName ? `&suspect_name=${encodeURIComponent(inputSuspectName)}` : ''}`, {
                method: 'POST',
                body: formData
            });

            let result;
            try {
                result = await response.json();
            } catch (jsonError) {
                const text = await response.text();
                throw new Error(`Server error (${response.status}): ${text}`);
            }

            if (!response.ok) {
                throw new Error(result.detail || result.message || `HTTP ${response.status}: ${response.statusText}`);
            }

            if (result.success) {
                const uploadedSuspectName = result.suspect_name || inputSuspectName;
                resultsDiv.innerHTML += `
                    <div style="margin-bottom: 1rem; padding: 1.5rem; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; color: #10b981;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                            <span style="font-size: 1.5rem;">✓</span>
                            <strong style="font-size: 1.1rem;">Upload Successful!</strong>
                        </div>
                        <div style="margin-bottom: 0.5rem;">
                            <strong>${file.name}</strong>: ${result.message}
                            ${result.format_detected ? `<br><small>Format: ${result.format_detected.vendor || 'Unknown'}</small>` : ''}
                        </div>
                        ${uploadedSuspectName ? `
                            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(16, 185, 129, 0.2);">
                                <p style="margin-bottom: 0.75rem; color: rgba(255, 255, 255, 0.9);">Ready to analyze data for <strong>${uploadedSuspectName}</strong></p>
                                <button class="btn btn-primary" onclick="goToAnalysis('${uploadedSuspectName}')" style="margin-right: 0.5rem;">
                                    Analyze ${uploadedSuspectName}
                                </button>
                                <button class="btn btn-secondary" onclick="navigateToSingleAnalysis()">
                                    View All Analysis
                                </button>
                            </div>
                        ` : `
                            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(16, 185, 129, 0.2);">
                                <p style="margin-bottom: 0.75rem; color: rgba(255, 255, 255, 0.9);">Next steps:</p>
                                <button class="btn btn-primary" onclick="navigateToSingleAnalysis()">
                                    Go to Analysis
                                </button>
                            </div>
                        `}
                    </div>
                `;
            } else {
                resultsDiv.innerHTML += `<div style="color: #ef4444;">Error processing ${file.name}: ${result.message || result.detail || 'Unknown error'}</div>`;
            }
        } catch (error) {
            console.error('Upload error:', error);
            resultsDiv.innerHTML += `<div style="color: #ef4444; padding: 1rem; background: rgba(239, 68, 68, 0.1); border-radius: 8px; margin-bottom: 0.5rem;">
                <strong>Error uploading ${file.name}</strong><br>
                ${error.message || 'Unknown error occurred. Check browser console for details.'}
            </div>`;
        }
    }

    progressText.textContent = 'Complete!';
    setTimeout(() => {
        progressDiv.style.display = 'none';
        loadSuspects();
    }, 2000);
}

// Navigate to single analysis view
function navigateToSingleAnalysis() {
    const navItem = document.querySelector('[data-view="single-analysis"]');
    if (navItem) {
        navItem.click();
    }
}

// Navigate to analysis with suspect pre-selected
function goToAnalysis(suspectName) {
    // Switch to single analysis view
    navigateToSingleAnalysis();

    // Wait for view to load, then select suspect and analyze
    setTimeout(() => {
        const select = document.getElementById('singleSuspectSelect');
        if (select) {
            select.value = suspectName;
            // Wait a bit more for suspects to load
            setTimeout(() => {
                loadSingleAnalysis();
            }, 500);
        } else {
            console.error('Single suspect select not found');
        }
    }, 500);
}

// Load Suspects
async function loadSuspects() {
    try {
        const response = await fetch(`${API_BASE}/suspects`);
        const data = await response.json();

        if (data.success) {
            const suspects = data.suspects || [];

            // Update suspects list
            const suspectsList = document.getElementById('suspectsList');
            suspectsList.innerHTML = suspects.map(suspect => `
                <div class="suspect-card" onclick="selectSuspect('${suspect}')">
                    <strong>${suspect}</strong>
                </div>
            `).join('');

            // Update select dropdowns
            const selects = ['singleSuspectSelect', 'exportSuspectSelect', 'geofenceSuspect'];
            selects.forEach(selectId => {
                const select = document.getElementById(selectId);
                if (select) {
                    const currentValue = select.value;
                    select.innerHTML = '<option value="">-- Select Suspect --</option>' +
                        suspects.map(s => `<option value="${s}" ${s === currentValue ? 'selected' : ''}>${s}</option>`).join('');
                }
            });

            // Update multi-select
            const multiSelect = document.getElementById('multipleSuspectSelect');
            if (multiSelect) {
                multiSelect.innerHTML = suspects.map(suspect => `
                    <div class="multi-select-item" onclick="toggleSuspectSelection(this, '${suspect}')">
                        <input type="checkbox" id="suspect_${suspect}" value="${suspect}">
                        <label for="suspect_${suspect}">${suspect}</label>
                    </div>
                `).join('');
            }
        }
    } catch (error) {
        console.error('Error loading suspects:', error);
    }
}

function selectSuspect(suspect) {
    document.getElementById('singleSuspectSelect').value = suspect;
    loadSingleAnalysis();
}

let selectedSuspects = [];

function toggleSuspectSelection(element, suspect) {
    const checkbox = element.querySelector('input[type="checkbox"]');
    checkbox.checked = !checkbox.checked;

    if (checkbox.checked) {
        element.classList.add('selected');
        if (!selectedSuspects.includes(suspect)) {
            selectedSuspects.push(suspect);
        }
    } else {
        element.classList.remove('selected');
        selectedSuspects = selectedSuspects.filter(s => s !== suspect);
    }
}

// Tabs
function setupTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;

            // Update active tab button
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Show corresponding tab content
            const tabContents = btn.closest('.view').querySelectorAll('.tab-content');
            tabContents.forEach(content => content.classList.remove('active'));

            const targetTab = document.getElementById(`${tabName}Tab`);
            if (targetTab) {
                targetTab.classList.add('active');
            }
        });
    });
}

// Single Analysis
async function loadSingleAnalysis() {
    const suspect = document.getElementById('singleSuspectSelect').value;
    if (!suspect) {
        alert('Please select a suspect');
        return;
    }

    // Load all analyses
    loadImeiAnalysis(suspect);
    loadTowerAnalysis(suspect);
    loadContactAnalysis(suspect);
    loadSmsAnalysis(suspect);
    loadInternationalAnalysis(suspect);
}

async function loadImeiAnalysis(suspect) {
    try {
        const response = await fetch(`${API_BASE}/analytics/single/imei?suspect_name=${encodeURIComponent(suspect)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('imeiContent');
            const imeis = data.data.imeis || [];

            // Create usage chart
            const usageChart = {
                x: imeis.map(i => i.imei.substring(0, 12) + '...'),
                y: imeis.map(i => i.usage_count),
                type: 'bar',
                marker: { color: 'rgb(99, 102, 241)' },
                name: 'Usage Count'
            };

            const timelineChart = {
                x: imeis.map(i => i.imei.substring(0, 12) + '...'),
                y: imeis.map(i => i.timeline.duration_days || 0),
                type: 'bar',
                marker: { color: 'rgb(236, 72, 153)' },
                name: 'Days Active'
            };

            content.innerHTML = `
                <div class="stats-grid" style="margin-bottom: 2rem;">
                    <div class="stat-card">
                        <div class="stat-value">${data.data.unique_imeis}</div>
                        <div class="stat-label">Unique IMEIs</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${imeis.reduce((sum, i) => sum + (i.usage_count || 0), 0)}</div>
                        <div class="stat-label">Total Usage</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${Math.max(...imeis.map(i => i.timeline.duration_days || 0), 0)}</div>
                        <div class="stat-label">Max Days Active</div>
                    </div>
                </div>

                <h4 style="margin-bottom: 1rem;">IMEI Usage Distribution</h4>
                <div id="imeiUsageChart" style="height: 400px; margin-bottom: 2rem;"></div>

                <h4 style="margin-bottom: 1rem;">Device Activity Timeline</h4>
                <div id="imeiTimelineChart" style="height: 400px; margin-bottom: 2rem;"></div>

                <h4 style="margin-bottom: 1rem;">Device Details</h4>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>IMEI</th>
                            <th>Device Info</th>
                            <th>Usage Count</th>
                            <th>First Seen</th>
                            <th>Last Seen</th>
                            <th>Duration (Days)</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${imeis.map(imei => `
                            <tr>
                                <td><code>${imei.imei}</code></td>
                                <td>TAC: ${imei.device_info.tac || 'N/A'}</td>
                                <td>${imei.usage_count}</td>
                                <td>${new Date(imei.first_seen).toLocaleString()}</td>
                                <td>${new Date(imei.last_seen).toLocaleString()}</td>
                                <td>${imei.timeline.duration_days}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;

            // Render charts
            if (imeis.length > 0) {
                Plotly.newPlot('imeiUsageChart', [usageChart], {
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    font: { color: '#ffffff' },
                    xaxis: { title: 'IMEI' },
                    yaxis: { title: 'Usage Count' }
                }, {responsive: true});

                Plotly.newPlot('imeiTimelineChart', [timelineChart], {
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    font: { color: '#ffffff' },
                    xaxis: { title: 'IMEI' },
                    yaxis: { title: 'Days Active' }
                }, {responsive: true});
            }
        }
    } catch (error) {
        console.error('Error loading IMEI analysis:', error);
        const content = document.getElementById('imeiContent');
        content.innerHTML = `<div style="color: #ef4444; padding: 1rem;">Error loading IMEI analysis: ${error.message}</div>`;
    }
}

async function loadTowerAnalysis(suspect) {
    try {
        // Get date filters if set
        const startDate = document.getElementById('towerStartDate')?.value || '';
        const endDate = document.getElementById('towerEndDate')?.value || '';

        let url = `${API_BASE}/analytics/single/cell-towers?suspect_name=${encodeURIComponent(suspect)}`;
        if (startDate) url += `&start_date=${encodeURIComponent(startDate)}`;
        if (endDate) url += `&end_date=${encodeURIComponent(endDate)}`;

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            const towers = data.data.towers || [];

            // Initialize map
            const mapContainer = document.getElementById('towerMap');
            mapContainer.innerHTML = '';

            if (towers.length > 0) {
                // Calculate center from all towers
                const validTowers = towers.filter(t => t.location && t.location.lat && t.location.lon);
                if (validTowers.length === 0) {
                    mapContainer.innerHTML = '<div style="padding: 2rem; color: #ef4444;">No towers with location data found</div>';
                    return;
                }

                const avgLat = validTowers.reduce((sum, t) => sum + t.location.lat, 0) / validTowers.length;
                const avgLon = validTowers.reduce((sum, t) => sum + t.location.lon, 0) / validTowers.length;
                const center = [avgLon, avgLat];

                const map = new maplibregl.Map({
                    container: 'towerMap',
                    style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
                    center: center,
                    zoom: 12
                });

                map.on('load', () => {
                    towers.forEach((tower, index) => {
                        if (tower.location && tower.location.lat && tower.location.lon) {
                            const el = document.createElement('div');
                            el.className = 'marker';
                            el.style.width = '20px';
                            el.style.height = '20px';
                            el.style.borderRadius = '50%';
                            el.style.background = `hsl(${index * 60}, 70%, 50%)`;
                            el.style.border = '2px solid white';
                            el.style.cursor = 'pointer';

                            const firstSeen = tower.first_seen ? new Date(tower.first_seen).toLocaleString() : 'N/A';
                            const lastSeen = tower.last_seen ? new Date(tower.last_seen).toLocaleString() : 'N/A';

                            new maplibregl.Marker(el)
                                .setLngLat([tower.location.lon, tower.location.lat])
                                .setPopup(new maplibregl.Popup().setHTML(`
                                    <strong>Tower ${tower.tower_id}</strong><br>
                                    Usage: ${tower.usage_count} calls<br>
                                    First seen: ${firstSeen}<br>
                                    Last seen: ${lastSeen}
                                `))
                                .addTo(map);
                        }
                    });
                });
            } else {
                mapContainer.innerHTML = '<div style="padding: 2rem; color: #ef4444;">No tower data found</div>';
            }
        }
    } catch (error) {
        console.error('Error loading tower analysis:', error);
        const mapContainer = document.getElementById('towerMap');
        mapContainer.innerHTML = `<div style="padding: 2rem; color: #ef4444;">Error loading tower analysis: ${error.message}</div>`;
    }
}

async function loadContactAnalysis(suspect) {
    try {
        const response = await fetch(`${API_BASE}/analytics/single/contacts?suspect_name=${encodeURIComponent(suspect)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('contactsContent');
            const mostCalled = data.data.most_called || [];
            const mostDurationCalled = data.data.most_duration_called || [];
            const longestCalls = data.data.longest_calls || [];

            // Create charts
            const top10Called = mostCalled.slice(0, 10);
            const callCountChart = {
                x: top10Called.map(c => c.number.substring(0, 15) + '...'),
                y: top10Called.map(c => c.call_count),
                type: 'bar',
                marker: { color: 'rgb(99, 102, 241)' },
                name: 'Call Count'
            };

            const durationChart = {
                x: top10Called.map(c => c.number.substring(0, 15) + '...'),
                y: top10Called.map(c => Math.round((c.total_duration_seconds || 0) / 60)),
                type: 'bar',
                marker: { color: 'rgb(236, 72, 153)' },
                name: 'Duration (minutes)'
            };

            content.innerHTML = `
                <div class="stats-grid" style="margin-bottom: 2rem;">
                    <div class="stat-card">
                        <div class="stat-value">${mostCalled.length}</div>
                        <div class="stat-label">Unique Contacts</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${mostCalled.reduce((sum, c) => sum + (c.call_count || 0), 0)}</div>
                        <div class="stat-label">Total Calls</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${Math.round(mostCalled.reduce((sum, c) => sum + ((c.total_duration_seconds || 0) / 3600), 0))}</div>
                        <div class="stat-label">Total Hours</div>
                    </div>
                </div>

                <h4 style="margin-bottom: 1rem;">Top 10 Most Called Numbers</h4>
                <div id="callCountChart" style="height: 400px; margin-bottom: 2rem;"></div>

                <h4 style="margin-bottom: 1rem;">Call Duration by Contact (Minutes)</h4>
                <div id="durationChart" style="height: 400px; margin-bottom: 2rem;"></div>

                <h4 style="margin-bottom: 1rem;">Detailed Contact List</h4>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Number</th>
                            <th>Call Count</th>
                            <th>Total Duration (hours)</th>
                            <th>Avg Duration (min)</th>
                            <th>First Contact</th>
                            <th>Last Contact</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${mostCalled.slice(0, 20).map(contact => {
                            const totalHours = (contact.total_duration_seconds || 0) / 3600;
                            const avgMin = contact.call_count > 0 ? ((contact.total_duration_seconds || 0) / 60) / contact.call_count : 0;
                            const firstContact = contact.first_contact ? new Date(contact.first_contact).toLocaleString() : 'N/A';
                            const lastContact = contact.last_contact ? new Date(contact.last_contact).toLocaleString() : 'N/A';
                            return `
                                <tr>
                                    <td><code>${contact.number}</code></td>
                                    <td>${contact.call_count}</td>
                                    <td>${totalHours.toFixed(2)}</td>
                                    <td>${avgMin.toFixed(1)}</td>
                                    <td>${firstContact}</td>
                                    <td>${lastContact}</td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>

                <h4 style="margin-top: 2rem; margin-bottom: 1rem;">Most Duration Called Numbers</h4>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Number</th>
                            <th>Total Duration (hours)</th>
                            <th>Call Count</th>
                            <th>First Contact</th>
                            <th>Last Contact</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${mostDurationCalled.slice(0, 20).map(contact => {
                            const totalHours = (contact.total_duration_seconds || 0) / 3600;
                            const firstContact = contact.first_contact ? new Date(contact.first_contact).toLocaleString() : 'N/A';
                            const lastContact = contact.last_contact ? new Date(contact.last_contact).toLocaleString() : 'N/A';
                            return `
                                <tr>
                                    <td><code>${contact.number}</code></td>
                                    <td>${totalHours.toFixed(2)}</td>
                                    <td>${contact.call_count}</td>
                                    <td>${firstContact}</td>
                                    <td>${lastContact}</td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>

                <h4 style="margin-top: 2rem; margin-bottom: 1rem;">Longest Duration Calls</h4>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Number</th>
                            <th>Duration (min)</th>
                            <th>Timestamp</th>
                            <th>Type</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${longestCalls.map(call => `
                            <tr>
                                <td><code>${call.called_number || call.calling_number}</code></td>
                                <td>${((call.duration_seconds || 0) / 60).toFixed(1)}</td>
                                <td>${new Date(call.call_start_time).toLocaleString()}</td>
                                <td>${call.call_type}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;

            // Render charts
            Plotly.newPlot('callCountChart', [callCountChart], {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#ffffff' },
                xaxis: { title: 'Phone Number' },
                yaxis: { title: 'Number of Calls' }
            }, {responsive: true});

            Plotly.newPlot('durationChart', [durationChart], {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#ffffff' },
                xaxis: { title: 'Phone Number' },
                yaxis: { title: 'Duration (Minutes)' }
            }, {responsive: true});
        }
    } catch (error) {
        console.error('Error loading contact analysis:', error);
        const content = document.getElementById('contactsContent');
        content.innerHTML = `<div style="color: #ef4444; padding: 1rem;">Error loading contact analysis: ${error.message}</div>`;
    }
}

async function loadSmsAnalysis(suspect) {
    try {
        const response = await fetch(`${API_BASE}/analytics/single/sms-services?suspect_name=${encodeURIComponent(suspect)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('smsContent');
            const services = data.data.services_detected || {};

            content.innerHTML = `
                <div class="stats-grid">
                    ${Object.entries(services).map(([service, info]) => `
                        <div class="stat-card">
                            <div class="stat-value">${info.count}</div>
                            <div class="stat-label">${service} Messages</div>
                        </div>
                    `).join('')}
                </div>
                ${Object.entries(services).map(([service, info]) => `
                    <div style="margin-bottom: 2rem;">
                        <h4>${service} (${info.count} messages)</h4>
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Timestamp</th>
                                    <th>Number</th>
                                    <th>Content Preview</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${info.detections.slice(0, 10).map(detection => `
                                    <tr>
                                        <td>${new Date(detection.timestamp).toLocaleString()}</td>
                                        <td><code>${detection.called_number}</code></td>
                                        <td>${detection.sms_content || 'N/A'}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `).join('')}
            `;
        }
    } catch (error) {
        console.error('Error loading SMS analysis:', error);
    }
}

async function loadInternationalAnalysis(suspect) {
    try {
        const response = await fetch(`${API_BASE}/analytics/single/international?suspect_name=${encodeURIComponent(suspect)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('internationalContent');
            const countries = data.data.countries || {};

            const countryData = Object.entries(countries).map(([country, stats]) => ({
                country,
                count: stats.call_count,
                duration: stats.total_duration_seconds
            }));

            // Create chart
            const chartData = [{
                x: countryData.map(d => d.country),
                y: countryData.map(d => d.count),
                type: 'bar',
                marker: {
                    color: 'rgb(99, 102, 241)'
                }
            }];

            const chartLayout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#ffffff' },
                xaxis: { title: 'Country' },
                yaxis: { title: 'Call Count' }
            };

            content.innerHTML = '<div id="internationalChart" style="height: 400px;"></div>';
            Plotly.newPlot('internationalChart', chartData, chartLayout, {responsive: true});

            // Add table
            content.innerHTML += `
                <table class="data-table" style="margin-top: 2rem;">
                    <thead>
                        <tr>
                            <th>Country</th>
                            <th>Call Count</th>
                            <th>Total Duration (sec)</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${Object.entries(countries).map(([country, stats]) => `
                            <tr>
                                <td>${country}</td>
                                <td>${stats.call_count}</td>
                                <td>${Math.round(stats.total_duration_seconds)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
    } catch (error) {
        console.error('Error loading international analysis:', error);
    }
}

// Multiple Analysis
async function loadMultipleAnalysis() {
    if (selectedSuspects.length < 2) {
        alert('Please select at least 2 suspects');
        return;
    }

    loadCommonNumbers(selectedSuspects);
    loadCommonTowers(selectedSuspects);
    loadCommonImei(selectedSuspects);
}

async function loadCommonNumbers(suspects) {
    try {
        const query = suspects.map(s => `suspect_names=${encodeURIComponent(s)}`).join('&');
        const response = await fetch(`${API_BASE}/analytics/multiple/common-numbers?${query}`);
        const data = await response.json();

        if (data.success) {
            const network = data.data.network || { nodes: [], edges: [] };
            const detailedNumbers = data.data.detailed_numbers || [];

            const container = document.getElementById('networkGraph');
            container.innerHTML = '';

            const nodes = new vis.DataSet(network.nodes);
            const edges = new vis.DataSet(network.edges);

            const networkData = { nodes, edges };
            const options = {
                nodes: {
                    shape: 'dot',
                    size: 20,
                    font: { color: '#ffffff', size: 14 },
                    borderWidth: 2
                },
                edges: {
                    width: 2,
                    color: { color: '#6366f1' },
                    arrows: { to: { enabled: true } },
                    labelHighlightBold: true
                },
                physics: {
                    enabled: true,
                    stabilization: { iterations: 200 }
                },
                interaction: {
                    tooltipDelay: 200,
                    hover: true
                }
            };

            const networkInstance = new vis.Network(container, networkData, options);

            // Add detailed table below graph
            const tableContainer = document.createElement('div');
            tableContainer.style.marginTop = '2rem';
            tableContainer.innerHTML = `
                <h4 style="margin-bottom: 1rem;">Common Numbers Details</h4>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Number</th>
                            <th>Total Calls</th>
                            <th>Total Duration (hours)</th>
                            <th>First Contact</th>
                            <th>Last Contact</th>
                            <th>Shared By</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${detailedNumbers.slice(0, 20).map(num => {
                            const totalHours = (num.total_duration_seconds || 0) / 3600;
                            const firstContact = num.first_contact ? new Date(num.first_contact).toLocaleString() : 'N/A';
                            const lastContact = num.last_contact ? new Date(num.last_contact).toLocaleString() : 'N/A';
                            const sharedBy = num.suspects.map(s => s.name).join(', ');
                            return `
                                <tr>
                                    <td><code>${num.number}</code></td>
                                    <td>${num.total_calls}</td>
                                    <td>${totalHours.toFixed(2)}</td>
                                    <td>${firstContact}</td>
                                    <td>${lastContact}</td>
                                    <td>${sharedBy}</td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            `;
            container.parentElement.appendChild(tableContainer);
        }
    } catch (error) {
        console.error('Error loading common numbers:', error);
    }
}

async function loadCommonTowers(suspects) {
    try {
        const query = suspects.map(s => `suspect_names=${encodeURIComponent(s)}`).join('&');
        const response = await fetch(`${API_BASE}/analytics/multiple/common-towers?${query}`);
        const data = await response.json();

        if (data.success) {
            const allTowers = data.data.all_towers || [];
            const coLocations = data.data.co_locations || [];
            const suspectColors = data.data.suspect_colors || {};

            const mapContainer = document.getElementById('towersMap');
            mapContainer.innerHTML = '';

            if (allTowers.length > 0) {
                // Calculate center from all towers
                const validTowers = allTowers.filter(t => t.location && t.location.lat && t.location.lon);
                if (validTowers.length === 0) {
                    mapContainer.innerHTML = '<div style="padding: 2rem; color: #ef4444;">No towers with location data found</div>';
                    return;
                }

                const avgLat = validTowers.reduce((sum, t) => sum + t.location.lat, 0) / validTowers.length;
                const avgLon = validTowers.reduce((sum, t) => sum + t.location.lon, 0) / validTowers.length;
                const center = [avgLon, avgLat];

                const map = new maplibregl.Map({
                    container: 'towersMap',
                    style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
                    center: center,
                    zoom: 12
                });

                map.on('load', () => {
                    // Add legend
                    const legend = document.createElement('div');
                    legend.style.position = 'absolute';
                    legend.style.top = '10px';
                    legend.style.right = '10px';
                    legend.style.background = 'rgba(0, 0, 0, 0.8)';
                    legend.style.padding = '1rem';
                    legend.style.borderRadius = '8px';
                    legend.style.color = '#ffffff';
                    legend.style.zIndex = '1000';
                    legend.innerHTML = `
                        <h4 style="margin: 0 0 0.5rem 0; font-size: 0.9rem;">Suspects</h4>
                        ${Object.entries(suspectColors).map(([name, color]) => `
                            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
                                <div style="width: 16px; height: 16px; border-radius: 50%; background: ${color}; border: 2px solid white;"></div>
                                <span style="font-size: 0.85rem;">${name}</span>
                            </div>
                        `).join('')}
                        ${coLocations.length > 0 ? `
                            <div style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.2);">
                                <div style="display: flex; align-items: center; gap: 0.5rem;">
                                    <div style="width: 16px; height: 16px; border-radius: 50%; background: #10b981; border: 3px solid white;"></div>
                                    <span style="font-size: 0.85rem;">Shared Locations</span>
                                </div>
                            </div>
                        ` : ''}
                    `;
                    mapContainer.appendChild(legend);

                    // Plot all towers with suspect colors
                    allTowers.forEach((tower) => {
                        if (tower.location && tower.location.lat && tower.location.lon) {
                            const color = tower.color || suspectColors[tower.suspect] || '#6366f1';
                            const isShared = tower.is_shared;

                            const el = document.createElement('div');
                            el.className = 'marker';
                            el.style.width = isShared ? '28px' : '20px';
                            el.style.height = isShared ? '28px' : '20px';
                            el.style.borderRadius = '50%';
                            el.style.background = color;
                            el.style.border = isShared ? '4px solid #10b981' : '2px solid white';
                            el.style.cursor = 'pointer';
                            el.style.boxShadow = isShared ? '0 0 10px rgba(16, 185, 129, 0.8)' : 'none';

                            const sharedInfo = isShared ? `<br><strong style="color: #10b981;">Shared Location!</strong><br>Shared by: ${tower.shared_with.join(', ')}` : '';
                            const firstSeen = tower.first_seen ? new Date(tower.first_seen).toLocaleString() : 'N/A';
                            const lastSeen = tower.last_seen ? new Date(tower.last_seen).toLocaleString() : 'N/A';

                            new maplibregl.Marker(el)
                                .setLngLat([tower.location.lon, tower.location.lat])
                                .setPopup(new maplibregl.Popup().setHTML(`
                                    <strong>Tower ${tower.tower_id}</strong><br>
                                    Suspect: ${tower.suspect}<br>
                                    Usage: ${tower.suspect_usage || tower.total_usage} calls${sharedInfo}<br>
                                    First seen: ${firstSeen}<br>
                                    Last seen: ${lastSeen}
                                `))
                                .addTo(map);
                        }
                    });
                });
            } else {
                mapContainer.innerHTML = '<div style="padding: 2rem; color: #ef4444;">No tower data found</div>';
            }
        }
    } catch (error) {
        console.error('Error loading common towers:', error);
    }
}

async function loadCommonImei(suspects) {
    try {
        const query = suspects.map(s => `suspect_names=${encodeURIComponent(s)}`).join('&');
        const response = await fetch(`${API_BASE}/analytics/multiple/common-imei?${query}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('commonImeiContent');
            const devices = data.data.common_devices || [];

            content.innerHTML = `
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">${data.data.common_devices_count}</div>
                        <div class="stat-label">Shared Devices</div>
                    </div>
                </div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>IMEI</th>
                            <th>Device Info</th>
                            <th>Shared By</th>
                            <th>Total Usage</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${devices.map(device => `
                            <tr>
                                <td><code>${device.imei}</code></td>
                                <td>TAC: ${device.device_info.tac || 'N/A'}</td>
                                <td>${device.shared_by.map(s => s.name).join(', ')}</td>
                                <td>${device.total_usage}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
    } catch (error) {
        console.error('Error loading common IMEI:', error);
    }
}

// Utilities
async function generateSampleData() {
    const suspectName = document.getElementById('sampleSuspectName').value;
    const recordCount = parseInt(document.getElementById('sampleRecordCount').value) || 100;

    if (!suspectName) {
        alert('Please enter a suspect name');
        return;
    }

    const resultDiv = document.getElementById('sampleDataResult');
    resultDiv.innerHTML = '<div class="loading"></div> Generating...';

    try {
        const response = await fetch(`${API_BASE}/utils/generate-sample?suspect_name=${encodeURIComponent(suspectName)}&record_count=${recordCount}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            resultDiv.innerHTML = `<div style="color: #10b981;">✓ Generated ${data.records_generated} sample records for ${suspectName}</div>`;
            loadSuspects();
        } else {
            resultDiv.innerHTML = `<div style="color: #ef4444;">Error: ${data.message || 'Unknown error'}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div style="color: #ef4444;">Error: ${error.message}</div>`;
    }
}

async function exportData(format = 'json') {
    const suspect = document.getElementById('exportSuspectSelect').value;

    if (!suspect) {
        alert('Please select a suspect');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/export/${encodeURIComponent(suspect)}?format=${format}`);
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const extension = format === 'csv' ? 'csv' : 'json';
        a.download = `${suspect}_cdr_export.${extension}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        alert(`Error exporting data: ${error.message}`);
    }
}

async function exportPDF() {
    const suspect = document.getElementById('exportSuspectSelect').value;

    if (!suspect) {
        alert('Please select a suspect');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/export-pdf/${encodeURIComponent(suspect)}`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate PDF');
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${suspect}_cdr_report.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        alert(`Error generating PDF: ${error.message}`);
    }
}

// Geofencing
function setupGeofencing() {
    geofenceMap = new maplibregl.Map({
        container: 'geofenceMap',
        style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
        center: [0, 0],
        zoom: 2
    });

    draw = new MapboxDraw({
        displayControlsDefault: false,
        controls: {
            polygon: true,
            trash: true
        }
    });
    geofenceMap.addControl(draw);

    geofenceMap.on('load', () => {
        loadGeofences();
    });
}

async function loadGeofences() {
    try {
        const response = await fetch(`${API_BASE}/geofences`);
        const geofences = await response.json();
        const geofenceList = document.getElementById('geofenceList');
        geofenceList.innerHTML = '';

        geofences.forEach(geofence => {
            draw.add(geofence.geometry);
            const item = document.createElement('div');
            item.className = 'geofence-item';
            item.innerHTML = `
                <span>${geofence.name}</span>
                <button onclick="deleteGeofence('${geofence._id}')">Delete</button>
            `;
            geofenceList.appendChild(item);
        });
    } catch (error) {
        console.error('Error loading geofences:', error);
    }
}

async function saveGeofence() {
    const name = document.getElementById('geofenceName').value;
    const description = document.getElementById('geofenceDescription').value;
    const suspect = document.getElementById('geofenceSuspect').value;
    const data = draw.getAll();

    if (data.features.length > 0) {
        const geofence = {
            name,
            description,
            suspect_name: suspect,
            geometry: data.features[0].geometry
        };

        try {
            await fetch(`${API_BASE}/geofences`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(geofence)
            });
            draw.deleteAll();
            loadGeofences();
        } catch (error) {
            console.error('Error saving geofence:', error);
        }
    }
}

async function deleteGeofence(id) {
    try {
        await fetch(`${API_BASE}/geofences/${id}`, {
            method: 'DELETE'
        });
        loadGeofences();
    } catch (error) {
        console.error('Error deleting geofence:', error);
    }
}

function setupWebSocket() {
    const socket = new WebSocket('ws://localhost:8000/ws/geofence-alerts');

    socket.onmessage = function(event) {
        const alert = JSON.parse(event.data);
        const alertsDiv = document.getElementById('geofenceAlerts');
        const alertEl = document.createElement('div');
        alertEl.className = 'alert';
        alertEl.innerHTML = `
            <strong>Geofence Breach:</strong> ${alert.suspect_name} entered ${alert.geofence_name} at ${new Date(alert.timestamp).toLocaleString()}
        `;
        alertsDiv.appendChild(alertEl);
    };
}
