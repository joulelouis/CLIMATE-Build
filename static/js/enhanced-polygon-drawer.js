/**
 * Enhanced Polygon Drawing System for Climate Hazards Analysis
 *
 * Features:
 * - Interactive polygon drawing with real-time feedback
 * - Mobile-optimized touch controls
 * - Keyboard shortcuts and accessibility support
 * - Visual drawing aids (snap to grid, area calculation)
 * - Undo/redo functionality
 * - Polygon editing capabilities
 * - Coordinate display and validation
 * - Responsive design for all screen sizes
 */

class EnhancedPolygonDrawer {
    constructor(options = {}) {
        this.options = {
            mapContainer: '#climate-hazard-map',
            minVertices: 3,
            maxVertices: 500,
            minArea: 0.0001, // Minimum area in square degrees
            maxArea: 5, // Maximum area in square degrees
            enableSnapToGrid: false,
            gridSize: 0.001, // Grid size in degrees
            enableKeyboardShortcuts: true,
            enableUndoRedo: true,
            showCoordinateDisplay: true,
            showAreaCalculation: true,
            mobileOptimized: true,
            accessibilityMode: false,
            ...options
        };

        // State management
        this.isDrawing = false;
        this.isEditing = false;
        this.currentPoints = [];
        this.currentPolygon = null;
        this.drawingHistory = [];
        this.historyIndex = -1;
        this.tempMarker = null;
        this.coordinateDisplay = null;
        this.areaDisplay = null;
        this.drawingTooltip = null;

        // Mobile detection
        this.isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        this.isTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

        // Map references (will be set during initialization)
        this.map = null;
        this.drawControl = null;

        this.init();
    }

    init() {
        console.log('Initializing Enhanced Polygon Drawer');

        // Wait for map to be available
        this.waitForMap().then(() => {
            this.setupUI();
            this.setupEventListeners();
            this.setupKeyboardShortcuts();
            this.setupAccessibility();
            this.setupMobileSupport();
        });
    }

    waitForMap() {
        return new Promise((resolve) => {
            const checkMap = () => {
                if (window.multiHazardMap && window.draw) {
                    this.map = window.multiHazardMap;
                    this.drawControl = window.draw;
                    resolve();
                } else {
                    setTimeout(checkMap, 100);
                }
            };
            checkMap();
        });
    }

    setupUI() {
        this.createDrawingControls();
        this.createInfoDisplays();
        this.createDrawingTooltip();
        this.updateControlVisibility();
    }

    createDrawingControls() {
        const controlsContainer = document.getElementById('draw-polygon-controls');
        if (!controlsContainer) {
            console.warn('Draw controls container not found');
            return;
        }

        // Enhanced control panel
        const controlsHtml = `
            <div class="enhanced-draw-controls bg-white rounded shadow-lg p-3" style="min-width: 280px;">
                <div class="d-flex align-items-center justify-content-between mb-3">
                    <h6 class="mb-0 fw-bold">
                        <i class="fas fa-draw-polygon text-primary me-2"></i>
                        Drawing Tools
                    </h6>
                    <button class="btn btn-sm btn-outline-secondary" id="minimize-controls" title="Minimize">
                        <i class="fas fa-minus"></i>
                    </button>
                </div>

                <div id="controls-content">
                    <!-- Drawing Mode Buttons -->
                    <div class="drawing-modes mb-3">
                        <div class="btn-group w-100" role="group">
                            <button type="button" id="draw-polygon-btn"
                                    class="btn btn-outline-primary flex-fill"
                                    title="Draw New Polygon (D)">
                                <i class="fas fa-draw-polygon"></i>
                                <span class="d-none d-md-inline ms-1">Draw</span>
                            </button>
                            <button type="button" id="edit-polygon-btn"
                                    class="btn btn-outline-warning flex-fill"
                                    title="Edit Polygon (E)">
                                <i class="fas fa-edit"></i>
                                <span class="d-none d-md-inline ms-1">Edit</span>
                            </button>
                            <button type="button" id="delete-polygon-btn"
                                    class="btn btn-outline-danger flex-fill"
                                    title="Delete Polygon (Delete)">
                                <i class="fas fa-trash"></i>
                                <span class="d-none d-md-inline ms-1">Delete</span>
                            </button>
                        </div>
                    </div>

                    <!-- Drawing Settings -->
                    <div class="drawing-settings mb-3">
                        <div class="form-check form-switch mb-2">
                            <input class="form-check-input" type="checkbox" id="snap-to-grid" ${this.options.enableSnapToGrid ? 'checked' : ''}>
                            <label class="form-check-label small" for="snap-to-grid">
                                <i class="fas fa-th me-1"></i>Snap to Grid
                            </label>
                        </div>
                        <div class="form-check form-switch mb-2">
                            <input class="form-check-input" type="checkbox" id="show-coordinates" ${this.options.showCoordinateDisplay ? 'checked' : ''}>
                            <label class="form-check-label small" for="show-coordinates">
                                <i class="fas fa-map-marker-alt me-1"></i>Show Coordinates
                            </label>
                        </div>
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" id="show-area" ${this.options.showAreaCalculation ? 'checked' : ''}>
                            <label class="form-check-label small" for="show-area">
                                <i class="fas fa-vector-square me-1"></i>Show Area
                            </label>
                        </div>
                    </div>

                    <!-- Action Buttons -->
                    <div class="drawing-actions">
                        <div class="btn-group w-100 mb-2" role="group">
                            <button type="button" id="undo-btn"
                                    class="btn btn-outline-secondary btn-sm flex-fill"
                                    title="Undo (Ctrl+Z)" disabled>
                                <i class="fas fa-undo"></i>
                                <span class="d-none d-md-inline ms-1">Undo</span>
                            </button>
                            <button type="button" id="redo-btn"
                                    class="btn btn-outline-secondary btn-sm flex-fill"
                                    title="Redo (Ctrl+Y)" disabled>
                                <i class="fas fa-redo"></i>
                                <span class="d-none d-md-inline ms-1">Redo</span>
                            </button>
                        </div>

                        <button type="button" id="clear-all-btn"
                                class="btn btn-outline-danger btn-sm w-100"
                                title="Clear All Drawings">
                            <i class="fas fa-eraser me-1"></i>Clear All
                        </button>
                    </div>

                    <!-- Quick Help -->
                    <div class="quick-help mt-3">
                        <button class="btn btn-link btn-sm text-muted p-0"
                                type="button"
                                data-bs-toggle="collapse"
                                data-bs-target="#drawing-help">
                            <i class="fas fa-question-circle me-1"></i>Quick Help
                        </button>
                        <div class="collapse" id="drawing-help">
                            <div class="card card-body bg-light small">
                                <ul class="mb-0">
                                    <li><kbd>D</kbd> - Draw mode</li>
                                    <li><kbd>E</kbd> - Edit mode</li>
                                    <li><kbd>Esc</kbd> - Cancel drawing</li>
                                    <li><kbd>Enter</kbd> - Finish polygon</li>
                                    <li><kbd>Ctrl+Z</kbd> - Undo</li>
                                    <li><kbd>Ctrl+Y</kbd> - Redo</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        controlsContainer.innerHTML = controlsHtml;
        controlsContainer.style.display = 'block';
        controlsContainer.classList.add('enhanced-controls-container');
    }

    createInfoDisplays() {
        const mapContainer = document.querySelector(this.options.mapContainer);
        if (!mapContainer) return;

        // Coordinate display
        const coordDisplay = document.createElement('div');
        coordDisplay.id = 'coordinate-display';
        coordDisplay.className = 'coordinate-display';
        coordDisplay.innerHTML = `
            <div class="coordinate-info bg-dark text-white px-3 py-2 rounded shadow"
                 style="position: absolute; top: 10px; right: 10px; z-index: 1000; font-size: 12px; display: none;">
                <i class="fas fa-crosshairs me-1"></i>
                <span id="coord-text">Lat: 0.000000, Lng: 0.000000</span>
            </div>
        `;
        mapContainer.appendChild(coordDisplay);
        this.coordinateDisplay = coordDisplay;

        // Area display
        const areaDisplay = document.createElement('div');
        areaDisplay.id = 'area-display';
        areaDisplay.className = 'area-display';
        areaDisplay.innerHTML = `
            <div class="area-info bg-info text-white px-3 py-2 rounded shadow"
                 style="position: absolute; top: 50px; right: 10px; z-index: 1000; font-size: 12px; display: none;">
                <i class="fas fa-vector-square me-1"></i>
                <span id="area-text">Area: 0.000 km²</span>
            </div>
        `;
        mapContainer.appendChild(areaDisplay);
        this.areaDisplay = areaDisplay;

        // Drawing status
        const statusDisplay = document.createElement('div');
        statusDisplay.id = 'drawing-status';
        statusDisplay.className = 'drawing-status';
        statusDisplay.innerHTML = `
            <div class="status-info bg-success text-white px-3 py-2 rounded shadow"
                 style="position: absolute; bottom: 10px; left: 10px; z-index: 1000; font-size: 12px; display: none;">
                <i class="fas fa-info-circle me-1"></i>
                <span id="status-text">Ready to draw</span>
            </div>
        `;
        mapContainer.appendChild(statusDisplay);
        this.statusDisplay = statusDisplay;
    }

    createDrawingTooltip() {
        const tooltip = document.createElement('div');
        tooltip.id = 'drawing-tooltip';
        tooltip.className = 'drawing-tooltip';
        tooltip.innerHTML = `
            <div class="tooltip-content bg-white border border-primary rounded px-2 py-1 shadow"
                 style="position: absolute; z-index: 1001; font-size: 11px; display: none; pointer-events: none;">
                <i class="fas fa-mouse-pointer text-primary me-1"></i>
                <span id="tooltip-text">Click to add point</span>
            </div>
        `;
        document.querySelector(this.options.mapContainer).appendChild(tooltip);
        this.drawingTooltip = tooltip;
    }

    setupEventListeners() {
        // Drawing mode buttons
        document.getElementById('draw-polygon-btn')?.addEventListener('click', () => this.startDrawing());
        document.getElementById('edit-polygon-btn')?.addEventListener('click', () => this.startEditing());
        document.getElementById('delete-polygon-btn')?.addEventListener('click', () => this.deletePolygons());

        // Action buttons
        document.getElementById('undo-btn')?.addEventListener('click', () => this.undo());
        document.getElementById('redo-btn')?.addEventListener('click', () => this.redo());
        document.getElementById('clear-all-btn')?.addEventListener('click', () => this.clearAll());

        // Settings toggles
        document.getElementById('snap-to-grid')?.addEventListener('change', (e) => {
            this.options.enableSnapToGrid = e.target.checked;
        });

        document.getElementById('show-coordinates')?.addEventListener('change', (e) => {
            this.options.showCoordinateDisplay = e.target.checked;
            this.updateDisplayVisibility();
        });

        document.getElementById('show-area')?.addEventListener('change', (e) => {
            this.options.showAreaCalculation = e.target.checked;
            this.updateDisplayVisibility();
        });

        // Minimize controls
        document.getElementById('minimize-controls')?.addEventListener('click', () => {
            const content = document.getElementById('controls-content');
            const btn = document.getElementById('minimize-controls');
            const icon = btn.querySelector('i');

            if (content.style.display === 'none') {
                content.style.display = 'block';
                icon.className = 'fas fa-minus';
            } else {
                content.style.display = 'none';
                icon.className = 'fas fa-plus';
            }
        });

        // Map events
        if (this.map) {
            this.map.on('mousemove', (e) => this.handleMouseMove(e));
            this.map.on('click', (e) => this.handleMapClick(e));

            // Touch events for mobile
            if (this.isTouch) {
                this.map.on('touchstart', (e) => this.handleTouchStart(e));
                this.map.on('touchmove', (e) => this.handleTouchMove(e));
                this.map.on('touchend', (e) => this.handleTouchEnd(e));
            }
        }

        // Draw control events
        if (this.drawControl) {
            this.drawControl.on('draw.create', (e) => this.handleDrawCreate(e));
            this.drawControl.on('draw.update', (e) => this.handleDrawUpdate(e));
            this.drawControl.on('draw.delete', (e) => this.handleDrawDelete(e));
        }
    }

    setupKeyboardShortcuts() {
        if (!this.options.enableKeyboardShortcuts) return;

        document.addEventListener('keydown', (e) => {
            // Only handle shortcuts when not in form inputs
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            switch(e.key.toLowerCase()) {
                case 'd':
                    if (!e.ctrlKey && !e.metaKey) {
                        e.preventDefault();
                        this.startDrawing();
                    }
                    break;
                case 'e':
                    if (!e.ctrlKey && !e.metaKey) {
                        e.preventDefault();
                        this.startEditing();
                    }
                    break;
                case 'escape':
                    e.preventDefault();
                    this.cancelDrawing();
                    break;
                case 'enter':
                    e.preventDefault();
                    this.finishDrawing();
                    break;
                case 'z':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.undo();
                    }
                    break;
                case 'y':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.redo();
                    }
                    break;
                case 'delete':
                    e.preventDefault();
                    this.deleteSelectedFeatures();
                    break;
            }
        });
    }

    setupAccessibility() {
        // Add ARIA labels and announcements
        const controls = document.querySelectorAll('.enhanced-draw-controls button');
        controls.forEach(btn => {
            if (!btn.getAttribute('aria-label')) {
                btn.setAttribute('aria-label', btn.title || btn.textContent.trim());
            }
        });

        // Create live region for screen reader announcements
        const liveRegion = document.createElement('div');
        liveRegion.setAttribute('aria-live', 'polite');
        liveRegion.setAttribute('aria-atomic', 'true');
        liveRegion.className = 'sr-only';
        liveRegion.id = 'drawing-announcements';
        document.body.appendChild(liveRegion);
        this.liveRegion = liveRegion;

        // Add keyboard navigation for control panel
        this.setupKeyboardNavigation();
    }

    setupKeyboardNavigation() {
        const controlsContainer = document.querySelector('.enhanced-draw-controls');
        if (!controlsContainer) return;

        let focusableElements = controlsContainer.querySelectorAll('button, input[type="checkbox"]');
        let currentIndex = 0;

        controlsContainer.addEventListener('keydown', (e) => {
            switch(e.key) {
                case 'Tab':
                    // Let browser handle tab navigation
                    break;
                case 'ArrowRight':
                case 'ArrowDown':
                    e.preventDefault();
                    currentIndex = (currentIndex + 1) % focusableElements.length;
                    focusableElements[currentIndex].focus();
                    break;
                case 'ArrowLeft':
                case 'ArrowUp':
                    e.preventDefault();
                    currentIndex = (currentIndex - 1 + focusableElements.length) % focusableElements.length;
                    focusableElements[currentIndex].focus();
                    break;
            }
        });
    }

    setupMobileSupport() {
        if (!this.isMobile && !this.isTouch) return;

        // Add mobile-specific CSS
        const mobileStyles = document.createElement('style');
        mobileStyles.textContent = `
            .enhanced-draw-controls {
                position: fixed !important;
                bottom: 20px !important;
                top: auto !important;
                left: 50% !important;
                right: auto !important;
                transform: translateX(-50%) !important;
                width: 90% !important;
                max-width: 320px !important;
                z-index: 1000 !important;
            }

            .coordinate-display, .area-display {
                font-size: 10px !important;
                padding: 4px 8px !important;
            }

            .btn-group .btn {
                font-size: 12px !important;
                padding: 6px 8px !important;
            }

            .drawing-tooltip {
                pointer-events: none !important;
            }

            @media (max-width: 768px) {
                .enhanced-draw-controls {
                    width: 95% !important;
                }

                .btn span.d-none.d-md-inline {
                    display: none !important;
                }
            }
        `;
        document.head.appendChild(mobileStyles);

        // Add touch-specific event handlers
        this.addTouchHandlers();
    }

    addTouchHandlers() {
        let touchStartPoint = null;
        let touchStartTime = null;

        const mapContainer = document.querySelector(this.options.mapContainer);

        mapContainer.addEventListener('touchstart', (e) => {
            if (this.isDrawing) {
                const touch = e.touches[0];
                touchStartPoint = { x: touch.clientX, y: touch.clientY };
                touchStartTime = Date.now();
            }
        });

        mapContainer.addEventListener('touchend', (e) => {
            if (this.isDrawing && touchStartPoint && touchStartTime) {
                const touchEndTime = Date.now();
                const touchDuration = touchEndTime - touchStartTime;

                // If it's a quick tap (less than 200ms), treat as click
                if (touchDuration < 200) {
                    const touch = e.changedTouches[0];
                    const rect = mapContainer.getBoundingClientRect();
                    const x = touch.clientX - rect.left;
                    const y = touch.clientY - rect.top;

                    // Convert to map coordinates and add point
                    const mapCoords = this.map.unproject([x, y]);
                    this.addPoint(mapCoords.lng, mapCoords.lat);
                }

                touchStartPoint = null;
                touchStartTime = null;
            }
        });
    }

    startDrawing() {
        if (this.isDrawing) return;

        this.isDrawing = true;
        this.isEditing = false;
        this.currentPoints = [];

        if (this.drawControl) {
            this.drawControl.changeMode('draw_polygon');
        }

        this.updateButtonStates();
        this.showStatus('Drawing mode: Click to add points');
        this.showTooltip('Click to add point');
        this.announceToScreenReader('Drawing mode activated. Click on the map to add polygon points.');

        // Update the original draw mode toggle if it exists
        if (window.toggleDrawMode) {
            const isCurrentlyDrawMode = window.isDrawMode;
            if (!isCurrentlyDrawMode) {
                window.toggleDrawMode();
            }
        }
    }

    startEditing() {
        if (this.isEditing) return;

        this.isEditing = true;
        this.isDrawing = false;

        if (this.drawControl) {
            this.drawControl.changeMode('simple_select');
        }

        this.updateButtonStates();
        this.showStatus('Edit mode: Click polygons to edit');
        this.announceToScreenReader('Edit mode activated. Click on polygons to edit them.');

        // Exit original draw mode if active
        if (window.isDrawMode) {
            window.toggleDrawMode();
        }
    }

    cancelDrawing() {
        if (!this.isDrawing) return;

        this.isDrawing = false;
        this.currentPoints = [];

        if (this.drawControl) {
            this.drawControl.changeMode('simple_select');
            this.drawControl.deleteAll();
        }

        this.updateButtonStates();
        this.hideStatus();
        this.hideTooltip();
        this.announceToScreenReader('Drawing cancelled.');

        // Exit original draw mode
        if (window.isDrawMode) {
            window.toggleDrawMode();
        }
    }

    finishDrawing() {
        if (!this.isDrawing || this.currentPoints.length < this.options.minVertices) {
            this.showStatus(`Need at least ${this.options.minVertices} points to create a polygon`);
            return;
        }

        this.isDrawing = false;

        if (this.drawControl) {
            this.drawControl.changeMode('simple_select');
        }

        this.updateButtonStates();
        this.hideStatus();
        this.hideTooltip();
        this.announceToScreenReader('Polygon completed successfully.');

        // Trigger the original polygon handling
        setTimeout(() => {
            this.triggerPolygonCompletion();
        }, 100);
    }

    addPoint(lng, lat) {
        if (!this.isDrawing) return;

        // Apply snap to grid if enabled
        if (this.options.enableSnapToGrid) {
            lng = Math.round(lng / this.options.gridSize) * this.options.gridSize;
            lat = Math.round(lat / this.options.gridSize) * this.options.gridSize;
        }

        this.currentPoints.push([lng, lat]);

        // Show temporary marker
        this.showTempMarker(lng, lat);

        // Update displays
        this.updateCoordinateDisplay(lng, lat);
        this.updateAreaDisplay();

        // Show status
        this.showStatus(`Added point ${this.currentPoints.length}. ${this.currentPoints.length >= this.options.minVertices ? 'Press Enter to finish.' : 'Add more points.'}`);

        // Check for maximum vertices
        if (this.currentPoints.length >= this.options.maxVertices) {
            this.finishDrawing();
        }
    }

    showTempMarker(lng, lat) {
        if (this.tempMarker) {
            this.tempMarker.remove();
        }

        const el = document.createElement('div');
        el.className = 'temp-point-marker';
        el.style.cssText = `
            width: 10px;
            height: 10px;
            background: #ff4444;
            border: 2px solid white;
            border-radius: 50%;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        `;

        this.tempMarker = new mapboxgl.Marker({ element: el })
            .setLngLat([lng, lat])
            .addTo(this.map);
    }

    handleMouseMove(e) {
        if (!this.options.showCoordinateDisplay) return;

        const lng = e.lngLat.lng;
        const lat = e.lngLat.lat;

        this.updateCoordinateDisplay(lng, lat);

        if (this.isDrawing) {
            this.updateTooltipPosition(e.originalEvent);
        }
    }

    handleMapClick(e) {
        if (!this.isDrawing) return;

        this.addPoint(e.lngLat.lng, e.lngLat.lat);
    }

    handleTouchStart(e) {
        // Touch events are handled in setupMobileSupport
    }

    handleTouchMove(e) {
        // Handle touch move for drawing preview
    }

    handleTouchEnd(e) {
        // Touch events are handled in setupMobileSupport
    }

    handleDrawCreate(e) {
        const features = e.features;
        if (features.length > 0) {
            const polygon = features[0];
            this.addToHistory('create', polygon);
            this.announceToScreenReader('Polygon created successfully.');
        }
    }

    handleDrawUpdate(e) {
        const features = e.features;
        if (features.length > 0) {
            const polygon = features[0];
            this.addToHistory('update', polygon);
            this.updateAreaDisplay();
        }
    }

    handleDrawDelete(e) {
        const features = e.features;
        if (features.length > 0) {
            this.addToHistory('delete', e.features[0]);
            this.announceToScreenReader('Polygon deleted.');
        }
    }

    deletePolygons() {
        if (this.drawControl) {
            const allFeatures = this.drawControl.getAll();
            if (allFeatures.features.length > 0) {
                if (confirm(`Delete ${allFeatures.features.length} polygon(s)?`)) {
                    this.addToHistory('delete_all', allFeatures);
                    this.drawControl.deleteAll();
                    this.announceToScreenReader('All polygons deleted.');
                }
            } else {
                this.showStatus('No polygons to delete');
            }
        }
    }

    deleteSelectedFeatures() {
        if (this.drawControl) {
            const selectedFeatures = this.drawControl.getSelected();
            if (selectedFeatures.features.length > 0) {
                this.drawControl.delete(selectedFeatures.features.map(f => f.id));
            }
        }
    }

    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            this.restoreFromHistory();
            this.updateUndoRedoButtons();
        }
    }

    redo() {
        if (this.historyIndex < this.drawingHistory.length - 1) {
            this.historyIndex++;
            this.restoreFromHistory();
            this.updateUndoRedoButtons();
        }
    }

    addToHistory(action, data) {
        // Remove any history after current index
        this.drawingHistory = this.drawingHistory.slice(0, this.historyIndex + 1);

        // Add new action
        this.drawingHistory.push({
            action: action,
            data: data,
            timestamp: Date.now()
        });

        this.historyIndex = this.drawingHistory.length - 1;
        this.updateUndoRedoButtons();
    }

    restoreFromHistory() {
        const historyItem = this.drawingHistory[this.historyIndex];

        // Clear current drawings
        if (this.drawControl) {
            this.drawControl.deleteAll();
        }

        // Restore based on action
        switch (historyItem.action) {
            case 'create':
            case 'update':
                if (this.drawControl && historyItem.data) {
                    this.drawControl.add(historyItem.data);
                }
                break;
            case 'delete':
            case 'delete_all':
                // Don't restore deleted items
                break;
        }

        this.updateAreaDisplay();
    }

    clearAll() {
        if (this.drawControl) {
            const allFeatures = this.drawControl.getAll();
            if (allFeatures.features.length > 0) {
                if (confirm('Clear all drawings? This cannot be undone.')) {
                    this.addToHistory('clear_all', allFeatures);
                    this.drawControl.deleteAll();
                    this.currentPoints = [];
                    this.drawingHistory = [];
                    this.historyIndex = -1;
                    this.updateUndoRedoButtons();
                    this.hideAreaDisplay();
                    this.announceToScreenReader('All drawings cleared.');
                }
            }
        }
    }

    updateButtonStates() {
        const drawBtn = document.getElementById('draw-polygon-btn');
        const editBtn = document.getElementById('edit-polygon-btn');
        const deleteBtn = document.getElementById('delete-polygon-btn');

        if (drawBtn) {
            if (this.isDrawing) {
                drawBtn.classList.remove('btn-outline-primary');
                drawBtn.classList.add('btn-primary');
            } else {
                drawBtn.classList.remove('btn-primary');
                drawBtn.classList.add('btn-outline-primary');
            }
        }

        if (editBtn) {
            if (this.isEditing) {
                editBtn.classList.remove('btn-outline-warning');
                editBtn.classList.add('btn-warning');
            } else {
                editBtn.classList.remove('btn-warning');
                editBtn.classList.add('btn-outline-warning');
            }
        }
    }

    updateUndoRedoButtons() {
        const undoBtn = document.getElementById('undo-btn');
        const redoBtn = document.getElementById('redo-btn');

        if (undoBtn) {
            undoBtn.disabled = this.historyIndex <= 0;
        }

        if (redoBtn) {
            redoBtn.disabled = this.historyIndex >= this.drawingHistory.length - 1;
        }
    }

    updateCoordinateDisplay(lng, lat) {
        if (!this.options.showCoordinateDisplay || !this.coordinateDisplay) return;

        const coordText = document.getElementById('coord-text');
        if (coordText) {
            coordText.textContent = `Lat: ${lat.toFixed(6)}, Lng: ${lng.toFixed(6)}`;
        }

        this.coordinateDisplay.querySelector('.coordinate-info').style.display = 'block';
    }

    updateAreaDisplay() {
        if (!this.options.showAreaCalculation || !this.areaDisplay) return;

        let area = 0;

        // Calculate area from current points if drawing
        if (this.currentPoints.length >= 3) {
            area = this.calculatePolygonArea(this.currentPoints);
        } else if (this.drawControl) {
            // Calculate area from drawn polygons
            const allFeatures = this.drawControl.getAll();
            allFeatures.features.forEach(feature => {
                if (feature.geometry.type === 'Polygon') {
                    area += this.calculatePolygonArea(feature.geometry.coordinates[0]);
                }
            });
        }

        const areaText = document.getElementById('area-text');
        if (areaText) {
            // Convert to approximate square kilometers (rough conversion)
            const areaKm2 = this.degreesToKm2(area);
            areaText.textContent = `Area: ${areaKm2.toFixed(3)} km²`;
        }

        if (area > 0) {
            this.areaDisplay.querySelector('.area-info').style.display = 'block';
        } else {
            this.hideAreaDisplay();
        }
    }

    hideAreaDisplay() {
        if (this.areaDisplay) {
            this.areaDisplay.querySelector('.area-info').style.display = 'none';
        }
    }

    updateDisplayVisibility() {
        const coordInfo = this.coordinateDisplay?.querySelector('.coordinate-info');
        const areaInfo = this.areaDisplay?.querySelector('.area-info');

        if (coordInfo) {
            coordInfo.style.display = this.options.showCoordinateDisplay ? 'block' : 'none';
        }

        if (areaInfo) {
            areaInfo.style.display = this.options.showAreaCalculation ? 'block' : 'none';
        }
    }

    updateControlVisibility() {
        // Hide controls on very small screens
        if (window.innerWidth < 480) {
            const controls = document.querySelector('.enhanced-draw-controls');
            if (controls) {
                controls.style.transform = 'translateX(-50%) scale(0.9)';
            }
        }
    }

    showStatus(message) {
        if (!this.statusDisplay) return;

        const statusText = document.getElementById('status-text');
        if (statusText) {
            statusText.textContent = message;
        }

        this.statusDisplay.querySelector('.status-info').style.display = 'block';

        // Auto-hide after 3 seconds
        setTimeout(() => {
            this.hideStatus();
        }, 3000);
    }

    hideStatus() {
        if (this.statusDisplay) {
            this.statusDisplay.querySelector('.status-info').style.display = 'none';
        }
    }

    showTooltip(message) {
        if (!this.drawingTooltip) return;

        const tooltipText = document.getElementById('tooltip-text');
        if (tooltipText) {
            tooltipText.textContent = message;
        }

        this.drawingTooltip.querySelector('.tooltip-content').style.display = 'block';
    }

    hideTooltip() {
        if (this.drawingTooltip) {
            this.drawingTooltip.querySelector('.tooltip-content').style.display = 'none';
        }
    }

    updateTooltipPosition(event) {
        if (!this.drawingTooltip) return;

        const tooltip = this.drawingTooltip.querySelector('.tooltip-content');
        tooltip.style.left = event.clientX + 10 + 'px';
        tooltip.style.top = event.clientY - 30 + 'px';
    }

    announceToScreenReader(message) {
        if (this.liveRegion) {
            this.liveRegion.textContent = message;
        }
    }

    calculatePolygonArea(coords) {
        // Shoelace formula for polygon area
        let area = 0;
        const n = coords.length;

        for (let i = 0; i < n - 1; i++) {
            area += coords[i][0] * coords[i + 1][1];
            area -= coords[i + 1][0] * coords[i][1];
        }

        return Math.abs(area / 2);
    }

    degreesToKm2(areaDegrees) {
        // Very rough conversion - assumes near equator
        // For better accuracy, use proper geodesic calculations
        const km2PerDegree = 111.32 * 111.32; // Approximate
        return areaDegrees * km2PerDegree;
    }

    triggerPolygonCompletion() {
        // Integrate with the existing polygon handling system
        if (window.polygonDrawHandler && this.currentPoints.length >= 3) {
            const polygon = {
                type: 'Feature',
                geometry: {
                    type: 'Polygon',
                    coordinates: [this.currentPoints]
                }
            };

            const validation = window.polygonDrawHandler.validatePolygon(polygon);
            if (validation.valid) {
                window.polygonDrawHandler.processValidPolygon(polygon);
            } else {
                this.showStatus('Invalid polygon: ' + (validation.error || 'Unknown error'));
            }
        }
    }
}

// Auto-initialize when DOM is ready and map is available
document.addEventListener('DOMContentLoaded', () => {
    // Wait a bit for the map to initialize
    setTimeout(() => {
        if (window.multiHazardMap && window.draw) {
            window.enhancedPolygonDrawer = new EnhancedPolygonDrawer({
                enableKeyboardShortcuts: true,
                enableUndoRedo: true,
                showCoordinateDisplay: true,
                showAreaCalculation: true,
                mobileOptimized: true
            });
        } else {
            console.warn('Enhanced Polygon Drawer: Map not available during initialization');
        }
    }, 1000);
});

// Also initialize if the DOM is already loaded
if (document.readyState !== 'loading') {
    setTimeout(() => {
        if (window.multiHazardMap && window.draw && !window.enhancedPolygonDrawer) {
            window.enhancedPolygonDrawer = new EnhancedPolygonDrawer();
        }
    }, 1000);
}