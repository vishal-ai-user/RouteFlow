/* Centralized API client layer for AEGIS Control Center
   Handles auth state, token headers, fetch requests, and unified error mapping.
*/

const TOKEN_KEY = 'aegis_bearer_token';

export const Auth = {
    getToken() {
        return localStorage.getItem(TOKEN_KEY);
    },
    
    setToken(token) {
        if (token) {
            localStorage.setItem(TOKEN_KEY, token);
        }
    },
    
    clearToken() {
        localStorage.removeItem(TOKEN_KEY);
    },
    
    isAuthenticated() {
        const token = this.getToken();
        return token !== null && token !== '';
    }
};

/**
 * Unified request wrapper with Bearer token authentication and error interception.
 */
async function apiRequest(path, options = {}) {
    const token = Auth.getToken();
    
    // Set headers
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {})
    };
    
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const config = {
        ...options,
        headers
    };
    
    try {
        const response = await fetch(path, config);
        
        // Handle unauthorized or forbidden status codes (401 / 403)
        if (response.status === 401 || response.status === 403) {
            Auth.clearToken();
            // Fire event so app.js can redirect to login immediately
            window.dispatchEvent(new CustomEvent('aegis-unauthorized'));
            throw new Error('Session expired or unauthorized. Please log in again.');
        }
        
        if (!response.ok) {
            let errorMessage = 'An error occurred';
            try {
                const errData = await response.json();
                errorMessage = errData?.detail || errData?.error?.message || errorMessage;
            } catch {
                errorMessage = `HTTP error ${response.status}: ${response.statusText}`;
            }
            const error = new Error(errorMessage);
            error.status = response.status;
            throw error;
        }
        
        if (response.status === 204) {
            return null;
        }
        
        return await response.json();
    } catch (err) {
        // Console log for diagnostics, but do not leak secrets
        console.error(`API Error on ${path}:`, err.message);
        throw err;
    }
}

export const API = {
    // 1. Dashboard & Health
    async getDashboardSummary() {
        return await apiRequest('/api/dashboard/summary');
    },
    
    async getControlHealth() {
        return await apiRequest('/api/control/health');
    },
    
    // 2. Providers CRUD
    async listProviders() {
        return await apiRequest('/api/providers');
    },
    
    async createProvider(providerData) {
        return await apiRequest('/api/providers', {
            method: 'POST',
            body: JSON.stringify(providerData)
        });
    },
    
    async updateProvider(providerId, providerData) {
        return await apiRequest(`/api/providers/${providerId}`, {
            method: 'PUT',
            body: JSON.stringify(providerData)
        });
    },
    
    async deleteProvider(providerId) {
        return await apiRequest(`/api/providers/${providerId}`, {
            method: 'DELETE'
        });
    },
    
    async enableProvider(providerId) {
        return await apiRequest(`/api/providers/${providerId}/enable`, {
            method: 'POST'
        });
    },
    
    async disableProvider(providerId) {
        return await apiRequest(`/api/providers/${providerId}/disable`, {
            method: 'POST'
        });
    },
    
    async testProviderConnection(providerId) {
        return await apiRequest(`/api/providers/${providerId}/test`, {
            method: 'POST'
        });
    },
    
    // 3. Model Mappings CRUD
    async listModelMappings() {
        return await apiRequest('/api/model_mappings');
    },
    
    async createModelMapping(mappingData) {
        return await apiRequest('/api/model_mappings', {
            method: 'POST',
            body: JSON.stringify(mappingData)
        });
    },
    
    async updateModelMapping(logicalModel, targetModel) {
        return await apiRequest(`/api/model_mappings/${logicalModel}`, {
            method: 'PUT',
            body: JSON.stringify({ nvidia_model: targetModel })
        });
    },
    
    async deleteModelMapping(logicalModel) {
        return await apiRequest(`/api/model_mappings/${logicalModel}`, {
            method: 'DELETE'
        });
    },
    
    // 4. Logs (Paginated & Details)
    async getRequestLogs({ limit = 20, offset = 0, providerId = null, status = null, start_date = null, end_date = null } = {}) {
        const params = new URLSearchParams({ limit, offset });
        if (providerId) params.append('provider_id', providerId);
        if (status) params.append('status', status);
        if (start_date) params.append('start_date', start_date);
        if (end_date) params.append('end_date', end_date);
        
        return await apiRequest(`/api/logs/requests?${params.toString()}`);
    },
    
    async getRequestDetails(requestId) {
        return await apiRequest(`/api/logs/requests/${requestId}`);
    },
    
    async getErrorLogs({ limit = 20, offset = 0, errorType = null, providerId = null, start_date = null, end_date = null } = {}) {
        const params = new URLSearchParams({ limit, offset });
        if (errorType) params.append('error_type', errorType);
        if (providerId) params.append('provider_id', providerId);
        if (start_date) params.append('start_date', start_date);
        if (end_date) params.append('end_date', end_date);
        
        return await apiRequest(`/api/logs/errors?${params.toString()}`);
    },
    
    // 5. Usage Summaries
    async getUsageSummary() {
        return await apiRequest('/api/usage/summary');
    },
    
    // 6. Settings
    async getSettings() {
        return await apiRequest('/api/settings');
    },
    
    async updateSettings(settingsData) {
        return await apiRequest('/api/settings', {
            method: 'PUT',
            body: JSON.stringify(settingsData)
        });
    }
};
