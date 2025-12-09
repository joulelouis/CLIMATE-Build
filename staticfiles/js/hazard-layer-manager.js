/**
 * Hazard Layer Manager for Climate Hazards Exposure Map
 * Manages layers, styling, and interactions for different hazard types
 */

class HazardLayerManager {
    constructor(map) {
        this.map = map;
        this.layers = new Map();
        this.sources = new Map();
        this.activeHazards = new Set();
        this.currentScenario = 'current';
        this.visualizationMode = 'points'; // 'points' or 'heatmap'

        // Hazard configuration
        this.hazardConfig = {
            flood: {
                name: 'Flood',
                colorProperty: 'flood_value',
                colorStops: [
                    [0, '#ffffff'],
                    [0.1, '#e6f3ff'],
                    [0.5, '#66b3ff'],
                    [1.0, '#0066cc'],
                    [2.0, '#003d7a'],
                    [5.0, '#001a33']
                ],
                unit: 'm',
                classification: 'depth'
            },
            waterStress: {
                name: 'Water Stress',
                colorProperty: 'water_stress_value',
                colorStops: [
                    [0, '#ffffff'],
                    [20, '#e6f2e6'],
                    [40, '#99cc99'],
                    [60, '#669966'],
                    [80, '#336633'],
                    [100, '#1a331a']
                ],
                unit: '%',
                classification: 'exposure'
            },
            seaLevelRise: {
                name: 'Sea Level Rise',
                colorProperty: 'slr_value',
                colorStops: [
                    [0, '#ffffff'],
                    [0.2, '#ffe6e6'],
                    [0.5, '#ffcccc'],
                    [1.0, '#ff9999'],
                    [2.0, '#ff6666'],
                    [5.0, '#cc0000']
                ],
                unit: 'm',
                classification: 'rise'
            },
            tropicalCyclone: {
                name: 'Tropical Cyclone',
                colorProperty: 'cyclone_value',
                colorStops: [
                    [0, '#ffffff'],
                    [50, '#fff0e6'],
                    [100, '#ffd9b3'],
                    [150, '#ffcc99'],
                    [200, '#ff9933'],
                    [250, '#ff6600']
                ],
                unit: 'km/h',
                classification: 'windspeed'
            },
            heat: {
                name: 'Heat',
                colorProperty: 'heat_value',
                colorStops: [
                    [0, '#ffffff'],
                    [50, '#fff5f5'],
                    [100, '#ffcccc'],
                    [200, '#ff9999'],
                    [300, '#ff6666'],
                    [365, '#cc0000']
                ],
                unit: 'days',
                classification: 'exposure'
            },
            stormSurge: {
                name: 'Storm Surge',
                colorProperty: 'storm_surge_value',
                colorStops: [
                    [0, '#ffffff'],
                    [0.5, '#e6f7ff'],
                    [1.0, '#99d6ff'],
                    [2.0, '#3399ff'],
                    [4.0, '#0066cc'],
                    [8.0, '#003d7a']
                ],
                unit: 'm',
                classification: 'depth'
            },
            landslide: {
                name: 'Landslide',
                colorProperty: 'landslide_value',
                colorStops: [
                    [0, '#ffffff'],
                    [0.5, '#f0e6ff'],
                    [1.0, '#d9b3ff'],
                    [1.5, '#b366ff'],
                    [2.0, '#7f00ff'],
                    [3.0, '#4d0099']
                ],
                unit: 'FoS',
                classification: 'safety'
            }
        };

        this.initializeLayers();
    }

    /**
     * Initialize base layers for granular points and polygon boundaries
     */
    initializeLayers() {
        // Add empty sources for granular points
        this.map.addSource('granular-points', {
            type: 'geojson',
            data: {
                type: 'FeatureCollection',
                features: []
            }
        });

        // Add empty source for polygon boundaries
        this.map.addSource('polygon-boundaries', {
            type: 'geojson',
            data: {
                type: 'FeatureCollection',
                features: []
            }
        });

        // Add base layer for polygon boundaries
        this.map.addLayer({
            id: 'polygon-boundaries-layer',
            type: 'line',
            source: 'polygon-boundaries',
            paint: {
                'line-color': '#333333',
                'line-width': 2,
                'line-opacity': 0.8
            }
        });

        // Add base layer for granular points (initially invisible)
        this.map.addLayer({
            id: 'granular-points-base',
            type: 'circle',
            source: 'granular-points',
            paint: {
                'circle-radius': 6,
                'circle-color': '#3388ff',
                'circle-stroke-color': '#ffffff',
                'circle-stroke-width': 2,
                'circle-opacity': 0.8
            },
            filter: ['==', ['get', 'hazard_type'], '']
        });

        // Add hover layer for granular points
        this.map.addLayer({
            id: 'granular-points-hover',
            type: 'circle',
            source: 'granular-points',
            paint: {
                'circle-radius': 8,
                'circle-color': '#ff6600',
                'circle-stroke-color': '#ffffff',
                'circle-stroke-width': 3,
                'circle-opacity': 1
            },
            filter: ['==', ['get', 'id'], -1] // Initially no points selected
        });

        this.setupInteractionHandlers();
    }

    /**
     * Setup interaction handlers for hover and click events
     */
    setupInteractionHandlers() {
        // Hover effect
        this.map.on('mousemove', 'granular-points-base', (e) => {
            if (e.features.length > 0) {
                const feature = e.features[0];
                this.map.getCanvas().style.cursor = 'pointer';

                // Update hover layer
                this.map.setFilter('granular-points-hover', ['==', ['get', 'id'], feature.properties.id]);

                // Show popup
                this.showPopup(feature, e.lngLat);
            }
        });

        this.map.on('mouseleave', 'granular-points-base', () => {
            this.map.getCanvas().style.cursor = '';
            this.map.setFilter('granular-points-hover', ['==', ['get', 'id'], -1]);
            this.hidePopup();
        });

        // Click event
        this.map.on('click', 'granular-points-base', (e) => {
            if (e.features.length > 0) {
                const feature = e.features[0];
                this.showDetailedPopup(feature, e.lngLat);
            }
        });
    }

    /**
     * Load granular data and create hazard layers
     */
    async loadGranularData() {
        try {
            await window.granularDataService.loadData();
            const data = window.granularDataService.processedData;

            // Update granular points source
            const geoJsonData = {
                type: 'FeatureCollection',
                features: data.granularPoints.map(point => ({
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

            this.map.getSource('granular-points').setData(geoJsonData);

            // Add polygon boundary if available
            const polygonBoundary = window.granularDataService.getPolygonBoundary();
            if (polygonBoundary) {
                this.map.getSource('polygon-boundaries').setData({
                    type: 'FeatureCollection',
                    features: [{
                        type: 'Feature',
                        geometry: polygonBoundary,
                        properties: {}
                    }]
                });
            }

            // Fit map to show all points
            this.fitMapToPoints();

        } catch (error) {
            console.error('Error loading granular data:', error);
            this.showErrorMessage('Failed to load granular hazard data');
        }
    }

    /**
     * Fit map to show all granular points
     */
    fitMapToPoints() {
        const data = this.map.getSource('granular-points')._data;
        if (data.features.length === 0) return;

        const bounds = new maplibregl.LngLatBounds();
        data.features.forEach(feature => {
            bounds.extend(feature.geometry.coordinates);
        });

        this.map.fitBounds(bounds, {
            padding: 50,
            maxZoom: 15
        });
    }

    /**
     * Toggle hazard layer visibility
     */
    toggleHazard(hazardType, isVisible) {
        if (isVisible) {
            this.activeHazards.add(hazardType);
            this.updateHazardLayer(hazardType);
        } else {
            this.activeHazards.delete(hazardType);
            this.removeHazardLayer(hazardType);
        }
    }

    /**
     * Update hazard layer with current scenario
     */
    updateHazardLayer(hazardType) {
        const layerId = `hazard-${hazardType}`;
        const config = this.hazardConfig[hazardType];

        if (!config) return;

        // Remove existing layer if it exists
        if (this.map.getLayer(layerId)) {
            this.map.removeLayer(layerId);
        }

        // Create filter for current hazard and scenario
        const filter = this.createHazardFilter(hazardType, this.currentScenario);

        // Add or update layer
        this.map.addLayer({
            id: layerId,
            type: 'circle',
            source: 'granular-points',
            paint: {
                'circle-radius': [
                    'interpolate',
                    ['linear'],
                    ['zoom'],
                    10, 4,
                    15, 8
                ],
                'circle-color': [
                    'interpolate',
                    ['linear'],
                    ['get', config.colorProperty],
                    ...config.colorStops.flat()
                ],
                'circle-stroke-color': '#ffffff',
                'circle-stroke-width': 1,
                'circle-opacity': 0.8
            },
            filter: filter
        });

        this.layers.set(layerId, hazardType);
    }

    /**
     * Create filter for hazard type and scenario
     */
    createHazardFilter(hazardType, scenario) {
        // This is a simplified filter - in practice, you'd need to
        // create more sophisticated filters based on your data structure
        return ['all',
            ['>', ['get', `${hazardType}_${scenario}_value`], 0]
        ];
    }

    /**
     * Remove hazard layer
     */
    removeHazardLayer(hazardType) {
        const layerId = `hazard-${hazardType}`;
        if (this.map.getLayer(layerId)) {
            this.map.removeLayer(layerId);
            this.layers.delete(layerId);
        }
    }

    /**
     * Update visualization mode (points vs heatmap)
     */
    setVisualizationMode(mode) {
        this.visualizationMode = mode;
        this.updateAllHazardLayers();
    }

    /**
     * Update scenario for all active hazards
     */
    setScenario(scenario) {
        this.currentScenario = scenario;
        this.updateAllHazardLayers();
    }

    /**
     * Update all active hazard layers
     */
    updateAllHazardLayers() {
        this.activeHazards.forEach(hazardType => {
            this.updateHazardLayer(hazardType);
        });
    }

    /**
     * Show popup with hazard information
     */
    showPopup(feature, lngLat) {
        const popupContent = this.createPopupContent(feature);

        if (this.popup) {
            this.popup.remove();
        }

        this.popup = new maplibregl.Popup({
            closeButton: false,
            closeOnClick: false,
            offset: 15
        }).setLngLat(lngLat)
          .setHTML(popupContent)
          .addTo(this.map);
    }

    /**
     * Show detailed popup with comprehensive hazard information
     */
    showDetailedPopup(feature, lngLat) {
        const detailedContent = this.createDetailedPopupContent(feature);

        if (this.popup) {
            this.popup.remove();
        }

        this.popup = new maplibregl.Popup({
            closeButton: true,
            closeOnClick: true,
            offset: 15,
            maxWidth: '300px'
        }).setLngLat(lngLat)
          .setHTML(detailedContent)
          .addTo(this.map);
    }

    /**
     * Hide popup
     */
    hidePopup() {
        if (this.popup) {
            this.popup.remove();
            this.popup = null;
        }
    }

    /**
     * Create popup content for a feature
     */
    createPopupContent(feature) {
        const props = feature.properties;
        const activeHazardData = this.getActiveHazardData(props);

        return `
            <div class="hazard-popup">
                <strong>${props.name}</strong><br>
                <small>${props.archetype}</small><br>
                ${activeHazardData ? `
                    <div style="margin-top: 5px;">
                        <strong>${activeHazardData.name}:</strong> ${activeHazardData.value}
                    </div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Create detailed popup content
     */
    createDetailedPopupContent(feature) {
        const props = feature.properties;
        const allHazardData = this.getAllHazardData(props);

        return `
            <div class="hazard-detailed-popup">
                <h6>${props.name}</h6>
                <p class="text-muted">${props.archetype}</p>
                <div class="hazard-details">
                    ${Object.entries(allHazardData).map(([key, data]) => `
                        <div class="hazard-item">
                            <strong>${data.name}:</strong> ${data.value}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    /**
     * Get active hazard data for a feature
     */
    getActiveHazardData(properties) {
        // Return data for the first active hazard
        for (const hazardType of this.activeHazards) {
            const config = this.hazardConfig[hazardType];
            if (config) {
                const value = properties[`${hazardType}_${this.currentScenario}_value`];
                if (value) {
                    return {
                        name: config.name,
                        value: `${value} ${config.unit}`
                    };
                }
            }
        }
        return null;
    }

    /**
     * Get all hazard data for a feature
     */
    getAllHazardData(properties) {
        const data = {};

        Object.entries(this.hazardConfig).forEach(([hazardType, config]) => {
            const value = properties[`${hazardType}_${this.currentScenario}_value`];
            if (value) {
                data[hazardType] = {
                    name: config.name,
                    value: `${value} ${config.unit}`
                };
            }
        });

        return data;
    }

    /**
     * Show error message
     */
    showErrorMessage(message) {
        // Implementation depends on your UI framework
        console.error(message);
        alert(message); // Simple fallback
    }

    /**
     * Get legend HTML for active hazards
     */
    getLegendHTML() {
        const legendItems = Array.from(this.activeHazards).map(hazardType => {
            const config = this.hazardConfig[hazardType];
            if (!config) return '';

            return `
                <div class="legend-item">
                    <div class="legend-title">${config.name}</div>
                    <div class="legend-gradient">
                        ${config.colorStops.map(([value, color]) => `
                            <div class="legend-stop" style="background-color: ${color};" title="${value} ${config.unit}"></div>
                        `).join('')}
                    </div>
                    <div class="legend-labels">
                        <span>${config.colorStops[0][0]} ${config.unit}</span>
                        <span>${config.colorStops[config.colorStops.length-1][0]} ${config.unit}</span>
                    </div>
                </div>
            `;
        }).join('');

        return `
            <div class="hazard-legend">
                <h6>Hazard Intensity</h6>
                ${legendItems}
            </div>
        `;
    }

    /**
     * Cleanup resources
     */
    destroy() {
        this.hidePopup();
        this.layers.clear();
        this.sources.clear();
        this.activeHazards.clear();
    }
}

// Export for global use
window.HazardLayerManager = HazardLayerManager;