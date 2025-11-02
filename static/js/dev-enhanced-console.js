/**
 * Development Enhanced Console Manager
 * Provides better debugging experience with structured logging
 */

class DevEnhancedConsole {
    constructor() {
        this.logLevels = {
            DEBUG: 0,
            INFO: 1,
            WARN: 2,
            ERROR: 3,
            SUCCESS: 4
        };

        this.currentLogLevel = this.logLevels.DEBUG;
        this.logHistory = [];
        this.maxLogHistory = 1000;
        this.performanceData = new Map();
        this.componentStates = new Map();
        this.debugMode = true;

        this.categories = {
            INIT: '🚀',
            API: '🌐',
            TABLE: '📊',
            POLYGON: '🏗️',
            WORKFLOW: '⚙️',
            DATA: '📈',
            ERROR: '❌',
            SUCCESS: '✅',
            DEBUG: '🐛',
            PERFORMANCE: '⚡',
            USER: '👤'
        };

        this.initializeEnhancedConsole();
    }

    /**
     * Initialize the enhanced console system
     */
    initializeEnhancedConsole() {
        console.log('🎛️ [Dev Console] Enhanced console system initializing...');

        // Add enhanced logging without overriding
        this.addEnhancedLogging();

        // Add visual console panel
        this.createConsolePanel();

        // Setup performance monitoring
        this.setupPerformanceMonitoring();

        // Setup error tracking
        this.setupErrorTracking();

        console.log('✅ [Dev Console] Enhanced console system ready!');
    }

    /**
     * Add enhanced logging without overriding console methods
     */
    addEnhancedLogging() {
        // Store original console methods
        this.originalConsole = {
            log: console.log,
            warn: console.warn,
            error: console.error,
            info: console.info
        };

        // Add enhanced logging methods that track but don't replace
        console.logEnhanced = (...args) => {
            this.addLogEntry('INFO', args);
            this.originalConsole.log.apply(console, args);
        };

        console.warnEnhanced = (...args) => {
            this.addLogEntry('WARN', args);
            this.originalConsole.warn.apply(console, args);
        };

        console.errorEnhanced = (...args) => {
            this.addLogEntry('ERROR', args);
            this.originalConsole.error.apply(console, args);
        };

        console.infoEnhanced = (...args) => {
            this.addLogEntry('INFO', args);
            this.originalConsole.info.apply(console, args);
        };
    }

    /**
     * Add structured log entry
     */
    addLogEntry(level, args) {
        const logEntry = {
            timestamp: new Date().toISOString(),
            level: level,
            message: this.formatMessage(args),
            args: args,
            stackTrace: level === 'ERROR' ? this.getStackTrace() : null,
            url: window.location.href,
            userAgent: navigator.userAgent
        };

        this.logHistory.push(logEntry);

        // Trim history if needed
        if (this.logHistory.length > this.maxLogHistory) {
            this.logHistory = this.logHistory.slice(-this.maxLogHistory);
        }

        // Update console panel if visible
        this.updateConsolePanel();

        return logEntry;
    }

    /**
     * Format console arguments for display
     */
    formatMessage(args) {
        return args.map(arg => {
            if (typeof arg === 'object') {
                try {
                    return JSON.stringify(arg, null, 2).substring(0, 200);
                } catch (e) {
                    return '[Object]';
                }
            }
            return String(arg);
        }).join(' ');
    }

    /**
     * Get current stack trace
     */
    getStackTrace() {
        try {
            throw new Error();
        } catch (e) {
            return e.stack;
        }
    }

    /**
     * Category-based logging methods
     */
    init(message, ...args) {
        console.log(`${this.categories.INIT} [Dev Console] ${message}`, ...args);
    }

    api(message, ...args) {
        console.log(`${this.categories.API} [Dev API] ${message}`, ...args);
    }

    table(message, ...args) {
        console.log(`${this.categories.TABLE} [Dev Table] ${message}`, ...args);
    }

    polygon(message, ...args) {
        console.log(`${this.categories.POLYGON} [Dev Polygon] ${message}`, ...args);
    }

    workflow(message, ...args) {
        console.log(`${this.categories.WORKFLOW} [Dev Workflow] ${message}`, ...args);
    }

    data(message, ...args) {
        console.log(`${this.categories.DATA} [Dev Data] ${message}`, ...args);
    }

    success(message, ...args) {
        console.log(`${this.categories.SUCCESS} [Success] ${message}`, ...args);
    }

    error(message, ...args) {
        console.error(`${this.categories.ERROR} [Error] ${message}`, ...args);
    }

    warn(message, ...args) {
        console.warn(`${this.categories.WARN} [Warning] ${message}`, ...args);
    }

    debug(message, ...args) {
        if (this.debugMode) {
            console.log(`${this.categories.DEBUG} [Debug] ${message}`, ...args);
        }
    }

    perf(message, ...args) {
        console.log(`${this.categories.PERFORMANCE} [Performance] ${message}`, ...args);
    }

    user(message, ...args) {
        console.log(`${this.categories.USER} [User Action] ${message}`, ...args);
    }

    /**
     * Performance measurement methods
     */
    startTimer(label) {
        this.performanceData.set(label, {
            startTime: performance.now(),
            endTime: null,
            duration: null
        });
        this.perf(`⏱️ Timer started: ${label}`);
    }

    endTimer(label) {
        const timer = this.performanceData.get(label);
        if (timer) {
            timer.endTime = performance.now();
            timer.duration = timer.endTime - timer.startTime;
            this.performanceData.set(label, timer);
            this.perf(`⏱️ Timer ended: ${label} (${timer.duration.toFixed(2)}ms)`);
            return timer.duration;
        } else {
            this.warn(`⏱️ Timer not found: ${label}`);
            return null;
        }
    }

    measureFunction(label, func) {
        this.startTimer(label);
        try {
            const result = func();
            if (result && typeof result.then === 'function') {
                // Handle async functions
                return result.finally(() => {
                    this.endTimer(label);
                });
            } else {
                this.endTimer(label);
                return result;
            }
        } catch (error) {
            this.endTimer(label);
            throw error;
        }
    }

    /**
     * Component state tracking
     */
    trackComponentState(componentName, state) {
        this.componentStates.set(componentName, {
            state: state,
            timestamp: new Date().toISOString(),
            previousState: this.componentStates.get(componentName)?.state
        });

        this.debug(`📊 Component state updated: ${componentName}`, state);
    }

    getComponentState(componentName) {
        return this.componentStates.get(componentName);
    }

    /**
     * Data inspection utilities
     */
    inspectObject(obj, label = 'Object') {
        console.group(`🔍 [Inspection] ${label}`);
        console.log('Type:', typeof obj);
        console.log('Constructor:', obj?.constructor?.name);

        if (obj !== null && typeof obj === 'object') {
            console.log('Keys:', Object.keys(obj));
            console.log('Length:', Object.keys(obj).length);

            if (Array.isArray(obj)) {
                console.log('Array length:', obj.length);
                console.log('First item:', obj[0]);
                console.log('Last item:', obj[obj.length - 1]);
            }

            console.log('Object:', obj);
        } else {
            console.log('Value:', obj);
        }

        console.groupEnd();
    }

    inspectTableData(tableData) {
        console.group('📊 [Table Data Inspection]');

        if (tableData) {
            console.log('Total rows:', tableData.allRows?.length || 0);
            console.log('Parent rows:', tableData.parentRows?.length || 0);
            console.log('Child rows:', tableData.childRows?.length || 0);

            if (tableData.parentRows && tableData.parentRows.length > 0) {
                console.log('First parent:', tableData.parentRows[0]);
            }

            if (tableData.childRows && tableData.childRows.length > 0) {
                console.log('First child:', tableData.childRows[0]);
            }
        } else {
            console.log('No table data available');
        }

        console.groupEnd();
    }

    /**
     * Create visual console panel
     */
    createConsolePanel() {
        const consolePanel = $(`
            <div id="dev-console-panel" style="position: fixed; bottom: 10px; right: 10px; width: 400px; height: 300px; background: #1e1e1e; border: 1px solid #444; border-radius: 8px; color: #fff; font-family: 'Courier New', monospace; font-size: 11px; z-index: 10000; display: none; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
                <div style="background: #333; padding: 8px; border-radius: 8px 8px 0 0; display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: bold;">🎛️ Dev Console</span>
                    <div>
                        <button onclick="window.devConsole.clearConsole()" style="background: #666; color: white; border: none; padding: 2px 6px; margin-right: 5px; font-size: 10px;">Clear</button>
                        <button onclick="window.devConsole.exportLogs()" style="background: #666; color: white; border: none; padding: 2px 6px; margin-right: 5px; font-size: 10px;">Export</button>
                        <button onclick="window.devConsole.toggleConsole()" style="background: #666; color: white; border: none; padding: 2px 6px; font-size: 10px;">Hide</button>
                    </div>
                </div>
                <div id="console-output" style="height: 250px; overflow-y: auto; padding: 8px; background: #1e1e1e;">
                    <div style="color: #888; text-align: center; padding: 20px;">Console output will appear here...</div>
                </div>
            </div>
        `);

        // Toggle button
        const toggleButton = $(`
            <button id="dev-console-toggle" style="position: fixed; bottom: 10px; right: 420px; background: #007bff; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; z-index: 9999;">
                🎛️ Console
            </button>
        `);

        $('body').append(consolePanel).append(toggleButton);

        // Setup toggle functionality
        toggleButton.on('click', () => this.toggleConsole());

        // Make globally accessible
        window.devConsole = this;
    }

    /**
     * Toggle console panel visibility
     */
    toggleConsole() {
        const panel = $('#dev-console-panel');
        const button = $('#dev-console-toggle');

        if (panel.is(':visible')) {
            panel.hide();
            button.css('right', '10px');
        } else {
            panel.show();
            button.css('right', '420px');
            this.updateConsolePanel();
        }
    }

    /**
     * Update console panel with recent logs
     */
    updateConsolePanel() {
        const output = $('#console-output');
        if (output.length === 0) return;

        const recentLogs = this.logHistory.slice(-20); // Show last 20 entries
        const logHtml = recentLogs.map(log => {
            const time = new Date(log.timestamp).toLocaleTimeString();
            const color = this.getLogLevelColor(log.level);
            const message = this.escapeHtml(log.message.substring(0, 150));

            return `<div style="margin-bottom: 4px; border-left: 3px solid ${color}; padding-left: 6px;">
                <span style="color: #888; font-size: 10px;">${time}</span>
                <span style="color: ${color}; font-weight: bold;"> [${log.level}]</span>
                <span style="color: #fff;">${message}</span>
            </div>`;
        }).join('');

        output.html(logHtml);
        output.scrollTop(output[0].scrollHeight);
    }

    /**
     * Get color for log level
     */
    getLogLevelColor(level) {
        const colors = {
            'DEBUG': '#888',
            'INFO': '#17a2b8',
            'WARN': '#ffc107',
            'ERROR': '#dc3545',
            'SUCCESS': '#28a745'
        };
        return colors[level] || '#fff';
    }

    /**
     * Escape HTML for safe display
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Clear console logs
     */
    clearConsole() {
        this.logHistory = [];
        this.updateConsolePanel();
        console.clear();
        console.log('🎛️ [Dev Console] Console cleared');
    }

    /**
     * Export logs to file
     */
    exportLogs() {
        const exportData = {
            timestamp: new Date().toISOString(),
            url: window.location.href,
            totalLogs: this.logHistory.length,
            performanceData: Object.fromEntries(this.performanceData),
            componentStates: Object.fromEntries(this.componentStates),
            logs: this.logHistory
        };

        const dataStr = JSON.stringify(exportData, null, 2);
        const dataBlob = new Blob([dataStr], {type: 'application/json'});
        const url = URL.createObjectURL(dataBlob);

        const link = document.createElement('a');
        link.href = url;
        link.download = `console-logs-${Date.now()}.json`;
        link.click();

        URL.revokeObjectURL(url);
    }

    /**
     * Setup performance monitoring
     */
    setupPerformanceMonitoring() {
        // Monitor page load performance
        window.addEventListener('load', () => {
            const perfData = performance.getEntriesByType('navigation')[0];
            this.perf('📊 Page load performance:', {
                domContentLoaded: perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart,
                loadComplete: perfData.loadEventEnd - perfData.loadEventStart,
                totalTime: perfData.loadEventEnd - perfData.fetchStart
            });
        });

        // Monitor slow operations
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            const start = performance.now();
            try {
                const response = await originalFetch.apply(window, args);
                const duration = performance.now() - start;

                if (duration > 1000) {
                    this.warn(`🐌 Slow API call: ${args[0]} (${duration.toFixed(2)}ms)`);
                } else {
                    this.api(`⚡ API call: ${args[0]} (${duration.toFixed(2)}ms)`);
                }

                return response;
            } catch (error) {
                const duration = performance.now() - start;
                this.error(`❌ Failed API call: ${args[0]} (${duration.toFixed(2)}ms)`, error);
                throw error;
            }
        };
    }

    /**
     * Setup error tracking
     */
    setupErrorTracking() {
        // Track JavaScript errors
        window.addEventListener('error', (event) => {
            this.error('🚨 JavaScript Error:', {
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
                stack: event.error?.stack
            });
        });

        // Track unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            this.error('🚨 Unhandled Promise Rejection:', {
                reason: event.reason,
                stack: event.reason?.stack
            });
        });
    }

    /**
     * Quick analysis methods
     */
    analyzePerformance() {
        console.group('⚡ [Performance Analysis]');

        // Analyze performance data
        const timers = Array.from(this.performanceData.entries());
        if (timers.length > 0) {
            console.table(timers.map(([name, data]) => ({
                Timer: name,
                'Duration (ms)': data.duration?.toFixed(2) || 'N/A',
                'Start Time': new Date(data.startTime).toLocaleTimeString()
            })));
        }

        // Analyze console logs
        const logsByLevel = {};
        this.logHistory.forEach(log => {
            logsByLevel[log.level] = (logsByLevel[log.level] || 0) + 1;
        });

        console.log('📊 Log Summary:', logsByLevel);
        console.log('📊 Total Logs:', this.logHistory.length);
        console.log('📊 Component States:', this.componentStates.size);

        console.groupEnd();
    }

    /**
     * System health check
     */
    systemHealthCheck() {
        console.group('🏥 [System Health Check]');

        // Check table manager
        if (window.devTableManager) {
            console.log('✅ Table Manager: Active');
            console.log('📊 Table Stats:', {
                totalRows: window.devTableManager.tableState.allRows.length,
                parentRows: window.devTableManager.tableState.parentRows.length,
                childRows: window.devTableManager.tableState.childRows.length
            });
        } else {
            console.warn('⚠️ Table Manager: Not found');
        }

        // Check API manager
        if (window.devAPIManager) {
            console.log('✅ API Manager: Active');
            console.log('📊 API Stats:', window.devAPIManager.requestMetrics);
        } else {
            console.warn('⚠️ API Manager: Not found');
        }

        // Check page performance
        const perfData = performance.getEntriesByType('navigation')[0];
        console.log('⚡ Page Performance:', {
            domContentLoaded: perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart,
            loadComplete: perfData.loadEventEnd - perfData.loadEventStart
        });

        console.log('📊 Memory Usage:', {
            used: (performance.memory?.usedJSHeapSize / 1024 / 1024).toFixed(2) + ' MB',
            total: (performance.memory?.totalJSHeapSize / 1024 / 1024).toFixed(2) + ' MB',
            limit: (performance.memory?.jsHeapSizeLimit / 1024 / 1024).toFixed(2) + ' MB'
        });

        console.groupEnd();
    }
}

// Initialize when DOM is ready
$(document).ready(function() {
    setTimeout(() => {
        if (typeof window.devConsole === 'undefined') {
            window.devConsole = new DevEnhancedConsole();

            // Show welcome message
            window.devConsole.init('🎛️ Enhanced Development Console is ready!');
            window.devConsole.success('🚀 All development utilities loaded successfully!');

            // Run system health check after 2 seconds
            setTimeout(() => {
                window.devConsole.systemHealthCheck();
            }, 2000);
        }
    }, 2000);
});