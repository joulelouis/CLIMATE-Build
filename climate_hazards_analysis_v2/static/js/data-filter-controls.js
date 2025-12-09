/**
 * Data Filtering and Scenario Selection Controls
 * Advanced filtering and control system for hazard exposure data
 */

class DataFilterControls {
    constructor(layerManager, options = {}) {
        this.layerManager = layerManager;
        this.options = {
            enableValueFiltering: true,
            enableRiskFiltering: true,
            enableTemporalFiltering: true,
            enableGeographicFiltering: true,
            ...options
        };

        this.filters = {
            hazardTypes: new Set(),
            scenarios: new Set(['current']),
            valueRanges: new Map(),
            riskLevels: new Set(),
            temporalRange: { start: null, end: null },
            geographicBounds: null,
            assetTypes: new Set()
        };

        this.originalData = null;
        this.filteredData = null;
        this.controlElements = {};

        this.init();
    }

    init() {
        this.createFilterControls();
        this.setupEventListeners();
        this.loadSavedFilters();
    }

    /**
     * Create filter control interface
     */
    createFilterControls() {
        const controlsContainer = document.getElementById('filter-controls') || this.createControlsContainer();

        controlsContainer.innerHTML = `
            <div class="data-filters">
                <!-- Quick Filters -->
                <div class="filter-section">
                    <h6 class="filter-title">
                        <i class="fas fa-filter me-2"></i>Quick Filters
                    </h6>
                    <div class="quick-filters">
                        <button class="btn btn-sm btn-outline-primary" onclick="dataFilterControls.showAllHazards()">
                            <i class="fas fa-eye me-1"></i>Show All
                        </button>
                        <button class="btn btn-sm btn-outline-secondary" onclick="dataFilterControls.hideAllHazards()">
                            <i class="fas fa-eye-slash me-1"></i>Hide All
                        </button>
                        <button class="btn btn-sm btn-outline-warning" onclick="dataFilterControls.showHighRiskOnly()">
                            <i class="fas fa-exclamation-triangle me-1"></i>High Risk Only
                        </button>
                        <button class="btn btn-sm btn-outline-info" onclick="dataFilterControls.resetFilters()">
                            <i class="fas fa-undo me-1"></i>Reset
                        </button>
                    </div>
                </div>

                <!-- Hazard Type Filters -->
                <div class="filter-section">
                    <h6 class="filter-title">
                        <i class="fas fa-exclamation-triangle me-2"></i>Hazard Types
                    </h6>
                    <div class="hazard-filters" id="hazard-filters">
                        ${this.createHazardFilters()}
                    </div>
                </div>

                <!-- Scenario Filters -->
                <div class="filter-section">
                    <h6 class="filter-title">
                        <i class="fas fa-calendar-alt me-2"></i>Scenarios
                    </h6>
                    <div class="scenario-filters">
                        <label class="form-check">
                            <input type="checkbox" class="form-check-input" data-scenario="current" checked>
                            <span class="form-check-label">Current Conditions</span>
                        </label>
                        <label class="form-check">
                            <input type="checkbox" class="form-check-input" data-scenario="moderate">
                            <span class="form-check-label">Moderate Case</span>
                        </label>
                        <label class="form-check">
                            <input type="checkbox" class="form-check-input" data-scenario="worst">
                            <span class="form-check-label">Worst Case</span>
                        </label>
                    </div>
                </div>

                <!-- Value Range Filters -->
                ${this.options.enableValueFiltering ? `
                    <div class="filter-section">
                        <h6 class="filter-title">
                            <i class="fas fa-sliders-h me-2"></i>Value Ranges
                        </h6>
                        <div class="value-filters" id="value-filters">
                            ${this.createValueRangeFilters()}
                        </div>
                    </div>
                ` : ''}

                <!-- Risk Level Filters -->
                ${this.options.enableRiskFiltering ? `
                    <div class="filter-section">
                        <h6 class="filter-title">
                            <i class="fas fa-shield-alt me-2"></i>Risk Levels
                        </h6>
                        <div class="risk-filters">
                            <label class="form-check">
                                <input type="checkbox" class="form-check-input" data-risk="very-high">
                                <span class="form-check-label risk-very-high">Very High</span>
                            </label>
                            <label class="form-check">
                                <input type="checkbox" class="form-check-input" data-risk="high">
                                <span class="form-check-label risk-high">High</span>
                            </label>
                            <label class="form-check">
                                <input type="checkbox" class="form-check-input" data-risk="medium">
                                <span class="form-check-label risk-medium">Medium</span>
                            </label>
                            <label class="form-check">
                                <input type="checkbox" class="form-check-input" data-risk="low">
                                <span class="form-check-label risk-low">Low</span>
                            </label>
                            <label class="form-check">
                                <input type="checkbox" class="form-check-input" data-risk="no-risk">
                                <span class="form-check-label risk-no-risk">No Risk</span>
                            </label>
                        </div>
                    </div>
                ` : ''}

                <!-- Geographic Filters -->
                ${this.options.enableGeographicFiltering ? `
                    <div class="filter-section">
                        <h6 class="filter-title">
                            <i class="fas fa-map me-2"></i>Geographic Filters
                        </h6>
                        <div class="geographic-filters">
                            <button class="btn btn-sm btn-outline-secondary" onclick="dataFilterControls.setBoundsFromView()">
                                <i class="fas fa-crop me-1"></i>Use Current View
                            </button>
                            <button class="btn btn-sm btn-outline-secondary" onclick="dataFilterControls.clearGeographicFilter()">
                                <i class="fas fa-times me-1"></i>Clear Bounds
                            </button>
                        </div>
                    </div>
                ` : ''}

                <!-- Filter Summary -->
                <div class="filter-section">
                    <h6 class="filter-title">
                        <i class="fas fa-info-circle me-2"></i>Filter Summary
                    </h6>
                    <div class="filter-summary" id="filter-summary">
                        <p class="text-muted mb-0">No filters applied</p>
                    </div>
                </div>
            </div>
        `;

        this.cacheControlElements();
    }

    /**
     * Create controls container if it doesn't exist
     */
    createControlsContainer() {
        const container = document.createElement('div');
        container.id = 'filter-controls';
        container.className = 'filter-controls-container';

        // Insert after existing controls
        const existingControls = document.querySelector('.control-panel');
        if (existingControls) {
            existingControls.appendChild(container);
        } else {
            document.body.appendChild(container);
        }

        return container;
    }

    /**
     * Create hazard filter checkboxes
     */
    createHazardFilters() {
        const hazards = [
            { id: 'flood', name: 'Flood', color: '#0066cc' },
            { id: 'waterStress', name: 'Water Stress', color: '#336633' },
            { id: 'seaLevelRise', name: 'Sea Level Rise', color: '#cc0000' },
            { id: 'tropicalCyclone', name: 'Tropical Cyclone', color: '#ff6600' },
            { id: 'heat', name: 'Heat Exposure', color: '#cc0000' },
            { id: 'stormSurge', name: 'Storm Surge', color: '#0066cc' },
            { id: 'landslide', name: 'Landslide', color: '#7f00ff' }
        ];

        return hazards.map(hazard => `
            <label class="form-check hazard-filter-item">
                <input type="checkbox" class="form-check-input" data-hazard="${hazard.id}">
                <span class="form-check-label">
                    <span class="hazard-color-indicator" style="background-color: ${hazard.color};"></span>
                    ${hazard.name}
                </span>
            </label>
        `).join('');
    }

    /**
     * Create value range filter sliders
     */
    createValueRangeFilters() {
        // This would be dynamically generated based on actual data ranges
        return `
            <div class="value-range-filter">
                <label class="form-label">Flood Depth (meters)</label>
                <div class="range-slider">
                    <input type="range" class="form-range" min="0" max="10" step="0.1"
                           data-hazard="flood" data-type="min" value="0">
                    <input type="range" class="form-range" min="0" max="10" step="0.1"
                           data-hazard="flood" data-type="max" value="10">
                    <div class="range-values">
                        <span class="range-min">0.0m</span>
                        <span class="range-max">10.0m</span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Cache control elements for efficient access
     */
    cacheControlElements() {
        this.controlElements = {
            hazardFilters: document.querySelectorAll('[data-hazard]'),
            scenarioFilters: document.querySelectorAll('[data-scenario]'),
            riskFilters: document.querySelectorAll('[data-risk]'),
            valueRangeFilters: document.querySelectorAll('[data-hazard][data-type]'),
            summary: document.getElementById('filter-summary')
        };
    }

    /**
     * Setup event listeners for all filter controls
     */
    setupEventListeners() {
        // Hazard type filters
        this.controlElements.hazardFilters.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const hazard = e.target.dataset.hazard;
                const isChecked = e.target.checked;

                if (isChecked) {
                    this.filters.hazardTypes.add(hazard);
                } else {
                    this.filters.hazardTypes.delete(hazard);
                }

                this.applyFilters();
                this.updateSummary();
            });
        });

        // Scenario filters
        this.controlElements.scenarioFilters.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const scenario = e.target.dataset.scenario;
                const isChecked = e.target.checked;

                if (isChecked) {
                    this.filters.scenarios.add(scenario);
                } else {
                    this.filters.scenarios.delete(scenario);
                }

                this.applyFilters();
                this.updateSummary();
            });
        });

        // Risk level filters
        this.controlElements.riskFilters.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const risk = e.target.dataset.risk;
                const isChecked = e.target.checked;

                if (isChecked) {
                    this.filters.riskLevels.add(risk);
                } else {
                    this.filters.riskLevels.delete(risk);
                }

                this.applyFilters();
                this.updateSummary();
            });
        });

        // Value range filters
        this.controlElements.valueRangeFilters.forEach(slider => {
            slider.addEventListener('input', (e) => {
                this.updateValueRangeFilter(e.target);
                this.applyFilters();
            });
        });
    }

    /**
     * Update value range filter
     */
    updateValueRangeFilter(slider) {
        const hazard = slider.dataset.hazard;
        const type = slider.dataset.type;
        const value = parseFloat(slider.value);

        if (!this.filters.valueRanges.has(hazard)) {
            this.filters.valueRanges.set(hazard, { min: 0, max: Infinity });
        }

        const range = this.filters.valueRanges.get(hazard);
        range[type] = value;

        // Update displayed values
        const container = slider.closest('.value-range-filter');
        const minDisplay = container.querySelector('.range-min');
        const maxDisplay = container.querySelector('.range-max');

        const currentRange = this.filters.valueRanges.get(hazard);
        minDisplay.textContent = `${currentRange.min.toFixed(1)}m`;
        maxDisplay.textContent = currentRange.max === Infinity ? '∞' : `${currentRange.max.toFixed(1)}m`;
    }

    /**
     * Apply all filters to the data
     */
    applyFilters() {
        if (!window.granularDataService || !window.granularDataService.isLoaded) {
            return;
        }

        const originalData = window.granularDataService.processedData.granularPoints;

        // Apply hazard type filter
        let filteredData = originalData.filter(point => {
            if (this.filters.hazardTypes.size === 0) return true;

            // Check if point has data for any selected hazard type
            return Array.from(this.filters.hazardTypes).some(hazardType => {
                return point.hazardData[hazardType] !== undefined;
            });
        });

        // Apply scenario filter
        if (this.filters.scenarios.size > 0) {
            // This would require more complex logic to filter by scenario
            // For now, we'll just pass all data
        }

        // Apply value range filters
        if (this.filters.valueRanges.size > 0) {
            filteredData = filteredData.filter(point => {
                return Array.from(this.filters.valueRanges.entries()).every(([hazard, range]) => {
                    const hazardData = point.hazardData[hazard];
                    if (!hazardData) return true;

                    const value = this.getHazardValueForCurrentScenario(hazardData, hazard);
                    return value >= range.min && value <= range.max;
                });
            });
        }

        // Apply risk level filters
        if (this.filters.riskLevels.size > 0) {
            filteredData = filteredData.filter(point => {
                return Array.from(this.filters.riskLevels).some(riskLevel => {
                    return this.calculateRiskLevel(point) === riskLevel;
                });
            });
        }

        // Apply geographic bounds filter
        if (this.filters.geographicBounds) {
            filteredData = filteredData.filter(point => {
                return this.isPointInBounds(point, this.filters.geographicBounds);
            });
        }

        this.filteredData = filteredData;
        this.updateMapWithFilteredData();
    }

    /**
     * Get hazard value for current scenario
     */
    getHazardValueForCurrentScenario(hazardData, hazardType) {
        const currentScenario = Array.from(this.filters.scenarios)[0] || 'current';

        if (hazardData[currentScenario]) {
            return typeof hazardData[currentScenario] === 'object' ?
                   hazardData[currentScenario].average || 0 :
                   hazardData[currentScenario];
        }

        return hazardData.current || 0;
    }

    /**
     * Calculate risk level for a point
     */
    calculateRiskLevel(point) {
        // Simplified risk calculation
        // In practice, this would be more sophisticated
        const totalRisk = Object.entries(point.hazardData).reduce((sum, [hazard, data]) => {
            const value = this.getHazardValueForCurrentScenario(data, hazard);
            return sum + this.normalizeHazardValue(hazard, value);
        }, 0);

        if (totalRisk > 0.8) return 'very-high';
        if (totalRisk > 0.6) return 'high';
        if (totalRisk > 0.4) return 'medium';
        if (totalRisk > 0.2) return 'low';
        return 'no-risk';
    }

    /**
     * Normalize hazard value to 0-1 scale
     */
    normalizeHazardValue(hazardType, value) {
        const normalizers = {
            flood: { min: 0, max: 10 },
            waterStress: { min: 0, max: 100 },
            seaLevelRise: { min: 0, max: 5 },
            tropicalCyclone: { min: 0, max: 250 },
            heat: { min: 0, max: 365 },
            stormSurge: { min: 0, max: 10 },
            landslide: { min: 0, max: 3 }
        };

        const normalizer = normalizers[hazardType];
        if (!normalizer) return 0;

        return Math.min(Math.max((value - normalizer.min) / (normalizer.max - normalizer.min), 0), 1);
    }

    /**
     * Check if point is within geographic bounds
     */
    isPointInBounds(point, bounds) {
        return point.latitude >= bounds.south && point.latitude <= bounds.north &&
               point.longitude >= bounds.west && point.longitude <= bounds.east;
    }

    /**
     * Update map with filtered data
     */
    updateMapWithFilteredData() {
        if (!this.layerManager || !this.filteredData) return;

        // Convert filtered data to GeoJSON
        const geoJsonData = {
            type: 'FeatureCollection',
            features: this.filteredData.map(point => ({
                type: 'Feature',
                geometry: {
                    type: 'Point',
                    coordinates: [point.longitude, point.latitude]
                },
                properties: {
                    id: point.id,
                    name: point.name,
                    archetype: point.archetype,
                    ...point.hazardData
                }
            }))
        };

        // Update map source
        if (this.layerManager.map.getSource('granular-points')) {
            this.layerManager.map.getSource('granular-points').setData(geoJsonData);
        }

        // Update statistics
        this.updateStatistics();
    }

    /**
     * Update statistics display
     */
    updateStatistics() {
        const statsElement = document.getElementById('filter-stats');
        if (!statsElement) return;

        const totalPoints = window.granularDataService.processedData.granularPoints.length;
        const filteredPoints = this.filteredData ? this.filteredData.length : totalPoints;
        const percentage = totalPoints > 0 ? (filteredPoints / totalPoints * 100).toFixed(1) : 0;

        statsElement.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <span>Showing ${filteredPoints} of ${totalPoints} points</span>
                <span class="badge bg-primary">${percentage}%</span>
            </div>
        `;
    }

    /**
     * Update filter summary
     */
    updateSummary() {
        if (!this.controlElements.summary) return;

        const activeFilters = [];

        if (this.filters.hazardTypes.size > 0) {
            activeFilters.push(`${this.filters.hazardTypes.size} hazards`);
        }

        if (this.filters.scenarios.size > 0) {
            activeFilters.push(`${this.filters.scenarios.size} scenarios`);
        }

        if (this.filters.riskLevels.size > 0) {
            activeFilters.push(`${this.filters.riskLevels.size} risk levels`);
        }

        if (this.filters.valueRanges.size > 0) {
            activeFilters.push(`${this.filters.valueRanges.size} value ranges`);
        }

        if (this.filters.geographicBounds) {
            activeFilters.push('geographic bounds');
        }

        if (activeFilters.length === 0) {
            this.controlElements.summary.innerHTML = '<p class="text-muted mb-0">No filters applied</p>';
        } else {
            this.controlElements.summary.innerHTML = `
                <p class="mb-0">
                    <strong>Active filters:</strong> ${activeFilters.join(', ')}
                </p>
            `;
        }
    }

    /**
     * Quick filter methods
     */
    showAllHazards() {
        this.controlElements.hazardFilters.forEach(checkbox => {
            checkbox.checked = true;
            this.filters.hazardTypes.add(checkbox.dataset.hazard);
        });
        this.applyFilters();
        this.updateSummary();
    }

    hideAllHazards() {
        this.controlElements.hazardFilters.forEach(checkbox => {
            checkbox.checked = false;
        });
        this.filters.hazardTypes.clear();
        this.applyFilters();
        this.updateSummary();
    }

    showHighRiskOnly() {
        this.controlElements.riskFilters.forEach(checkbox => {
            const risk = checkbox.dataset.risk;
            checkbox.checked = risk === 'very-high' || risk === 'high';
            if (checkbox.checked) {
                this.filters.riskLevels.add(risk);
            } else {
                this.filters.riskLevels.delete(risk);
            }
        });
        this.applyFilters();
        this.updateSummary();
    }

    resetFilters() {
        // Reset all filters to default state
        this.filters = {
            hazardTypes: new Set(),
            scenarios: new Set(['current']),
            valueRanges: new Map(),
            riskLevels: new Set(),
            temporalRange: { start: null, end: null },
            geographicBounds: null,
            assetTypes: new Set()
        };

        // Reset UI
        this.controlElements.hazardFilters.forEach(checkbox => {
            checkbox.checked = false;
        });

        this.controlElements.scenarioFilters.forEach(checkbox => {
            checkbox.checked = checkbox.dataset.scenario === 'current';
        });

        this.controlElements.riskFilters.forEach(checkbox => {
            checkbox.checked = false;
        });

        this.applyFilters();
        this.updateSummary();
    }

    /**
     * Geographic filter methods
     */
    setBoundsFromView() {
        if (!this.layerManager || !this.layerManager.map) return;

        const bounds = this.layerManager.map.getBounds();
        this.filters.geographicBounds = {
            north: bounds.getNorth(),
            south: bounds.getSouth(),
            east: bounds.getEast(),
            west: bounds.getWest()
        };

        this.applyFilters();
        this.updateSummary();
    }

    clearGeographicFilter() {
        this.filters.geographicBounds = null;
        this.applyFilters();
        this.updateSummary();
    }

    /**
     * Save filters to localStorage
     */
    saveFilters() {
        const filterState = {
            hazardTypes: Array.from(this.filters.hazardTypes),
            scenarios: Array.from(this.filters.scenarios),
            riskLevels: Array.from(this.filters.riskLevels),
            valueRanges: Array.from(this.filters.valueRanges.entries())
        };

        localStorage.setItem('hazardMapFilters', JSON.stringify(filterState));
    }

    /**
     * Load saved filters from localStorage
     */
    loadSavedFilters() {
        try {
            const savedFilters = localStorage.getItem('hazardMapFilters');
            if (savedFilters) {
                const filterState = JSON.parse(savedFilters);

                // Apply saved filters
                filterState.hazardTypes.forEach(hazard => {
                    this.filters.hazardTypes.add(hazard);
                    const checkbox = document.querySelector(`[data-hazard="${hazard}"]`);
                    if (checkbox) checkbox.checked = true;
                });

                filterState.scenarios.forEach(scenario => {
                    this.filters.scenarios.add(scenario);
                    const checkbox = document.querySelector(`[data-scenario="${scenario}"]`);
                    if (checkbox) checkbox.checked = true;
                });

                filterState.riskLevels.forEach(risk => {
                    this.filters.riskLevels.add(risk);
                    const checkbox = document.querySelector(`[data-risk="${risk}"]`);
                    if (checkbox) checkbox.checked = true;
                });

                this.applyFilters();
                this.updateSummary();
            }
        } catch (error) {
            console.warn('Error loading saved filters:', error);
        }
    }

    /**
     * Destroy the filter controls
     */
    destroy() {
        this.saveFilters();
        this.filters = null;
        this.controlElements = null;
    }
}

// Export for global use
window.DataFilterControls = DataFilterControls;