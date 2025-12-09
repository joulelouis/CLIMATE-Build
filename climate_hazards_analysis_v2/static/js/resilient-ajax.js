/**
 * Resilient AJAX handler with retry mechanisms and offline support
 * Provides robust error handling for all backend communications
 */

class ResilientAjaxHandler {
    constructor(options = {}) {
        this.options = {
            maxRetries: 3,
            retryDelay: 1000,
            timeout: 30000,
            enableOfflineMode: true,
            cacheKey: 'climaterisk_ajax_cache',
            ...options
        };

        this.requestQueue = [];
        this.isOnline = navigator.onLine;
        this.cache = new Map();
        this.setupEventListeners();
        this.loadCache();
    }

    setupEventListeners() {
        window.addEventListener('online', () => {
            this.isOnline = true;
            console.log('Network connection restored');
            this.processQueue();
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
            console.log('Network connection lost');
        });

        // Handle page visibility changes
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.isOnline) {
                this.processQueue();
            }
        });
    }

    async request(url, options = {}) {
        const requestId = this.generateRequestId();
        const requestOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken(),
                'X-Request-ID': requestId,
                ...options.headers
            },
            timeout: this.options.timeout,
            ...options
        };

        try {
            // Check if we're offline
            if (!this.isOnline && this.options.enableOfflineMode) {
                return this.handleOfflineRequest(url, requestOptions);
            }

            // Check cache for GET requests
            if (requestOptions.method === 'GET' && this.hasCache(url, requestOptions)) {
                return this.getCachedResponse(url, requestOptions);
            }

            // Attempt request with retry logic
            const response = await this.executeWithRetry(url, requestOptions);

            // Cache successful GET responses
            if (requestOptions.method === 'GET' && response.ok) {
                this.setCache(url, requestOptions, response.clone());
            }

            return response;

        } catch (error) {
            console.error('Request failed:', error);
            throw error;
        }
    }

    async executeWithRetry(url, options, attempt = 1) {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), options.timeout);

            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Reset retry counter on success
            this.resetRetryCounter(url);

            // Check if response is JSON
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();

                // Check for application-level errors
                if (data.success === false) {
                    throw new Error(data.error || 'Request failed');
                }

                return {
                    ok: true,
                    status: response.status,
                    data: data,
                    headers: response.headers
                };
            }

            return response;

        } catch (error) {
            console.error(`Attempt ${attempt} failed for ${url}:`, error);

            // Don't retry if it's an abort or client error (4xx)
            if (error.name === 'AbortError' || (error.status && error.status >= 400 && error.status < 500)) {
                throw error;
            }

            // Check if we should retry
            if (attempt < this.options.maxRetries) {
                const delay = this.calculateRetryDelay(attempt);
                console.log(`Retrying in ${delay}ms (attempt ${attempt + 1}/${this.options.maxRetries})`);

                await this.delay(delay);
                return this.executeWithRetry(url, options, attempt + 1);
            }

            // If all retries failed, queue for later if offline
            if (!this.isOnline && this.options.enableOfflineMode && options.method !== 'GET') {
                return this.queueRequest(url, options);
            }

            throw error;
        }
    }

    calculateRetryDelay(attempt) {
        // Exponential backoff with jitter
        const baseDelay = this.options.retryDelay;
        const exponentialDelay = baseDelay * Math.pow(2, attempt - 1);
        const jitter = Math.random() * 0.3 * exponentialDelay; // 30% jitter
        return exponentialDelay + jitter;
    }

    generateRequestId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }

    async handleOfflineRequest(url, options) {
        console.log('Handling offline request:', url);

        if (options.method === 'GET') {
            // Try to return cached data
            if (this.hasCache(url, options)) {
                console.log('Returning cached data for offline GET request');
                return this.getCachedResponse(url, options);
            }
        } else {
            // Queue POST/PUT/DELETE requests for later
            return this.queueRequest(url, options);
        }

        throw new Error('No cached data available and offline');
    }

    queueRequest(url, options) {
        const requestId = this.generateRequestId();
        const queuedRequest = {
            id: requestId,
            url,
            options,
            timestamp: Date.now()
        };

        this.requestQueue.push(queuedRequest);
        this.saveQueue();

        console.log('Request queued for later:', requestId);

        // Return a mock response
        return {
            ok: false,
            queued: true,
            requestId,
            message: 'Request queued - will be processed when connection is restored'
        };
    }

    async processQueue() {
        if (this.requestQueue.length === 0) return;

        console.log(`Processing ${this.requestQueue.length} queued requests`);

        const queue = [...this.requestQueue];
        this.requestQueue = [];

        for (const request of queue) {
            try {
                console.log('Processing queued request:', request.id);
                await this.executeWithRetry(request.url, request.options);
            } catch (error) {
                console.error('Failed to process queued request:', request.id, error);
                // Re-queue failed requests
                this.requestQueue.push(request);
            }
        }

        this.saveQueue();
    }

    // Cache management
    hasCache(url, options) {
        const cacheKey = this.getCacheKey(url, options);
        const cached = this.cache.get(cacheKey);

        if (!cached) return false;

        // Check if cache is still valid (5 minutes)
        const maxAge = 5 * 60 * 1000; // 5 minutes
        return (Date.now() - cached.timestamp) < maxAge;
    }

    getCachedResponse(url, options) {
        const cacheKey = this.getCacheKey(url, options);
        const cached = this.cache.get(cacheKey);

        if (!cached) throw new Error('No cached response');

        console.log('Returning cached response for:', url);
        return Promise.resolve(cached.response);
    }

    setCache(url, options, response) {
        const cacheKey = this.getCacheKey(url, options);

        // Limit cache size
        if (this.cache.size > 100) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }

        this.cache.set(cacheKey, {
            response: response,
            timestamp: Date.now()
        });

        this.saveCache();
    }

    getCacheKey(url, options) {
        // Create a cache key based on URL and relevant options
        const keyData = {
            url,
            method: options.method || 'GET',
            headers: options.headers || {}
        };

        return btoa(JSON.stringify(keyData));
    }

    loadCache() {
        try {
            const cached = localStorage.getItem(this.options.cacheKey);
            if (cached) {
                const data = JSON.parse(cached);
                this.cache = new Map(Object.entries(data));
                console.log('Loaded AJAX cache from localStorage');
            }
        } catch (error) {
            console.warn('Failed to load AJAX cache:', error);
        }
    }

    saveCache() {
        try {
            const data = Object.fromEntries(this.cache);
            localStorage.setItem(this.options.cacheKey, JSON.stringify(data));
        } catch (error) {
            console.warn('Failed to save AJAX cache:', error);
        }
    }

    saveQueue() {
        try {
            localStorage.setItem('climaterisk_request_queue', JSON.stringify(this.requestQueue));
        } catch (error) {
            console.warn('Failed to save request queue:', error);
        }
    }

    loadQueue() {
        try {
            const queued = localStorage.getItem('climaterisk_request_queue');
            if (queued) {
                this.requestQueue = JSON.parse(queued);
                console.log(`Loaded ${this.requestQueue.length} queued requests`);
            }
        } catch (error) {
            console.warn('Failed to load request queue:', error);
        }
    }

    resetRetryCounter(url) {
        // Could implement per-URL retry tracking here
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // Utility methods for specific API endpoints
    async saveTableChanges(changes) {
        return this.request('/climate-hazards-analysis-v2/save-table-changes/', {
            method: 'POST',
            body: JSON.stringify({
                changes: changes,
                csrf_token: this.getCSRFToken()
            })
        });
    }

    async resetTableData() {
        return this.request('/climate-hazards-analysis-v2/reset-table-data/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCSRFToken()
            }
        });
    }

    async getFacilityData(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = `/climate-hazards-analysis-v2/api/facility-data/${queryString ? '?' + queryString : ''}`;

        return this.request(url);
    }

    // Status indicators
    showNetworkStatus() {
        const indicator = document.createElement('div');
        indicator.id = 'network-status';
        indicator.className = 'position-fixed top-0 end-0 p-3';
        indicator.style.zIndex = '9999';
        indicator.innerHTML = `
            <div class="toast align-items-center ${this.isOnline ? 'text-bg-success' : 'text-bg-warning'}" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        ${this.isOnline ? 'Connected' : 'Offline - Changes will be synced when connection is restored'}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        document.body.appendChild(indicator);

        const toast = new bootstrap.Toast(indicator.querySelector('.toast'));
        toast.show();

        setTimeout(() => {
            document.body.removeChild(indicator);
        }, 5000);
    }

    clearCache() {
        this.cache.clear();
        localStorage.removeItem(this.options.cacheKey);
        console.log('AJAX cache cleared');
    }

    clearQueue() {
        this.requestQueue = [];
        localStorage.removeItem('climaterisk_request_queue');
        console.log('Request queue cleared');
    }

    getStats() {
        return {
            isOnline: this.isOnline,
            queuedRequests: this.requestQueue.length,
            cachedResponses: this.cache.size,
            cacheSize: new Blob([JSON.stringify(Object.fromEntries(this.cache))]).size
        };
    }
}

// Connection status monitor
class ConnectionMonitor {
    constructor() {
        this.statusElement = null;
        this.setupStatusIndicator();
        this.startMonitoring();
    }

    setupStatusIndicator() {
        // Create status indicator
        this.statusElement = document.createElement('div');
        this.statusElement.id = 'connection-status';
        this.statusElement.className = 'connection-status';
        this.statusElement.innerHTML = `
            <div class="status-indicator">
                <span class="status-dot"></span>
                <span class="status-text">Connected</span>
            </div>
        `;

        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .connection-status {
                position: fixed;
                top: 10px;
                right: 10px;
                z-index: 9999;
                background: rgba(0,0,0,0.8);
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #28a745;
            }

            .status-dot.offline {
                background: #ffc107;
            }

            .status-dot.syncing {
                background: #17a2b8;
                animation: pulse 1s infinite;
            }

            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
        `;

        document.head.appendChild(style);
        document.body.appendChild(this.statusElement);
    }

    startMonitoring() {
        this.updateStatus(navigator.onLine);

        window.addEventListener('online', () => this.updateStatus(true));
        window.addEventListener('offline', () => this.updateStatus(false));

        // Check connection periodically
        setInterval(() => {
            this.checkConnection();
        }, 30000); // Every 30 seconds
    }

    updateStatus(isOnline) {
        const dot = this.statusElement.querySelector('.status-dot');
        const text = this.statusElement.querySelector('.status-text');

        if (isOnline) {
            dot.classList.remove('offline', 'syncing');
            text.textContent = 'Connected';
        } else {
            dot.classList.add('offline');
            text.textContent = 'Offline';
        }
    }

    setSyncing() {
        const dot = this.statusElement.querySelector('.status-dot');
        const text = this.statusElement.querySelector('.status-text');

        dot.classList.add('syncing');
        text.textContent = 'Syncing...';
    }

    async checkConnection() {
        try {
            const response = await fetch('/favicon.ico', {
                method: 'HEAD',
                cache: 'no-cache'
            });

            this.updateStatus(response.ok);
        } catch (error) {
            this.updateStatus(false);
        }
    }
}

// Initialize and export
window.ResilientAjaxHandler = ResilientAjaxHandler;
window.ConnectionMonitor = ConnectionMonitor;

// Auto-initialize
document.addEventListener('DOMContentLoaded', function() {
    window.ajaxHandler = new ResilientAjaxHandler();
    window.connectionMonitor = new ConnectionMonitor();

    // Load any queued requests
    window.ajaxHandler.loadQueue();

    // Process queue if online
    if (navigator.onLine) {
        window.ajaxHandler.processQueue();
    }

    console.log('Resilient AJAX handler initialized');
});