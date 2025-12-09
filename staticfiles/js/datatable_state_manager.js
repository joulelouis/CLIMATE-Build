/**
 * DataTables State Manager
 *
 * Handles the asynchronous initialization of DataTables and provides a robust
 * queuing system for functions that depend on DataTables being fully ready.
 *
 * Features:
 * - Event-driven initialization detection
 * - Function queuing with retry mechanisms
 * - Proper state management for complex table structures
 * - Error handling and fallback mechanisms
 */

class DataTableStateManager {
    constructor() {
        this.tables = new Map();
        this.pendingQueues = new Map();
        this.initializationPromises = new Map();
        this.retryAttempts = new Map();
        this.maxRetries = 3;
        this.retryDelay = 250;
        this.maxInitWaitTime = 10000; // 10 seconds max wait

        // Bind methods to maintain context
        this.registerTable = this.registerTable.bind(this);
        this.isTableReady = this.isTableReady.bind(this);
        this.queueFunction = this.queueFunction.bind(this);
        this.executeWhenReady = this.executeWhenReady.bind(this);
    }

    /**
     * Register a table for state management
     * @param {string} tableId - The ID of the table element
     * @param {Object} options - Configuration options
     */
    registerTable(tableId, options = {}) {
        console.log(`Registering table: ${tableId}`);

        const tableState = {
            id: tableId,
            status: 'pending', // pending, initializing, ready, error
            dataTable: null,
            element: null,
            initStartTime: Date.now(),
            options: {
                initTimeout: options.initTimeout || this.maxInitWaitTime,
                retryOnFail: options.retryOnFail !== false,
                customReadyCheck: options.customReadyCheck || null,
                ...options
            }
        };

        this.tables.set(tableId, tableState);
        this.pendingQueues.set(tableId, []);
        this.retryAttempts.set(tableId, 0);

        // Create initialization promise
        this.initializationPromises.set(tableId, this._createInitializationPromise(tableId));

        return this.initializationPromises.get(tableId);
    }

    /**
     * Create a promise that resolves when the table is ready
     * @private
     */
    _createInitializationPromise(tableId) {
        return new Promise((resolve, reject) => {
            const tableState = this.tables.get(tableId);
            const startTime = Date.now();

            const checkReady = () => {
                if (Date.now() - startTime > tableState.options.initTimeout) {
                    this._setTableStatus(tableId, 'error', 'Initialization timeout');
                    reject(new Error(`Table ${tableId} initialization timeout`));
                    return;
                }

                if (this._isTableReadyInternal(tableId)) {
                    this._setTableStatus(tableId, 'ready');
                    resolve(this.tables.get(tableId));
                } else {
                    setTimeout(checkReady, 50);
                }
            };

            // Start checking after a short delay to allow for setup
            setTimeout(checkReady, 100);
        });
    }

    /**
     * Check if a table is ready internally
     * @private
     */
    _isTableReadyInternal(tableId) {
        const tableState = this.tables.get(tableId);
        if (!tableState) return false;

        // Get the table element
        const element = $(`#${tableId}`);
        if (!element.length) return false;

        tableState.element = element;

        // Check if DataTable is initialized
        let dataTable = null;
        try {
            if ($.fn.DataTable.isDataTable(`#${tableId}`)) {
                dataTable = element.DataTable();

                // Verify the DataTable has columns and is fully initialized
                if (dataTable &&
                    dataTable.columns &&
                    typeof dataTable.columns === 'function' &&
                    dataTable.columns().count() > 0) {

                    tableState.dataTable = dataTable;

                    // Run custom ready check if provided
                    if (tableState.options.customReadyCheck) {
                        return tableState.options.customReadyCheck(dataTable, element);
                    }

                    return true;
                }
            }
        } catch (error) {
            console.warn(`Error checking DataTable readiness for ${tableId}:`, error);
        }

        return false;
    }

    /**
     * Set table status and process queue if ready
     * @private
     */
    _setTableStatus(tableId, status, error = null) {
        const tableState = this.tables.get(tableId);
        if (!tableState) return;

        const previousStatus = tableState.status;
        tableState.status = status;
        tableState.lastUpdate = Date.now();

        if (error) {
            tableState.error = error;
        }

        console.log(`Table ${tableId} status changed: ${previousStatus} -> ${status}`);

        // Process pending queue if table is ready
        if (status === 'ready') {
            this._processPendingQueue(tableId);
        }
    }

    /**
     * Process all pending functions for a table
     * @private
     */
    _processPendingQueue(tableId) {
        const queue = this.pendingQueues.get(tableId);
        if (!queue || queue.length === 0) return;

        console.log(`Processing ${queue.length} pending functions for table ${tableId}`);

        const tableState = this.tables.get(tableId);
        const processedFunctions = [];

        queue.forEach((queuedFunction, index) => {
            try {
                const result = queuedFunction.fn.call(queuedFunction.context || window, tableState.dataTable, tableState.element);

                if (queuedFunction.resolve) {
                    queuedFunction.resolve(result);
                }

                processedFunctions.push(index);
                console.log(`Successfully executed queued function: ${queuedFunction.name || 'anonymous'}`);

            } catch (error) {
                console.error(`Error executing queued function for ${tableId}:`, error);

                if (queuedFunction.reject) {
                    queuedFunction.reject(error);
                }
            }
        });

        // Remove processed functions from queue (in reverse order to maintain indices)
        processedFunctions.reverse().forEach(index => queue.splice(index, 1));
    }

    /**
     * Check if a table is ready
     * @param {string} tableId - The ID of the table
     * @returns {boolean}
     */
    isTableReady(tableId) {
        const tableState = this.tables.get(tableId);
        return tableState && tableState.status === 'ready';
    }

    /**
     * Get the DataTable instance for a table
     * @param {string} tableId - The ID of the table
     * @returns {Object|null}
     */
    getDataTable(tableId) {
        const tableState = this.tables.get(tableId);
        return tableState && tableState.status === 'ready' ? tableState.dataTable : null;
    }

    /**
     * Get the jQuery element for a table
     * @param {string} tableId - The ID of the table
     * @returns {Object|null}
     */
    getTableElement(tableId) {
        const tableState = this.tables.get(tableId);
        return tableState ? tableState.element : null;
    }

    /**
     * Queue a function to be executed when the table is ready
     * @param {string} tableId - The ID of the table
     * @param {Function} fn - The function to execute
     * @param {Object} options - Options for the queued function
     * @returns {Promise}
     */
    queueFunction(tableId, fn, options = {}) {
        return new Promise((resolve, reject) => {
            // If table is already ready, execute immediately
            if (this.isTableReady(tableId)) {
                try {
                    const tableState = this.tables.get(tableId);
                    const result = fn.call(options.context || window, tableState.dataTable, tableState.element);
                    resolve(result);
                } catch (error) {
                    reject(error);
                }
                return;
            }

            // Add to queue
            const queue = this.pendingQueues.get(tableId);
            if (queue) {
                queue.push({
                    fn: fn,
                    name: options.name || fn.name || 'anonymous',
                    context: options.context,
                    resolve: resolve,
                    reject: reject,
                    queuedAt: Date.now()
                });

                console.log(`Queued function "${options.name || 'anonymous'}" for table ${tableId}`);
            } else {
                reject(new Error(`Table ${tableId} not registered`));
            }
        });
    }

    /**
     * Execute a function when the table is ready (with retry logic)
     * @param {string} tableId - The ID of the table
     * @param {Function} fn - The function to execute
     * @param {Object} options - Options including retry configuration
     * @returns {Promise}
     */
    executeWhenReady(tableId, fn, options = {}) {
        const retryOptions = {
            maxRetries: options.maxRetries || this.maxRetries,
            retryDelay: options.retryDelay || this.retryDelay,
            name: options.name || fn.name || 'anonymous',
            ...options
        };

        return new Promise(async (resolve, reject) => {
            let lastError = null;

            for (let attempt = 0; attempt <= retryOptions.maxRetries; attempt++) {
                try {
                    // Wait for table to be ready
                    await this.initializationPromises.get(tableId);

                    // Execute the function
                    const result = await this.queueFunction(tableId, fn, retryOptions);
                    resolve(result);
                    return;

                } catch (error) {
                    lastError = error;
                    console.warn(`Attempt ${attempt + 1} failed for function "${retryOptions.name}" on table ${tableId}:`, error);

                    if (attempt < retryOptions.maxRetries) {
                        await this._delay(retryOptions.retryDelay * (attempt + 1));
                    }
                }
            }

            console.error(`All attempts failed for function "${retryOptions.name}" on table ${tableId}`);
            reject(lastError);
        });
    }

    /**
     * Manually mark a table as ready (for cases where automatic detection fails)
     * @param {string} tableId - The ID of the table
     * @param {Object} dataTable - The DataTable instance
     */
    markTableReady(tableId, dataTable = null) {
        const tableState = this.tables.get(tableId);
        if (!tableState) {
            console.warn(`Attempted to mark unknown table as ready: ${tableId}`);
            return;
        }

        if (dataTable) {
            tableState.dataTable = dataTable;
        } else {
            // Try to get the DataTable instance
            try {
                const element = $(`#${tableId}`);
                if ($.fn.DataTable.isDataTable(`#${tableId}`)) {
                    tableState.dataTable = element.DataTable();
                }
            } catch (error) {
                console.warn(`Could not get DataTable instance for ${tableId}:`, error);
            }
        }

        this._setTableStatus(tableId, 'ready');
    }

    /**
     * Reset a table's state (useful for re-initialization)
     * @param {string} tableId - The ID of the table
     */
    resetTable(tableId) {
        console.log(`Resetting table state for: ${tableId}`);

        const tableState = this.tables.get(tableId);
        if (tableState) {
            tableState.status = 'pending';
            tableState.dataTable = null;
            tableState.error = null;
            tableState.initStartTime = Date.now();
        }

        // Clear queues and retry attempts
        this.pendingQueues.set(tableId, []);
        this.retryAttempts.set(tableId, 0);

        // Create new initialization promise
        this.initializationPromises.set(tableId, this._createInitializationPromise(tableId));

        return this.initializationPromises.get(tableId);
    }

    /**
     * Get status information for a table
     * @param {string} tableId - The ID of the table
     * @returns {Object}
     */
    getTableStatus(tableId) {
        const tableState = this.tables.get(tableId);
        const queue = this.pendingQueues.get(tableId);

        return {
            exists: !!tableState,
            status: tableState?.status || 'unknown',
            queueLength: queue?.length || 0,
            retryAttempts: this.retryAttempts.get(tableId) || 0,
            error: tableState?.error || null,
            initTime: tableState ? Date.now() - tableState.initStartTime : 0
        };
    }

    /**
     * Utility method to create a delay
     * @private
     */
    _delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Clean up resources for a table
     * @param {string} tableId - The ID of the table
     */
    cleanup(tableId) {
        console.log(`Cleaning up resources for table: ${tableId}`);

        this.tables.delete(tableId);
        this.pendingQueues.delete(tableId);
        this.initializationPromises.delete(tableId);
        this.retryAttempts.delete(tableId);
    }
}

// Create global instance
window.dataTableStateManager = new DataTableStateManager();

// Helper functions for backward compatibility and ease of use
window.dtStateManager = {
    // Register a table
    register: (tableId, options) => window.dataTableStateManager.registerTable(tableId, options),

    // Check if ready
    isReady: (tableId) => window.dataTableStateManager.isTableReady(tableId),

    // Get DataTable instance
    getTable: (tableId) => window.dataTableStateManager.getDataTable(tableId),

    // Execute when ready
    whenReady: (tableId, fn, options) => window.dataTableStateManager.executeWhenReady(tableId, fn, options),

    // Queue function
    queue: (tableId, fn, options) => window.dataTableStateManager.queueFunction(tableId, fn, options),

    // Mark as ready manually
    markReady: (tableId, dataTable) => window.dataTableStateManager.markTableReady(tableId, dataTable),

    // Get status
    status: (tableId) => window.dataTableStateManager.getTableStatus(tableId),

    // Reset table
    reset: (tableId) => window.dataTableStateManager.resetTable(tableId)
};

console.log('DataTable State Manager loaded successfully');