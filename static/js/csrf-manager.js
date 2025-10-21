/**
 * Robust CSRF Handling for Climate Risk Analytics
 *
 * This module provides comprehensive CSRF token management with automatic
 * detection, regeneration, and error handling capabilities.
 *
 * Features:
 * - CSRF token detection and validation
 * - Automatic token regeneration
 * - User-friendly error handling
 * - Graceful fallback mechanisms
 * - Session state recovery
 */

(function() {
    'use strict';

    // CSRF Manager class
    window.CSRFManager = class CSRFManager {
        constructor(options = {}) {
            this.options = {
                tokenName: 'csrftoken',
                maxRetries: 3,
                retryDelay: 1000,
                refreshOnFailure: true,
                debugMode: false,
                ...options
            };

            this.retryCount = 0;
            this.isRegenerating = false;
            this.init();
        }

        /**
         * Initialize the CSRF manager
         */
        init() {
            this.log('Initializing CSRF Manager');
            this.setupEventListeners();
            this.validateCurrentToken();
        }

        /**
         * Setup event listeners for CSRF-related events
         */
        setupEventListeners() {
            // Monitor form submissions
            document.addEventListener('submit', (e) => {
                const form = e.target;
                if (form.tagName === 'FORM' && this.shouldProtectForm(form)) {
                    this.handleFormSubmission(form, e);
                }
            });

            // Monitor AJAX requests
            const originalFetch = window.fetch;
            window.fetch = (...args) => {
                const [url, options = {}] = args;
                if (this.shouldProtectRequest(url, options)) {
                    return this.protectedFetch(url, options);
                }
                return originalFetch.apply(window, args);
            };

            // Monitor storage changes
            window.addEventListener('storage', (e) => {
                if (e.key === null || e.key === this.options.tokenName) {
                    this.log('Storage changed, validating CSRF token');
                    this.validateCurrentToken();
                }
            });
        }

        /**
         * Determine if a form needs CSRF protection
         */
        shouldProtectForm(form) {
            // Skip forms with method="GET"
            if (form.method && form.method.toUpperCase() === 'GET') {
                return false;
            }

            // Skip forms with novalidate attribute
            if (form.hasAttribute('data-no-csrf')) {
                return false;
            }

            // Check if form has CSRF token
            const csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
            return !csrfInput || !csrfInput.value;
        }

        /**
         * Determine if a request needs CSRF protection
         */
        shouldProtectRequest(url, options) {
            // Only protect POST, PUT, PATCH, DELETE requests
            if (!options.method || !['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method.toUpperCase())) {
                return false;
            }

            // Skip external requests
            if (url && (url.startsWith('http://') || url.startsWith('https://')) && !url.includes(window.location.hostname)) {
                return false;
            }

            // Skip CSRF-exempt endpoints
            if (url && url.includes('/api/add-facility/')) {
                return false;
            }

            return true;
        }

        /**
         * Handle form submission with CSRF validation
         */
        async handleFormSubmission(form, event) {
            this.log('Handling form submission with CSRF validation');

            try {
                // Ensure CSRF token is present and valid
                const isValid = await this.ensureValidToken();

                if (!isValid) {
                    event.preventDefault();
                    this.showCSRFError('Unable to secure your form submission. Please refresh the page and try again.');
                    return;
                }

                // Update form CSRF token if needed
                this.updateFormCSRFToken(form);

            } catch (error) {
                this.log('Error in form submission handling:', error);
                event.preventDefault();
                this.showCSRFError('A security error occurred. Please refresh the page.');
            }
        }

        /**
         * Protected fetch with CSRF token handling
         */
        async protectedFetch(url, options) {
            this.log('Protected fetch called for:', url);

            try {
                // Ensure valid CSRF token
                const isValid = await this.ensureValidToken();

                if (!isValid) {
                    throw new Error('CSRF token validation failed');
                }

                // Add CSRF token to headers
                options.headers = {
                    ...options.headers,
                    'X-CSRFToken': this.getToken()
                };

                // Perform the original fetch
                return fetch(url, options);

            } catch (error) {
                this.log('Error in protected fetch:', error);
                throw error;
            }
        }

        /**
         * Ensure a valid CSRF token exists
         */
        async ensureValidToken() {
            this.log('Ensuring valid CSRF token');

            // Check if current token is valid
            if (this.isTokenValid()) {
                this.log('Current token is valid');
                return true;
            }

            // Try to regenerate token
            return await this.regenerateToken();
        }

        /**
         * Check if current CSRF token is valid
         */
        isTokenValid() {
            const token = this.getToken();
            return token && token.length > 0;
        }

        /**
         * Validate current token
         */
        validateCurrentToken() {
            this.log('Validating current CSRF token');

            if (!this.isTokenValid()) {
                this.log('CSRF token is missing or invalid');

                // Try to regenerate token asynchronously
                setTimeout(() => {
                    this.regenerateToken().catch(error => {
                        this.log('Async token regeneration failed:', error);
                    });
                }, 100);
            }
        }

        /**
         * Get current CSRF token
         */
        getToken() {
            return this.getCookie(this.options.tokenName);
        }

        /**
         * Get cookie value
         */
        getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        /**
         * Regenerate CSRF token
         */
        async regenerateToken() {
            if (this.isRegenerating) {
                this.log('Token regeneration already in progress');
                return false;
            }

            this.isRegenerating = true;
            this.log('Starting CSRF token regeneration');

            try {
                // Method 1: Try to get token from a hidden form field
                const hiddenToken = this.getTokenFromHiddenField();
                if (hiddenToken) {
                    this.log('Got token from hidden field');
                    return true;
                }

                // Method 2: Try to refresh token via AJAX
                const refreshed = await this.refreshTokenViaAJAX();
                if (refreshed) {
                    this.log('Token refreshed via AJAX');
                    return true;
                }

                // Method 3: Page refresh as last resort
                if (this.options.refreshOnFailure) {
                    this.log('Refreshing page to get new token');
                    this.showCSRFWarning('Refreshing page to restore security session...');

                    setTimeout(() => {
                        window.location.reload();
                    }, 1500);

                    return true; // We'll consider this a success since we're refreshing
                }

                return false;

            } catch (error) {
                this.log('Error regenerating token:', error);
                return false;
            } finally {
                this.isRegenerating = false;
            }
        }

        /**
         * Try to get CSRF token from hidden form field
         */
        getTokenFromHiddenField() {
            // Look for Django's standard CSRF token field
            const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
            if (csrfInput && csrfInput.value) {
                // Set the cookie manually
                this.setCookie(this.options.tokenName, csrfInput.value, 1);
                return csrfInput.value;
            }

            // Look for meta tag
            const metaTag = document.querySelector('meta[name="csrf-token"]');
            if (metaTag && metaTag.content) {
                this.setCookie(this.options.tokenName, metaTag.content, 1);
                return metaTag.content;
            }

            return null;
        }

        /**
         * Refresh CSRF token via AJAX
         */
        async refreshTokenViaAJAX() {
            try {
                // Try to use the dedicated CSRF refresh endpoint
                const refreshUrl = this.getCSRFRefreshUrl();

                const response = await fetch(refreshUrl, {
                    method: 'GET',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRF-Refresh': 'true'
                    },
                    credentials: 'same-origin'
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data.success && data.csrf_token) {
                        this.setCookie(this.options.tokenName, data.csrf_token, 1);
                        this.log('CSRF token refreshed via dedicated endpoint');
                        return true;
                    }
                }

                // Fallback: Create a minimal form to get a new CSRF token
                return await this.refreshTokenViaFallback();
            } catch (error) {
                this.log('Error refreshing token via AJAX:', error);
                return false;
            }
        }

        /**
         * Get CSRF refresh URL
         */
        getCSRFRefreshUrl() {
            // Try to determine the current app's CSRF refresh endpoint
            const path = window.location.pathname;

            if (path.includes('/climate-hazards-analysis/')) {
                return '/climate-hazards-analysis/refresh-csrf-token/';
            } else if (path.includes('/climate-hazards-analysis-v2/')) {
                return '/climate-hazards-analysis-v2/refresh-csrf-token/';
            } else if (path.includes('/flood-exposure-analysis/')) {
                return '/flood-exposure-analysis/refresh-csrf-token/';
            } else if (path.includes('/sea-level-rise-analysis/')) {
                return '/sea-level-rise-analysis/refresh-csrf-token/';
            } else if (path.includes('/tropical-cyclone-analysis/')) {
                return '/tropical-cyclone-analysis/refresh-csrf-token/';
            } else if (path.includes('/water-stress/')) {
                return '/water-stress/refresh-csrf-token/';
            }

            // Default fallback
            return '/refresh-csrf-token/';
        }

        /**
         * Fallback method to refresh CSRF token
         */
        async refreshTokenViaFallback() {
            try {
                const response = await fetch(window.location.href, {
                    method: 'GET',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRF-Refresh': 'true'
                    },
                    credentials: 'same-origin'
                });

                if (response.ok) {
                    // Try to extract token from response
                    const text = await response.text();
                    const tokenMatch = text.match(/name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']/);

                    if (tokenMatch && tokenMatch[1]) {
                        this.setCookie(this.options.tokenName, tokenMatch[1], 1);
                        this.log('CSRF token refreshed via fallback method');
                        return true;
                    }
                }

                return false;
            } catch (error) {
                this.log('Error in fallback token refresh:', error);
                return false;
            }
        }

        /**
         * Set cookie value
         */
        setCookie(name, value, days) {
            const expires = new Date();
            expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
            document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/;samesite=strict`;
        }

        /**
         * Update CSRF token in form
         */
        updateFormCSRFToken(form) {
            let csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');

            if (!csrfInput) {
                // Create CSRF input if it doesn't exist
                csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrfmiddlewaretoken';
                form.appendChild(csrfInput);
            }

            const token = this.getToken();
            if (token) {
                csrfInput.value = token;
            }
        }

        /**
         * Show CSRF error message
         */
        showCSRFError(message) {
            this.removeCSRFMessages(); // Remove any existing messages

            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger alert-dismissible fade show csrf-error-message';
            errorDiv.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                max-width: 400px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                border-left: 4px solid #dc3545;
            `;

            errorDiv.innerHTML = `
                <strong><i class="fas fa-exclamation-triangle me-2"></i>Security Error</strong>
                <p class="mb-2 mt-1">${message}</p>
                <button type="button" class="btn btn-sm btn-outline-danger me-2" onclick="window.location.reload()">
                    <i class="fas fa-sync me-1"></i>Refresh Page
                </button>
                <button type="button" class="btn btn-sm btn-secondary" data-bs-dismiss="alert">
                    Dismiss
                </button>
            `;

            document.body.appendChild(errorDiv);

            // Auto-remove after 10 seconds
            setTimeout(() => {
                if (errorDiv.parentNode) {
                    errorDiv.parentNode.removeChild(errorDiv);
                }
            }, 10000);
        }

        /**
         * Show CSRF warning message
         */
        showCSRFWarning(message) {
            this.removeCSRFMessages();

            const warningDiv = document.createElement('div');
            warningDiv.className = 'alert alert-warning alert-dismissible fade show csrf-warning-message';
            warningDiv.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                max-width: 400px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                border-left: 4px solid #ffc107;
            `;

            warningDiv.innerHTML = `
                <strong><i class="fas fa-info-circle me-2"></i>Security Update</strong>
                <p class="mb-0 mt-1">${message}</p>
            `;

            document.body.appendChild(warningDiv);
        }

        /**
         * Remove existing CSRF messages
         */
        removeCSRFMessages() {
            const messages = document.querySelectorAll('.csrf-error-message, .csrf-warning-message');
            messages.forEach(msg => {
                if (msg.parentNode) {
                    msg.parentNode.removeChild(msg);
                }
            });
        }

        /**
         * Log messages if debug mode is enabled
         */
        log(...args) {
            if (this.options.debugMode) {
                console.log('[CSRF Manager]', ...args);
            }
        }

        /**
         * Public method to manually validate token
         */
        async validateToken() {
            return await this.ensureValidToken();
        }

        /**
         * Public method to get current token
         */
        getCurrentToken() {
            return this.getToken();
        }

        /**
         * Public method to force token refresh
         */
        async forceRefreshToken() {
            this.retryCount = 0;
            return await this.regenerateToken();
        }
    };

    // Auto-initialize CSRF manager when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        window.csrfManager = new CSRFManager({
            debugMode: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        });
    });

    // Also initialize immediately if DOM is already loaded
    if (document.readyState === 'loading') {
        // DOM is still loading
    } else {
        // DOM is already loaded
        if (!window.csrfManager) {
            window.csrfManager = new CSRFManager({
                debugMode: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
            });
        }
    }

})();