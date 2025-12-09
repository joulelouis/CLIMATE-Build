/**
 * Enhanced Polygon Drawing Handler
 * Provides robust polygon validation, error handling, and user feedback
 */

class PolygonDrawHandler {
    constructor() {
        this.minVertices = 3;
        this.maxVertices = 100;
        this.minArea = 0.001; // Minimum area in square degrees
        this.maxArea = 10; // Maximum area in square degrees
        this.isDrawing = false;
        this.currentPolygon = [];
        this.validationErrors = [];
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupValidationStyles();
    }

    setupEventListeners() {
        // Drawing mode is handled by inline onclick in the template
        // No additional event listeners needed to avoid conflicts
    }

    setupValidationStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .drag-over {
                background-color: #e3f2fd !important;
                border: 2px dashed #2196f3 !important;
            }

            .file-details {
                font-size: 0.875rem;
                padding: 0.5rem;
                background-color: #f8f9fa;
                border-radius: 0.25rem;
            }

            .upload-progress {
                margin-top: 1rem;
            }

            .polygon-validation-error {
                position: absolute;
                top: 10px;
                right: 10px;
                background: rgba(220, 53, 69, 0.9);
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                z-index: 1001;
                max-width: 300px;
            }

            .polygon-validation-success {
                position: absolute;
                top: 10px;
                right: 10px;
                background: rgba(40, 167, 69, 0.9);
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                z-index: 1001;
                max-width: 300px;
            }

            .drawing-status {
                position: absolute;
                bottom: 10px;
                left: 10px;
                background: rgba(0, 0, 0, 0.7);
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                z-index: 1001;
            }
        `;
        document.head.appendChild(style);
    }

    handleDrawModeToggle() {
        // Delegate to the built-in toggleDrawMode function in climate_hazard_map.html
        if (window.toggleDrawMode) {
            window.toggleDrawMode();
        } else {
            this.showError('Drawing functionality not available.');
        }
    }

    // Drawing event listeners are handled by the built-in system in climate_hazard_map.html
    // This handler provides validation utilities only

    validatePolygon(polygon) {
        this.validationErrors = [];

        // Check if geometry exists
        if (!polygon.geometry) {
            return { valid: false, error: 'Invalid polygon geometry' };
        }

        // Check geometry type
        if (polygon.geometry.type !== 'Polygon') {
            return { valid: false, error: 'Only polygons are allowed' };
        }

        // Get coordinates
        const coords = polygon.geometry.coordinates[0];
        if (!coords || coords.length < 4) {
            return { valid: false, error: 'Polygon must have at least 3 points' };
        }

        // Check minimum vertices
        if (coords.length < this.minVertices + 1) {
            return { valid: false, error: `Polygon must have at least ${this.minVertices} points` };
        }

        // Check maximum vertices
        if (coords.length > this.maxVertices + 1) {
            return { valid: false, error: `Polygon cannot have more than ${this.maxVertices} points` };
        }

        // Check for self-intersection
        if (this.isSelfIntersecting(coords)) {
            return { valid: false, error: 'Polygon cannot intersect itself' };
        }

        // Check area (if we can calculate it)
        try {
            const area = this.calculateArea(coords);
            if (area < this.minArea) {
                return { valid: false, error: 'Polygon is too small' };
            }
            if (area > this.maxArea) {
                return { valid: false, error: 'Polygon is too large' };
            }
        } catch (error) {
            console.warn('Could not calculate polygon area:', error);
        }

        // Check if all coordinates are valid
        for (let i = 0; i < coords.length; i++) {
            const [lng, lat] = coords[i];
            if (!this.isValidCoordinate(lng, lat)) {
                return { valid: false, error: 'Invalid coordinates detected' };
            }
        }

        return { valid: true };
    }

    isValidCoordinate(lng, lat) {
        return (
            typeof lng === 'number' && !isNaN(lng) &&
            typeof lat === 'number' && !isNaN(lat) &&
            lng >= -180 && lng <= 180 &&
            lat >= -90 && lat <= 90
        );
    }

    isSelfIntersecting(coords) {
        // Simple self-intersection check
        // A more robust implementation would use proper polygon intersection algorithms
        const n = coords.length - 1; // Last point is same as first

        for (let i = 0; i < n - 2; i++) {
            for (let j = i + 2; j < n; j++) {
                if (this.doSegmentsIntersect(
                    coords[i], coords[i + 1],
                    coords[j], coords[j + 1]
                )) {
                    return true;
                }
            }
        }
        return false;
    }

    doSegmentsIntersect(p1, p2, p3, p4) {
        // Check if line segments p1-p2 and p3-p4 intersect
        const det = (p4[1] - p3[1]) * (p2[0] - p1[0]) - (p4[0] - p3[0]) * (p2[1] - p1[1]);

        if (det === 0) return false;

        const lambda = ((p4[1] - p3[1]) * (p3[0] - p1[0]) + (p4[0] - p3[0]) * (p1[1] - p3[1])) / det;
        const gamma = ((p2[1] - p1[1]) * (p3[0] - p1[0]) - (p2[0] - p1[0]) * (p3[1] - p1[1])) / det;

        return (0 < lambda && lambda < 1) && (0 < gamma && gamma < 1);
    }

    calculateArea(coords) {
        // Calculate polygon area using Shoelace formula
        let area = 0;
        const n = coords.length - 1;

        for (let i = 0; i < n; i++) {
            area += coords[i][0] * coords[i + 1][1];
            area -= coords[i + 1][0] * coords[i][1];
        }

        return Math.abs(area / 2);
    }

    processValidPolygon(polygon) {
        try {
            // Calculate centroid using Turf.js if available
            let centroid;
            if (window.turf) {
                centroid = window.turf.centroid(polygon);
                const [lng, lat] = centroid.geometry.coordinates;

                window.drawnPolygonData = {
                    geometry: polygon.geometry,
                    centroid: { lat, lng }
                };
            } else {
                // Fallback: calculate simple centroid
                const coords = polygon.geometry.coordinates[0];
                let sumX = 0, sumY = 0;
                for (let i = 0; i < coords.length - 1; i++) {
                    sumX += coords[i][0];
                    sumY += coords[i][1];
                }
                const n = coords.length - 1;
                window.drawnPolygonData = {
                    geometry: polygon.geometry,
                    centroid: { lat: sumY / n, lng: sumX / n }
                };
            }

            this.clearValidationMessages();
            this.showValidationSuccess('Valid polygon created!');
            this.showStatus('Click "Add Asset" to save this polygon');

            // Exit draw mode
            setTimeout(() => {
                this.exitDrawMode();
                this.showPolygonAssetModal();
            }, 1000);

        } catch (error) {
            this.showError('Error processing polygon: ' + error.message);
        }
    }

    showPolygonAssetModal() {
        if (window.drawnPolygonData && window.showPolygonAssetModal) {
            const { lat, lng } = window.drawnPolygonData.centroid;
            window.showPolygonAssetModal(lat, lng);
        }
    }

    updateDrawButton(isDrawMode) {
        const button = document.getElementById('toggle-draw-mode');
        if (!button) return;

        if (isDrawMode) {
            button.classList.remove('btn-warning');
            button.classList.add('btn-danger');
            button.innerHTML = '<i class="fas fa-times"></i> Cancel Drawing';
        } else {
            button.classList.remove('btn-danger');
            button.classList.add('btn-warning');
            button.innerHTML = '<i class="fas fa-draw-polygon"></i> Draw Polygon Asset';
        }
    }

    showDrawingInstructions() {
        const instructions = document.getElementById('draw-instructions');
        if (instructions) {
            instructions.style.display = 'block';
        }
    }

    hideDrawingInstructions() {
        const instructions = document.getElementById('draw-instructions');
        if (instructions) {
            instructions.style.display = 'none';
        }
    }

    showValidationError(message) {
        this.clearValidationMessages();
        const errorDiv = document.createElement('div');
        errorDiv.className = 'polygon-validation-error';
        errorDiv.innerHTML = `<i class="fas fa-exclamation-triangle me-1"></i>${message}`;

        const mapContainer = document.getElementById('climate-hazard-map');
        if (mapContainer) {
            mapContainer.appendChild(errorDiv);

            // Auto-remove after 5 seconds
            setTimeout(() => {
                if (errorDiv.parentNode) {
                    errorDiv.parentNode.removeChild(errorDiv);
                }
            }, 5000);
        }
    }

    showValidationSuccess(message) {
        this.clearValidationMessages();
        const successDiv = document.createElement('div');
        successDiv.className = 'polygon-validation-success';
        successDiv.innerHTML = `<i class="fas fa-check-circle me-1"></i>${message}`;

        const mapContainer = document.getElementById('climate-hazard-map');
        if (mapContainer) {
            mapContainer.appendChild(successDiv);

            // Auto-remove after 3 seconds
            setTimeout(() => {
                if (successDiv.parentNode) {
                    successDiv.parentNode.removeChild(successDiv);
                }
            }, 3000);
        }
    }

    clearValidationMessages() {
        const messages = document.querySelectorAll('.polygon-validation-error, .polygon-validation-success');
        messages.forEach(msg => msg.remove());
    }

    showStatus(message) {
        this.hideStatus();
        const statusDiv = document.createElement('div');
        statusDiv.className = 'drawing-status';
        statusDiv.textContent = message;

        const mapContainer = document.getElementById('climate-hazard-map');
        if (mapContainer) {
            mapContainer.appendChild(statusDiv);
        }
    }

    hideStatus() {
        const statusElements = document.querySelectorAll('.drawing-status');
        statusElements.forEach(el => el.remove());
    }

    showError(message) {
        console.error('Polygon Draw Error:', message);

        // Show user-friendly error
        if (window.alert) {
            alert('Drawing Error: ' + message);
        }

        // Exit draw mode on error
        if (window.isDrawMode) {
            this.exitDrawMode();
        }
    }

    // Public methods for external access
    isValidPolygonGeometry(geometry) {
        const mockFeature = { type: 'Feature', geometry };
        return this.validatePolygon(mockFeature);
    }

    getPolygonStats(polygon) {
        const validation = this.validatePolygon(polygon);
        if (!validation.valid) {
            return null;
        }

        const coords = polygon.geometry.coordinates[0];
        return {
            vertices: coords.length - 1,
            area: this.calculateArea(coords),
            centroid: this.calculateCentroid(coords),
            perimeter: this.calculatePerimeter(coords)
        };
    }

    calculateCentroid(coords) {
        let sumX = 0, sumY = 0;
        const n = coords.length - 1;

        for (let i = 0; i < n; i++) {
            sumX += coords[i][0];
            sumY += coords[i][1];
        }

        return [sumX / n, sumY / n];
    }

    calculatePerimeter(coords) {
        let perimeter = 0;
        const n = coords.length - 1;

        for (let i = 0; i < n; i++) {
            const dx = coords[i + 1][0] - coords[i][0];
            const dy = coords[i + 1][1] - coords[i][1];
            perimeter += Math.sqrt(dx * dx + dy * dy);
        }

        return perimeter;
    }
}

// Initialize the polygon draw handler when DOM is ready (only if not already initialized)
document.addEventListener('DOMContentLoaded', () => {
    if (!window.polygonDrawHandler) {
        window.polygonDrawHandler = new PolygonDrawHandler();
    }
});