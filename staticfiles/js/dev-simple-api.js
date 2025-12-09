/**
 * Development-Simplified API Manager
 * Removes CSRF complexity for easier development
 */

class DevSimpleAPIManager {
    constructor() {
        this.baseURL = window.location.origin;
        this.endpoints = {
            addFacility: '/api/add-facility/',
            granularWorkflow: '/api/granular/workflow/execute/',
            createPolygonAssets: '/api/polygon-assets/create/',
            generateAssetExposure: '/api/generate-asset-exposure/',
            clearSessionData: '/api/clear-session-data/'
        };

        this.requestQueue = [];
        this.isProcessing = false;
        this.debugMode = true;
        this.retryAttempts = 3;
        this.retryDelay = 1000;

        this.requestMetrics = {
            totalRequests: 0,
            successfulRequests: 0,
            failedRequests: 0,
            averageResponseTime: 0
        };
    }

    /**
     * Simplified request method without CSRF complexity
     */
    async makeRequest(url, options = {}) {
        const startTime = performance.now();
        const requestId = this.generateRequestId();

        console.log(`🌐 [Dev API] Request ${requestId}: ${options.method || 'GET'} ${url}`);

        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            },
            credentials: 'same-origin'
        };

        const finalOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers
            }
        };

        try {
            this.requestMetrics.totalRequests++;

            const response = await fetch(url, finalOptions);
            const responseTime = performance.now() - startTime;

            console.log(`📊 [Dev API] Response ${requestId}: ${response.status} (${responseTime.toFixed(2)}ms)`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.requestMetrics.successfulRequests++;
            this.updateAverageResponseTime(responseTime);

            console.log(`✅ [Dev API] Success ${requestId}:`, data);

            return {
                success: true,
                data: data,
                responseTime: responseTime,
                requestId: requestId
            };

        } catch (error) {
            this.requestMetrics.failedRequests++;
            console.error(`❌ [Dev API] Error ${requestId}:`, error.message);

            // Automatic retry for failed requests
            if (this.shouldRetry(url, options)) {
                console.log(`🔄 [Dev API] Retrying request ${requestId}...`);
                await this.delay(this.retryDelay);
                return this.makeRequest(url, options);
            }

            return {
                success: false,
                error: error.message,
                requestId: requestId
            };
        }
    }

    /**
     * Simplified polygon asset creation
     */
    async createPolygonAssets(polygonData) {
        console.log('🏗️ [Dev API] Creating polygon assets...', polygonData);

        return this.makeRequest(this.endpoints.createPolygonAssets, {
            method: 'POST',
            body: JSON.stringify({
                polygon_data: polygonData,
                session_id: this.getSessionId(),
                development_mode: true
            })
        });
    }

    /**
     * Simplified granular workflow execution
     */
    async executeGranularWorkflow(options = {}) {
        console.log('⚙️ [Dev API] Executing granular workflow...', options);

        return this.makeRequest(this.endpoints.granularWorkflow, {
            method: 'POST',
            body: JSON.stringify({
                session_id: this.getSessionId(),
                development_mode: true,
                ...options
            })
        });
    }

    /**
     * Simplified asset exposure generation
     */
    async generateAssetExposure(options = {}) {
        console.log('📈 [Dev API] Generating asset exposure...', options);

        return this.makeRequest(this.endpoints.generateAssetExposure, {
            method: 'POST',
            body: JSON.stringify({
                session_id: this.getSessionId(),
                development_mode: true,
                ...options
            })
        });
    }

    /**
     * Add facility without CSRF complexity
     */
    async addFacility(facilityData) {
        console.log('📍 [Dev API] Adding facility...', facilityData);

        return this.makeRequest(this.endpoints.addFacility, {
            method: 'POST',
            body: JSON.stringify({
                facility_data: facilityData,
                session_id: this.getSessionId(),
                development_mode: true
            })
        });
    }

    /**
     * Clear session data
     */
    async clearSessionData() {
        console.log('🧹 [Dev API] Clearing session data...');

        return this.makeRequest(this.endpoints.clearSessionData, {
            method: 'POST',
            body: JSON.stringify({
                session_id: this.getSessionId(),
                development_mode: true
            })
        });
    }

    /**
     * Batch API requests for efficiency
     */
    async batchRequests(requests) {
        console.log(`📦 [Dev API] Processing batch of ${requests.length} requests...`);

        const results = [];
        const batchSize = 3; // Process 3 requests concurrently

        for (let i = 0; i < requests.length; i += batchSize) {
            const batch = requests.slice(i, i + batchSize);
            const batchPromises = batch.map(request => {
                if (request.type === 'createPolygonAssets') {
                    return this.createPolygonAssets(request.data);
                } else if (request.type === 'executeGranularWorkflow') {
                    return this.executeGranularWorkflow(request.data);
                } else if (request.type === 'generateAssetExposure') {
                    return this.generateAssetExposure(request.data);
                } else if (request.type === 'addFacility') {
                    return this.addFacility(request.data);
                } else {
                    return this.makeRequest(request.url, request.options);
                }
            });

            const batchResults = await Promise.allSettled(batchPromises);
            results.push(...batchResults.map(result =>
                result.status === 'fulfilled' ? result.value : { success: false, error: result.reason.message }
            ));

            // Small delay between batches
            if (i + batchSize < requests.length) {
                await this.delay(100);
            }
        }

        const successful = results.filter(r => r.success).length;
        console.log(`✅ [Dev API] Batch completed: ${successful}/${requests.length} successful`);

        return results;
    }

    /**
     * Mock API responses for development testing
     */
    mockResponse(endpoint, data) {
        console.log(`🎭 [Dev API] Mocking response for ${endpoint}`);

        return new Promise((resolve) => {
            setTimeout(() => {
                resolve({
                    success: true,
                    data: data,
                    mock: true,
                    responseTime: Math.random() * 500 + 100
                });
            }, Math.random() * 500 + 100); // Simulate network delay
        });
    }

    /**
     * Enable mock mode for offline development
     */
    enableMockMode() {
        console.log('🎭 [Dev API] Mock mode enabled - API calls will be simulated');

        this.mockMode = true;
        this.originalMakeRequest = this.makeRequest;

        this.makeRequest = async (url, options = {}) => {
            console.log(`🎭 [Dev API] Mocking: ${options.method || 'GET'} ${url}`);

            // Simulate different responses based on endpoint
            if (url.includes('createPolygonAssets')) {
                return this.mockResponse(url, {
                    success: true,
                    polygon_assets_created: Math.floor(Math.random() * 10) + 1,
                    granular_points: Math.floor(Math.random() * 50) + 10
                });
            } else if (url.includes('granular/workflow/execute')) {
                return this.mockResponse(url, {
                    success: true,
                    workflow_completed: true,
                    results_generated: true
                });
            } else if (url.includes('generateAssetExposure')) {
                return this.mockResponse(url, {
                    success: true,
                    exposure_data_generated: true,
                    records_processed: Math.floor(Math.random() * 100) + 20
                });
            } else {
                return this.mockResponse(url, {
                    success: true,
                    message: 'Mock response for development'
                });
            }
        };
    }

    /**
     * Disable mock mode
     */
    disableMockMode() {
        if (this.originalMakeRequest) {
            this.makeRequest = this.originalMakeRequest;
            this.mockMode = false;
            console.log('🌐 [Dev API] Mock mode disabled - using real API calls');
        }
    }

    /**
     * Add development controls panel
     */
    addDevControls() {
        const devPanel = $(`
            <div id="dev-api-controls" style="position: fixed; top: 10px; left: 10px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 15px; z-index: 1000; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 250px;">
                <h6 style="margin: 0 0 10px 0; font-weight: bold; color: #856404;">🔧 Dev API Controls</h6>
                <div style="font-size: 12px; color: #856404;">
                    <div>Requests: ${this.requestMetrics.totalRequests} | Success: ${this.requestMetrics.successfulRequests} | Failed: ${this.requestMetrics.failedRequests}</div>
                    <div>Avg Response: ${this.requestMetrics.averageResponseTime.toFixed(2)}ms</div>
                    <div style="margin-top: 8px;">
                        <button onclick="window.devAPIManager.toggleMockMode()" style="padding: 2px 8px; font-size: 11px; margin-right: 5px;">Toggle Mock</button>
                        <button onclick="window.devAPIManager.showMetrics()" style="padding: 2px 8px; font-size: 11px; margin-right: 5px;">Metrics</button>
                        <button onclick="window.devAPIManager.testAPI()" style="padding: 2px 8px; font-size: 11px;">Test API</button>
                    </div>
                    <div style="margin-top: 5px;">
                        <button onclick="window.devAPIManager.clearSessionData()" style="padding: 2px 8px; font-size: 11px; background: #dc3545; color: white; border: none;">Clear Session</button>
                    </div>
                </div>
            </div>
        `);

        $('body').append(devPanel);

        // Update metrics every 5 seconds
        setInterval(() => {
            $('#dev-api-controls').find('div').first().html(
                `Requests: ${this.requestMetrics.totalRequests} | Success: ${this.requestMetrics.successfulRequests} | Failed: ${this.requestMetrics.failedRequests}`
            );
            $('#dev-api-controls').find('div').eq(1).html(
                `Avg Response: ${this.requestMetrics.averageResponseTime.toFixed(2)}ms`
            );
        }, 5000);

        // Make globally accessible
        window.devAPIManager = this;
    }

    /**
     * Toggle mock mode
     */
    toggleMockMode() {
        if (this.mockMode) {
            this.disableMockMode();
        } else {
            this.enableMockMode();
        }
    }

    /**
     * Show detailed metrics
     */
    showMetrics() {
        console.table(this.requestMetrics);
        const successRate = this.requestMetrics.totalRequests > 0 ?
            ((this.requestMetrics.successfulRequests / this.requestMetrics.totalRequests) * 100).toFixed(2) : 0;

        alert(`API Performance Metrics:\n\n` +
              `Total Requests: ${this.requestMetrics.totalRequests}\n` +
              `Successful: ${this.requestMetrics.successfulRequests}\n` +
              `Failed: ${this.requestMetrics.failedRequests}\n` +
              `Success Rate: ${successRate}%\n` +
              `Average Response Time: ${this.requestMetrics.averageResponseTime.toFixed(2)}ms\n` +
              `Mock Mode: ${this.mockMode ? 'Enabled' : 'Disabled'}`);
    }

    /**
     * Test API endpoints
     */
    async testAPI() {
        console.log('🧪 [Dev API] Testing API endpoints...');

        const testResults = [];

        // Test 1: Mock polygon creation
        const polygonTest = await this.createPolygonAssets({
            name: 'Test Polygon',
            coordinates: [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
        });
        testResults.push({ endpoint: 'createPolygonAssets', result: polygonTest });

        // Test 2: Mock workflow execution
        const workflowTest = await this.executeGranularWorkflow({
            analysis_type: 'climate_hazards'
        });
        testResults.push({ endpoint: 'executeGranularWorkflow', result: workflowTest });

        // Test 3: Mock exposure generation
        const exposureTest = await this.generateAssetExposure({
            hazard_types: ['flood', 'wind']
        });
        testResults.push({ endpoint: 'generateAssetExposure', result: exposureTest });

        console.log('🧪 [Dev API] Test results:', testResults);
        alert(`API Test Results:\n\n` +
              testResults.map(r => `${r.endpoint}: ${r.result.success ? '✅ Success' : '❌ Failed'}`).join('\n'));
    }

    /**
     * Utility functions
     */
    generateRequestId() {
        return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    getSessionId() {
        // Try to get session ID from various sources
        return $('meta[name="csrf-token"]').attr('content') ||
               $('[name="csrfmiddlewaretoken"]').val() ||
               'dev_session_' + Date.now();
    }

    shouldRetry(url, options) {
        // Don't retry GET requests or if we've already retried too many times
        if (options.method === 'GET' || options.method === undefined) return false;
        if (this.retryAttempts <= 0) return false;

        this.retryAttempts--;
        return true;
    }

    updateAverageResponseTime(responseTime) {
        const total = this.requestMetrics.averageResponseTime * (this.requestMetrics.successfulRequests - 1) + responseTime;
        this.requestMetrics.averageResponseTime = total / this.requestMetrics.successfulRequests;
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Initialize when DOM is ready
$(document).ready(function() {
    console.log('🚀 [Dev API] Document ready, initializing simplified API manager...');

    setTimeout(() => {
        if (typeof window.devAPIManager === 'undefined') {
            window.devAPIManager = new DevSimpleAPIManager();
            window.devAPIManager.addDevControls();

            // Enable mock mode by default for development
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                window.devAPIManager.enableMockMode();
            }
        }
    }, 1500);
});