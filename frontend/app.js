// Use relative URLs - works for both local and production
const API_BASE = '/api';

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
    setupGeofencing();
    setupWebSocket();
}

// Connection Status
async function checkConnection() {
    try {
        const response = await fetch('/health');
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

            // Auto-load analysis if session exists
            if (viewName === 'single-analysis' && window.currentSessionId) {
                showAnalysisResults(window.currentSessionId);
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
            // Convert FileList to Array for consistent handling
            const filesArray = Array.from(files);
            handleFiles(filesArray);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            const files = Array.from(e.target.files); // Create a copy of the file list
            // Reset the input so the same file can be selected again
            e.target.value = '';
            handleFiles(files);
        }
    });
}

async function handleFiles(files) {
    console.log('Handling files:', files.length);

    const progressDiv = document.getElementById('uploadProgress');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const resultsDiv = document.getElementById('uploadResults');
    const fileInput = document.getElementById('fileInput');

    if (!progressDiv || !progressFill || !progressText || !resultsDiv) {
        console.error('Upload UI elements not found');
        return;
    }

    // Reset file input to allow selecting the same file again
    if (fileInput) {
        fileInput.value = '';
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

        const autoDetect = document.getElementById('autoDetect').checked;

        try {
            const response = await fetch(`${API_BASE}/upload?auto_detect=${autoDetect}`, {
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
                const sessionId = result.session_id;
                resultsDiv.innerHTML += `
                    <div style="margin-bottom: 1rem; padding: 1.5rem; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; color: #10b981;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                            <span style="font-size: 1.5rem;">✓</span>
                            <strong style="font-size: 1.1rem;">Upload & Analysis Complete!</strong>
                        </div>
                        <div style="margin-bottom: 0.5rem;">
                            <strong>${file.name}</strong>: ${result.message}
                            ${result.format_detected ? `<br><small>Format: ${result.format_detected.vendor || 'Unknown'}</small>` : ''}
                        </div>
                            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(16, 185, 129, 0.2);">
                            <p style="margin-bottom: 0.75rem; color: rgba(255, 255, 255, 0.9);">Analysis results are ready!</p>
                            <button class="btn btn-primary" onclick="showAnalysisResults('${sessionId}')" style="margin-right: 0.5rem;">
                                View Analysis Results
                                </button>
                            <button class="btn btn-secondary" onclick="exportCurrentSession('${sessionId}', 'excel')">
                                Export to Excel
                                </button>
                            </div>
                    </div>
                `;

                // Store session_id for later use
                window.currentSessionId = sessionId;

                // Auto-navigate to analysis view and load results
                setTimeout(() => {
                    navigateToSingleAnalysis();
                    showAnalysisResults(sessionId);
                }, 1000);
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
    }, 2000);
}

// Navigate to analysis view
function navigateToSingleAnalysis() {
    const navItem = document.querySelector('[data-view="single-analysis"]');
    if (navItem) {
        navItem.click();
    }
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

            // Update active tab button (only within the same view)
            const view = btn.closest('.view');
            if (view) {
                view.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Show corresponding tab content
                view.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

                // Handle kebab-case to camelCase conversion for tab IDs
                // Special cases: max-call -> maxCall, max-circle-call -> maxCircleCall, etc.
                let tabId;
                if (tabName.includes('-')) {
                    const parts = tabName.split('-');
                    tabId = parts[0] + parts.slice(1).map(word =>
                        word.charAt(0).toUpperCase() + word.slice(1)
                    ).join('') + 'Tab';
                } else {
                    tabId = tabName + 'Tab';
                }

                const targetTab = document.getElementById(tabId);
            if (targetTab) {
                targetTab.classList.add('active');
                } else {
                    console.warn(`Tab content not found: ${tabId} (from tab: ${tabName})`);
                }
            }
        });
    });
}

// Show analysis results for current session
async function showAnalysisResults(sessionId) {
    if (!sessionId) {
        sessionId = window.currentSessionId;
    }

    if (!sessionId) {
        alert('No analysis data available. Please upload a file first.');
        return;
    }

    // Load comprehensive analytics
    loadSummary(sessionId);
    loadCorrected(sessionId);
    loadMaxCall(sessionId);
    loadMaxCircleCall(sessionId);
    loadDailyFirstLast(sessionId);
    loadMaxDuration(sessionId);
    loadMaxIMEI(sessionId);
    loadDailyIMEITracking(sessionId);
    loadMaxLocation(sessionId);
    loadDailyFirstLastLocation(sessionId);
}

// Single Analysis (legacy - kept for compatibility)
async function loadSingleAnalysis() {
    const sessionId = window.currentSessionId;
    if (!sessionId) {
        alert('No data available. Please upload a file first.');
        return;
    }
    showAnalysisResults(sessionId);
}

// Comprehensive Analytics Functions
async function loadSummary(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/summary?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('summaryContent');
            const summary = data.data;

            content.innerHTML = `
                <div style="margin-bottom: 2rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    <button class="btn btn-primary" onclick="exportCurrentSession('${sessionId}', 'excel')" style="background: linear-gradient(135deg, #10b981, #059669);">
                        📊 Export to Excel (All Sheets)
                    </button>
                    <button class="btn btn-primary" onclick="exportCurrentSessionPDF('${sessionId}')" style="background: linear-gradient(135deg, #ec4899, #8b5cf6);">
                        📄 Export to PDF (All Results)
                    </button>
                </div>
                <div class="stats-grid" style="margin-bottom: 2rem;">
                    <div class="stat-card">
                        <div class="stat-value">${summary.total_calls || 0}</div>
                        <div class="stat-label">Total Calls</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${summary.incoming_count || 0}</div>
                        <div class="stat-label">Incoming Calls</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${summary.outgoing_count || 0}</div>
                        <div class="stat-label">Outgoing Calls</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${summary.unique_b_numbers || 0}</div>
                        <div class="stat-label">Unique B-Numbers</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${summary.unique_imeis || 0}</div>
                        <div class="stat-label">Unique IMEIs</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${summary.unique_locations || 0}</div>
                        <div class="stat-label">Unique Locations</div>
                    </div>
                </div>
                <div style="overflow-x: auto; -webkit-overflow-scrolling: touch;">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Metric</th>
                                <th>Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr><td>First Activity Date</td><td>${summary.first_activity_date || 'N/A'}</td></tr>
                            <tr><td>Last Activity Date</td><td>${summary.last_activity_date || 'N/A'}</td></tr>
                        </tbody>
                    </table>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading summary:', error);
    }
}

async function loadCorrected(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/corrected?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('correctedContent');
            const records = data.data || [];

            if (records.length === 0) {
                content.innerHTML = '<p>No corrected records found</p>';
                return;
            }

            content.innerHTML = `
                <p style="margin-bottom: 1rem;">Total Corrected Records: ${records.length}</p>
                <div class="table-container" style="border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px;">
                    <table class="data-table" style="min-width: 1200px; white-space: nowrap;">
                        <thead>
                            <tr>
                                <th style="min-width: 120px;">Record ID</th>
                                <th style="min-width: 120px;">MSISDN A</th>
                                <th style="min-width: 120px;">MSISDN B</th>
                                <th style="min-width: 100px;">Call Type</th>
                                <th style="min-width: 120px;">Call Date</th>
                                <th style="min-width: 150px;">Call Start Time</th>
                                <th style="min-width: 100px;">Duration (sec)</th>
                                <th style="min-width: 150px;">IMEI</th>
                                <th style="min-width: 100px;">Cell ID</th>
                                <th style="min-width: 100px;">Operator</th>
                                <th style="min-width: 100px;">Circle</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${records.slice(0, 100).map(record => `
                                <tr>
                                    <td style="white-space: nowrap;"><code>${record.record_id || ''}</code></td>
                                    <td style="white-space: nowrap;"><code>${record.msisdn_a || ''}</code></td>
                                    <td style="white-space: nowrap;"><code>${record.msisdn_b || ''}</code></td>
                                    <td style="white-space: nowrap;">${record.call_type || ''}</td>
                                    <td style="white-space: nowrap;">${record.call_date || ''}</td>
                                    <td style="white-space: nowrap;">${record.call_start_time || ''}</td>
                                    <td style="white-space: nowrap;">${record.call_duration_sec || 0}</td>
                                    <td style="white-space: nowrap;"><code>${record.imei || ''}</code></td>
                                    <td style="white-space: nowrap;">${record.cell_id || ''}</td>
                                    <td style="white-space: nowrap;">${record.operator || ''}</td>
                                    <td style="white-space: nowrap;">${record.circle || ''}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
                ${records.length > 100 ? `<p style="margin-top: 1rem; color: #888;">Showing first 100 of ${records.length} records</p>` : ''}
            `;
        }
    } catch (error) {
        console.error('Error loading corrected:', error);
    }
}

async function loadMaxCall(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/max-call?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('maxCallContent');
            const maxCall = data.data;

            content.innerHTML = `
                <div class="stat-card" style="max-width: 400px;">
                    <div class="stat-value">${maxCall.total_call_count || 0}</div>
                    <div class="stat-label">Total Calls</div>
                </div>
                <table class="data-table" style="margin-top: 2rem;">
                    <thead>
                        <tr>
                            <th>B-Number</th>
                            <th>Call Count</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><code>${maxCall.b_number || 'N/A'}</code></td>
                            <td>${maxCall.total_call_count || 0}</td>
                        </tr>
                    </tbody>
                </table>
            `;
        }
    } catch (error) {
        console.error('Error loading max call:', error);
    }
}

async function loadMaxCircleCall(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/max-circle-call?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('maxCircleCallContent');
            const maxCircle = data.data;

            content.innerHTML = `
                <div class="stat-card" style="max-width: 400px;">
                    <div class="stat-value">${maxCircle.activity_count || 0}</div>
                    <div class="stat-label">Activity Count</div>
                </div>
                <table class="data-table" style="margin-top: 2rem;">
                    <thead>
                        <tr>
                            <th>Circle/State</th>
                            <th>Activity Count</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>${maxCircle.circle || 'N/A'}</td>
                            <td>${maxCircle.activity_count || 0}</td>
                        </tr>
                    </tbody>
                </table>
            `;
        }
    } catch (error) {
        console.error('Error loading max circle call:', error);
    }
}

async function loadDailyFirstLast(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/daily-first-last?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('dailyFirstLastContent');
            const dailyData = data.data || [];

            if (dailyData.length === 0) {
                content.innerHTML = '<p>No daily call data found</p>';
                return;
            }

            content.innerHTML = `
                <div style="overflow-x: auto; -webkit-overflow-scrolling: touch; width: 100%;">
                    <table class="data-table" style="min-width: 100%;">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>First Call Time</th>
                                <th>First Call B-Number</th>
                                <th>Last Call Time</th>
                                <th>Last Call B-Number</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${dailyData.map(item => `
                                <tr>
                                    <td>${item.date || ''}</td>
                                    <td>${item.first_call_time || ''}</td>
                                    <td><code>${item.first_call_b_number || ''}</code></td>
                                    <td>${item.last_call_time || ''}</td>
                                    <td><code>${item.last_call_b_number || ''}</code></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading daily first last:', error);
    }
}

async function loadMaxDuration(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/max-duration?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('maxDurationContent');
            const maxDuration = data.data;

            const durationMinutes = ((maxDuration.duration_seconds || 0) / 60).toFixed(2);

            content.innerHTML = `
                <div class="stat-card" style="max-width: 400px;">
                    <div class="stat-value">${durationMinutes}</div>
                    <div class="stat-label">Duration (minutes)</div>
                </div>
                <table class="data-table" style="margin-top: 2rem;">
                    <thead>
                        <tr>
                            <th>Field</th>
                            <th>Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td>B-Number</td><td><code>${maxDuration.b_number || 'N/A'}</code></td></tr>
                        <tr><td>Duration (seconds)</td><td>${maxDuration.duration_seconds || 0}</td></tr>
                        <tr><td>Date</td><td>${maxDuration.date || 'N/A'}</td></tr>
                        <tr><td>Call Start Time</td><td>${maxDuration.call_start_time || 'N/A'}</td></tr>
                        <tr><td>Cell ID</td><td>${maxDuration.cell_id || 'N/A'}</td></tr>
                        <tr><td>Location Description</td><td>${maxDuration.location_description || 'N/A'}</td></tr>
                    </tbody>
                </table>
            `;
        }
    } catch (error) {
        console.error('Error loading max duration:', error);
    }
}

async function loadMaxIMEI(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/max-imei?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('maxImeiContent');
            const maxIMEI = data.data;

            content.innerHTML = `
                <div class="stats-grid" style="margin-bottom: 2rem;">
                    <div class="stat-card">
                        <div class="stat-value">${maxIMEI.max_imei_call_count || 0}</div>
                        <div class="stat-label">Max IMEI Call Count</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${maxIMEI.total_imeis || 0}</div>
                        <div class="stat-label">Total IMEIs</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${maxIMEI.multi_device_usage ? 'Yes' : 'No'}</div>
                        <div class="stat-label">Multi-Device Usage</div>
                    </div>
                </div>
                <h4 style="margin-bottom: 1rem;">Max IMEI: <code>${maxIMEI.max_imei || 'N/A'}</code></h4>
                <h4 style="margin-bottom: 1rem; margin-top: 2rem;">IMEI Ranking</h4>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>IMEI</th>
                            <th>Call Count</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${maxIMEI.imei_ranking.map((item, idx) => `
                            <tr>
                                <td>${idx + 1}</td>
                                <td><code>${item.imei || ''}</code></td>
                                <td>${item.call_count || 0}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
    } catch (error) {
        console.error('Error loading max IMEI:', error);
    }
}

async function loadDailyIMEITracking(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/daily-imei-tracking?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('dailyImeiTrackingContent');
            const dailyData = data.data || [];

            if (dailyData.length === 0) {
                content.innerHTML = '<p>No daily IMEI tracking data found</p>';
                return;
            }

            content.innerHTML = `
                <div style="overflow-x: auto; -webkit-overflow-scrolling: touch; width: 100%;">
                    <table class="data-table" style="min-width: 100%;">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>IMEI</th>
                                <th>Call Count</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${dailyData.flatMap(item =>
                                (item.imeis || []).map(imeiData => `
                                    <tr>
                                        <td>${item.date || ''}</td>
                                        <td><code>${imeiData.imei || ''}</code></td>
                                        <td>${imeiData.call_count || 0}</td>
                                    </tr>
                                `)
                            ).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading daily IMEI tracking:', error);
    }
}

async function loadMaxLocation(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/max-location?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('maxLocationContent');
            const maxLocation = data.data;

            content.innerHTML = `
                <div class="stat-card" style="max-width: 400px;">
                    <div class="stat-value">${maxLocation.usage_count || 0}</div>
                    <div class="stat-label">Usage Count</div>
                </div>
                <table class="data-table" style="margin-top: 2rem;">
                    <thead>
                        <tr>
                            <th>Cell ID</th>
                            <th>Usage Count</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>${maxLocation.cell_id || 'N/A'}</td>
                            <td>${maxLocation.usage_count || 0}</td>
                        </tr>
                    </tbody>
                </table>
            `;
        }
    } catch (error) {
        console.error('Error loading max location:', error);
    }
}

async function loadDailyFirstLastLocation(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/daily-first-last-location?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const content = document.getElementById('dailyFirstLastLocationContent');
            const dailyData = data.data || [];

            if (dailyData.length === 0) {
                content.innerHTML = '<p>No daily location data found</p>';
                return;
            }

            content.innerHTML = `
                <div style="overflow-x: auto; -webkit-overflow-scrolling: touch; width: 100%;">
                    <table class="data-table" style="min-width: 100%;">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>First Location Cell ID</th>
                                <th>First Location Time</th>
                                <th>Last Location Cell ID</th>
                                <th>Last Location Time</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${dailyData.map(item => `
                                <tr>
                                    <td>${item.date || ''}</td>
                                    <td>${item.first_location?.cell_id || ''}</td>
                                    <td>${item.first_location?.time || ''}</td>
                                    <td>${item.last_location?.cell_id || ''}</td>
                                    <td>${item.last_location?.time || ''}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading daily first last location:', error);
    }
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
            // Removed loadSuspects - no longer needed
        } else {
            resultDiv.innerHTML = `<div style="color: #ef4444;">Error: ${data.message || 'Unknown error'}</div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div style="color: #ef4444;">Error: ${error.message}</div>`;
    }
}

async function exportCurrentSession(sessionId, format = 'excel') {
    if (!sessionId) {
        sessionId = window.currentSessionId;
    }

    if (!sessionId) {
        alert('No session data available. Please upload a file first.');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/export?format=${format}&session_id=${encodeURIComponent(sessionId)}`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Export failed');
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        let extension = 'json';
        if (format === 'csv') extension = 'csv';
        else if (format === 'excel' || format === 'xlsx') extension = 'xlsx';
        else if (format === 'kml') extension = 'kml';
        a.download = `cdr_analysis.${extension}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        alert(`Error exporting data: ${error.message}`);
    }
}

async function exportCurrentSessionPDF(sessionId) {
    if (!sessionId) {
        sessionId = window.currentSessionId;
    }

    if (!sessionId) {
        alert('No session data available. Please upload a file first.');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/export-pdf-session?session_id=${encodeURIComponent(sessionId)}`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate PDF');
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cdr_analysis_${sessionId}_report.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        alert(`Error generating PDF: ${error.message}`);
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
    // Use the same protocol and host as the current page
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/geofence-alerts`;
    const socket = new WebSocket(wsUrl);

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

// Advanced Intelligence Dashboard Functions
function showAdvancedDashboard() {
    const standardView = document.getElementById('singleAnalysisView');
    const advancedView = document.getElementById('advancedDashboardView');

    if (standardView && advancedView) {
        standardView.style.display = 'none';
        advancedView.style.display = 'block';

        // Load advanced analytics if session exists
        if (window.currentSessionId) {
            loadAdvancedAnalytics(window.currentSessionId);
        }
    }
}

function hideAdvancedDashboard() {
    const standardView = document.getElementById('singleAnalysisView');
    const advancedView = document.getElementById('advancedDashboardView');

    if (standardView && advancedView) {
        advancedView.style.display = 'none';
        standardView.style.display = 'block';
    }
}

function switchAdvancedSection(section) {
    // No longer needed - all sections are visible in grid
    // Keep for backward compatibility if needed
}

async function loadAdvancedAnalytics(sessionId) {
    if (!sessionId) {
        sessionId = window.currentSessionId;
    }

    if (!sessionId) {
        console.error('No session ID available');
        return;
    }

    // Load all sections in parallel for grid view
    await Promise.all([
        loadAdvancedOverview(sessionId),
        loadAdvancedNetwork(sessionId),
        loadAdvancedTimeline(sessionId),
        loadAdvancedIMEI(sessionId),
        loadAdvancedLocation(sessionId),
        loadAdvancedColocation(sessionId),
        loadAdvancedAnomalies(sessionId),
        loadAdvancedAudit(sessionId)
    ]);
}

async function loadAdvancedSectionData(section, sessionId) {
    switch(section) {
        case 'overview':
            await loadAdvancedOverview(sessionId);
            break;
        case 'network':
            await loadAdvancedNetwork(sessionId);
            break;
        case 'timeline':
            await loadAdvancedTimeline(sessionId);
            break;
        case 'imei':
            await loadAdvancedIMEI(sessionId);
            break;
        case 'location':
            await loadAdvancedLocation(sessionId);
            break;
        case 'colocation':
            await loadAdvancedColocation(sessionId);
            break;
        case 'anomalies':
            await loadAdvancedAnomalies(sessionId);
            break;
        case 'tables':
            await loadAdvancedTables(sessionId);
            break;
        case 'audit':
            await loadAdvancedAudit(sessionId);
            break;
    }
}

async function loadAdvancedOverview(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/intelligence/overview?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const overview = data.data;

            // Update case header
            const caseId = document.getElementById('caseId');
            const targetMsisdn = document.getElementById('targetMsisdn');
            if (caseId) caseId.textContent = overview.case_id || `CDR_INV_${new Date().getFullYear()}_${String(Math.floor(Math.random() * 1000)).padStart(3, '0')}`;
            if (targetMsisdn) targetMsisdn.textContent = overview.target_msisdn || '--';

            // Update KPIs
            const kpiContainer = document.getElementById('overviewKpis');
            if (kpiContainer) {
                kpiContainer.innerHTML = `
                    <div class="stat-card">
                        <div class="stat-value">${overview.total_calls || 0}</div>
                        <div class="stat-label">Total Calls</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${overview.unique_contacts || 0}</div>
                        <div class="stat-label">Unique Contacts</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${overview.unique_imeis || 0}</div>
                        <div class="stat-label">IMEIs</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${overview.unique_locations || 0}</div>
                        <div class="stat-label">Locations</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value"><span class="risk-flag ${(overview.risk_level || 'low').toLowerCase()}">${(overview.risk_level || 'LOW').toUpperCase()}</span></div>
                        <div class="stat-label">Risk Flag</div>
                    </div>
                `;
            }

            // Update intelligence story
            const storyContainer = document.getElementById('intelligenceStory');
            if (storyContainer) {
                storyContainer.innerHTML = `<p style="line-height: 1.8; color: var(--text-secondary);">${overview.intelligence_story || 'No intelligence story available.'}</p>`;
            }

            // Update alerts
            const alertsContainer = document.getElementById('activeAlerts');
            if (alertsContainer && overview.alerts) {
                alertsContainer.innerHTML = overview.alerts.map(alert => `
                    <div class="alert-item ${alert.severity || 'info'}">
                        <h5>${alert.title || 'Alert'}</h5>
                        <p>${alert.description || ''}</p>
                        ${alert.evidence ? `<div class="evidence">Evidence: ${alert.evidence}</div>` : ''}
                    </div>
                `).join('');
            }
        }
    } catch (error) {
        console.error('Error loading advanced overview:', error);
    }
}

async function loadAdvancedNetwork(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/intelligence/network?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const network = data.data;
            const container = document.getElementById('networkGraphContainer');

            if (container && network.nodes && network.edges) {
                container.innerHTML = '';

                const nodes = new vis.DataSet(network.nodes);
                const edges = new vis.DataSet(network.edges);

                const networkData = { nodes, edges };
                const options = {
                    nodes: {
                        shape: 'dot',
                        size: (node) => Math.max(10, Math.min(30, node.value || 20)),
                        font: { color: '#ffffff', size: 12 },
                        borderWidth: 2,
                        color: {
                            border: '#ffffff',
                            background: (node) => node.color || '#6366f1'
                        }
                    },
                    edges: {
                        width: (edge) => Math.max(1, Math.min(5, (edge.value || 1) / 10)),
                        color: { color: '#6366f1', highlight: '#ec4899' },
                        arrows: { to: { enabled: true } },
                        smooth: { type: 'continuous' }
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

                new vis.Network(container, networkData, options);
            }
        }
    } catch (error) {
        console.error('Error loading network graph:', error);
    }
}

async function loadAdvancedTimeline(sessionId, callType = 'all') {
    try {
        const response = await fetch(`${API_BASE}/analytics/intelligence/timeline?session_id=${encodeURIComponent(sessionId)}&call_type=${callType}`);
        const data = await response.json();

        if (data.success) {
            const heatmapData = data.data;
            const container = document.getElementById('heatmapContainer');

            if (container && heatmapData.z && heatmapData.x && heatmapData.y) {
                const trace = {
                    x: heatmapData.x,
                    y: heatmapData.y,
                    z: heatmapData.z,
                    type: 'heatmap',
                    colorscale: 'Viridis',
                    showscale: true
                };

                const layout = {
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    font: { color: '#ffffff' },
                    xaxis: { title: 'Hour of Day' },
                    yaxis: { title: 'Date' }
                };

                Plotly.newPlot(container, [trace], layout, {responsive: true});
            }
        }
    } catch (error) {
        console.error('Error loading timeline heatmap:', error);
    }
}

function toggleHeatmapType(type) {
    // Update active button
    document.querySelectorAll('#timelineSection .tab-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    // Reload with filter
    if (window.currentSessionId) {
        loadAdvancedTimeline(window.currentSessionId, type);
    }
}

async function loadAdvancedIMEI(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/intelligence/imei?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const imeiData = data.data;
            const container = document.getElementById('imeiTimelineContainer');
            const detailsContainer = document.getElementById('imeiDetails');

            if (container && imeiData.timeline && imeiData.timeline.length > 0) {
                // Create timeline chart - use bar chart to show usage over time
                const traces = imeiData.timeline.map((item, idx) => {
                    const colors = ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#3b82f6'];
                    return {
                        x: item.dates,
                        y: item.call_counts || new Array(item.dates.length).fill(1),
                        type: 'bar',
                        name: item.imei.substring(0, 12) + '...',
                        marker: { color: colors[idx % colors.length] }
                    };
                });

                const layout = {
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    font: { color: '#ffffff' },
                    xaxis: { title: 'Date' },
                    yaxis: { title: 'Call Count' },
                    barmode: 'stack',
                    showlegend: true
                };

                Plotly.newPlot(container, traces, layout, {responsive: true});
            } else if (container) {
                container.innerHTML = '<div style="padding: 2rem; color: #888;">No IMEI timeline data available</div>';
            }

            if (detailsContainer) {
                if (imeiData.switches && imeiData.switches.length > 0) {
                    detailsContainer.innerHTML = `
                        <h4 style="margin-top: 2rem; margin-bottom: 1rem;">IMEI Switches Detected</h4>
                        ${imeiData.switches.map(switchItem => `
                            <div class="alert-item warning">
                                <h5>Device Change on ${new Date(switchItem.timestamp).toLocaleString()}</h5>
                                <p>From: <code>${switchItem.from_imei || 'Unknown'}</code> → To: <code>${switchItem.to_imei || 'Unknown'}</code></p>
                                <div class="evidence">Location: ${switchItem.location || 'N/A'}</div>
                            </div>
                        `).join('')}
                    `;
                } else {
                    detailsContainer.innerHTML = '<p>No IMEI switches detected.</p>';
                }
            }
        }
    } catch (error) {
        console.error('Error loading IMEI analysis:', error);
        const container = document.getElementById('imeiTimelineContainer');
        if (container) {
            container.innerHTML = `<div style="padding: 2rem; color: #ef4444;">Error loading IMEI analysis: ${error.message}</div>`;
        }
    }
}

async function loadAdvancedLocation(sessionId, layer = 'day') {
    try {
        const response = await fetch(`${API_BASE}/analytics/intelligence/location?session_id=${encodeURIComponent(sessionId)}&layer=${layer}`);
        const data = await response.json();

        if (data.success) {
            const locationData = data.data;
            const mapContainer = document.getElementById('movementMap');

            if (mapContainer && locationData.paths) {
                mapContainer.innerHTML = '';

                // Calculate center
                const allCoords = locationData.paths.flatMap(p => p.coordinates || []);
                if (allCoords.length > 0) {
                    const avgLat = allCoords.reduce((sum, c) => sum + c[1], 0) / allCoords.length;
                    const avgLon = allCoords.reduce((sum, c) => sum + c[0], 0) / allCoords.length;

                    const map = new maplibregl.Map({
                        container: 'movementMap',
                        style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
                        center: [avgLon, avgLat],
                        zoom: 12
                    });

                    map.on('load', () => {
                        // Add paths
                        locationData.paths.forEach((path, idx) => {
                            if (path.coordinates && path.coordinates.length > 0) {
                                map.addSource(`path-${idx}`, {
                                    type: 'geojson',
                                    data: {
                                        type: 'Feature',
                                        geometry: {
                                            type: 'LineString',
                                            coordinates: path.coordinates
                                        }
                                    }
                                });

                                map.addLayer({
                                    id: `path-layer-${idx}`,
                                    type: 'line',
                                    source: `path-${idx}`,
                                    paint: {
                                        'line-color': path.color || '#6366f1',
                                        'line-width': 3
                                    }
                                });
                            }
                        });

                        // Add markers
                        if (locationData.markers) {
                            locationData.markers.forEach((marker, idx) => {
                                if (marker.coordinates) {
                                    const el = document.createElement('div');
                                    el.className = 'marker';
                                    el.style.width = '20px';
                                    el.style.height = '20px';
                                    el.style.borderRadius = '50%';
                                    el.style.background = marker.color || '#6366f1';
                                    el.style.border = '2px solid white';

                                    new maplibregl.Marker(el)
                                        .setLngLat(marker.coordinates)
                                        .setPopup(new maplibregl.Popup().setHTML(`
                                            <strong>${marker.title || 'Location'}</strong><br>
                                            ${marker.description || ''}
                                        `))
                                        .addTo(map);
                                }
                            });
                        }
                    });
                } else {
                    mapContainer.innerHTML = '<div style="padding: 2rem; color: #ef4444;">No location data available</div>';
                }
            }
        }
    } catch (error) {
        console.error('Error loading location map:', error);
        const mapContainer = document.getElementById('movementMap');
        if (mapContainer) {
            mapContainer.innerHTML = `<div style="padding: 2rem; color: #ef4444;">Error loading location map: ${error.message}</div>`;
        }
    }
}

function toggleLocationLayer(layer) {
    // Update active button
    document.querySelectorAll('#locationSection .tab-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    // Reload with layer filter
    if (window.currentSessionId) {
        loadAdvancedLocation(window.currentSessionId, layer);
    }
}

async function loadAdvancedColocation(sessionId) {
    try {
        const windowMinutes = document.getElementById('colocationWindow')?.value || 15;
        const response = await fetch(`${API_BASE}/analytics/intelligence/colocation?session_id=${encodeURIComponent(sessionId)}&window_minutes=${windowMinutes}`);
        const data = await response.json();

        if (data.success) {
            const colocations = data.data;
            const container = document.getElementById('colocationResults');

            if (container) {
                if (colocations.length === 0) {
                    container.innerHTML = '<p>No co-locations detected.</p>';
                } else {
                    container.innerHTML = colocations.map(coloc => `
                        <div class="colocation-item ${coloc.repeated ? 'high-risk' : ''}">
                            <h4>${coloc.date || 'Unknown Date'} | ${coloc.time_window || 'Unknown Time'}</h4>
                            <p><strong>Location:</strong> ${coloc.location || 'Unknown'}</p>
                            <ul>
                                ${coloc.msisdns.map(msisdn => `<li>${msisdn}</li>`).join('')}
                            </ul>
                            ${coloc.repeated ? '<p style="color: #ef4444; margin-top: 0.5rem;"><strong>⚠ Repeated co-location detected</strong></p>' : ''}
                        </div>
                    `).join('');
                }
            }
        }
    } catch (error) {
        console.error('Error loading co-location analysis:', error);
    }
}

function analyzeColocation() {
    if (window.currentSessionId) {
        loadAdvancedColocation(window.currentSessionId);
    }
}

async function loadAdvancedAnomalies(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/intelligence/anomalies?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const anomalies = data.data;
            const container = document.getElementById('anomaliesList');

            if (container) {
                if (anomalies.length === 0) {
                    container.innerHTML = '<p>No anomalies detected.</p>';
                } else {
                    container.innerHTML = anomalies.map(anomaly => `
                        <div class="alert-item ${anomaly.severity || 'warning'}">
                            <h5>${anomaly.title || 'Anomaly'}</h5>
                            <p>${anomaly.description || ''}</p>
                            <div class="evidence">
                                <strong>Reason:</strong> ${anomaly.reason || 'N/A'}<br>
                                <strong>Evidence:</strong> ${anomaly.evidence || 'N/A'}<br>
                                ${anomaly.supporting_data ? `<strong>Supporting Data:</strong> ${JSON.stringify(anomaly.supporting_data)}` : ''}
                            </div>
                        </div>
                    `).join('');
                }
            }
        }
    } catch (error) {
        console.error('Error loading anomalies:', error);
    }
}

async function loadAdvancedTables(sessionId) {
    const container = document.getElementById('tablesContent');
    if (!container) return;

    // Get active tab
    const activeTab = container.querySelector('.tab-content.active')?.id || 'corrected-advanced';

    // Load data based on active tab
    switch(activeTab) {
        case 'corrected-advanced':
            await loadCorrected(sessionId);
            if (container) {
                const correctedDiv = document.createElement('div');
                correctedDiv.id = 'correctedContentAdvanced';
                container.appendChild(correctedDiv);
                // Copy content from standard view
                const standardContent = document.getElementById('correctedContent');
                if (standardContent) {
                    correctedDiv.innerHTML = standardContent.innerHTML;
                }
            }
            break;
        case 'daily-first-last-advanced':
            await loadDailyFirstLast(sessionId);
            break;
        case 'imei-advanced':
            await loadMaxIMEI(sessionId);
            break;
        case 'location-advanced':
            await loadMaxLocation(sessionId);
            break;
    }
}

async function loadAdvancedAudit(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/analytics/intelligence/audit?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();

        if (data.success) {
            const audit = data.data;
            const container = document.getElementById('auditTrail');

            if (container) {
                container.innerHTML = `
                    <div style="margin-bottom: 2rem;">
                        <h4>Data Flow</h4>
                        <div style="padding: 1rem; background: rgba(255,255,255,0.03); border-radius: 8px; margin-top: 1rem;">
                            <p>RAW CDR ROW → NORMALIZED RECORD → ANALYTICS</p>
                        </div>
                    </div>
                    <div>
                        <h4>Audit Trail</h4>
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Timestamp</th>
                                    <th>Action</th>
                                    <th>Details</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${audit.trail.map(item => `
                                    <tr>
                                        <td>${new Date(item.timestamp).toLocaleString()}</td>
                                        <td>${item.action}</td>
                                        <td>${item.details || ''}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error loading audit trail:', error);
    }
}

function applyAdvancedFilters() {
    // Reload current section with filters
    const activeSection = document.querySelector('.advanced-section.active');
    if (activeSection && window.currentSessionId) {
        const sectionId = activeSection.id.replace('Section', '');
        loadAdvancedSectionData(sectionId, window.currentSessionId);
    }
}
