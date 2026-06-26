/* AEGIS Control Center SPA Controller
   Coordinates routing, authentication checks, view lifecycle rendering, and page interactivity.
*/

import { Auth, API } from './api.js';
import { Toast, Modal, Loader, EmptyState, renderPagination, ChartRenderer } from './components.js';

// ===========================================================================
// Helper Utilities
// ===========================================================================
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return str.toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatUptime(seconds) {
    const s = Number(seconds);
    const d = Math.floor(s / (3600 * 24));
    const h = Math.floor((s % (3600 * 24)) / 3600);
    const m = Math.floor((s % 3600) / 60);
    
    let parts = [];
    if (d > 0) parts.push(`${d}d`);
    if (h > 0) parts.push(`${h}h`);
    if (m > 0 || parts.length === 0) parts.push(`${m}m`);
    return parts.join(' ');
}

// ===========================================================================
// Application State
// ===========================================================================
const AppState = {
    currentPage: 'dashboard',
    activeRequestsOffset: 0,
    activeErrorsOffset: 0,
    logsLimit: 15,
    providersList: [],
    settingsCache: null,
};

// ===========================================================================
// Routing Dispatcher
// ===========================================================================
const Routes = {
    login: renderLoginPage,
    dashboard: renderDashboardPage,
    providers: renderProvidersPage,
    mappings: renderMappingsPage,
    logs: renderLogsPage,
    errors: renderErrorsPage,
    usage: renderUsagePage,
    settings: renderSettingsPage
};

async function dispatchRoute() {
    const hash = window.location.hash || '#/dashboard';
    
    // Auth Guard check
    if (!Auth.isAuthenticated() && hash !== '#/login') {
        window.location.hash = '#/login';
        return;
    }
    
    let page = hash.replace('#/', '');
    if (page === 'login' && Auth.isAuthenticated()) {
        window.location.hash = '#/dashboard';
        return;
    }
    
    if (!Routes[page]) {
        page = 'dashboard';
        window.location.hash = '#/dashboard';
    }
    
    AppState.currentPage = page;
    updateSidebarNavHighlight(page);
    
    const viewport = document.getElementById('viewport');
    const titleEl = document.getElementById('current-page-title');
    
    if (page === 'login') {
        document.getElementById('app-container').className = 'unauthenticated-layout';
        titleEl.textContent = 'Login';
    } else {
        document.getElementById('app-container').className = 'authenticated-layout';
        // Capitalize title
        titleEl.textContent = page.charAt(0).toUpperCase() + page.slice(1).replace('-', ' ');
        // Trigger background server health poll
        pollServerHealth();
    }
    
    // Call the page renderer
    try {
        await Routes[page](viewport);
    } catch (err) {
        viewport.innerHTML = EmptyState.render('Error loading view', err.message, '⚠️');
    }
}

function updateSidebarNavHighlight(page) {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    const activeItem = document.getElementById(`nav-${page}`);
    if (activeItem) {
        activeItem.classList.add('active');
    }
}

// Background server health checker
async function pollServerHealth() {
    const badge = document.getElementById('server-health-badge');
    if (!badge || !Auth.isAuthenticated()) return;
    
    try {
        const summary = await API.getDashboardSummary();
        const serverStatus = summary?.server?.status;
        if (serverStatus === 'running') {
            badge.className = 'health-badge running';
            badge.querySelector('.badge-text').textContent = 'Server Online';
        } else {
            badge.className = 'health-badge error';
            badge.querySelector('.badge-text').textContent = 'Server Status: ' + (serverStatus || 'Unknown');
        }
    } catch {
        badge.className = 'health-badge error';
        badge.querySelector('.badge-text').textContent = 'Offline';
    }
}

// ===========================================================================
// PAGE 1: Login
// ===========================================================================
function renderLoginPage(container) {
    container.innerHTML = `
        <div class="login-container">
            <div class="login-card">
                <div class="login-logo">
                    <span class="logo-mark">▲</span>
                    <h1>AEGIS Control Center</h1>
                    <p>Intelligent AI Gateway</p>
                </div>
                <form id="login-form">
                    <div class="form-group">
                        <label for="bearer-token">Bearer Auth Token</label>
                        <input type="password" id="bearer-token" class="form-control" placeholder="Enter AEGIS_AUTH_TOKEN" required autocomplete="current-password">
                    </div>
                    <button type="submit" id="btn-login-submit" class="btn btn-primary" style="width: 100%; margin-top: 10px;">
                        Sign In
                    </button>
                </form>
            </div>
        </div>
    `;
    
    const form = container.querySelector('#login-form');
    const submitBtn = container.querySelector('#btn-login-submit');
    
    form.onsubmit = async (e) => {
        e.preventDefault();
        const token = container.querySelector('#bearer-token').value.trim();
        if (!token) return;
        
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Verifying...';
        
        // Save temporarily
        Auth.setToken(token);
        
        try {
            // Test validity using dashboard endpoint
            await API.getDashboardSummary();
            Toast.success('Login Successful', 'Welcome to AEGIS Control Center');
            window.location.hash = '#/dashboard';
        } catch (err) {
            Auth.clearToken();
            Toast.error('Login Failed', 'Invalid auth token. Please verify credentials.');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Sign In';
        }
    };
}

// ===========================================================================
// PAGE 2: Dashboard
// ===========================================================================
async function renderDashboardPage(container) {
    container.innerHTML = Loader.renderSpinner();
    
    const summary = await API.getDashboardSummary();
    const systemUptime = summary?.server?.uptime_seconds || 0;
    
    container.innerHTML = `
        <!-- Top Stats Cards -->
        <div class="dashboard-grid">
            <div class="stat-card">
                <span class="stat-label">Server Status</span>
                <span class="stat-value success">ONLINE</span>
                <span class="stat-footer">AEGIS v${escapeHtml(summary?.server?.version || '0.1.0')}</span>
            </div>
            
            <div class="stat-card">
                <span class="stat-label">System Uptime</span>
                <span class="stat-value">${formatUptime(systemUptime)}</span>
                <span class="stat-footer">Uptime since boot</span>
            </div>
            
            <div class="stat-card">
                <span class="stat-label">Success Rate</span>
                <span class="stat-value ${summary?.runtime?.success_rate >= 90 ? 'success' : 'error'}">${summary?.runtime?.success_rate}%</span>
                <span class="stat-footer">Requests processed successfully</span>
            </div>
            
            <div class="stat-card">
                <span class="stat-label">Total Requests</span>
                <span class="stat-value">${summary?.runtime?.total_requests?.toLocaleString() || 0}</span>
                <span class="stat-footer">With ${summary?.runtime?.total_errors || 0} error conditions</span>
            </div>
        </div>

        <div class="dashboard-details">
            <!-- Provider pool overview -->
            <div class="card" style="margin-bottom: 0;">
                <div class="card-header">
                    <h3 class="card-title">Active Provider Pool</h3>
                    <a href="#/providers" class="btn btn-secondary btn-sm" style="padding: 6px 12px; font-size: 11px;">Manage Pool</a>
                </div>
                
                <div class="provider-details-list" style="margin-bottom: 24px;">
                    <div class="provider-detail-item">
                        <span>Total Registered Providers</span>
                        <span>${summary?.pool?.total_members || 0}</span>
                    </div>
                    <div class="provider-detail-item">
                        <span>Healthy Providers</span>
                        <span style="color: var(--success-green); font-weight: bold;">${summary?.pool?.healthy_members || 0}</span>
                    </div>
                    <div class="provider-detail-item">
                        <span>Active Pool Load</span>
                        <span>${summary?.pool?.active_members || 0} active workers</span>
                    </div>
                    <div class="provider-detail-item">
                        <span>Disabled Members</span>
                        <span>${summary?.pool?.disabled_members || 0}</span>
                    </div>
                </div>
                
                <div class="form-group" style="margin-bottom: 0; border-top: 1px solid var(--border-color); padding-top: 20px;">
                    <label>Scheduler Selection Strategy</label>
                    <div style="font-size: 15px; font-weight: 600; color: var(--accent-orange); text-transform: uppercase;">
                        ${escapeHtml(summary?.runtime?.scheduler_mode || 'health-first')}
                    </div>
                    <p style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">Configured in settings for routing model requests.</p>
                </div>
            </div>

            <!-- Provider active metrics list -->
            <div class="card" style="margin-bottom: 0;">
                <div class="card-header">
                    <h3 class="card-title">Provider Health Details</h3>
                </div>
                <div id="dashboard-health-list" class="table-responsive">
                    ${Loader.renderSpinner()}
                </div>
            </div>
        </div>
    `;
    
    // Fetch individual pool details asynchronously
    try {
        const details = await API.getControlHealth();
        const listContainer = container.querySelector('#dashboard-health-list');
        
        if (!details.providers || details.providers.length === 0) {
            listContainer.innerHTML = EmptyState.render('No Providers Registered', 'Please go to the Providers page to add connection accounts.');
            return;
        }
        
        let trs = '';
        details.providers.forEach(p => {
            const healthBadge = p.healthy 
                ? '<span class="badge badge-success">Healthy</span>' 
                : '<span class="badge badge-error">Cooldown / Fail</span>';
            const statusBadge = p.enabled
                ? '<span class="badge badge-info">Active</span>'
                : '<span class="badge badge-disabled">Disabled</span>';
                
            trs += `
                <tr>
                    <td>
                        <strong style="display: block;">${escapeHtml(p.display_name)}</strong>
                        <span style="font-size: 11px; color: var(--text-muted); font-family: monospace;">${escapeHtml(p.provider_id)}</span>
                    </td>
                    <td>${statusBadge}</td>
                    <td>${healthBadge}</td>
                    <td style="text-align: center;"><strong>${p.active_requests}</strong></td>
                </tr>
            `;
        });
        
        listContainer.innerHTML = `
            <table class="table">
                <thead>
                    <tr>
                        <th>Provider</th>
                        <th>Pool Status</th>
                        <th>Health</th>
                        <th style="text-align: center;">Active Requests</th>
                    </tr>
                </thead>
                <tbody>
                    ${trs}
                </tbody>
            </table>
        `;
    } catch (err) {
        container.querySelector('#dashboard-health-list').innerHTML = `<div style="color: var(--error-red); font-size: 12px;">Failed to load health list.</div>`;
    }
}

// ===========================================================================
// PAGE 3: Providers
// ===========================================================================
async function renderProvidersPage(container) {
    container.innerHTML = `
        <div class="actions-bar">
            <div class="search-box">
                <span class="search-icon">🔍</span>
                <input type="text" id="provider-search" class="form-control search-control" placeholder="Search provider by name...">
            </div>
            <button id="btn-add-provider" class="btn btn-primary">🔌 Add Provider Key</button>
        </div>
        <div id="providers-content">
            ${Loader.renderSpinner()}
        </div>
    `;
    
    const providersContent = container.querySelector('#providers-content');
    const searchInput = container.querySelector('#provider-search');
    
    // Load lists
    const loadProviders = async () => {
        providersContent.innerHTML = Loader.renderSkeletonCards(3);
        try {
            const poolSummary = await API.getControlHealth();
            const poolMembers = poolSummary?.providers || [];
            
            AppState.providersList = await API.listProviders();
            
            // Map active request status from memory pool
            AppState.providersList.forEach(p => {
                const mem = poolMembers.find(m => m.provider_id === p.provider_id);
                if (mem) {
                    p.healthy = mem.healthy;
                    p.active_requests = mem.active_requests;
                    p.recent_failures = mem.recent_failures;
                    p.cooldown_expiry = mem.cooldown_expiry;
                } else {
                    p.healthy = true;
                    p.active_requests = 0;
                    p.recent_failures = 0;
                    p.cooldown_expiry = null;
                }
            });
            
            renderProvidersGrid(providersContent, searchInput.value.trim());
        } catch (err) {
            providersContent.innerHTML = EmptyState.render('Failed to Load Providers', err.message, '⚠️');
        }
    };
    
    searchInput.oninput = () => {
        renderProvidersGrid(providersContent, searchInput.value.trim());
    };
    
    container.querySelector('#btn-add-provider').onclick = () => {
        openProviderFormModal(null, loadProviders);
    };
    
    await loadProviders();
}

function renderProvidersGrid(container, searchQuery = '') {
    const filtered = AppState.providersList.filter(p => 
        p.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.provider_id.toLowerCase().includes(searchQuery.toLowerCase())
    );
    
    if (filtered.length === 0) {
        container.innerHTML = EmptyState.render(
            searchQuery ? 'No Providers Found' : 'No Providers Configured',
            searchQuery ? `No names matched "${searchQuery}"` : 'Get started by adding your first NVIDIA account keys.',
            '🔌'
        );
        return;
    }
    
    let cards = '';
    filtered.forEach(p => {
        const enabledClass = p.enabled ? 'badge-info' : 'badge-disabled';
        const enabledText = p.enabled ? 'Enabled' : 'Disabled';
        
        const healthClass = p.healthy ? 'badge-success' : 'badge-error';
        const healthText = p.healthy ? 'Healthy' : 'Cooldown';
        
        cards += `
            <div class="provider-card">
                <div class="provider-card-header">
                    <div class="provider-info">
                        <h3>${escapeHtml(p.display_name)}</h3>
                        <span class="provider-id">${escapeHtml(p.provider_id)}</span>
                    </div>
                    <div style="display: flex; gap: 6px;">
                        <span class="badge ${enabledClass}">${enabledText}</span>
                        <span class="badge ${healthClass}">${healthText}</span>
                    </div>
                </div>
                
                <div class="provider-details-list">
                    <div class="provider-detail-item">
                        <span>API Base URL</span>
                        <span style="font-family: monospace; font-size: 11px; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(p.base_url)}">${escapeHtml(p.base_url)}</span>
                    </div>
                    <div class="provider-detail-item">
                        <span>API Key Mask</span>
                        <span style="font-family: monospace;">${escapeHtml(p.api_key)}</span>
                    </div>
                    <div class="provider-detail-item">
                        <span>Active Requests</span>
                        <strong>${p.active_requests || 0}</strong>
                    </div>
                    <div class="provider-detail-item">
                        <span>Recent Failures</span>
                        <span style="color: ${p.recent_failures > 0 ? 'var(--error-red)' : 'var(--text-secondary)'}">${p.recent_failures || 0}</span>
                    </div>
                    ${p.cooldown_expiry ? `
                    <div class="provider-detail-item">
                        <span>Cooldown Expiry</span>
                        <span style="color: var(--warning-amber); font-size: 11px;">${new Date(p.cooldown_expiry).toLocaleTimeString()}</span>
                    </div>
                    ` : ''}
                </div>
                
                <div class="provider-card-actions">
                    <button class="btn btn-secondary btn-sm btn-test-conn" data-id="${p.provider_id}" style="padding: 6px 12px; font-size: 11px;">⚡ Test</button>
                    <button class="btn btn-secondary btn-sm btn-edit-provider" data-id="${p.provider_id}" style="padding: 6px 12px; font-size: 11px;">✏️ Edit</button>
                    <button class="btn btn-danger btn-sm btn-delete-provider" data-id="${p.provider_id}" style="padding: 6px 12px; font-size: 11px;">Delete</button>
                    
                    <label class="switch" style="margin-left: 12px;" title="${p.enabled ? 'Disable Provider' : 'Enable Provider'}">
                        <input type="checkbox" class="toggle-provider-status" data-id="${p.provider_id}" ${p.enabled ? 'checked' : ''}>
                        <span class="switch-slider"></span>
                    </label>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = `<div class="providers-grid">${cards}</div>`;
    
    // Bind Actions
    container.querySelectorAll('.btn-test-conn').forEach(btn => {
        btn.onclick = async () => {
            const pid = btn.dataset.id;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Testing';
            try {
                const res = await API.testProviderConnection(pid);
                if (res.ok) {
                    Toast.success('Connection Successful', `Latency: ${res.latency_ms}ms`);
                } else {
                    Toast.error('Connection Failed', `Type: ${res.error_type} - ${res.error_message}`);
                }
            } catch (err) {
                Toast.error('Connection Error', err.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '⚡ Test';
            }
        };
    });
    
    container.querySelectorAll('.btn-edit-provider').forEach(btn => {
        btn.onclick = () => {
            const pid = btn.dataset.id;
            const item = AppState.providersList.find(p => p.provider_id === pid);
            if (item) {
                openProviderFormModal(item, () => renderProvidersGrid(container, searchQuery));
            }
        };
    });
    
    container.querySelectorAll('.btn-delete-provider').forEach(btn => {
        btn.onclick = () => {
            const pid = btn.dataset.id;
            Modal.confirm(
                'Delete Provider',
                `Are you sure you want to remove the provider key "${pid}"? This cannot be undone and will immediately halt schedules to this account.`,
                async () => {
                    await API.deleteProvider(pid);
                    Toast.success('Provider Deleted', `Provider key "${pid}" was removed successfully.`);
                    AppState.providersList = AppState.providersList.filter(p => p.provider_id !== pid);
                    renderProvidersGrid(container, searchQuery);
                },
                'Delete Key',
                'danger'
            );
        };
    });
    
    container.querySelectorAll('.toggle-provider-status').forEach(input => {
        input.onchange = async () => {
            const pid = input.dataset.id;
            const checked = input.checked;
            input.disabled = true;
            try {
                if (checked) {
                    await API.enableProvider(pid);
                    Toast.success('Provider Enabled', `Switched routing state ON for ${pid}`);
                } else {
                    await API.disableProvider(pid);
                    Toast.success('Provider Disabled', `Switched routing state OFF for ${pid}`);
                }
                const item = AppState.providersList.find(p => p.provider_id === pid);
                if (item) item.enabled = checked;
            } catch (err) {
                Toast.error('Toggle Failed', err.message);
                input.checked = !checked; // revert
            } finally {
                input.disabled = false;
                renderProvidersGrid(container, searchQuery);
            }
        };
    });
}

function openProviderFormModal(provider = null, onSaveSuccess) {
    const isEdit = !!provider;
    const title = isEdit ? 'Edit Provider Settings' : 'Register New Provider Account';
    
    const html = `
        <form id="provider-form">
            <div class="form-group">
                <label for="prov-id">Unique Provider ID</label>
                <input type="text" id="prov-id" class="form-control" placeholder="e.g. nvidia-account-primary" required ${isEdit ? 'disabled' : ''} value="${isEdit ? escapeHtml(provider.provider_id) : ''}">
                <p style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Lowercase, alphanumeric, and hyphens only.</p>
            </div>
            
            <div class="form-group">
                <label for="prov-name">Friendly Display Name</label>
                <input type="text" id="prov-name" class="form-control" placeholder="e.g. NVIDIA NIM Primary" required value="${isEdit ? escapeHtml(provider.display_name) : ''}">
            </div>
            
            <div class="form-group">
                <label for="prov-url">Base API Endpoint URL</label>
                <input type="url" id="prov-url" class="form-control" placeholder="https://api.nvidia.com/v1" required value="${isEdit ? escapeHtml(provider.base_url) : 'https://integrate.api.nvidia.com/v1'}">
            </div>
            
            <div class="form-group">
                <label for="prov-key">${isEdit ? 'Update API Secret Key' : 'API Secret Key'}</label>
                <input type="password" id="prov-key" class="form-control" placeholder="${isEdit ? 'Leave blank to preserve current key' : 'nvapi-...'}" ${isEdit ? '' : 'required'}>
            </div>
            
            <div class="form-group checkbox-label" style="display: flex; align-items: center; gap: 8px;">
                <input type="checkbox" id="prov-enabled" ${!isEdit || provider.enabled ? 'checked' : ''}>
                <label for="prov-enabled" class="checkbox-label">Enable immediate request scheduling to this member</label>
            </div>
            
            <div class="modal-footer" style="padding-bottom: 0; padding-right: 0;">
                <button type="button" id="form-cancel-btn" class="btn btn-secondary">Cancel</button>
                <button type="submit" id="form-submit-btn" class="btn btn-primary">${isEdit ? 'Save Changes' : 'Register'}</button>
            </div>
        </form>
    `;
    
    Modal.show(title, html, (body, close) => {
        const cancelBtn = body.querySelector('#form-cancel-btn');
        const submitBtn = body.querySelector('#form-submit-btn');
        const form = body.querySelector('#provider-form');
        
        cancelBtn.onclick = close;
        
        form.onsubmit = async (e) => {
            e.preventDefault();
            
            const payload = {
                display_name: body.querySelector('#prov-name').value.trim(),
                base_url: body.querySelector('#prov-url').value.trim(),
                enabled: body.querySelector('#prov-enabled').checked,
            };
            
            const keyVal = body.querySelector('#prov-key').value;
            if (keyVal) {
                payload.api_key = keyVal;
            }
            
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner"></span> Saving...';
            
            try {
                if (isEdit) {
                    await API.updateProvider(provider.provider_id, payload);
                    Toast.success('Provider Saved', `Updated configuration for "${provider.provider_id}"`);
                } else {
                    payload.provider_id = body.querySelector('#prov-id').value.trim().toLowerCase();
                    payload.api_key = keyVal; // Required for create
                    
                    if (!payload.provider_id) throw new Error('Provider ID is required');
                    
                    await API.createProvider(payload);
                    Toast.success('Provider Created', `Successfully registered "${payload.provider_id}"`);
                }
                
                if (onSaveSuccess) await onSaveSuccess();
                close();
            } catch (err) {
                Toast.error('Operation Failed', err.message);
                submitBtn.disabled = false;
                submitBtn.textContent = isEdit ? 'Save Changes' : 'Register';
            }
        };
    });
}

// ===========================================================================
// PAGE 4: Model Mappings
// ===========================================================================
async function renderMappingsPage(container) {
    container.innerHTML = `
        <div class="actions-bar">
            <div style="font-size: 13px; color: var(--text-secondary);">
                Map downstream client models (e.g. <code>claude-sonnet</code>) to NVIDIA backend services.
            </div>
            <button id="btn-add-mapping" class="btn btn-primary">🗺️ Create Model Mapping</button>
        </div>
        <div id="mappings-content" class="card">
            ${Loader.renderSpinner()}
        </div>
    `;
    
    const mappingsContent = container.querySelector('#mappings-content');
    
    const loadMappings = async () => {
        mappingsContent.innerHTML = Loader.renderSkeletonTable(6, 4);
        try {
            const list = await API.listModelMappings();
            
            if (list.length === 0) {
                mappingsContent.innerHTML = EmptyState.render(
                    'No Model Mappings Configured',
                    'Requests matching unmapped models will route to settings defaults.',
                    '🗺️'
                );
                return;
            }
            
            let trs = '';
            list.forEach(m => {
                trs += `
                    <tr>
                        <td style="font-weight: 600; color: var(--accent-orange); font-family: monospace;">${escapeHtml(m.logical_model)}</td>
                        <td style="font-family: monospace;">${escapeHtml(m.nvidia_model)}</td>
                        <td style="font-size: 11px; color: var(--text-muted);">${new Date(m.updated_at).toLocaleString()}</td>
                        <td style="text-align: right;">
                            <button class="btn btn-secondary btn-sm btn-edit-mapping" data-logical="${m.logical_model}" data-nvidia="${m.nvidia_model}" style="padding: 6px 12px; font-size: 11px; margin-right: 8px;">✏️ Edit</button>
                            <button class="btn btn-danger btn-sm btn-delete-mapping" data-logical="${m.logical_model}" style="padding: 6px 12px; font-size: 11px;">Delete</button>
                        </td>
                    </tr>
                `;
            });
            
            mappingsContent.innerHTML = `
                <div class="table-responsive">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Client Model Name</th>
                                <th>Target NVIDIA Model String</th>
                                <th>Last Updated</th>
                                <th style="text-align: right;">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${trs}
                        </tbody>
                    </table>
                </div>
            `;
            
            // Bind actions
            mappingsContent.querySelectorAll('.btn-edit-mapping').forEach(btn => {
                btn.onclick = () => {
                    openMappingFormModal(btn.dataset.logical, btn.dataset.nvidia, loadMappings);
                };
            });
            
            mappingsContent.querySelectorAll('.btn-delete-mapping').forEach(btn => {
                btn.onclick = () => {
                    const lModel = btn.dataset.logical;
                    Modal.confirm(
                        'Delete Model Mapping',
                        `Remove mapping translation for "${lModel}"? Requests matching this name will revert to default.`,
                        async () => {
                            await API.deleteModelMapping(lModel);
                            Toast.success('Mapping Removed', `Model mapping for "${lModel}" was deleted successfully.`);
                            loadMappings();
                        },
                        'Delete Mapping',
                        'danger'
                    );
                };
            });
            
        } catch (err) {
            mappingsContent.innerHTML = EmptyState.render('Failed to Load Mappings', err.message, '⚠️');
        }
    };
    
    container.querySelector('#btn-add-mapping').onclick = () => {
        openMappingFormModal(null, null, loadMappings);
    };
    
    await loadMappings();
}

function openMappingFormModal(logicalModel = null, nvidiaModel = null, onSaveSuccess) {
    const isEdit = !!logicalModel;
    const title = isEdit ? 'Edit Target NVIDIA Model' : 'Create Logical Model Mapping';
    
    const html = `
        <form id="mapping-form">
            <div class="form-group">
                <label for="map-logical">Client Logical Model Name</label>
                <input type="text" id="map-logical" class="form-control" placeholder="e.g. claude-sonnet-4-20250514" required ${isEdit ? 'disabled' : ''} value="${isEdit ? escapeHtml(logicalModel) : ''}">
            </div>
            
            <div class="form-group">
                <label for="map-nvidia">NVIDIA Target Service Name</label>
                <input type="text" id="map-nvidia" class="form-control" placeholder="e.g. meta/llama3-70b-instruct" required value="${isEdit ? escapeHtml(nvidiaModel) : ''}">
            </div>
            
            <div class="modal-footer" style="padding-bottom: 0; padding-right: 0;">
                <button type="button" id="map-cancel-btn" class="btn btn-secondary">Cancel</button>
                <button type="submit" id="map-submit-btn" class="btn btn-primary">${isEdit ? 'Update Target' : 'Create Mapping'}</button>
            </div>
        </form>
    `;
    
    Modal.show(title, html, (body, close) => {
        const cancelBtn = body.querySelector('#map-cancel-btn');
        const submitBtn = body.querySelector('#map-submit-btn');
        const form = body.querySelector('#mapping-form');
        
        cancelBtn.onclick = close;
        
        form.onsubmit = async (e) => {
            e.preventDefault();
            
            const targetNvidia = body.querySelector('#map-nvidia').value.trim();
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner"></span> Saving...';
            
            try {
                if (isEdit) {
                    await API.updateModelMapping(logicalModel, targetNvidia);
                    Toast.success('Mapping Updated', `Logical model "${logicalModel}" target changed.`);
                } else {
                    const logicalName = body.querySelector('#map-logical').value.trim();
                    await API.createModelMapping({
                        logical_model: logicalName,
                        nvidia_model: targetNvidia
                    });
                    Toast.success('Mapping Created', `Mapped client "${logicalName}" to NVIDIA service.`);
                }
                
                if (onSaveSuccess) await onSaveSuccess();
                close();
            } catch (err) {
                Toast.error('Operation Failed', err.message);
                submitBtn.disabled = false;
                submitBtn.textContent = isEdit ? 'Update Target' : 'Create Mapping';
            }
        };
    });
}

// ===========================================================================
// PAGE 5: Request Logs
// ===========================================================================
async function renderLogsPage(container) {
    AppState.activeRequestsOffset = 0;
    
    container.innerHTML = `
        <div class="card">
            <div class="filters-row">
                <input type="text" id="log-search-id" class="form-control" placeholder="Search Request ID..." style="max-width: 240px; padding: 8px 12px; font-size: 13px;">
                
                <select id="log-filter-status" class="filter-select">
                    <option value="">All Status Codes</option>
                    <option value="200">Success (200)</option>
                    <option value="499">Client Cancelled (499)</option>
                    <option value="500">Internal Error (500)</option>
                    <option value="502">Bad Gateway (502)</option>
                </select>
                
                <select id="log-filter-provider" class="filter-select">
                    <option value="">All Providers</option>
                    <!-- Populated dynamically -->
                </select>
                
                <button id="btn-reset-filters" class="btn btn-secondary" style="padding: 8px 14px; font-size: 13px;">Reset</button>
            </div>
            
            <div id="logs-table-container">
                ${Loader.renderSpinner()}
            </div>
        </div>
    `;
    
    const logsContainer = container.querySelector('#logs-table-container');
    const searchInput = container.querySelector('#log-search-id');
    const statusSelect = container.querySelector('#log-filter-status');
    const providerSelect = container.querySelector('#log-filter-provider');
    const resetBtn = container.querySelector('#btn-reset-filters');
    
    // Populating provider options
    try {
        const providers = await API.listProviders();
        providers.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.provider_id;
            opt.textContent = p.display_name;
            providerSelect.appendChild(opt);
        });
    } catch {
        // Suppress failure silently
    }
    
    const loadLogs = async (offset = 0) => {
        AppState.activeRequestsOffset = offset;
        logsContainer.innerHTML = Loader.renderSkeletonTable(AppState.logsLimit, 6);
        
        try {
            const query = {
                limit: AppState.logsLimit,
                offset: AppState.activeRequestsOffset,
                status: statusSelect.value || null,
                providerId: providerSelect.value || null
            };
            
            let list = [];
            const searchVal = searchInput.value.trim();
            if (searchVal) {
                // Compatibility mode: retrieve single log via combined API
                const singleLog = await API.getRequestDetails(searchVal).catch(() => null);
                if (singleLog?.request) {
                    list = [singleLog.request];
                }
            } else {
                list = await API.getRequestLogs(query);
            }
            
            if (list.length === 0) {
                logsContainer.innerHTML = EmptyState.render('No logs found', 'Try adjusting filter settings or query terms.', '📝');
                return;
            }
            
            let trs = '';
            list.forEach(r => {
                let badgeClass = 'badge-disabled';
                if (r.status_code === 200) badgeClass = 'badge-success';
                else if (r.status_code === 499) badgeClass = 'badge-warning';
                else if (r.status_code >= 500) badgeClass = 'badge-error';
                
                const streamBadge = r.stream 
                    ? '<span class="badge badge-info" style="font-size: 9px; padding: 2px 5px;">SSE</span>' 
                    : '<span class="badge badge-disabled" style="font-size: 9px; padding: 2px 5px;">REST</span>';
                
                trs += `
                    <tr class="log-row" data-id="${r.request_id}" style="cursor: pointer;">
                        <td style="font-family: monospace; font-size: 12px; font-weight: 600; color: var(--accent-orange);">${escapeHtml(r.request_id)}</td>
                        <td style="font-family: monospace; font-size: 13px;">${escapeHtml(r.model)}</td>
                        <td>${streamBadge}</td>
                        <td style="font-family: monospace; font-size: 12px;">${escapeHtml(r.provider_id || 'unknown')}</td>
                        <td><span class="badge ${badgeClass}">${r.status_code || '---'}</span></td>
                        <td><strong>${r.latency_ms !== null ? r.latency_ms.toLocaleString() + ' ms' : '---'}</strong></td>
                        <td style="font-size: 11px; color: var(--text-secondary);">${new Date(r.created_at).toLocaleString()}</td>
                    </tr>
                `;
            });
            
            logsContainer.innerHTML = `
                <div class="table-responsive">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Request ID</th>
                                <th>Model</th>
                                <th>Mode</th>
                                <th>Provider ID</th>
                                <th>Status</th>
                                <th>Latency</th>
                                <th>Timestamp</th>
                            </tr>
                        </thead>
                        <tbody>${trs}</tbody>
                    </table>
                </div>
            `;
            
            // Add pagination component
            if (!searchVal) {
                const pagination = renderPagination(
                    AppState.activeRequestsOffset,
                    AppState.logsLimit,
                    list.length,
                    loadLogs
                );
                logsContainer.appendChild(pagination);
            }
            
            // Bind row details modal click
            logsContainer.querySelectorAll('.log-row').forEach(row => {
                row.onclick = () => {
                    openLogDetailsModal(row.dataset.id);
                };
            });
            
        } catch (err) {
            logsContainer.innerHTML = EmptyState.render('Failed to fetch request history', err.message, '⚠️');
        }
    };
    
    // Bind triggers
    statusSelect.onchange = () => loadLogs(0);
    providerSelect.onchange = () => loadLogs(0);
    
    let searchTimeout = null;
    searchInput.oninput = () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => loadLogs(0), 400);
    };
    
    resetBtn.onclick = () => {
        searchInput.value = '';
        statusSelect.value = '';
        providerSelect.value = '';
        loadLogs(0);
    };
    
    await loadLogs(0);
}

async function openLogDetailsModal(requestId) {
    Modal.show('Retrieving lifecycle records...', Loader.renderSpinner());
    
    try {
        const details = await API.getRequestDetails(requestId);
        
        let statusBadge = 'badge-disabled';
        if (details.request?.status_code === 200) statusBadge = 'badge-success';
        else if (details.request?.status_code === 499) statusBadge = 'badge-warning';
        else if (details.request?.status_code >= 500) statusBadge = 'badge-error';
        
        const html = `
            <div class="log-details-grid">
                <div style="display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; border-bottom: 1px solid var(--border-color); padding-bottom: 16px;">
                    <div>
                        <span style="font-size: 11px; color: var(--text-muted);">REQUEST ID</span>
                        <h3 style="font-family: monospace; color: var(--accent-orange); font-size: 15px;">${escapeHtml(requestId)}</h3>
                    </div>
                    <div>
                        <span style="font-size: 11px; color: var(--text-muted); display: block; text-align: right;">STATUS CODE</span>
                        <span class="badge ${statusBadge}" style="margin-top: 4px;">${details.request?.status_code || '---'}</span>
                    </div>
                    <div>
                        <span style="font-size: 11px; color: var(--text-muted); display: block; text-align: right;">LATENCY</span>
                        <strong style="display: block; margin-top: 4px;">${details.request?.latency_ms !== null ? details.request?.latency_ms + ' ms' : '---'}</strong>
                    </div>
                    <div>
                        <span style="font-size: 11px; color: var(--text-muted); display: block; text-align: right;">PROVIDER</span>
                        <strong style="display: block; margin-top: 4px; font-family: monospace; font-size: 12px;">${escapeHtml(details.request?.provider_id || 'unknown')}</strong>
                    </div>
                </div>
                
                <div class="log-details-section">
                    <h4>Request Parameters</h4>
                    <pre>Model: ${escapeHtml(details.request?.model)}
Format: ${details.request?.stream ? 'Streaming (SSE)' : 'Unary (JSON)'}
Created At: ${new Date(details.request?.created_at).toLocaleString()}</pre>
                </div>
                
                ${details.usage ? `
                <div class="log-details-section">
                    <h4>Token Metrics</h4>
                    <pre>Input Tokens: ${details.usage.input_tokens || 0}
Output Tokens: ${details.usage.output_tokens || 0}
Total Usage: ${details.usage.total_tokens || 0} tokens</pre>
                </div>
                ` : ''}
                
                ${details.error ? `
                <div class="log-details-section" style="border: 1px solid var(--error-red); border-radius: 6px; padding: 12px; background-color: rgba(239, 68, 68, 0.05);">
                    <h4 style="color: var(--error-red); margin-bottom: 4px;">Failure Details (Type: ${escapeHtml(details.error.error_type)})</h4>
                    <p style="font-family: monospace; font-size: 12px; color: var(--text-secondary); white-space: pre-wrap;">${escapeHtml(details.error.error_message)}</p>
                </div>
                ` : ''}
                
                ${details.response?.content ? `
                <div class="log-details-section">
                    <h4>Response Contents (Collapsible)</h4>
                    <pre style="max-height: 200px;">${escapeHtml(details.response.content)}</pre>
                </div>
                ` : ''}
                
                <div style="display: flex; justify-content: flex-end; margin-top: 10px;">
                    <button id="btn-close-log-details" class="btn btn-secondary">Close Details</button>
                </div>
            </div>
        `;
        
        Modal.show(`Log Lifecycle: ${requestId.substring(0, 12)}...`, html, (body, close) => {
            body.querySelector('#btn-close-log-details').onclick = close;
        });
        
    } catch (err) {
        Modal.show('Details Unavailable', `<div style="color: var(--error-red); font-size: 13px;">Failed to load log metrics: ${err.message}</div>`);
    }
}

// ===========================================================================
// PAGE 6: Error Logs
// ===========================================================================
async function renderErrorsPage(container) {
    AppState.activeErrorsOffset = 0;
    
    container.innerHTML = `
        <div class="card">
            <div class="filters-row">
                <select id="err-filter-type" class="filter-select">
                    <option value="">All Errors Types</option>
                    <option value="rate_limited">rate_limited</option>
                    <option value="provider_error">provider_error</option>
                    <option value="unauthorized">unauthorized</option>
                    <option value="validation_error">validation_error</option>
                    <option value="timeout">timeout</option>
                </select>
                
                <select id="err-filter-provider" class="filter-select">
                    <option value="">All Providers</option>
                    <!-- Populated dynamically -->
                </select>
                
                <button id="btn-err-reset" class="btn btn-secondary" style="padding: 8px 14px; font-size: 13px;">Clear Filters</button>
            </div>
            
            <div id="errors-table-container">
                ${Loader.renderSpinner()}
            </div>
        </div>
    `;
    
    const errsContainer = container.querySelector('#errors-table-container');
    const typeSelect = container.querySelector('#err-filter-type');
    const providerSelect = container.querySelector('#err-filter-provider');
    const resetBtn = container.querySelector('#btn-err-reset');
    
    try {
        const providers = await API.listProviders();
        providers.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.provider_id;
            opt.textContent = p.display_name;
            providerSelect.appendChild(opt);
        });
    } catch {
        // Suppress silently
    }
    
    const loadErrors = async (offset = 0) => {
        AppState.activeErrorsOffset = offset;
        errsContainer.innerHTML = Loader.renderSkeletonTable(AppState.logsLimit, 5);
        
        try {
            const query = {
                limit: AppState.logsLimit,
                offset: AppState.activeErrorsOffset,
                errorType: typeSelect.value || null,
                providerId: providerSelect.value || null
            };
            
            const list = await API.getErrorLogs(query);
            
            if (list.length === 0) {
                errsContainer.innerHTML = EmptyState.render('No errors logged', 'All systems operating within acceptable tolerances.', '👍');
                return;
            }
            
            let trs = '';
            list.forEach(e => {
                trs += `
                    <tr>
                        <td style="font-family: monospace; font-size: 11px; font-weight: 600; color: var(--accent-orange); cursor: pointer;" class="err-req-link" data-id="${e.request_id}">${escapeHtml(e.request_id)}</td>
                        <td><span class="badge badge-error">${escapeHtml(e.error_type)}</span></td>
                        <td style="font-family: monospace; font-size: 12px; color: var(--text-secondary); max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(e.error_message)}">${escapeHtml(e.error_message)}</td>
                        <td style="font-family: monospace; font-size: 11px;">${escapeHtml(e.provider_id || 'unknown')}</td>
                        <td style="font-size: 11px; color: var(--text-muted);">${new Date(e.created_at).toLocaleString()}</td>
                    </tr>
                `;
            });
            
            errsContainer.innerHTML = `
                <div class="table-responsive">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Request ID</th>
                                <th>Failure Type</th>
                                <th>Message</th>
                                <th>Provider</th>
                                <th>Timestamp</th>
                            </tr>
                        </thead>
                        <tbody>${trs}</tbody>
                    </table>
                </div>
            `;
            
            // Add Pagination
            const pagination = renderPagination(
                AppState.activeErrorsOffset,
                AppState.logsLimit,
                list.length,
                loadErrors
            );
            errsContainer.appendChild(pagination);
            
            // Bind request ID click links
            errsContainer.querySelectorAll('.err-req-link').forEach(link => {
                link.onclick = () => {
                    openLogDetailsModal(link.dataset.id);
                };
            });
            
        } catch (err) {
            errsContainer.innerHTML = EmptyState.render('Failed to fetch error lists', err.message, '⚠️');
        }
    };
    
    typeSelect.onchange = () => loadErrors(0);
    providerSelect.onchange = () => loadErrors(0);
    resetBtn.onclick = () => {
        typeSelect.value = '';
        providerSelect.value = '';
        loadErrors(0);
    };
    
    await loadErrors(0);
}

// ===========================================================================
// PAGE 7: Usage Analytics
// ===========================================================================
async function renderUsagePage(container) {
    container.innerHTML = `
        <div class="dashboard-grid">
            <div class="stat-card">
                <span class="stat-label">Cumulative Token Frequencies</span>
                <span class="stat-value" id="cumulative-tokens">...</span>
                <span class="stat-footer">Across input & output exchanges</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Total Requests Run</span>
                <span class="stat-value" id="total-requests">...</span>
                <span class="stat-footer">Stored since schema setup</span>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(480px, 1fr)); gap: 24px;">
            <div class="card">
                <h3 class="card-title" style="margin-bottom: 20px;">Daily Request Volumes</h3>
                <div id="chart-daily-volume" style="min-height: 260px;">${Loader.renderSpinner()}</div>
            </div>
            
            <div class="card">
                <h3 class="card-title" style="margin-bottom: 20px;">Allocation by Provider (Tokens)</h3>
                <div id="chart-provider-alloc" style="min-height: 260px;">${Loader.renderSpinner()}</div>
            </div>
            
            <div class="card">
                <h3 class="card-title" style="margin-bottom: 20px;">Allocation by Client Model (Tokens)</h3>
                <div id="chart-model-alloc" style="min-height: 260px;">${Loader.renderSpinner()}</div>
            </div>
        </div>
    `;
    
    try {
        const usage = await API.getUsageSummary();
        
        // Populate stats
        container.querySelector('#cumulative-tokens').textContent = (usage?.total_tokens || 0).toLocaleString();
        container.querySelector('#total-requests').textContent = (usage?.total_requests || 0).toLocaleString();
        
        // 1. Render Daily requests chart
        const dailyData = usage.daily_usage || [];
        ChartRenderer.renderLineChart(
            container.querySelector('#chart-daily-volume'),
            dailyData,
            'day',
            'request_count',
            'calls'
        );
        
        // 2. Render Provider usage chart
        const providerData = usage.provider_usage || [];
        ChartRenderer.renderBarChart(
            container.querySelector('#chart-provider-alloc'),
            providerData,
            'provider_id',
            'total_tokens',
            ' t'
        );
        
        // 3. Render Model allocation Donut
        const modelData = usage.model_usage || [];
        ChartRenderer.renderDonutChart(
            container.querySelector('#chart-model-alloc'),
            modelData,
            'model',
            'total_tokens',
            ' t'
        );
        
    } catch (err) {
        Toast.error('Analytics Error', 'Failed to render charts: ' + err.message);
    }
}

// ===========================================================================
// PAGE 8: Settings
// ===========================================================================
async function renderSettingsPage(container) {
    container.innerHTML = Loader.renderSpinner();
    
    try {
        const settings = await API.getSettings();
        AppState.settingsCache = settings;
        
        container.innerHTML = `
            <div class="card" style="max-width: 720px; margin: 0 auto;">
                <form id="settings-form">
                    
                    <div style="border-bottom: 1px solid var(--border-color); padding-bottom: 16px; margin-bottom: 24px;">
                        <h3 style="font-size: 16px; font-weight: 600;">System Configuration</h3>
                        <p style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">Dynamic parameters overridden from SQLite settings. Administrative access only.</p>
                    </div>
                    
                    <div class="form-group">
                        <label for="set-default-model">Default Gateway Model</label>
                        <input type="text" id="set-default-model" class="form-control" value="${escapeHtml(settings.default_model)}" required>
                        <p style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Fall-back target when mapping translations aren't triggered.</p>
                    </div>
                    
                    <div class="form-group">
                        <label for="set-scheduler-mode">Scheduler Selection Mode</label>
                        <select id="set-scheduler-mode" class="filter-select" style="width: 100%; padding: 12px; font-size: 14px;">
                            <option value="health-first" ${settings.scheduler_mode === 'health-first' ? 'selected' : ''}>health-first (Preferred)</option>
                            <option value="least-busy" ${settings.scheduler_mode === 'least-busy' ? 'selected' : ''}>least-busy (Least active requests)</option>
                            <option value="round-robin" ${settings.scheduler_mode === 'round-robin' ? 'selected' : ''}>round-robin</option>
                        </select>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                        <div class="form-group">
                            <label for="set-retry-count">Gateway Retry Limits</label>
                            <input type="number" id="set-retry-count" class="form-control" min="0" max="10" value="${settings.retry_count}" required>
                        </div>
                        <div class="form-group">
                            <label for="set-timeout">Provider Request Timeout (seconds)</label>
                            <input type="number" id="set-timeout" class="form-control" min="1" max="300" value="${settings.timeout_seconds}" required>
                        </div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px;">
                        <div class="form-group checkbox-label" style="display: flex; align-items: center; gap: 8px;">
                            <input type="checkbox" id="set-streaming-enabled" ${settings.streaming_enabled ? 'checked' : ''}>
                            <label for="set-streaming-enabled" class="checkbox-label">Enable SSE Streaming</label>
                        </div>
                        <div class="form-group checkbox-label" style="display: flex; align-items: center; gap: 8px;">
                            <input type="checkbox" id="set-thinking-enabled" ${settings.thinking_enabled ? 'checked' : ''}>
                            <label for="set-thinking-enabled" class="checkbox-label">Support Thinking Blocks</label>
                        </div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                        <div class="form-group">
                            <label for="set-max-req-size">Max Payload size (MB)</label>
                            <input type="number" id="set-max-req-size" class="form-control" min="1" max="100" value="${settings.max_request_size_mb}" required>
                        </div>
                        <div class="form-group">
                            <label for="set-log-level">Internal Log Level</label>
                            <select id="set-log-level" class="filter-select" style="width: 100%; padding: 12px; font-size: 14px;">
                                <option value="DEBUG" ${settings.log_level === 'DEBUG' ? 'selected' : ''}>DEBUG</option>
                                <option value="INFO" ${settings.log_level === 'INFO' ? 'selected' : ''}>INFO</option>
                                <option value="WARNING" ${settings.log_level === 'WARNING' ? 'selected' : ''}>WARNING</option>
                                <option value="ERROR" ${settings.log_level === 'ERROR' ? 'selected' : ''}>ERROR</option>
                            </select>
                        </div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; border-top: 1px solid var(--border-color); padding-top: 20px; margin-top: 10px;">
                        <div class="form-group">
                            <label>Server Bind Host (Env only)</label>
                            <input type="text" class="form-control" value="${escapeHtml(settings.host)}" disabled>
                        </div>
                        <div class="form-group">
                            <label>Server Port (Env only)</label>
                            <input type="text" class="form-control" value="${settings.port}" disabled>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>SQLite Path (Env only)</label>
                        <input type="text" class="form-control" value="${escapeHtml(settings.database_path)}" disabled style="font-family: monospace;">
                    </div>
                    
                    <div style="display: flex; justify-content: flex-end; gap: 12px; border-top: 1px solid var(--border-color); padding-top: 20px; margin-top: 10px;">
                        <button type="button" id="btn-reset-settings" class="btn btn-secondary">Reset Fields</button>
                        <button type="submit" id="btn-save-settings" class="btn btn-primary">Save Settings</button>
                    </div>
                </form>
            </div>
        `;
        
        const form = container.querySelector('#settings-form');
        const resetBtn = container.querySelector('#btn-reset-settings');
        const saveBtn = container.querySelector('#btn-save-settings');
        
        resetBtn.onclick = () => {
            // Re-render setting inputs to clear modifications
            renderSettingsPage(container);
            Toast.warning('Reset', 'Settings modifications discarded.');
        };
        
        form.onsubmit = (e) => {
            e.preventDefault();
            
            const payload = {
                default_model: container.querySelector('#set-default-model').value.trim(),
                scheduler_mode: container.querySelector('#set-scheduler-mode').value,
                retry_count: parseInt(container.querySelector('#set-retry-count').value),
                timeout_seconds: parseInt(container.querySelector('#set-timeout').value),
                streaming_enabled: container.querySelector('#set-streaming-enabled').checked,
                thinking_enabled: container.querySelector('#set-thinking-enabled').checked,
                max_request_size_mb: parseInt(container.querySelector('#set-max-req-size').value),
                log_level: container.querySelector('#set-log-level').value,
            };
            
            Modal.confirm(
                'Save Settings Overrides',
                'Confirm updates to backend configuration? Modifications will immediately apply to incoming client traffic.',
                async () => {
                    saveBtn.disabled = true;
                    saveBtn.innerHTML = '<span class="spinner"></span> Saving...';
                    try {
                        const updated = await API.updateSettings(payload);
                        Toast.success('Settings Saved', 'Configuration flushed to DB and cache reloaded.');
                        AppState.settingsCache = updated;
                    } catch (err) {
                        Toast.error('Save Failed', err.message);
                    } finally {
                        saveBtn.disabled = false;
                        saveBtn.textContent = 'Save Settings';
                    }
                },
                'Apply Updates'
            );
        };
        
    } catch (err) {
        container.innerHTML = EmptyState.render('Failed to Load Configuration', err.message, '⚠️');
    }
}

// ===========================================================================
// Global Bootloader
// ===========================================================================
function initApp() {
    // 1. Set Router Events
    window.addEventListener('hashchange', dispatchRoute);
    
    // 2. Intercept unauthorized api events
    window.addEventListener('aegis-unauthorized', () => {
        window.location.hash = '#/login';
        Toast.error('Session Expired', 'Please re-authenticate to continue.');
    });
    
    // 3. Bind sidebar responsive toggle
    const toggleBtn = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    
    if (toggleBtn && sidebar) {
        toggleBtn.onclick = (e) => {
            e.stopPropagation();
            sidebar.classList.toggle('open');
        };
        
        document.body.onclick = () => {
            sidebar.classList.remove('open');
        };
        
        sidebar.onclick = (e) => {
            e.stopPropagation();
        };
    }
    
    // 4. Bind logout
    const logoutBtn = document.getElementById('btn-logout');
    if (logoutBtn) {
        logoutBtn.onclick = () => {
            Modal.confirm(
                'Confirm Logout',
                'Do you wish to end your AEGIS Control Center session?',
                async () => {
                    Auth.clearToken();
                    Toast.success('Signed Out', 'Your session was cleared.');
                    window.location.hash = '#/login';
                },
                'Logout',
                'danger'
            );
        };
    }
    
    // 5. Run Initial dispatch
    dispatchRoute();
}

// Start application
document.addEventListener('DOMContentLoaded', initApp);
