/**
 * Comprehensive Polygon Validation and Error Handling System
 * Provides robust validation, error reporting, and user feedback
 */

class PolygonValidator {
    constructor(options = {}) {
        this.options = {
            minVertices: 3,
            maxVertices: 500,
            minArea: 0.0001, // Minimum area in square degrees
            maxArea: 5, // Maximum area in square degrees
            minSideLength: 0.0001, // Minimum side length in degrees
            maxSideLength: 10, // Maximum side length in degrees
            allowSelfIntersection: false,
            enableCoordinateValidation: true,
            enableGeospatialValidation: true,
            strictMode: false,
            ...options
        };

        this.errors = [];
        this.warnings = [];
        this.validationHistory = [];
        this.init();
    }

    init() {
        this.setupErrorDisplay();
        this.setupValidationRules();
    }

    setupErrorDisplay() {
        // Create error display container if it doesn't exist
        if (!document.getElementById('validation-errors')) {
            const errorContainer = document.createElement('div');
            errorContainer.id = 'validation-errors';
            errorContainer.className = 'validation-errors';
            errorContainer.innerHTML = `
                <div class="validation-messages position-fixed top-0 start-50 translate-middle-x mt-3"
                     style="z-index: 10000; max-width: 500px; width: 90%;">
                </div>
            `;
            document.body.appendChild(errorContainer);
        }
    }

    setupValidationRules() {
        this.validationRules = [
            {
                name: 'basic_structure',
                description: 'Basic polygon structure validation',
                validator: this.validateBasicStructure.bind(this),
                critical: true
            },
            {
                name: 'vertices_count',
                description: 'Vertices count validation',
                validator: this.validateVerticesCount.bind(this),
                critical: true
            },
            {
                name: 'coordinate_ranges',
                description: 'Coordinate range validation',
                validator: this.validateCoordinateRanges.bind(this),
                critical: true
            },
            {
                name: 'self_intersection',
                description: 'Self-intersection detection',
                validator: this.validateSelfIntersection.bind(this),
                critical: !this.options.allowSelfIntersection
            },
            {
                name: 'area_limits',
                description: 'Area size validation',
                validator: this.validateAreaLimits.bind(this),
                critical: false
            },
            {
                name: 'side_lengths',
                description: 'Side length validation',
                validator: this.validateSideLengths.bind(this),
                critical: false
            },
            {
                name: 'geospatial_validity',
                description: 'Geospatial validity check',
                validator: this.validateGeospatialValidity.bind(this),
                critical: false
            },
            {
                name: 'topology',
                description: 'Topology validation',
                validator: this.validateTopology.bind(this),
                critical: false
            }
        ];
    }

    validatePolygon(polygon) {
        this.errors = [];
        this.warnings = [];

        const validationResult = {
            valid: true,
            errors: [],
            warnings: [],
            metadata: {
                vertices: 0,
                area: 0,
                perimeter: 0,
                centroid: null,
                boundingBox: null
            }
        };

        try {
            // Extract polygon geometry
            let geometry;
            if (polygon.geometry) {
                geometry = polygon.geometry;
            } else if (polygon.type && polygon.coordinates) {
                geometry = polygon;
            } else {
                throw new Error('Invalid polygon format: missing geometry or coordinates');
            }

            // Validate geometry type
            if (geometry.type !== 'Polygon') {
                throw new Error('Invalid geometry type: only Polygon type is supported');
            }

            // Extract coordinates
            const coordinates = geometry.coordinates;
            if (!coordinates || !Array.isArray(coordinates) || coordinates.length === 0) {
                throw new Error('Invalid coordinates: polygon must have coordinate arrays');
            }

            // Get the main ring (first coordinate array)
            const mainRing = coordinates[0];
            if (!mainRing || !Array.isArray(mainRing)) {
                throw new Error('Invalid polygon: missing main coordinate ring');
            }

            // Store metadata
            validationResult.metadata.vertices = mainRing.length - 1; // Exclude closing point
            validationResult.metadata.area = this.calculateArea(mainRing);
            validationResult.metadata.perimeter = this.calculatePerimeter(mainRing);
            validationResult.metadata.centroid = this.calculateCentroid(mainRing);
            validationResult.metadata.boundingBox = this.calculateBoundingBox(mainRing);

            // Run validation rules
            for (const rule of this.validationRules) {
                try {
                    const ruleResult = rule.validator(mainRing, validationResult.metadata);
                    if (!ruleResult.valid) {
                        if (rule.critical || this.options.strictMode) {
                            validationResult.valid = false;
                            validationResult.errors.push({
                                rule: rule.name,
                                message: ruleResult.message,
                                severity: 'error',
                                code: ruleResult.code || 'VALIDATION_ERROR'
                            });
                            this.errors.push(ruleResult);
                        } else {
                            validationResult.warnings.push({
                                rule: rule.name,
                                message: ruleResult.message,
                                severity: 'warning',
                                code: ruleResult.code || 'VALIDATION_WARNING'
                            });
                            this.warnings.push(ruleResult);
                        }
                    }
                } catch (error) {
                    console.error(`Validation rule '${rule.name}' failed:`, error);
                    if (rule.critical) {
                        validationResult.valid = false;
                        validationResult.errors.push({
                            rule: rule.name,
                            message: `Validation error: ${error.message}`,
                            severity: 'error',
                            code: 'RULE_EXECUTION_ERROR'
                        });
                    }
                }
            }

            // Log validation result
            this.validationHistory.push({
                timestamp: Date.now(),
                polygon: polygon,
                result: validationResult,
                errors: [...this.errors],
                warnings: [...this.warnings]
            });

            return validationResult;

        } catch (error) {
            console.error('Polygon validation failed:', error);
            return {
                valid: false,
                errors: [{
                    rule: 'general',
                    message: error.message,
                    severity: 'error',
                    code: 'VALIDATION_EXCEPTION'
                }],
                warnings: [],
                metadata: null
            };
        }
    }

    validateBasicStructure(coordinates, metadata) {
        // Check if coordinates array is valid
        if (!Array.isArray(coordinates)) {
            return {
                valid: false,
                message: 'Coordinates must be an array',
                code: 'INVALID_COORDINATES_ARRAY'
            };
        }

        // Check if polygon is closed (first and last points match)
        if (coordinates.length < 2) {
            return {
                valid: false,
                message: 'Polygon must have at least 2 coordinate points',
                code: 'INSUFFICIENT_COORDINATES'
            };
        }

        const firstPoint = coordinates[0];
        const lastPoint = coordinates[coordinates.length - 1];

        if (firstPoint.length !== 2 || lastPoint.length !== 2) {
            return {
                valid: false,
                message: 'Each coordinate must have exactly 2 values (longitude, latitude)',
                code: 'INVALID_COORDINATE_FORMAT'
            };
        }

        // Check if polygon is properly closed
        const tolerance = 1e-10;
        if (Math.abs(firstPoint[0] - lastPoint[0]) > tolerance ||
            Math.abs(firstPoint[1] - lastPoint[1]) > tolerance) {
            return {
                valid: false,
                message: 'Polygon must be closed (first and last coordinates must match)',
                code: 'POLYGON_NOT_CLOSED'
            };
        }

        return { valid: true };
    }

    validateVerticesCount(coordinates, metadata) {
        const vertexCount = metadata.vertices;

        if (vertexCount < this.options.minVertices) {
            return {
                valid: false,
                message: `Polygon must have at least ${this.options.minVertices} vertices, but has ${vertexCount}`,
                code: 'INSUFFICIENT_VERTICES'
            };
        }

        if (vertexCount > this.options.maxVertices) {
            return {
                valid: false,
                message: `Polygon cannot have more than ${this.options.maxVertices} vertices, but has ${vertexCount}`,
                code: 'EXCESSIVE_VERTICES'
            };
        }

        return { valid: true };
    }

    validateCoordinateRanges(coordinates, metadata) {
        for (let i = 0; i < coordinates.length - 1; i++) { // Exclude closing point
            const [lng, lat] = coordinates[i];

            // Check longitude range
            if (lng < -180 || lng > 180) {
                return {
                    valid: false,
                    message: `Invalid longitude ${lng} at vertex ${i + 1}. Must be between -180 and 180.`,
                    code: 'INVALID_LONGITUDE'
                };
            }

            // Check latitude range
            if (lat < -90 || lat > 90) {
                return {
                    valid: false,
                    message: `Invalid latitude ${lat} at vertex ${i + 1}. Must be between -90 and 90.`,
                    code: 'INVALID_LATITUDE'
                };
            }

            // Check for NaN or Infinity
            if (!isFinite(lng) || !isFinite(lat)) {
                return {
                    valid: false,
                    message: `Invalid coordinate at vertex ${i + 1}: (${lng}, ${lat})`,
                    code: 'INVALID_COORDINATE_VALUE'
                };
            }
        }

        return { valid: true };
    }

    validateSelfIntersection(coordinates, metadata) {
        if (this.options.allowSelfIntersection) {
            return { valid: true };
        }

        const n = coordinates.length - 1; // Exclude closing point
        if (n < 4) return { valid: true }; // Triangle can't self-intersect

        // Check for self-intersection using line segment intersection
        for (let i = 0; i < n - 2; i++) {
            for (let j = i + 2; j < n; j++) {
                // Skip adjacent segments
                if (Math.abs(i - j) <= 1) continue;

                // Skip first and last segment intersection (polygon closure)
                if (i === 0 && j === n - 1) continue;

                const segment1 = [coordinates[i], coordinates[i + 1]];
                const segment2 = [coordinates[j], coordinates[j + 1]];

                if (this.doSegmentsIntersect(segment1[0], segment1[1], segment2[0], segment2[1])) {
                    return {
                        valid: false,
                        message: `Polygon self-intersects between segments (${i + 1}-${i + 2}) and (${j + 1}-${j + 2})`,
                        code: 'SELF_INTERSECTION'
                    };
                }
            }
        }

        return { valid: true };
    }

    validateAreaLimits(coordinates, metadata) {
        const area = metadata.area;

        if (area < this.options.minArea) {
            return {
                valid: false,
                message: `Polygon area ${area.toFixed(6)}°² is too small. Minimum is ${this.options.minArea}°²`,
                code: 'AREA_TOO_SMALL'
            };
        }

        if (area > this.options.maxArea) {
            return {
                valid: false,
                message: `Polygon area ${area.toFixed(6)}°² is too large. Maximum is ${this.options.maxArea}°²`,
                code: 'AREA_TOO_LARGE'
            };
        }

        return { valid: true };
    }

    validateSideLengths(coordinates, metadata) {
        const n = coordinates.length - 1; // Exclude closing point

        for (let i = 0; i < n; i++) {
            const p1 = coordinates[i];
            const p2 = coordinates[(i + 1) % n];
            const length = this.calculateDistance(p1, p2);

            if (length < this.options.minSideLength) {
                return {
                    valid: false,
                    message: `Side ${i + 1} is too short: ${length.toFixed(6)}°. Minimum is ${this.options.minSideLength}°`,
                    code: 'SIDE_TOO_SHORT'
                };
            }

            if (length > this.options.maxSideLength) {
                return {
                    valid: false,
                    message: `Side ${i + 1} is too long: ${length.toFixed(6)}°. Maximum is ${this.options.maxSideLength}°`,
                    code: 'SIDE_TOO_LONG'
                };
            }
        }

        return { valid: true };
    }

    validateGeospatialValidity(coordinates, metadata) {
        // Check for degenerate polygons (all points collinear)
        if (this.isCollinear(coordinates)) {
            return {
                valid: false,
                message: 'Polygon is degenerate: all vertices are collinear',
                code: 'DEGENERATE_POLYGON'
            };
        }

        // Check for duplicate consecutive vertices
        for (let i = 0; i < coordinates.length - 1; i++) {
            const p1 = coordinates[i];
            const p2 = coordinates[i + 1];
            const distance = this.calculateDistance(p1, p2);

            if (distance < 1e-10) {
                return {
                    valid: false,
                    message: `Duplicate consecutive vertices found at position ${i + 1}`,
                    code: 'DUPLICATE_VERTICES'
                };
            }
        }

        return { valid: true };
    }

    validateTopology(coordinates, metadata) {
        // Check if polygon has a valid orientation (should be clockwise for exterior ring)
        const signedArea = this.calculateSignedArea(coordinates);

        if (signedArea === 0) {
            return {
                valid: false,
                message: 'Polygon has zero area (invalid topology)',
                code: 'ZERO_AREA'
            };
        }

        // Check if polygon spans the antimeridian or poles
        const bbox = metadata.boundingBox;
        if (bbox.minLng < -170 && bbox.maxLng > 170) {
            return {
                valid: true,
                message: 'Warning: Polygon spans the antimeridian',
                code: 'ANTIMERIDIAN_SPAN',
                severity: 'warning'
            };
        }

        if (bbox.minLat < -85 || bbox.maxLat > 85) {
            return {
                valid: true,
                message: 'Warning: Polygon extends into polar regions',
                code: 'POLAR_REGION',
                severity: 'warning'
            };
        }

        return { valid: true };
    }

    // Utility methods
    calculateArea(coordinates) {
        let area = 0;
        const n = coordinates.length - 1;

        for (let i = 0; i < n; i++) {
            area += coordinates[i][0] * coordinates[i + 1][1];
            area -= coordinates[i + 1][0] * coordinates[i][1];
        }

        return Math.abs(area / 2);
    }

    calculateSignedArea(coordinates) {
        let area = 0;
        const n = coordinates.length - 1;

        for (let i = 0; i < n; i++) {
            area += coordinates[i][0] * coordinates[i + 1][1];
            area -= coordinates[i + 1][0] * coordinates[i][1];
        }

        return area / 2;
    }

    calculatePerimeter(coordinates) {
        let perimeter = 0;
        const n = coordinates.length - 1;

        for (let i = 0; i < n; i++) {
            perimeter += this.calculateDistance(coordinates[i], coordinates[i + 1]);
        }

        return perimeter;
    }

    calculateCentroid(coordinates) {
        let sumX = 0, sumY = 0;
        const n = coordinates.length - 1;

        for (let i = 0; i < n; i++) {
            sumX += coordinates[i][0];
            sumY += coordinates[i][1];
        }

        return [sumX / n, sumY / n];
    }

    calculateBoundingBox(coordinates) {
        const lngs = coordinates.map(coord => coord[0]);
        const lats = coordinates.map(coord => coord[1]);

        return {
            minLng: Math.min(...lngs),
            maxLng: Math.max(...lngs),
            minLat: Math.min(...lats),
            maxLat: Math.max(...lats)
        };
    }

    calculateDistance(p1, p2) {
        const dx = p2[0] - p1[0];
        const dy = p2[1] - p1[1];
        return Math.sqrt(dx * dx + dy * dy);
    }

    doSegmentsIntersect(p1, p2, p3, p4) {
        const det = (p4[1] - p3[1]) * (p2[0] - p1[0]) - (p4[0] - p3[0]) * (p2[1] - p1[1]);

        if (Math.abs(det) < 1e-10) return false; // Parallel or collinear

        const lambda = ((p4[1] - p3[1]) * (p3[0] - p1[0]) + (p4[0] - p3[0]) * (p1[1] - p3[1])) / det;
        const gamma = ((p2[1] - p1[1]) * (p3[0] - p1[0]) - (p2[0] - p1[0]) * (p3[1] - p1[1])) / det;

        return (0 < lambda && lambda < 1) && (0 < gamma && gamma < 1);
    }

    isCollinear(coordinates) {
        if (coordinates.length < 3) return true;

        const p1 = coordinates[0];
        const p2 = coordinates[1];
        const p3 = coordinates[2];

        // Calculate cross product
        const crossProduct = (p2[0] - p1[0]) * (p3[1] - p1[1]) - (p2[1] - p1[1]) * (p3[0] - p1[0]);

        return Math.abs(crossProduct) < 1e-10;
    }

    // Error display methods
    showError(message, options = {}) {
        this.showMessage(message, 'error', options);
    }

    showWarning(message, options = {}) {
        this.showMessage(message, 'warning', options);
    }

    showSuccess(message, options = {}) {
        this.showMessage(message, 'success', options);
    }

    showMessage(message, type, options = {}) {
        const container = document.querySelector('.validation-messages');
        if (!container) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `alert alert-${type} alert-dismissible fade show mb-2 shadow-lg`;
        messageDiv.setAttribute('role', 'alert');

        const iconMap = {
            error: 'fas fa-exclamation-triangle',
            warning: 'fas fa-exclamation-circle',
            success: 'fas fa-check-circle',
            info: 'fas fa-info-circle'
        };

        const autoHide = options.autoHide !== false && type !== 'error';
        const hideDelay = options.hideDelay || (type === 'success' ? 3000 : 5000);

        messageDiv.innerHTML = `
            <div class="d-flex align-items-start">
                <i class="${iconMap[type]} me-2 mt-1"></i>
                <div class="flex-grow-1">
                    <div class="fw-bold">${options.title || this.getDefaultTitle(type)}</div>
                    <div class="small">${message}</div>
                </div>
                <button type="button" class="btn-close ms-2" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;

        container.appendChild(messageDiv);

        // Add animation
        messageDiv.classList.add('fade-in');

        // Auto-hide if specified
        if (autoHide) {
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.classList.add('fade-out');
                    setTimeout(() => {
                        if (messageDiv.parentNode) {
                            messageDiv.remove();
                        }
                    }, 300);
                }
            }, hideDelay);
        }

        // Announce to screen readers
        this.announceToScreenReader(`${options.title || this.getDefaultTitle(type)}: ${message}`);
    }

    getDefaultTitle(type) {
        const titles = {
            error: 'Validation Error',
            warning: 'Warning',
            success: 'Success',
            info: 'Information'
        };
        return titles[type] || 'Message';
    }

    announceToScreenReader(message) {
        const announcement = document.createElement('div');
        announcement.setAttribute('aria-live', 'polite');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.className = 'sr-only';
        announcement.textContent = message;
        document.body.appendChild(announcement);

        setTimeout(() => {
            announcement.remove();
        }, 1000);
    }

    clearMessages() {
        const container = document.querySelector('.validation-messages');
        if (container) {
            container.innerHTML = '';
        }
    }

    // Validation history methods
    getValidationHistory() {
        return [...this.validationHistory];
    }

    clearValidationHistory() {
        this.validationHistory = [];
    }

    getLastValidation() {
        return this.validationHistory[this.validationHistory.length - 1] || null;
    }

    // Static methods for convenience
    static validate(polygon, options = {}) {
        const validator = new PolygonValidator(options);
        return validator.validatePolygon(polygon);
    }

    static showError(message, options = {}) {
        const validator = new PolygonValidator();
        validator.showError(message, options);
    }

    static showWarning(message, options = {}) {
        const validator = new PolygonValidator();
        validator.showWarning(message, options);
    }

    static showSuccess(message, options = {}) {
        const validator = new PolygonValidator();
        validator.showSuccess(message, options);
    }
}

// Auto-initialize if needed
document.addEventListener('DOMContentLoaded', () => {
    // Make validator available globally
    window.PolygonValidator = PolygonValidator;
    window.polygonValidator = new PolygonValidator();
});