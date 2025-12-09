/**
 * Resilient JavaScript initialization for climate hazards results page
 * Provides graceful degradation and comprehensive error handling
 */

// Global error handler
window.addEventListener('error', function(event) {
    console.error('Global JavaScript error:', event.error);
    window.ClimateriskErrorHandler?.handleCriticalError('JavaScript Error', event.error.message);
});

// Unhandled promise rejection handler
window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
    window.ClimateriskErrorHandler?.handleCriticalError('Promise Rejection', event.reason);
});

// Safe jQuery loader with fallbacks
class SafeJQueryLoader {
    constructor() {
        this.loadAttempts = 0;
        this.maxAttempts = 3;
        this.loadTimeout = 5000;
    }

    async loadJQuery() {
        return new Promise((resolve, reject) => {
            const attempt = () => {
                this.loadAttempts++;

                // Check if jQuery is already loaded
                if (typeof window.jQuery !== 'undefined') {
                    console.log('jQuery already available');
                    resolve(window.jQuery);
                    return;
                }

                // Try to load from CDN
                const script = document.createElement('script');
                script.src = 'https://code.jquery.com/jquery-3.6.0.min.js';
                script.onload = () => {
                    if (typeof window.jQuery !== 'undefined') {
                        console.log('jQuery loaded successfully from CDN');
                        resolve(window.jQuery);
                    } else {
                        this.tryFallback(resolve, reject);
                    }
                };
                script.onerror = () => this.tryFallback(resolve, reject);
                script.timeout = this.loadTimeout;
                script.ontimeout = () => this.tryFallback(resolve, reject);

                document.head.appendChild(script);
            };

            attempt();
        });
    }

    tryFallback(resolve, reject) {
        if (this.loadAttempts < this.maxAttempts) {
            console.log(`jQuery load attempt ${this.loadAttempts} failed, retrying...`);
            setTimeout(() => this.loadJQuery().then(resolve).catch(reject), 1000);
        } else {
            console.error('Failed to load jQuery after maximum attempts');
            reject(new Error('Failed to load jQuery'));
        }
    }
}

// DataTables loader with fallbacks
class DataTablesLoader {
    constructor() {
        this.requiredLibs = [
            'https://cdn.datatables.net/1.11.5/js/jquery.dataTables.min.js',
            'https://cdn.datatables.net/buttons/2.3.6/js/dataTables.buttons.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.1.3/jszip.min.js',
            'https://cdn.datatables.net/buttons/2.3.6/js/buttons.html5.min.js',
            'https://cdn.datatables.net/fixedcolumns/4.2.2/js/dataTables.fixedColumns.min.js'
        ];
        this.loadedLibs = 0;
    }

    async loadDataTables() {
        return new Promise((resolve, reject) => {
            if (typeof window.jQuery === 'undefined') {
                reject(new Error('jQuery must be loaded before DataTables'));
                return;
            }

            // Check if DataTables is already available
            if (typeof window.jQuery.fn.DataTable !== 'undefined') {
                console.log('DataTables already available');
                resolve();
                return;
            }

            const loadScript = (src) => {
                return new Promise((libResolve, libReject) => {
                    const script = document.createElement('script');
                    script.src = src;
                    script.onload = libResolve;
                    script.onerror = () => {
                        console.warn(`Failed to load ${src}, continuing without it`);
                        libResolve(); // Don't reject for individual library failures
                    };
                    document.head.appendChild(script);
                });
            };

            Promise.all(this.requiredLibs.map(loadScript))
                .then(() => {
                    if (typeof window.jQuery.fn.DataTable !== 'undefined') {
                        console.log('DataTables loaded successfully');
                        resolve();
                    } else {
                        console.warn('DataTables not fully available, will use manual table');
                        resolve(); // Don't reject, allow manual table fallback
                    }
                })
                .catch(reject);
        });
    }
}

// Data validator and sanitizer
class DataValidator {
    static validateTableData(data) {
        if (!Array.isArray(data)) {
            throw new Error('Table data must be an array');
        }

        return data.map((row, index) => {
            if (!row || typeof row !== 'object') {
                console.warn(`Invalid row at index ${index}:`, row);
                return this.createFallbackRow(index);
            }
            return this.sanitizeRow(row);
        });
    }

    static sanitizeRow(row) {
        const sanitized = {};
        for (const [key, value] of Object.entries(row)) {
            sanitized[key] = this.sanitizeValue(value);
        }
        return sanitized;
    }

    static sanitizeValue(value) {
        if (value === null || value === undefined) {
            return 'N/A';
        }

        if (typeof value === 'string') {
            // Remove potential XSS content
            return value
                .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
                .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '')
                .trim();
        }

        return String(value);
    }

    static createFallbackRow(index) {
        return {
            'Facility': `Asset ${index + 1}`,
            'Asset Archetype': 'N/A',
            'default': 'Data not available'
        };
    }

    static validateColumns(columns) {
        if (!Array.isArray(columns) || columns.length === 0) {
            return ['Facility', 'Asset Archetype']; // Fallback columns
        }
        return columns.filter(col => col && typeof col === 'string');
    }
}

// Error handler class
class ClimateriskErrorHandler {
    constructor() {
        this.errors = [];
        this.maxErrors = 10;
        this.errorContainer = null;
        this.setupErrorContainer();
    }

    setupErrorContainer() {
        this.errorContainer = document.getElementById('js-error');
        if (!this.errorContainer) {
            this.errorContainer = document.createElement('div');
            this.errorContainer.id = 'js-error';
            this.errorContainer.className = 'alert alert-danger alert-dismissible fade show d-none';
            this.errorContainer.innerHTML = `
                <span id="js-error-text"></span>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            `;
            document.body.prepend(this.errorContainer);
        }
    }

    handleError(message, error = null) {
        console.error(message, error);

        this.errors.push({
            message,
            error,
            timestamp: new Date()
        });

        if (this.errors.length > this.maxErrors) {
            this.errors.shift();
        }

        this.displayError(message);
    }

    handleCriticalError(type, message) {
        const fullMessage = `${type}: ${message}`;
        this.handleError(fullMessage);

        // Show fallback UI for critical errors
        this.showFallbackUI();
    }

    displayError(message) {
        if (this.errorContainer) {
            const textEl = this.errorContainer.querySelector('#js-error-text');
            if (textEl) {
                textEl.textContent = message;
                this.errorContainer.classList.remove('d-none');
            }
        }
    }

    hideError() {
        if (this.errorContainer) {
            this.errorContainer.classList.add('d-none');
        }
    }

    showFallbackUI() {
        // Show a basic table interface if JavaScript fails
        const tableContainer = document.getElementById('hazard-data-table');
        if (tableContainer && tableContainer.style.display !== 'none') {
            this.enableBasicTableFunctionality();
        }
    }

    enableBasicTableFunctionality() {
        // Add basic sorting and filtering without DataTables
        const table = document.getElementById('hazard-data-table');
        if (table) {
            // Make headers clickable for basic sorting
            const headers = table.querySelectorAll('thead th');
            headers.forEach(header => {
                header.style.cursor = 'pointer';
                header.addEventListener('click', () => this.basicSort(header));
            });
        }
    }

    basicSort(header) {
        const table = document.getElementById('hazard-data-table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const columnIndex = Array.from(header.parentNode.children).indexOf(header);
        const isAscending = !header.classList.contains('sort-desc');

        rows.sort((a, b) => {
            const aText = a.children[columnIndex].textContent.trim();
            const bText = b.children[columnIndex].textContent.trim();

            const aNum = parseFloat(aText.replace(/[^\d.-]/g, ''));
            const bNum = parseFloat(bText.replace(/[^\d.-]/g, ''));

            if (!isNaN(aNum) && !isNaN(bNum)) {
                return isAscending ? aNum - bNum : bNum - aNum;
            }

            return isAscending ? aText.localeCompare(bText) : bText.localeCompare(aText);
        });

        // Update header classes
        headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
        header.classList.add(isAscending ? 'sort-asc' : 'sort-desc');

        // Reorder rows
        rows.forEach(row => tbody.appendChild(row));
    }
}

// Initialize the error handler
window.ClimateriskErrorHandler = new ClimateriskErrorHandler();

// Safe initialization manager
class SafeInitializationManager {
    constructor() {
        this.initializationSteps = [];
        this.currentStep = 0;
        this.retryAttempts = 0;
        this.maxRetries = 3;
    }

    addStep(name, fn, dependencies = []) {
        this.initializationSteps.push({ name, fn, dependencies, status: 'pending' });
    }

    async initialize() {
        try {
            console.log('Starting safe initialization...');

            // Step 1: Load jQuery
            await this.executeStep('Load jQuery', async () => {
                const loader = new SafeJQueryLoader();
                return await loader.loadJQuery();
            });

            // Step 2: Load DataTables (optional)
            await this.executeStep('Load DataTables', async () => {
                const loader = new DataTablesLoader();
                return await loader.loadDataTables();
            }, ['Load jQuery']);

            // Step 3: Validate and prepare data
            await this.executeStep('Validate Data', async () => {
                this.validateAndPrepareData();
            });

            // Step 4: Initialize table functionality
            await this.executeStep('Initialize Table', async () => {
                this.initializeTableFunctionality();
            }, ['Load jQuery', 'Validate Data']);

            // Step 5: Setup interactive features
            await this.executeStep('Setup Interactions', async () => {
                this.setupInteractiveFeatures();
            }, ['Initialize Table']);

            console.log('Initialization completed successfully');
            return true;

        } catch (error) {
            console.error('Initialization failed:', error);
            window.ClimateriskErrorHandler.handleCriticalError('Initialization Failed', error.message);
            return false;
        }
    }

    async executeStep(stepName, fn, dependencies = []) {
        console.log(`Executing step: ${stepName}`);

        // Check dependencies
        for (const dep of dependencies) {
            const depStep = this.initializationSteps.find(s => s.name === dep);
            if (!depStep || depStep.status !== 'completed') {
                throw new Error(`Dependency '${dep}' not satisfied for step '${stepName}'`);
            }
        }

        try {
            const result = await fn();
            const step = this.initializationSteps.find(s => s.name === stepName);
            if (step) {
                step.status = 'completed';
            }
            console.log(`Step completed: ${stepName}`);
            return result;
        } catch (error) {
            const step = this.initializationSteps.find(s => s.name === stepName);
            if (step) {
                step.status = 'failed';
            }
            throw error;
        }
    }

    validateAndPrepareData() {
        // Validate table data from Django template
        if (typeof window.tableData !== 'undefined') {
            window.validatedData = DataValidator.validateTableData(window.tableData);
        } else {
            console.warn('No table data available, creating fallback data');
            window.validatedData = [];
        }

        // Validate columns
        if (typeof window.tableColumns !== 'undefined') {
            window.validatedColumns = DataValidator.validateColumns(window.tableColumns);
        } else {
            window.validatedColumns = ['Facility', 'Asset Archetype'];
        }
    }

    initializeTableFunctionality() {
        // Initialize manual table with fallback support
        if (typeof initializeManualTable === 'function') {
            initializeManualTable();
        } else {
            console.warn('Manual table initialization function not found');
            this.createBasicTable();
        }
    }

    createBasicTable() {
        // Create a very basic table if all else fails
        const tableContainer = document.getElementById('hazard-data-table');
        if (tableContainer) {
            tableContainer.style.display = 'table';
            console.log('Basic table functionality enabled');
        }
    }

    setupInteractiveFeatures() {
        // Setup column selector, editing, etc. with error handling
        try {
            if (typeof setupColumnSelector === 'function') {
                setupColumnSelector();
            }
        } catch (error) {
            console.warn('Column selector setup failed:', error);
        }

        try {
            if (typeof attachEditableHandlers === 'function') {
                attachEditableHandlers();
            }
        } catch (error) {
            console.warn('Editable handlers setup failed:', error);
        }
    }

    async retry() {
        if (this.retryAttempts < this.maxRetries) {
            this.retryAttempts++;
            console.log(`Retrying initialization (attempt ${this.retryAttempts})`);
            this.currentStep = 0;
            return await this.initialize();
        } else {
            throw new Error('Maximum initialization retries exceeded');
        }
    }
}

// Export for use in main script
window.SafeInitializationManager = SafeInitializationManager;
window.DataValidator = DataValidator;

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const manager = new SafeInitializationManager();

    // Add data from Django template to window scope
    if (typeof tableData !== 'undefined') {
        window.tableData = tableData;
    }
    if (typeof tableColumns !== 'undefined') {
        window.tableColumns = tableColumns;
    }

    manager.initialize().catch(error => {
        console.error('Auto-initialization failed:', error);
        // Show retry option to user
        const retryButton = document.createElement('button');
        retryButton.textContent = 'Retry Loading';
        retryButton.className = 'btn btn-warning';
        retryButton.onclick = () => manager.retry();
        document.body.prepend(retryButton);
    });
});