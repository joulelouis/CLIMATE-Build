/**
 * Development Utilities Integration
 * Integrates all development tools and provides additional utilities
 */

class DevUtilitiesIntegration {
    constructor() {
        this.utilities = {
            dataInspector: new DataInspector(),
            polygonDebugger: new PolygonDebugger(),
            workflowAnalyzer: new WorkflowAnalyzer(),
            performanceProfiler: new PerformanceProfiler(),
            exportManager: new ExportManager()
        };

        this.integrationComplete = false;
        this.initializeIntegration();
    }

    /**
     * Initialize all development utilities
     */
    initializeIntegration() {
        console.log('🔧 [Dev Integration] Initializing development utilities...');

        // Wait for all components to load
        this.waitForComponents().then(() => {
            this.setupIntegration();
            this.createMasterControlPanel();
            this.setupKeyboardShortcuts();
            this.addQuickAnalysisTools();

            this.integrationComplete = true;
            console.success('✅ [Dev Integration] All development utilities integrated successfully!');
        });
    }

    /**
     * Wait for all development components to be available
     */
    async waitForComponents() {
        const maxWaitTime = 10000; // 10 seconds
        const checkInterval = 100;
        let waitTime = 0;

        while (waitTime < maxWaitTime) {
            if (window.devTableManager && window.devAPIManager && window.devConsole) {
                console.log('✅ [Dev Integration] All components ready');
                return;
            }

            await this.delay(checkInterval);
            waitTime += checkInterval;
        }

        console.warn('⚠️ [Dev Integration] Some components may not be fully loaded');
    }

    /**
     * Setup integration between components
     */
    setupIntegration() {
        console.log('🔗 [Dev Integration] Setting up component integration...');

        // Connect API manager with console logging
        if (window.devAPIManager && window.devConsole) {
            const originalMakeRequest = window.devAPIManager.makeRequest;
            window.devAPIManager.makeRequest = async function(url, options) {
                window.devConsole.api(`📡 Request: ${options.method || 'GET'} ${url}`);
                const result = await originalMakeRequest.call(this, url, options);

                if (result.success) {
                    window.devConsole.success(`✅ Response: ${result.responseTime?.toFixed(2)}ms`);
                } else {
                    window.devConsole.error(`❌ Error: ${result.error}`);
                }

                return result;
            };
        }

        // Connect table manager with performance monitoring
        if (window.devTableManager && window.devConsole) {
            const originalRenderTable = window.devTableManager.renderTable;
            window.devTableManager.renderTable = function(page) {
                window.devConsole.startTimer('tableRender');
                const result = originalRenderTable.call(this, page);
                window.devConsole.endTimer('tableRender');
                return result;
            };
        }

        // Connect polygon debugging with table manager
        this.utilities.polygonDebugger.setTableManager(window.devTableManager);

        console.log('✅ [Dev Integration] Component integration complete');
    }

    /**
     * Create master control panel
     */
    createMasterControlPanel() {
        const masterPanel = $(`
            <div id="dev-master-controls" style="position: fixed; top: 50%; right: 10px; transform: translateY(-50%); background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border: none; border-radius: 12px; padding: 15px; color: white; z-index: 10001; box-shadow: 0 8px 32px rgba(0,0,0,0.3); min-width: 200px;">
                <h6 style="margin: 0 0 12px 0; font-size: 14px; font-weight: bold; text-align: center;">🛠️ Dev Tools</h6>

                <div style="display: grid; gap: 8px; font-size: 11px;">
                    <button onclick="window.devIntegration.quickSystemCheck()" style="background: rgba(255,255,255,0.2); color: white; border: none; padding: 6px 8px; border-radius: 4px; cursor: pointer;">🔍 System Check</button>
                    <button onclick="window.devIntegration.analyzeCurrentData()" style="background: rgba(255,255,255,0.2); color: white; border: none; padding: 6px 8px; border-radius: 4px; cursor: pointer;">📊 Analyze Data</button>
                    <button onclick="window.devIntegration.debugPolygons()" style="background: rgba(255,255,255,0.2); color: white; border: none; padding: 6px 8px; border-radius: 4px; cursor: pointer;">🏗️ Debug Polygons</button>
                    <button onclick="window.devIntegration.exportAllData()" style="background: rgba(255,255,255,0.2); color: white; border: none; padding: 6px 8px; border-radius: 4px; cursor: pointer;">💾 Export All</button>
                    <button onclick="window.devIntegration.performanceAnalysis()" style="background: rgba(255,255,255,0.2); color: white; border: none; padding: 6px 8px; border-radius: 4px; cursor: pointer;">⚡ Performance</button>
                    <button onclick="window.devIntegration.showDevConsole()" style="background: rgba(255,255,255,0.2); color: white; border: none; padding: 6px 8px; border-radius: 4px; cursor: pointer;">🎛️ Console</button>
                    <button onclick="window.devIntegration.toggleMockMode()" style="background: rgba(255,255,255,0.2); color: white; border: none; padding: 6px 8px; border-radius: 4px; cursor: pointer;">🎭 Mock Mode</button>
                    <button onclick="window.devIntegration.runQuickTests()" style="background: rgba(255,255,255,0.2); color: white; border: none; padding: 6px 8px; border-radius: 4px; cursor: pointer;">🧪 Quick Tests</button>
                </div>

                <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.3); font-size: 10px; text-align: center;">
                    <div id="dev-status-indicator" style="color: #4ade80;">● All Systems Ready</div>
                </div>
            </div>
        `);

        $('body').append(masterPanel);

        // Minimize/maximize functionality
        let minimized = false;
        masterPanel.find('h6').on('click', () => {
            minimized = !minimized;
            masterPanel.find('div').eq(0).toggle();
            masterPanel.css('min-width', minimized ? '60px' : '200px');
        });

        // Make globally accessible
        window.devIntegration = this;
    }

    /**
     * Setup keyboard shortcuts for development
     */
    setupKeyboardShortcuts() {
        $(document).on('keydown', (e) => {
            // Only activate when not typing in input fields
            if ($(e.target).is('input, textarea, select')) return;

            // Ctrl/Cmd + Shift + D: Toggle debug console
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'D') {
                e.preventDefault();
                window.devConsole?.toggleConsole();
            }

            // Ctrl/Cmd + Shift + S: System health check
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'S') {
                e.preventDefault();
                this.quickSystemCheck();
            }

            // Ctrl/Cmd + Shift + E: Export data
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'E') {
                e.preventDefault();
                this.exportAllData();
            }

            // Ctrl/Cmd + Shift + P: Performance analysis
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'P') {
                e.preventDefault();
                this.performanceAnalysis();
            }
        });

        console.log('⌨️ [Dev Integration] Keyboard shortcuts configured');
        console.log('   Ctrl+Shift+D: Toggle Console');
        console.log('   Ctrl+Shift+S: System Check');
        console.log('   Ctrl+Shift+E: Export Data');
        console.log('   Ctrl+Shift+P: Performance Analysis');
    }

    /**
     * Add quick analysis tools to the page
     */
    addQuickAnalysisTools() {
        // Add floating stats indicator
        const statsIndicator = $(`
            <div id="dev-stats-indicator" style="position: fixed; top: 10px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.8); color: white; padding: 5px 15px; border-radius: 20px; font-size: 11px; z-index: 1000;">
                Loading...
            </div>
        `);

        $('body').append(statsIndicator);

        // Update stats every 2 seconds
        setInterval(() => {
            this.updateStatsIndicator();
        }, 2000);
    }

    /**
     * Update stats indicator
     */
    updateStatsIndicator() {
        const stats = this.gatherQuickStats();
        const indicator = $('#dev-stats-indicator');

        if (indicator.length > 0) {
            indicator.text(`📊 ${stats.totalRows} rows | 🏗️ ${stats.polygons} polygons | ⚡ ${stats.avgResponseTime}ms | 🧪 ${stats.mockMode ? 'Mock' : 'Live'}`);
        }
    }

    /**
     * Gather quick statistics
     */
    gatherQuickStats() {
        return {
            totalRows: window.devTableManager?.tableState?.allRows?.length || 0,
            parentRows: window.devTableManager?.tableState?.parentRows?.length || 0,
            childRows: window.devTableManager?.tableState?.childRows?.length || 0,
            polygons: window.devTableManager?.tableState?.parentRows?.length || 0,
            apiRequests: window.devAPIManager?.requestMetrics?.totalRequests || 0,
            avgResponseTime: window.devAPIManager?.requestMetrics?.averageResponseTime?.toFixed(0) || 0,
            mockMode: window.devAPIManager?.mockMode || false
        };
    }

    /**
     * Master control panel methods
     */
    quickSystemCheck() {
        console.group('🔍 [Quick System Check]');

        try {
            // Check all components
            const components = {
                'Table Manager': !!window.devTableManager,
                'API Manager': !!window.devAPIManager,
                'Enhanced Console': !!window.devConsole,
                'Data Inspector': !!this.utilities.dataInspector,
                'Polygon Debugger': !!this.utilities.polygonDebugger
            };

            console.table(components);
            console.success('✅ System check completed');

            // Update status indicator
            const allReady = Object.values(components).every(status => status);
            $('#dev-status-indicator')
                .text(allReady ? '● All Systems Ready' : '⚠️ Some Issues Detected')
                .css('color', allReady ? '#4ade80' : '#fbbf24');

        } catch (error) {
            console.error('❌ System check failed:', error);
        }

        console.groupEnd();
    }

    analyzeCurrentData() {
        console.group('📊 [Data Analysis]');

        this.utilities.dataInspector.analyzeTableData();
        this.utilities.dataInspector.analyzePolygonData();
        this.utilities.dataInspector.analyzeClimateData();

        console.groupEnd();
    }

    debugPolygons() {
        console.group('🏗️ [Polygon Debugging]');

        this.utilities.polygonDebugger.debugPolygonHierarchy();
        this.utilities.polygonDebugger.debugPolygonGeometry();
        this.utilities.polygonDebugger.debugPolygonDataFlow();

        console.groupEnd();
    }

    exportAllData() {
        console.group('💾 [Data Export]');

        this.utilities.exportManager.exportTableData();
        this.utilities.exportManager.exportAPIMetrics();
        this.utilities.exportManager.exportConsoleLogs();
        this.utilities.exportManager.exportPerformanceData();

        console.groupEnd();
    }

    performanceAnalysis() {
        console.group('⚡ [Performance Analysis]');

        this.utilities.performanceProfiler.analyzeTablePerformance();
        this.utilities.performanceProfiler.analyzeAPIPerformance();
        this.utilities.performanceProfiler.analyzeMemoryUsage();

        console.groupEnd();
    }

    showDevConsole() {
        window.devConsole?.toggleConsole();
    }

    toggleMockMode() {
        if (window.devAPIManager) {
            window.devAPIManager.toggleMockMode();
            const status = window.devAPIManager.mockMode ? 'enabled' : 'disabled';
            console.log(`🎭 Mock mode ${status}`);
        }
    }

    runQuickTests() {
        console.group('🧪 [Quick Tests]');

        this.runTableManagerTest();
        this.runAPIManagerTest();
        this.runConsoleTest();

        console.groupEnd();
    }

    /**
     * Quick test methods
     */
    runTableManagerTest() {
        if (!window.devTableManager) {
            console.warn('⚠️ Table Manager not available for testing');
            return;
        }

        try {
            const startTime = performance.now();
            const rowCount = window.devTableManager.tableState.allRows.length;
            const duration = performance.now() - startTime;

            console.success(`✅ Table Manager Test: ${rowCount} rows processed in ${duration.toFixed(2)}ms`);
        } catch (error) {
            console.error('❌ Table Manager Test failed:', error);
        }
    }

    runAPIManagerTest() {
        if (!window.devAPIManager) {
            console.warn('⚠️ API Manager not available for testing');
            return;
        }

        try {
            const metrics = window.devAPIManager.requestMetrics;
            console.success(`✅ API Manager Test: ${metrics.totalRequests} requests, ${metrics.successfulRequests} successful`);
        } catch (error) {
            console.error('❌ API Manager Test failed:', error);
        }
    }

    runConsoleTest() {
        if (!window.devConsole) {
            console.warn('⚠️ Enhanced Console not available for testing');
            return;
        }

        try {
            const logCount = window.devConsole.logHistory.length;
            console.success(`✅ Console Test: ${logCount} logs captured`);
        } catch (error) {
            console.error('❌ Console Test failed:', error);
        }
    }

    /**
     * Utility methods
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

/**
 * Data Inspector Utility
 */
class DataInspector {
    analyzeTableData() {
        if (!window.devTableManager) {
            console.warn('⚠️ Table Manager not available');
            return;
        }

        const data = window.devTableManager.tableState;
        console.log('📊 Table Data Analysis:');
        console.table({
            'Total Rows': data.allRows.length,
            'Parent Rows': data.parentRows.length,
            'Child Rows': data.childRows.length,
            'Current Page': data.currentPage,
            'Rows Per Page': data.rowsPerPage
        });
    }

    analyzePolygonData() {
        if (!window.devTableManager) {
            console.warn('⚠️ Table Manager not available');
            return;
        }

        const polygons = window.devTableManager.tableState.parentRows;
        console.log(`🏗️ Polygon Analysis: ${polygons.length} polygons found`);

        polygons.forEach((polygon, index) => {
            const facilityName = polygon.cells.find(c => c.columnName === 'Facility')?.value || `Polygon ${index + 1}`;
            const lat = polygon.cells.find(c => c.columnName === 'Lat')?.numericValue;
            const lng = polygon.cells.find(c => c.columnName === 'Long')?.numericValue;

            console.log(`   ${index + 1}. ${facilityName} (${lat}, ${lng})`);
        });
    }

    analyzeClimateData() {
        if (!window.devTableManager) {
            console.warn('⚠️ Table Manager not available');
            return;
        }

        const columns = window.devTableManager.tableState.columnHeaders;
        const climateColumns = columns.filter(col =>
            col.name.toLowerCase().includes('flood') ||
            col.name.toLowerCase().includes('wind') ||
            col.name.toLowerCase().includes('temperature') ||
            col.name.toLowerCase().includes('stress')
        );

        console.log(`🌡️ Climate Data: ${climateColumns.length} climate columns detected`);
        climateColumns.forEach(col => console.log(`   - ${col.name} (${col.dataType})`));
    }
}

/**
 * Polygon Debugger Utility
 */
class PolygonDebugger {
    setTableManager(tableManager) {
        this.tableManager = tableManager;
    }

    debugPolygonHierarchy() {
        if (!this.tableManager) {
            console.warn('⚠️ Table Manager not set');
            return;
        }

        const parents = this.tableManager.tableState.parentRows;
        const children = this.tableManager.tableState.childRows;

        console.log('🏗️ Polygon Hierarchy Debug:');
        console.log(`   Parents: ${parents.length}`);
        console.log(`   Children: ${children.length}`);

        parents.forEach(parent => {
            const parentName = parent.cells.find(c => c.columnName === 'Facility')?.value;
            const childCount = children.filter(child =>
                child.element.dataset.parentId === parentName ||
                child.element.dataset.parentFacility === parentName
            ).length;

            console.log(`   📁 ${parentName}: ${childCount} children`);
        });
    }

    debugPolygonGeometry() {
        console.log('🏗️ Polygon Geometry Debug: Geometry inspection would be implemented here');
        // This would inspect the actual polygon geometries if available
    }

    debugPolygonDataFlow() {
        console.log('🏗️ Polygon Data Flow Debug: Data flow inspection would be implemented here');
        // This would trace how polygon data flows through the system
    }
}

/**
 * Performance Profiler Utility
 */
class PerformanceProfiler {
    analyzeTablePerformance() {
        if (!window.devTableManager) return;

        const metrics = window.devTableManager.performanceMetrics;
        console.log('⚡ Table Performance:');
        console.table(metrics);
    }

    analyzeAPIPerformance() {
        if (!window.devAPIManager) return;

        const metrics = window.devAPIManager.requestMetrics;
        console.log('⚡ API Performance:');
        console.table(metrics);
    }

    analyzeMemoryUsage() {
        if (performance.memory) {
            console.log('⚡ Memory Usage:');
            console.table({
                'Used JS Heap': `${(performance.memory.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`,
                'Total JS Heap': `${(performance.memory.totalJSHeapSize / 1024 / 1024).toFixed(2)} MB`,
                'JS Heap Limit': `${(performance.memory.jsHeapSizeLimit / 1024 / 1024).toFixed(2)} MB`
            });
        }
    }
}

/**
 * Export Manager Utility
 */
class ExportManager {
    exportTableData() {
        if (window.devTableManager) {
            window.devTableManager.exportData();
        }
    }

    exportAPIMetrics() {
        if (window.devAPIManager) {
            const metrics = window.devAPIManager.requestMetrics;
            const dataStr = JSON.stringify(metrics, null, 2);
            this.downloadFile(dataStr, 'api-metrics.json', 'application/json');
        }
    }

    exportConsoleLogs() {
        if (window.devConsole) {
            window.devConsole.exportLogs();
        }
    }

    exportPerformanceData() {
        const performanceData = {
            timestamp: new Date().toISOString(),
            navigation: performance.getEntriesByType('navigation')[0],
            resources: performance.getEntriesByType('resource'),
            memory: performance.memory
        };

        const dataStr = JSON.stringify(performanceData, null, 2);
        this.downloadFile(dataStr, 'performance-data.json', 'application/json');
    }

    downloadFile(content, filename, contentType) {
        const blob = new Blob([content], { type: contentType });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.click();
        URL.revokeObjectURL(url);
    }
}

// Initialize the integration system
$(document).ready(function() {
    setTimeout(() => {
        if (typeof window.devIntegration === 'undefined') {
            window.devIntegration = new DevUtilitiesIntegration();
        }
    }, 3000);
});