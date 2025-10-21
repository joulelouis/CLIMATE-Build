/**
 * CSRF Testing and Validation Script
 *
 * This script provides functions to test CSRF handling in various scenarios
 * including storage clearing, token regeneration, and error recovery.
 */

(function() {
    'use strict';

    window.CSRFTester = class CSRFTester {
        constructor() {
            this.testResults = [];
            this.debugMode = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        }

        /**
         * Run all CSRF tests
         */
        async runAllTests() {
            this.log('Starting comprehensive CSRF tests...');

            const tests = [
                this.testCSRFManagerPresence,
                this.testCurrentTokenPresence,
                this.testTokenValidation,
                this.testTokenRegeneration,
                this.testFormCSRFProtection,
                this.testAJAXCSRFProtection,
                this.testStorageClearScenario,
                this.testErrorRecovery
            ];

            for (const test of tests) {
                try {
                    await test.call(this);
                } catch (error) {
                    this.logError(`Test ${test.name} failed:`, error);
                    this.addTestResult(test.name, false, error.message);
                }
            }

            this.displayResults();
        }

        /**
         * Test if CSRF Manager is present and initialized
         */
        testCSRFManagerPresence() {
            this.log('Testing CSRF Manager presence...');

            const managerPresent = typeof window.csrfManager !== 'undefined';
            const managerInitialized = managerPresent && window.csrfManager instanceof window.CSRFManager;

            this.addTestResult('CSRF Manager Presence', managerInitialized,
                managerInitialized ? 'CSRF Manager is properly initialized' : 'CSRF Manager not found or not initialized');
        }

        /**
         * Test if current CSRF token is present
         */
        testCurrentTokenPresence() {
            this.log('Testing current CSRF token presence...');

            const hasCookie = document.cookie.includes('csrftoken=');
            const hasMetaTag = document.querySelector('meta[name="csrf-token"]') !== null;
            const hasHiddenField = document.querySelector('input[name="csrfmiddlewaretoken"]') !== null;

            const tokenPresent = hasCookie || hasMetaTag || hasHiddenField;

            this.addTestResult('CSRF Token Presence', tokenPresent,
                `Cookie: ${hasCookie}, Meta: ${hasMetaTag}, Hidden: ${hasHiddenField}`);
        }

        /**
         * Test token validation
         */
        async testTokenValidation() {
            this.log('Testing token validation...');

            if (!window.csrfManager) {
                this.addTestResult('Token Validation', false, 'CSRF Manager not available');
                return;
            }

            try {
                const isValid = await window.csrfManager.validateToken();
                this.addTestResult('Token Validation', isValid,
                    isValid ? 'Token is valid' : 'Token validation failed');
            } catch (error) {
                this.addTestResult('Token Validation', false, `Error: ${error.message}`);
            }
        }

        /**
         * Test token regeneration
         */
        async testTokenRegeneration() {
            this.log('Testing token regeneration...');

            if (!window.csrfManager) {
                this.addTestResult('Token Regeneration', false, 'CSRF Manager not available');
                return;
            }

            try {
                const originalToken = window.csrfManager.getCurrentToken();
                const refreshed = await window.csrfManager.forceRefreshToken();
                const newToken = window.csrfManager.getCurrentToken();

                const success = refreshed && newToken && newToken !== originalToken;

                this.addTestResult('Token Regeneration', success,
                    success ? 'Token successfully regenerated' : 'Token regeneration failed');
            } catch (error) {
                this.addTestResult('Token Regeneration', false, `Error: ${error.message}`);
            }
        }

        /**
         * Test form CSRF protection
         */
        testFormCSRFProtection() {
            this.log('Testing form CSRF protection...');

            const forms = document.querySelectorAll('form');
            let protectedForms = 0;
            let totalForms = 0;

            forms.forEach(form => {
                totalForms++;
                const csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
                if (csrfInput && csrfInput.value) {
                    protectedForms++;
                }
            });

            const protectionRate = totalForms > 0 ? (protectedForms / totalForms) * 100 : 100;
            const isProtected = protectionRate >= 80; // 80% of forms should be protected

            this.addTestResult('Form CSRF Protection', isProtected,
                `${protectedForms}/${totalForms} forms protected (${protectionRate.toFixed(1)}%)`);
        }

        /**
         * Test AJAX CSRF protection
         */
        testAJAXCSRFProtection() {
            this.log('Testing AJAX CSRF protection...');

            // Check if fetch is patched
            const originalFetch = window.fetch;
            const fetchPatched = originalFetch.toString().includes('CSRF') ||
                                 (window.csrfManager && window.csrfManager.protectedFetch);

            this.addTestResult('AJAX CSRF Protection', fetchPatched,
                fetchPatched ? 'Fetch API is protected' : 'Fetch API protection not detected');
        }

        /**
         * Test storage clearing scenario
         */
        async testStorageClearScenario() {
            this.log('Testing storage clearing scenario...');

            if (!window.csrfManager) {
                this.addTestResult('Storage Clear Scenario', false, 'CSRF Manager not available');
                return;
            }

            try {
                // Save current token
                const originalToken = window.csrfManager.getCurrentToken();

                // Simulate storage clearing
                const originalCookie = document.cookie;
                document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';

                // Test if manager can recover
                const recovered = await window.csrfManager.validateToken();

                // Restore original cookie if possible
                if (originalToken && !recovered) {
                    document.cookie = `csrftoken=${originalToken}; path=/`;
                }

                this.addTestResult('Storage Clear Scenario', recovered,
                    recovered ? 'Successfully recovered from storage clear' : 'Failed to recover from storage clear');
            } catch (error) {
                this.addTestResult('Storage Clear Scenario', false, `Error: ${error.message}`);
            }
        }

        /**
         * Test error recovery
         */
        async testErrorRecovery() {
            this.log('Testing error recovery...');

            if (!window.csrfManager) {
                this.addTestResult('Error Recovery', false, 'CSRF Manager not available');
                return;
            }

            try {
                // Test invalid token handling
                const invalidToken = 'invalid-token-12345';

                // Temporarily set invalid token
                document.cookie = `csrftoken=${invalidToken}; path=/`;

                // Try to validate - should trigger regeneration
                const recovered = await window.csrfManager.validateToken();

                this.addTestResult('Error Recovery', recovered,
                    recovered ? 'Successfully recovered from invalid token' : 'Failed to recover from invalid token');
            } catch (error) {
                this.addTestResult('Error Recovery', false, `Error: ${error.message}`);
            }
        }

        /**
         * Add test result
         */
        addTestResult(testName, passed, details) {
            this.testResults.push({
                name: testName,
                passed: passed,
                details: details,
                timestamp: new Date().toISOString()
            });

            this.log(`${testName}: ${passed ? 'PASSED' : 'FAILED'} - ${details}`);
        }

        /**
         * Display test results
         */
        displayResults() {
            const passedCount = this.testResults.filter(r => r.passed).length;
            const totalCount = this.testResults.length;
            const successRate = (passedCount / totalCount) * 100;

            this.log('\n=== CSRF Test Results ===');
            this.log(`Overall: ${passedCount}/${totalCount} tests passed (${successRate.toFixed(1)}%)`);
            this.log('======================');

            // Create visual results display
            this.createResultsDisplay(successRate);
        }

        /**
         * Create visual results display
         */
        createResultsDisplay(successRate) {
            // Remove existing display if present
            const existingDisplay = document.getElementById('csrf-test-results');
            if (existingDisplay) {
                existingDisplay.remove();
            }

            const resultsDiv = document.createElement('div');
            resultsDiv.id = 'csrf-test-results';
            resultsDiv.style.cssText = `
                position: fixed;
                top: 10px;
                left: 10px;
                width: 400px;
                max-height: 80vh;
                overflow-y: auto;
                background: white;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 20px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 10001;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            `;

            const headerColor = successRate >= 80 ? '#28a745' : successRate >= 60 ? '#ffc107' : '#dc3545';

            resultsDiv.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <h4 style="margin: 0; color: #333;">CSRF Protection Test Results</h4>
                    <button onclick="this.parentElement.parentElement.remove()"
                            style="background: none; border: none; font-size: 18px; cursor: pointer;">×</button>
                </div>

                <div style="background: ${headerColor}20; border-left: 4px solid ${headerColor}; padding: 10px; margin-bottom: 15px; border-radius: 4px;">
                    <div style="font-weight: bold; margin-bottom: 5px;">Overall Status: ${successRate >= 80 ? 'GOOD' : successRate >= 60 ? 'NEEDS ATTENTION' : 'PROBLEMATIC'}</div>
                    <div style="font-size: 14px;">${successRate.toFixed(1)}% of tests passed (${this.testResults.filter(r => r.passed).length}/${this.testResults.length})</div>
                </div>

                <div style="max-height: 400px; overflow-y: auto;">
                    ${this.testResults.map(result => `
                        <div style="margin-bottom: 10px; padding: 8px; border-radius: 4px; background: ${result.passed ? '#d4edda' : '#f8d7da'}; border-left: 3px solid ${result.passed ? '#28a745' : '#dc3545'};">
                            <div style="font-weight: bold; color: ${result.passed ? '#155724' : '#721c24'};">
                                ${result.passed ? '✓' : '✗'} ${result.name}
                            </div>
                            <div style="font-size: 12px; color: #6c757d; margin-top: 2px;">
                                ${result.details}
                            </div>
                        </div>
                    `).join('')}
                </div>

                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #dee2e6;">
                    <button onclick="window.csrfTester.runAllTests()"
                            style="background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-right: 10px;">
                        Re-run Tests
                    </button>
                    <button onclick="this.parentElement.parentElement.remove()"
                            style="background: #6c757d; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">
                        Close
                    </button>
                </div>
            `;

            document.body.appendChild(resultsDiv);
        }

        /**
         * Log messages if debug mode is enabled
         */
        log(...args) {
            if (this.debugMode) {
                console.log('[CSRF Tester]', ...args);
            }
        }

        /**
         * Log errors
         */
        logError(...args) {
            console.error('[CSRF Tester]', ...args);
        }
    };

    // Auto-initialize CSRF tester when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        window.csrfTester = new CSRFTester();

        // Add keyboard shortcut to run tests (Ctrl+Shift+C)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'C') {
                e.preventDefault();
                window.csrfTester.runAllTests();
            }
        });

        // Run tests automatically if URL contains test parameter
        if (window.location.search.includes('csrf-test=true')) {
            setTimeout(() => {
                window.csrfTester.runAllTests();
            }, 2000);
        }
    });

})();