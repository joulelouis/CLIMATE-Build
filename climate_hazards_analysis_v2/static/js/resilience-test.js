/**
 * Resilience Testing Suite
 * Comprehensive testing for the resilient frontend implementation
 */

class ResilienceTestSuite {
    constructor() {
        this.tests = [];
        this.results = [];
        this.currentTest = null;
    }

    addTest(name, testFunction, category = 'general') {
        this.tests.push({
            name,
            fn: testFunction,
            category,
            status: 'pending'
        });
    }

    async runTests() {
        console.log('🧪 Starting Resilience Test Suite...');
        console.log(`Found ${this.tests.length} tests to run`);

        this.results = [];

        for (const test of this.tests) {
            this.currentTest = test;
            console.log(`\n📋 Running: ${test.name}`);

            try {
                const startTime = performance.now();
                const result = await test.fn();
                const endTime = performance.now();

                this.results.push({
                    name: test.name,
                    category: test.category,
                    status: 'passed',
                    duration: endTime - startTime,
                    result
                });

                console.log(`✅ ${test.name} - PASSED (${(endTime - startTime).toFixed(2)}ms)`);

            } catch (error) {
                this.results.push({
                    name: test.name,
                    category: test.category,
                    status: 'failed',
                    error: error.message,
                    stack: error.stack
                });

                console.error(`❌ ${test.name} - FAILED: ${error.message}`);
            }
        }

        this.printSummary();
        return this.results;
    }

    printSummary() {
        const passed = this.results.filter(r => r.status === 'passed').length;
        const failed = this.results.filter(r => r.status === 'failed').length;
        const total = this.results.length;

        console.log('\n' + '='.repeat(60));
        console.log('📊 TEST SUMMARY');
        console.log('='.repeat(60));
        console.log(`Total Tests: ${total}`);
        console.log(`Passed: ${passed} ✅`);
        console.log(`Failed: ${failed} ❌`);
        console.log(`Success Rate: ${((passed / total) * 100).toFixed(1)}%`);

        if (failed > 0) {
            console.log('\n❌ Failed Tests:');
            this.results
                .filter(r => r.status === 'failed')
                .forEach(r => {
                    console.log(`  - ${r.name}: ${r.error}`);
                });
        }

        // Print category breakdown
        const categories = [...new Set(this.tests.map(t => t.category))];
        console.log('\n📂 Results by Category:');
        categories.forEach(category => {
            const categoryTests = this.results.filter(r => r.category === category);
            const categoryPassed = categoryTests.filter(r => r.status === 'passed').length;
            const categoryTotal = categoryTests.length;
            console.log(`  ${category}: ${categoryPassed}/${categoryTotal} (${((categoryPassed / categoryTotal) * 100).toFixed(1)}%)`);
        });
    }

    exportResults() {
        const exportData = {
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent,
            url: window.location.href,
            summary: {
                total: this.results.length,
                passed: this.results.filter(r => r.status === 'passed').length,
                failed: this.results.filter(r => r.status === 'failed').length
            },
            results: this.results
        };

        const blob = new Blob([JSON.stringify(exportData, null, 2)], {
            type: 'application/json'
        });

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `resilience-test-results-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

// Test implementations
const testSuite = new ResilienceTestSuite();

// Data Validation Tests
testSuite.addTest('Validate window.tableData exists', () => {
    if (!window.tableData) {
        throw new Error('window.tableData is not defined');
    }
    if (!Array.isArray(window.tableData)) {
        throw new Error('window.tableData is not an array');
    }
    return { dataLength: window.tableData.length };
}, 'data-validation');

testSuite.addTest('Validate window.tableColumns exists', () => {
    if (!window.tableColumns) {
        throw new Error('window.tableColumns is not defined');
    }
    if (!Array.isArray(window.tableColumns)) {
        throw new Error('window.tableColumns is not an array');
    }
    return { columnsLength: window.tableColumns.length };
}, 'data-validation');

testSuite.addTest('Validate data structure integrity', () => {
    if (!window.tableData || window.tableData.length === 0) {
        throw new Error('No data to validate');
    }

    const firstRow = window.tableData[0];
    if (!firstRow || typeof firstRow !== 'object') {
        throw new Error('First data row is not an object');
    }

    // Check if required columns exist
    const requiredColumns = ['Facility', 'Asset Archetype'];
    for (const column of requiredColumns) {
        if (!(column in firstRow)) {
            throw new Error(`Required column '${column}' not found in data`);
        }
    }

    return {
        firstRowKeys: Object.keys(firstRow),
        sampleValues: requiredColumns.map(col => firstRow[col])
    };
}, 'data-validation');

// Error Handling Tests
testSuite.addTest('Test ClimateriskErrorHandler exists', () => {
    if (!window.ClimateriskErrorHandler) {
        throw new Error('ClimateriskErrorHandler not available');
    }

    const errorHandler = window.ClimateriskErrorHandler;
    if (typeof errorHandler.handleError !== 'function') {
        throw new Error('handleError method not found');
    }

    return { methods: Object.getOwnPropertyNames(errorHandler) };
}, 'error-handling');

testSuite.addTest('Test error handling functionality', () => {
    if (!window.ClimateriskErrorHandler) {
        throw new Error('ClimateriskErrorHandler not available');
    }

    // Test error display
    const originalDisplay = window.ClimateriskErrorHandler.displayError;
    let errorDisplayed = false;
    window.ClimateriskErrorHandler.displayError = (message) => {
        errorDisplayed = true;
        return originalDisplay.call(window.ClimateriskErrorHandler, message);
    };

    window.ClimateriskErrorHandler.handleError('Test error message');

    // Restore original method
    window.ClimateriskErrorHandler.displayError = originalDisplay;

    if (!errorDisplayed) {
        throw new Error('Error was not displayed');
    }

    return { errorHandled: true };
}, 'error-handling');

// AJAX and Network Tests
testSuite.addTest('Test ResilientAjaxHandler exists', () => {
    if (!window.ResilientAjaxHandler) {
        throw new Error('ResilientAjaxHandler not available');
    }

    if (!window.ajaxHandler) {
        throw new Error('Global ajaxHandler instance not found');
    }

    return {
        classAvailable: true,
        instanceAvailable: true,
        stats: window.ajaxHandler.getStats()
    };
}, 'network');

testSuite.addTest('Test network status monitoring', () => {
    if (!window.connectionMonitor) {
        throw new Error('Connection monitor not available');
    }

    const isOnline = window.connectionMonitor.isOnline;
    if (typeof isOnline !== 'boolean') {
        throw new Error('Network status not properly detected');
    }

    return {
        isOnline,
        hasStatusIndicator: !!document.getElementById('network-status')
    };
}, 'network');

// State Management Tests
testSuite.addTest('Test StateManager exists', () => {
    if (!window.StateManager) {
        throw new Error('StateManager class not available');
    }

    if (!window.stateManager) {
        throw new Error('Global stateManager instance not found');
    }

    return {
        classAvailable: true,
        instanceAvailable: true,
        stats: window.stateManager.getStats()
    };
}, 'state-management');

testSuite.addTest('Test state persistence', () => {
    if (!window.stateManager) {
        throw new Error('StateManager not available');
    }

    // Save current state
    const originalState = window.stateManager.getState();

    // Modify state
    window.stateManager.state.testProperty = 'test-value';
    window.stateManager.markDirty();

    // Save state
    window.stateManager.saveState(true);

    // Check if localStorage was updated
    const storageKey = window.stateManager.options.storageKey;
    const savedState = localStorage.getItem(storageKey);

    if (!savedState) {
        throw new Error('State was not saved to localStorage');
    }

    // Restore original state
    window.stateManager.state = originalState;
    window.stateManager.saveState(true);

    return {
        stateSaved: true,
        storageKey,
        stateSize: savedState.length
    };
}, 'state-management');

// Progressive Loading Tests
testSuite.addTest('Test ProgressiveTableLoader exists', () => {
    if (!window.ProgressiveTableLoader) {
        throw new Error('ProgressiveTableLoader not available');
    }

    return { classAvailable: true };
}, 'performance');

testSuite.addTest('Test table DOM elements exist', () => {
    const table = document.getElementById('hazard-data-table');
    if (!table) {
        throw new Error('Main table element not found');
    }

    const tbody = table.querySelector('tbody');
    if (!tbody) {
        throw new Error('Table tbody not found');
    }

    const rows = tbody.querySelectorAll('tr');
    if (rows.length === 0) {
        throw new Error('No table rows found');
    }

    return {
        tableExists: true,
        rowCount: rows.length,
        hasData: rows.length > 0
    };
}, 'dom-elements');

testSuite.addTest('Test column selector functionality', () => {
    const columnCheckboxes = document.querySelectorAll('.hazard-column, .base-column');
    if (columnCheckboxes.length === 0) {
        throw new Error('No column checkboxes found');
    }

    let checkedCount = 0;
    columnCheckboxes.forEach(checkbox => {
        if (checkbox.checked) checkedCount++;
    });

    return {
        totalColumns: columnCheckboxes.length,
        checkedColumns: checkedCount,
        hasUnchecked: checkedCount < columnCheckboxes.length
    };
}, 'dom-elements');

testSuite.addTest('Test tab functionality', () => {
    const tabs = document.querySelectorAll('[data-bs-toggle="tab"]');
    if (tabs.length === 0) {
        throw new Error('No tabs found');
    }

    const activeTab = document.querySelector('.tab-pane.active');
    if (!activeTab) {
        throw new Error('No active tab found');
    }

    return {
        totalTabs: tabs.length,
        activeTabId: activeTab.id,
        hasMapTabs: tabs.length > 1
    };
}, 'dom-elements');

// Performance Tests
testSuite.addTest('Test page load performance', () => {
    const loadTime = performance.timing.loadEventEnd - performance.timing.navigationStart;
    if (loadTime > 10000) { // 10 seconds
        console.warn(`Page load time is high: ${loadTime}ms`);
    }

    return {
        loadTime,
        domContentLoaded: performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart
    };
}, 'performance');

testSuite.addTest('Test memory usage', () => {
    if (performance.memory) {
        const memory = performance.memory;
        const usedMB = memory.usedJSHeapSize / 1024 / 1024;
        const totalMB = memory.totalJSHeapSize / 1024 / 1024;

        return {
            usedMB: usedMB.toFixed(2),
            totalMB: totalMB.toFixed(2),
            limitMB: (memory.jsHeapSizeLimit / 1024 / 1024).toFixed(2)
        };
    } else {
        return { message: 'Memory API not available in this browser' };
    }
}, 'performance');

// Browser Compatibility Tests
testSuite.addTest('Test modern JavaScript features', () => {
    const features = {
        arrowFunctions: (() => true)(),
        destructuring: (() => { const [a] = [1]; return a === 1; })(),
        templateLiterals: `test`.includes('test'),
        asyncAwait: (async () => true)() instanceof Promise,
        classes: class Test {} !== undefined
    };

    const unsupportedFeatures = Object.entries(features)
        .filter(([name, supported]) => !supported)
        .map(([name]) => name);

    if (unsupportedFeatures.length > 0) {
        throw new Error(`Unsupported features: ${unsupportedFeatures.join(', ')}`);
    }

    return { features };
}, 'compatibility');

testSuite.addTest('Test required browser APIs', () => {
    const requiredAPIs = [
        'fetch',
        'localStorage',
        'sessionStorage',
        'History',
        'MutationObserver'
    ];

    const missingAPIs = requiredAPIs.filter(api => !(api in window));

    if (missingAPIs.length > 0) {
        throw new Error(`Missing required APIs: ${missingAPIs.join(', ')}`);
    }

    return {
        supportedAPIs: requiredAPIs,
        hasIntersectionObserver: 'IntersectionObserver' in window,
        hasRequestIdleCallback: 'requestIdleCallback' in window
    };
}, 'compatibility');

// Security Tests
testSuite.addTest('Test XSS prevention in data', () => {
    if (!window.tableData || window.tableData.length === 0) {
        return { message: 'No data to test' };
    }

    const suspiciousPatterns = [
        /<script/i,
        /javascript:/i,
        /on\w+\s*=/i,
        /<iframe/i
    ];

    let suspiciousEntries = [];

    window.tableData.forEach((row, index) => {
        Object.values(row).forEach(value => {
            if (typeof value === 'string') {
                suspiciousPatterns.forEach(pattern => {
                    if (pattern.test(value)) {
                        suspiciousEntries.push({ row: index, value, pattern: pattern.source });
                    }
                });
            }
        });
    });

    if (suspiciousEntries.length > 0) {
        console.warn('Potentially suspicious content found:', suspiciousEntries);
    }

    return {
        entriesChecked: window.tableData.length,
        suspiciousEntries: suspiciousEntries.length,
        suspiciousEntries
    };
}, 'security');

// Error Recovery Tests
testSuite.addTest('Test error fallback UI', () => {
    const errorFallback = document.getElementById('error-fallback');
    const loadingOverlay = document.getElementById('loading-overlay');

    if (!errorFallback) {
        throw new Error('Error fallback element not found');
    }

    if (!loadingOverlay) {
        throw new Error('Loading overlay element not found');
    }

    return {
        errorFallbackExists: true,
        loadingOverlayExists: true,
        hasRetryButton: !!errorFallback.querySelector('.btn-retry')
    };
}, 'error-recovery');

// Export/Import Tests
testSuite.addTest('Test state export functionality', () => {
    if (!window.stateManager) {
        throw new Error('StateManager not available');
    }

    if (typeof window.stateManager.exportState !== 'function') {
        throw new Error('exportState method not available');
    }

    // Test export (this will download a file in real usage)
    const originalCreateObjectURL = URL.createObjectURL;
    let exportCalled = false;

    URL.createObjectURL = (blob) => {
        exportCalled = true;
        console.log('State export triggered, blob size:', blob.size);
        return originalCreateObjectURL.call(URL, blob);
    };

    try {
        window.stateManager.exportState();
    } catch (error) {
        // Expected in test environment
    }

    // Restore original function
    URL.createObjectURL = originalCreateObjectURL;

    return { exportFunctionExists: true, exportCalled };
}, 'state-management');

// Run tests if this script is executed directly
if (typeof window !== 'undefined') {
    // Auto-run after page loads
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            setTimeout(() => runResilienceTests(), 1000);
        });
    } else {
        setTimeout(() => runResilienceTests(), 1000);
    }
}

// Global function to run tests
async function runResilienceTests() {
    console.log('🚀 Starting Climate Hazards Resilience Tests...');

    try {
        const results = await testSuite.runTests();

        // Store results globally for access
        window.resilienceTestResults = results;

        // Show summary in UI if possible
        showTestSummary(results);

        return results;
    } catch (error) {
        console.error('Test suite failed:', error);
        return null;
    }
}

function showTestSummary(results) {
    const passed = results.filter(r => r.status === 'passed').length;
    const failed = results.filter(r => r.status === 'failed').length;
    const total = results.length;

    // Create summary element
    const summary = document.createElement('div');
    summary.className = 'alert alert-info';
    summary.innerHTML = `
        <h6>🧪 Resilience Test Results</h6>
        <div class="progress mb-2">
            <div class="progress-bar bg-success" style="width: ${(passed/total)*100}%">
                ${passed} passed
            </div>
            ${failed > 0 ? `<div class="progress-bar bg-danger" style="width: ${(failed/total)*100}%">${failed} failed</div>` : ''}
        </div>
        <small>
            Success Rate: ${((passed/total)*100).toFixed(1)}% |
            <button class="btn btn-sm btn-outline-primary" onclick="testSuite.exportResults()">Export Results</button>
            <button class="btn btn-sm btn-outline-secondary" onclick="runResilienceTests()">Run Again</button>
        </small>
    `;

    // Add to page
    const container = document.querySelector('.container-fluid');
    if (container) {
        container.insertBefore(summary, container.firstChild);
    }
}

// Export for use in other scripts
window.ResilienceTestSuite = ResilienceTestSuite;
window.testSuite = testSuite;
window.runResilienceTests = runResilienceTests;