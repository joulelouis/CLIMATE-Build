/**
 * Map Performance Optimizer for Hazard Exposure Map
 * Handles efficient rendering of granular points and optimizes performance
 */

class MapPerformanceOptimizer {
    constructor(map, options = {}) {
        this.map = map;
        this.options = {
            maxPoints: options.maxPoints || 100,
            clusterRadius: options.clusterRadius || 50,
            updateThreshold: options.updateThreshold || 100,
            enableClustering: options.enableClustering !== false,
            enableLOD: options.enableLOD !== false, // Level of Detail
            ...options
        };

        this.pointCache = new Map();
        this.clusterCache = new Map();
        this.lastZoom = this.map.getZoom();
        this.lastBounds = this.map.getBounds();
        this.isVisible = true;
        this.updateTimer = null;

        this.setupEventListeners();
    }

    /**
     * Setup event listeners for performance optimization
     */
    setupEventListeners() {
        // Zoom-based optimization
        this.map.on('zoom', this.handleZoomChange.bind(this));
        this.map.on('zoomend', this.handleZoomEnd.bind(this));

        // Move-based optimization
        this.map.on('move', this.handleMove.bind(this));
        this.map.on('moveend', this.handleMoveEnd.bind(this));

        // Visibility optimization
        document.addEventListener('visibilitychange', this.handleVisibilityChange.bind(this));

        // Window resize optimization
        window.addEventListener('resize', this.handleResize.bind(this));
    }

    /**
     * Handle zoom changes for Level of Detail (LOD)
     */
    handleZoomChange() {
        const currentZoom = this.map.getZoom();

        // Debounce zoom handling
        if (this.updateTimer) {
            clearTimeout(this.updateTimer);
        }

        this.updateTimer = setTimeout(() => {
            this.updatePointVisibility(currentZoom);
            this.updateClusterVisibility(currentZoom);
            this.lastZoom = currentZoom;
        }, this.options.updateThreshold);
    }

    /**
     * Handle zoom end for heavy operations
     */
    handleZoomEnd() {
        this.performHeavyOperations();
    }

    /**
     * Handle map movement for viewport optimization
     */
    handleMove() {
        // Debounce move handling
        if (this.updateTimer) {
            clearTimeout(this.updateTimer);
        }

        this.updateTimer = setTimeout(() => {
            this.updateViewportOptimization();
        }, this.options.updateThreshold);
    }

    /**
     * Handle move end for heavy operations
     */
    handleMoveEnd() {
        const currentBounds = this.map.getBounds();

        // Only perform heavy operations if bounds changed significantly
        if (!this.boundsEqual(this.lastBounds, currentBounds)) {
            this.performHeavyOperations();
            this.lastBounds = currentBounds;
        }
    }

    /**
     * Handle visibility changes
     */
    handleVisibilityChange() {
        this.isVisible = !document.hidden;

        if (this.isVisible) {
            this.resumeRendering();
        } else {
            this.pauseRendering();
        }
    }

    /**
     * Handle window resize
     */
    handleResize() {
        // Debounce resize handling
        if (this.updateTimer) {
            clearTimeout(this.updateTimer);
        }

        this.updateTimer = setTimeout(() => {
            this.map.resize();
            this.performHeavyOperations();
        }, 250);
    }

    /**
     * Update point visibility based on zoom level (LOD)
     */
    updatePointVisibility(zoom) {
        const layers = this.getGranularPointLayers();

        layers.forEach(layerId => {
            const layer = this.map.getLayer(layerId);
            if (!layer) return;

            // Adjust point size based on zoom
            const baseSize = this.getBaseSizeForZoom(zoom);
            const opacity = this.getOpacityForZoom(zoom);

            this.map.setPaintProperty(layerId, 'circle-radius', baseSize);
            this.map.setPaintProperty(layerId, 'circle-opacity', opacity);
        });
    }

    /**
     * Update cluster visibility based on zoom level
     */
    updateClusterVisibility(zoom) {
        if (!this.options.enableClustering) return;

        // Show clusters at lower zoom levels, individual points at higher zoom levels
        const clusterZoomThreshold = 12;

        if (zoom < clusterZoomThreshold) {
            this.enableClustering();
        } else {
            this.disableClustering();
        }
    }

    /**
     * Update viewport optimization
     */
    updateViewportOptimization() {
        const bounds = this.map.getBounds();
        const visiblePoints = this.getPointsInViewport(bounds);

        // Only render points that are currently visible
        this.updateVisiblePoints(visiblePoints);
    }

    /**
     * Perform heavy operations that should be debounced
     */
    performHeavyOperations() {
        if (!this.isVisible) return;

        this.updateViewportOptimization();
        this.updatePointVisibility(this.map.getZoom());
        this.cleanupMemory();
    }

    /**
     * Get base size for points based on zoom level
     */
    getBaseSizeForZoom(zoom) {
        if (zoom < 10) return 4;
        if (zoom < 12) return 6;
        if (zoom < 14) return 8;
        if (zoom < 16) return 10;
        return 12;
    }

    /**
     * Get opacity for points based on zoom level
     */
    getOpacityForZoom(zoom) {
        if (zoom < 8) return 0.3;
        if (zoom < 10) return 0.5;
        if (zoom < 12) return 0.7;
        return 0.8;
    }

    /**
     * Get granular point layers
     */
    getGranularPointLayers() {
        const layers = [];
        const style = this.map.getStyle();

        if (style && style.layers) {
            style.layers.forEach(layer => {
                if (layer.id.includes('granular') || layer.id.includes('hazard-')) {
                    layers.push(layer.id);
                }
            });
        }

        return layers;
    }

    /**
     * Get points within current viewport
     */
    getPointsInViewport(bounds) {
        const source = this.map.getSource('granular-points');
        if (!source || !source._data) return [];

        const features = source._data.features || [];
        return features.filter(feature => {
            const coords = feature.geometry.coordinates;
            return bounds.contains([coords[0], coords[1]]);
        });
    }

    /**
     * Update visible points for rendering
     */
    updateVisiblePoints(visiblePoints) {
        // Limit number of points for performance
        if (visiblePoints.length > this.options.maxPoints) {
            visiblePoints = this.downsamplePoints(visiblePoints, this.options.maxPoints);
        }

        // Update source with filtered points
        const source = this.map.getSource('granular-points');
        if (source) {
            source.setData({
                type: 'FeatureCollection',
                features: visiblePoints
            });
        }
    }

    /**
     * Downsample points for performance
     */
    downsamplePoints(points, maxPoints) {
        if (points.length <= maxPoints) return points;

        // Simple grid-based downsampling
        const bounds = this.map.getBounds();
        const gridSize = Math.ceil(Math.sqrt(points.length / maxPoints));

        const grid = new Map();

        points.forEach(point => {
            const coords = point.geometry.coordinates;
            const gridX = Math.floor((coords[0] - bounds.getWest()) / (bounds.getEast() - bounds.getWest()) * gridSize);
            const gridY = Math.floor((coords[1] - bounds.getSouth()) / (bounds.getNorth() - bounds.getSouth()) * gridSize);
            const key = `${gridX},${gridY}`;

            if (!grid.has(key)) {
                grid.set(key, point);
            }
        });

        return Array.from(grid.values());
    }

    /**
     * Enable clustering for points
     */
    enableClustering() {
        // Implementation depends on clustering library
        // This is a placeholder for clustering logic
        console.log('Enabling point clustering');
    }

    /**
     * Disable clustering for points
     */
    disableClustering() {
        // Implementation depends on clustering library
        // This is a placeholder for clustering logic
        console.log('Disabling point clustering');
    }

    /**
     * Resume rendering when page becomes visible
     */
    resumeRendering() {
        this.getGranularPointLayers().forEach(layerId => {
            this.map.setLayoutProperty(layerId, 'visibility', 'visible');
        });

        this.performHeavyOperations();
    }

    /**
     * Pause rendering when page is hidden
     */
    pauseRendering() {
        this.getGranularPointLayers().forEach(layerId => {
            this.map.setLayoutProperty(layerId, 'visibility', 'none');
        });
    }

    /**
     * Cleanup memory caches
     */
    cleanupMemory() {
        // Clear old cache entries
        if (this.pointCache.size > 1000) {
            const entriesToKeep = Array.from(this.pointCache.keys()).slice(-500);
            const newCache = new Map();
            entriesToKeep.forEach(key => {
                newCache.set(key, this.pointCache.get(key));
            });
            this.pointCache = newCache;
        }

        if (this.clusterCache.size > 100) {
            this.clusterCache.clear();
        }
    }

    /**
     * Check if two bounds are approximately equal
     */
    boundsEqual(bounds1, bounds2, tolerance = 0.001) {
        return Math.abs(bounds1.getNorth() - bounds2.getNorth()) < tolerance &&
               Math.abs(bounds1.getSouth() - bounds2.getSouth()) < tolerance &&
               Math.abs(bounds1.getEast() - bounds2.getEast()) < tolerance &&
               Math.abs(bounds1.getWest() - bounds2.getWest()) < tolerance;
    }

    /**
     * Optimize for a large number of points
     */
    optimizeForLargePointCount(pointCount) {
        if (pointCount > 1000) {
            // Enable aggressive optimization
            this.options.enableClustering = true;
            this.options.maxPoints = 100;
            this.options.updateThreshold = 200;
        } else if (pointCount > 500) {
            // Moderate optimization
            this.options.enableClustering = true;
            this.options.maxPoints = 200;
            this.options.updateThreshold = 150;
        } else {
            // Light optimization
            this.options.enableClustering = false;
            this.options.maxPoints = 500;
            this.options.updateThreshold = 100;
        }
    }

    /**
     * Get performance statistics
     */
    getPerformanceStats() {
        return {
            visiblePoints: this.getPointsInViewport(this.map.getBounds()).length,
            totalPoints: this.pointCache.size,
            clusterCount: this.clusterCache.size,
            currentZoom: this.map.getZoom(),
            isVisible: this.isVisible,
            optimizationLevel: this.getOptimizationLevel()
        };
    }

    /**
     * Get current optimization level
     */
    getOptimizationLevel() {
        const pointCount = this.getPointsInViewport(this.map.getBounds()).length;

        if (pointCount > 1000) return 'aggressive';
        if (pointCount > 500) return 'moderate';
        if (pointCount > 100) return 'light';
        return 'minimal';
    }

    /**
     * Destroy the optimizer and clean up resources
     */
    destroy() {
        // Clear timers
        if (this.updateTimer) {
            clearTimeout(this.updateTimer);
        }

        // Clear caches
        this.pointCache.clear();
        this.clusterCache.clear();

        // Remove event listeners
        this.map.off('zoom', this.handleZoomChange);
        this.map.off('zoomend', this.handleZoomEnd);
        this.map.off('move', this.handleMove);
        this.map.off('moveend', this.handleMoveEnd);
        document.removeEventListener('visibilitychange', this.handleVisibilityChange);
        window.removeEventListener('resize', this.handleResize);
    }
}

// Export for global use
window.MapPerformanceOptimizer = MapPerformanceOptimizer;