/**
 * JSON Workflow Integration for Climate Hazards Analysis
 *
 * This module provides JavaScript functions to integrate with the JSON workflow API endpoints.
 * It enables seamless communication between the frontend and the new JSON-based backend.
 */

class JSONWorkflowManager {
    constructor(baseUrl = '/climate-hazards-analysis-v2') {
        this.baseUrl = baseUrl;
        this.apiEndpoints = {
            saveHazardSelection: `${baseUrl}/api/v2/json/save-hazard-selection/`,
            runAnalysis: `${baseUrl}/api/v2/json/run-analysis/`,
            getResults: `${baseUrl}/api/v2/json/get-results/`
        };
    }

    /**
     * Save hazard selection for assets
     * @param {Array} assetIds - List of asset IDs
     * @param {Array} hazards - List of selected hazards
     * @param {Object} parameters - Analysis parameters
     */
    async saveHazardSelection(assetIds, hazards, parameters = {}) {
        try {
            const response = await fetch(this.apiEndpoints.saveHazardSelection, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    asset_ids: assetIds,
                    hazards: hazards,
                    parameters: parameters
                })
            });

            const result = await response.json();

            if (response.ok) {
                console.log('Hazard selection saved successfully:', result);
                return result;
            } else {
                console.error('Error saving hazard selection:', result.error);
                throw new Error(result.error || 'Failed to save hazard selection');
            }
        } catch (error) {
            console.error('Network error saving hazard selection:', error);
            throw error;
        }
    }

    /**
     * Run climate hazards analysis
     * @param {Array} assetIds - List of asset IDs to analyze
     */
    async runAnalysis(assetIds) {
        try {
            const response = await fetch(this.apiEndpoints.runAnalysis, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    asset_ids: assetIds
                })
            });

            const result = await response.json();

            if (response.ok) {
                console.log('Analysis completed successfully:', result);
                return result;
            } else {
                console.error('Error running analysis:', result.error);
                throw new Error(result.error || 'Failed to run analysis');
            }
        } catch (error) {
            console.error('Network error running analysis:', error);
            throw error;
        }
    }

    /**
     * Get stored analysis results
     * @param {Array} assetIds - List of asset IDs to get results for
     */
    async getResults(assetIds) {
        try {
            const url = new URL(this.apiEndpoints.getResults);
            assetIds.forEach(id => url.searchParams.append('asset_ids', id));

            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            const result = await response.json();

            if (response.ok) {
                console.log('Results retrieved successfully:', result);
                return result;
            } else {
                console.error('Error getting results:', result.error);
                throw new Error(result.error || 'Failed to get results');
            }
        } catch (error) {
            console.error('Network error getting results:', error);
            throw error;
        }
    }

    /**
     * Complete JSON workflow: save hazards, run analysis, get results
     * @param {Array} assetIds - List of asset IDs
     * @param {Array} hazards - List of selected hazards
     * @param {Object} parameters - Analysis parameters
     */
    async runCompleteWorkflow(assetIds, hazards, parameters = {}) {
        try {
            // Step 1: Save hazard selection
            console.log('Step 1: Saving hazard selection...');
            await this.saveHazardSelection(assetIds, hazards, parameters);

            // Step 2: Run analysis
            console.log('Step 2: Running analysis...');
            const analysisResult = await this.runAnalysis(assetIds);

            // Step 3: Return results directly (already included in analysis response)
            console.log('Step 3: Workflow completed!');
            return analysisResult;

        } catch (error) {
            console.error('JSON workflow failed:', error);
            throw error;
        }
    }

    /**
     * Get uploaded asset IDs from session
     */
    getUploadedAssetIds() {
        // This would typically be retrieved from the page context or session
        // Implementation depends on how asset IDs are exposed to the frontend
        const assetIdsElement = document.getElementById('uploaded-asset-ids');
        if (assetIdsElement) {
            return JSON.parse(assetIdsElement.textContent || '[]');
        }
        return [];
    }

    /**
     * Get selected hazards from form
     */
    getSelectedHazards() {
        const selectedHazards = [];
        const hazardCheckboxes = document.querySelectorAll('input[name="hazards"]:checked');

        hazardCheckboxes.forEach(checkbox => {
            selectedHazards.push(checkbox.value);
        });

        return selectedHazards;
    }

    /**
     * Update hazard exposure table with new results
     * @param {Object} results - Analysis results from API
     */
    updateHazardExposureTable(results) {
        if (!results || !results.data) {
            console.error('No results data available');
            return;
        }

        try {
            // Update the data table if DataTables is initialized
            if (window.dataTable) {
                // Clear existing data
                window.dataTable.clear();

                // Add new data
                results.data.forEach(row => {
                    window.dataTable.row.add(row);
                });

                // Redraw table
                window.dataTable.draw();
            } else {
                // Fallback: reload the page to show new results
                window.location.reload();
            }

            console.log('Hazard exposure table updated successfully');
        } catch (error) {
            console.error('Error updating hazard exposure table:', error);
        }
    }

    /**
     * Get CSRF token from cookies
     */
    getCSRFToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return decodeURIComponent(value);
            }
        }
        return '';
    }
}

// Initialize global JSON workflow manager
window.jsonWorkflowManager = new JSONWorkflowManager();

// Auto-bind to existing form submissions when document is ready
document.addEventListener('DOMContentLoaded', function() {
    // Intercept hazard selection form submission
    const hazardForm = document.querySelector('form[action*="select-hazards"]');
    if (hazardForm) {
        hazardForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const assetIds = window.jsonWorkflowManager.getUploadedAssetIds();
            const selectedHazards = window.jsonWorkflowManager.getSelectedHazards();

            if (assetIds.length === 0) {
                alert('No assets found for analysis. Please upload asset data first.');
                return;
            }

            if (selectedHazards.length === 0) {
                alert('Please select at least one hazard type for analysis.');
                return;
            }

            // Show loading state
            const submitBtn = hazardForm.querySelector('button[type="submit"]');
            const originalText = submitBtn.textContent;
            submitBtn.textContent = 'Running Analysis...';
            submitBtn.disabled = true;

            // Run JSON workflow
            window.jsonWorkflowManager.runCompleteWorkflow(assetIds, selectedHazards)
                .then(results => {
                    // Redirect to results page with JSON data
                    const resultsUrl = window.jsonWorkflowManager.baseUrl.replace('/climate-hazards-analysis-v2', '') + '/climate-hazards-analysis-v2/results/';
                    window.location.href = resultsUrl;
                })
                .catch(error => {
                    console.error('Analysis failed:', error);
                    alert('Analysis failed: ' + error.message);

                    // Reset button state
                    submitBtn.textContent = originalText;
                    submitBtn.disabled = false;
                });
        });
    }
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = JSONWorkflowManager;
}