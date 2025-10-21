/**
 * Mobile-Enhanced Polygon Drawing System
 * Optimizes polygon drawing for mobile devices with touch controls
 */

class MobilePolygonDrawer {
    constructor(options = {}) {
        this.options = {
            enableTouchGestures: true,
            touchThreshold: 10, // Minimum touch movement to register as gesture
            longPressThreshold: 500, // Long press duration in milliseconds
            doubleTapThreshold: 300, // Double tap time window
            enableHapticFeedback: true,
            enableTouchGuidance: true,
            zoomOnDraw: true,
            autoCenterOnTouch: true,
            ...options
        };

        // Touch state tracking
        this.touchState = {
            isDrawing: false,
            isTouching: false,
            touchStartTime: 0,
            lastTapTime: 0,
            touchStartPoint: null,
            touchCurrentPoint: null,
            touchPoints: [],
            gestureType: null,
            longPressTimer: null
        };

        // Mobile detection
        this.isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        this.isTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        this.hasHapticFeedback = 'vibrate' in navigator;

        this.init();
    }

    init() {
        if (!this.isMobile && !this.isTouch) {
            console.log('MobilePolygonDrawer: Not a mobile/touch device, skipping initialization');
            return;
        }

        console.log('MobilePolygonDrawer: Initializing for mobile/touch device');
        this.setupMobileUI();
        this.setupTouchHandlers();
        this.setupMobileOptimizations();
        this.setupHapticFeedback();
    }

    setupMobileUI() {
        // Add mobile-specific CSS
        const mobileStyles = document.createElement('style');
        mobileStyles.textContent = `
            .mobile-drawing-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                z-index: 999;
                pointer-events: none;
                background: transparent;
            }

            .mobile-drawing-overlay.active {
                pointer-events: all;
            }

            .touch-guidance {
                position: fixed;
                bottom: 100px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 15px 20px;
                border-radius: 25px;
                font-size: 14px;
                text-align: center;
                z-index: 1000;
                max-width: 280px;
                opacity: 0;
                transition: opacity 0.3s ease;
            }

            .touch-guidance.visible {
                opacity: 1;
            }

            .touch-point {
                position: absolute;
                width: 20px;
                height: 20px;
                border: 3px solid #007bff;
                border-radius: 50%;
                background: rgba(0, 123, 255, 0.3);
                transform: translate(-50%, -50%);
                z-index: 1001;
                pointer-events: none;
                animation: touchPulse 1.5s infinite;
            }

            @keyframes touchPulse {
                0% {
                    transform: translate(-50%, -50%) scale(1);
                    opacity: 1;
                }
                50% {
                    transform: translate(-50%, -50%) scale(1.3);
                    opacity: 0.7;
                }
                100% {
                    transform: translate(-50%, -50%) scale(1);
                    opacity: 1;
                }
            }

            .mobile-toolbar {
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 25px;
                padding: 8px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
                z-index: 1000;
                display: flex;
                gap: 8px;
                border: 1px solid rgba(255, 255, 255, 0.3);
            }

            .mobile-toolbar button {
                width: 50px;
                height: 50px;
                border-radius: 50%;
                border: none;
                background: #007bff;
                color: white;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
                transition: all 0.2s ease;
                box-shadow: 0 2px 8px rgba(0, 123, 255, 0.3);
            }

            .mobile-toolbar button:hover {
                transform: scale(1.1);
                box-shadow: 0 4px 12px rgba(0, 123, 255, 0.5);
            }

            .mobile-toolbar button.active {
                background: #28a745;
                box-shadow: 0 2px 8px rgba(40, 167, 69, 0.3);
            }

            .mobile-toolbar button.danger {
                background: #dc3545;
                box-shadow: 0 2px 8px rgba(220, 53, 69, 0.3);
            }

            .zoom-controls {
                position: fixed;
                right: 20px;
                bottom: 100px;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                padding: 8px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
                z-index: 1000;
                display: flex;
                flex-direction: column;
                gap: 4px;
            }

            .zoom-controls button {
                width: 40px;
                height: 40px;
                border-radius: 8px;
                border: none;
                background: #6c757d;
                color: white;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 16px;
                transition: all 0.2s ease;
            }

            .zoom-controls button:hover {
                background: #5a6268;
            }

            .drawing-preview {
                position: absolute;
                border: 2px dashed #007bff;
                background: rgba(0, 123, 255, 0.1);
                pointer-events: none;
                z-index: 998;
                border-radius: 4px;
            }

            @media (max-width: 480px) {
                .mobile-toolbar button {
                    width: 45px;
                    height: 45px;
                    font-size: 16px;
                }

                .touch-guidance {
                    font-size: 12px;
                    padding: 12px 16px;
                    max-width: 240px;
                }

                .zoom-controls {
                    right: 10px;
                    bottom: 80px;
                }

                .zoom-controls button {
                    width: 35px;
                    height: 35px;
                    font-size: 14px;
                }
            }

            /* Prevent zooming on double tap */
            .prevent-zoom {
                touch-action: manipulation;
            }

            /* Visual feedback for touch areas */
            .touch-area {
                position: absolute;
                border: 2px solid transparent;
                border-radius: 8px;
                transition: border-color 0.2s ease;
            }

            .touch-area.active {
                border-color: #007bff;
                background: rgba(0, 123, 255, 0.1);
            }
        `;
        document.head.appendChild(mobileStyles);

        this.createMobileUI();
    }

    createMobileUI() {
        // Create mobile drawing overlay
        const overlay = document.createElement('div');
        overlay.className = 'mobile-drawing-overlay';
        overlay.id = 'mobile-drawing-overlay';
        document.body.appendChild(overlay);

        // Create touch guidance element
        const guidance = document.createElement('div');
        guidance.className = 'touch-guidance';
        guidance.id = 'touch-guidance';
        guidance.innerHTML = '<i class="fas fa-hand-pointer me-2"></i>Tap to start drawing';
        document.body.appendChild(guidance);

        // Create mobile toolbar
        const toolbar = document.createElement('div');
        toolbar.className = 'mobile-toolbar';
        toolbar.innerHTML = `
            <button id="mobile-draw-btn" title="Draw Polygon" aria-label="Draw Polygon">
                <i class="fas fa-draw-polygon"></i>
            </button>
            <button id="mobile-edit-btn" title="Edit" aria-label="Edit">
                <i class="fas fa-edit"></i>
            </button>
            <button id="mobile-undo-btn" title="Undo" aria-label="Undo">
                <i class="fas fa-undo"></i>
            </button>
            <button id="mobile-clear-btn" title="Clear" aria-label="Clear">
                <i class="fas fa-trash"></i>
            </button>
            <button id="mobile-done-btn" title="Done" aria-label="Done Drawing">
                <i class="fas fa-check"></i>
            </button>
        `;
        document.body.appendChild(toolbar);

        // Create zoom controls
        const zoomControls = document.createElement('div');
        zoomControls.className = 'zoom-controls';
        zoomControls.innerHTML = `
            <button id="mobile-zoom-in-btn" title="Zoom In" aria-label="Zoom In">
                <i class="fas fa-plus"></i>
            </button>
            <button id="mobile-zoom-out-btn" title="Zoom Out" aria-label="Zoom Out">
                <i class="fas fa-minus"></i>
            </button>
        `;
        document.body.appendChild(zoomControls);

        // Store references
        this.mobileUI = {
            overlay: overlay,
            guidance: guidance,
            toolbar: toolbar,
            zoomControls: zoomControls
        };

        // Initially hide mobile UI
        this.hideMobileUI();
    }

    setupTouchHandlers() {
        const overlay = this.mobileUI.overlay;
        const mapContainer = document.querySelector('#climate-hazard-map');

        // Touch event handlers
        overlay.addEventListener('touchstart', (e) => this.handleTouchStart(e), { passive: false });
        overlay.addEventListener('touchmove', (e) => this.handleTouchMove(e), { passive: false });
        overlay.addEventListener('touchend', (e) => this.handleTouchEnd(e), { passive: false });
        overlay.addEventListener('touchcancel', (e) => this.handleTouchCancel(e), { passive: false });

        // Map container touch events (when not drawing)
        if (mapContainer) {
            mapContainer.addEventListener('touchstart', (e) => this.handleMapTouchStart(e), { passive: false });
        }

        // Prevent default touch behaviors
        document.addEventListener('touchmove', (e) => {
            if (this.touchState.isDrawing) {
                e.preventDefault();
            }
        }, { passive: false });

        // Prevent double-tap zoom
        document.addEventListener('touchend', (e) => {
            const currentTime = Date.now();
            if (currentTime - this.touchState.lastTapTime < this.options.doubleTapThreshold) {
                e.preventDefault();
            }
            this.touchState.lastTapTime = currentTime;
        }, { passive: false });
    }

    setupMobileOptimizations() {
        // Add mobile-specific event listeners
        document.getElementById('mobile-draw-btn')?.addEventListener('click', () => this.startMobileDrawing());
        document.getElementById('mobile-edit-btn')?.addEventListener('click', () => this.startMobileEditing());
        document.getElementById('mobile-undo-btn')?.addEventListener('click', () => this.undo());
        document.getElementById('mobile-clear-btn')?.addEventListener('click', () => this.clearAll());
        document.getElementById('mobile-done-btn')?.addEventListener('click', () => this.finishDrawing());

        document.getElementById('mobile-zoom-in-btn')?.addEventListener('click', () => this.zoomIn());
        document.getElementById('mobile-zoom-out-btn')?.addEventListener('click', () => this.zoomOut());

        // Handle device orientation changes
        window.addEventListener('orientationchange', () => this.handleOrientationChange());
        window.addEventListener('resize', () => this.handleResize());

        // Optimize for mobile performance
        this.optimizeMobilePerformance();
    }

    setupHapticFeedback() {
        if (!this.options.enableHapticFeedback || !this.hasHapticFeedback) {
            return;
        }

        // Add haptic feedback methods
        this.hapticFeedback = {
            light: () => navigator.vibrate(10),
            medium: () => navigator.vibrate(25),
            heavy: () => navigator.vibrate(50),
            success: () => navigator.vibrate([10, 50, 10]),
            error: () => navigator.vibrate([50, 30, 50, 30, 50]),
            doubleTap: () => navigator.vibrate(15)
        };
    }

    handleTouchStart(e) {
        e.preventDefault();

        const touch = e.touches[0];
        this.touchState.isTouching = true;
        this.touchState.touchStartTime = Date.now();
        this.touchState.touchStartPoint = { x: touch.clientX, y: touch.clientY };
        this.touchState.touchCurrentPoint = { x: touch.clientX, y: touch.clientY };

        // Start long press timer
        this.touchState.longPressTimer = setTimeout(() => {
            this.handleLongPress(touch);
        }, this.options.longPressThreshold);

        // Show touch indicator
        this.showTouchIndicator(touch.clientX, touch.clientY);

        // Haptic feedback
        if (this.hapticFeedback) {
            this.hapticFeedback.light();
        }
    }

    handleTouchMove(e) {
        e.preventDefault();

        if (!this.touchState.isTouching) return;

        const touch = e.touches[0];
        this.touchState.touchCurrentPoint = { x: touch.clientX, y: touch.clientY };

        // Check if movement exceeds threshold
        const distance = this.calculateDistance(
            this.touchState.touchStartPoint,
            this.touchState.touchCurrentPoint
        );

        if (distance > this.options.touchThreshold) {
            // Cancel long press
            clearTimeout(this.touchState.longPressTimer);

            // Determine gesture type
            if (!this.touchState.gestureType) {
                this.touchState.gestureType = this.detectGestureType(e);
            }

            // Handle gesture
            this.handleGesture(e);
        }

        // Update touch indicator position
        this.updateTouchIndicator(touch.clientX, touch.clientY);
    }

    handleTouchEnd(e) {
        e.preventDefault();

        clearTimeout(this.touchState.longPressTimer);

        if (this.touchState.isTouching) {
            const touchDuration = Date.now() - this.touchState.touchStartTime;

            // Handle as tap if short duration and small movement
            if (touchDuration < this.options.longPressThreshold) {
                const distance = this.calculateDistance(
                    this.touchState.touchStartPoint,
                    this.touchState.touchCurrentPoint
                );

                if (distance <= this.options.touchThreshold) {
                    this.handleTap(this.touchState.touchStartPoint);
                }
            }
        }

        // Reset touch state
        this.resetTouchState();
        this.hideTouchIndicator();
    }

    handleTouchCancel(e) {
        e.preventDefault();
        clearTimeout(this.touchState.longPressTimer);
        this.resetTouchState();
        this.hideTouchIndicator();
    }

    handleMapTouchStart(e) {
        // Handle touch events on the map when not in drawing mode
        if (!this.touchState.isDrawing) {
            // Allow normal map interactions
            return;
        }
    }

    handleTap(point) {
        if (!this.touchState.isDrawing) return;

        // Convert screen coordinates to map coordinates
        const mapCoords = this.screenToMapCoordinates(point.x, point.y);
        if (mapCoords && window.enhancedPolygonDrawer) {
            window.enhancedPolygonDrawer.addPoint(mapCoords.lng, mapCoords.lat);

            // Haptic feedback
            if (this.hapticFeedback) {
                this.hapticFeedback.doubleTap();
            }

            // Show guidance
            this.updateTouchGuidance(`Point added. ${window.enhancedPolygonDrawer.currentPoints.length >= 3 ? 'Tap Done when finished.' : 'Add more points.'}`);
        }
    }

    handleLongPress(touch) {
        // Handle long press actions
        this.showTouchMenu(touch.clientX, touch.clientY);

        // Haptic feedback
        if (this.hapticFeedback) {
            this.hapticFeedback.heavy();
        }
    }

    handleGesture(e) {
        if (this.touchState.gestureType === 'pinch') {
            this.handlePinchGesture(e);
        } else if (this.touchState.gestureType === 'pan') {
            this.handlePanGesture(e);
        }
    }

    detectGestureType(e) {
        if (e.touches.length === 2) {
            return 'pinch';
        } else if (e.touches.length === 1) {
            return 'pan';
        }
        return null;
    }

    handlePinchGesture(e) {
        if (e.touches.length !== 2) return;

        // Calculate pinch distance and center
        const touch1 = e.touches[0];
        const touch2 = e.touches[1];
        const distance = this.calculateDistance(
            { x: touch1.clientX, y: touch1.clientY },
            { x: touch2.clientX, y: touch2.clientY }
        );

        // Update map zoom based on pinch
        if (window.multiHazardMap) {
            const currentZoom = window.multiHazardMap.getZoom();
            const newZoom = currentZoom + (distance > 100 ? 0.5 : -0.5);
            window.multiHazardMap.setZoom(Math.max(1, Math.min(20, newZoom)));
        }
    }

    handlePanGesture(e) {
        // Handle pan gestures for map navigation when not drawing
        if (!this.touchState.isDrawing && window.multiHazardMap) {
            // Allow map panning
            return;
        }
    }

    startMobileDrawing() {
        if (window.enhancedPolygonDrawer) {
            window.enhancedPolygonDrawer.startDrawing();
            this.touchState.isDrawing = true;
            this.showMobileUI();
            this.updateTouchGuidance('Tap on the map to add points');

            // Haptic feedback
            if (this.hapticFeedback) {
                this.hapticFeedback.success();
            }

            // Update button states
            document.getElementById('mobile-draw-btn')?.classList.add('active');
            document.getElementById('mobile-edit-btn')?.classList.remove('active');
        }
    }

    startMobileEditing() {
        if (window.enhancedPolygonDrawer) {
            window.enhancedPolygonDrawer.startEditing();
            this.touchState.isDrawing = false;
            this.showMobileUI();
            this.updateTouchGuidance('Tap on polygons to edit');

            // Haptic feedback
            if (this.hapticFeedback) {
                this.hapticFeedback.medium();
            }

            // Update button states
            document.getElementById('mobile-edit-btn')?.classList.add('active');
            document.getElementById('mobile-draw-btn')?.classList.remove('active');
        }
    }

    finishDrawing() {
        if (window.enhancedPolygonDrawer) {
            window.enhancedPolygonDrawer.finishDrawing();
            this.touchState.isDrawing = false;
            this.hideMobileUI();

            // Haptic feedback
            if (this.hapticFeedback) {
                this.hapticFeedback.success();
            }
        }
    }

    undo() {
        if (window.enhancedPolygonDrawer) {
            window.enhancedPolygonDrawer.undo();

            // Haptic feedback
            if (this.hapticFeedback) {
                this.hapticFeedback.light();
            }
        }
    }

    clearAll() {
        if (window.enhancedPolygonDrawer) {
            window.enhancedPolygonDrawer.clearAll();
            this.touchState.isDrawing = false;
            this.hideMobileUI();

            // Haptic feedback
            if (this.hapticFeedback) {
                this.hapticFeedback.error();
            }
        }
    }

    zoomIn() {
        if (window.multiHazardMap) {
            window.multiHazardMap.zoomIn();
            if (this.hapticFeedback) this.hapticFeedback.light();
        }
    }

    zoomOut() {
        if (window.multiHazardMap) {
            window.multiHazardMap.zoomOut();
            if (this.hapticFeedback) this.hapticFeedback.light();
        }
    }

    showMobileUI() {
        this.mobileUI.overlay.classList.add('active');
        this.mobileUI.toolbar.style.display = 'flex';
        this.mobileUI.zoomControls.style.display = 'flex';

        if (this.options.enableTouchGuidance) {
            this.mobileUI.guidance.classList.add('visible');
        }
    }

    hideMobileUI() {
        this.mobileUI.overlay.classList.remove('active');
        this.mobileUI.toolbar.style.display = 'none';
        this.mobileUI.zoomControls.style.display = 'none';
        this.mobileUI.guidance.classList.remove('visible');
    }

    showTouchIndicator(x, y) {
        this.hideTouchIndicator(); // Remove existing indicator

        const indicator = document.createElement('div');
        indicator.className = 'touch-point';
        indicator.id = 'touch-indicator';
        indicator.style.left = x + 'px';
        indicator.style.top = y + 'px';
        document.body.appendChild(indicator);
    }

    updateTouchIndicator(x, y) {
        const indicator = document.getElementById('touch-indicator');
        if (indicator) {
            indicator.style.left = x + 'px';
            indicator.style.top = y + 'px';
        }
    }

    hideTouchIndicator() {
        const indicator = document.getElementById('touch-indicator');
        if (indicator) {
            indicator.remove();
        }
    }

    showTouchMenu(x, y) {
        // Create context menu for touch
        const menu = document.createElement('div');
        menu.className = 'touch-context-menu';
        menu.style.cssText = `
            position: fixed;
            left: ${x}px;
            top: ${y}px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            padding: 8px 0;
            z-index: 1002;
            min-width: 150px;
        `;

        menu.innerHTML = `
            <button class="touch-menu-item" onclick="window.mobilePolygonDrawer.cancelDrawing()">
                <i class="fas fa-times me-2"></i>Cancel
            </button>
            <button class="touch-menu-item" onclick="window.mobilePolygonDrawer.undo()">
                <i class="fas fa-undo me-2"></i>Undo
            </button>
            <button class="touch-menu-item" onclick="window.mobilePolygonDrawer.finishDrawing()">
                <i class="fas fa-check me-2"></i>Done
            </button>
        `;

        // Add styles for menu items
        const style = document.createElement('style');
        style.textContent = `
            .touch-menu-item {
                width: 100%;
                padding: 12px 16px;
                border: none;
                background: none;
                text-align: left;
                cursor: pointer;
                font-size: 14px;
                color: #333;
                transition: background-color 0.2s ease;
            }
            .touch-menu-item:hover {
                background-color: #f8f9fa;
            }
        `;
        document.head.appendChild(style);

        document.body.appendChild(menu);

        // Auto-hide menu after 3 seconds
        setTimeout(() => {
            if (menu.parentNode) {
                menu.remove();
            }
        }, 3000);
    }

    updateTouchGuidance(message) {
        if (this.mobileUI.guidance) {
            this.mobileUI.guidance.innerHTML = `<i class="fas fa-hand-pointer me-2"></i>${message}`;
        }
    }

    screenToMapCoordinates(screenX, screenY) {
        if (!window.multiHazardMap) return null;

        const mapContainer = document.querySelector('#climate-hazard-map');
        if (!mapContainer) return null;

        const rect = mapContainer.getBoundingClientRect();
        const x = screenX - rect.left;
        const y = screenY - rect.top;

        return window.multiHazardMap.unproject([x, y]);
    }

    calculateDistance(point1, point2) {
        const dx = point2.x - point1.x;
        const dy = point2.y - point1.y;
        return Math.sqrt(dx * dx + dy * dy);
    }

    resetTouchState() {
        this.touchState.isTouching = false;
        this.touchState.touchStartTime = 0;
        this.touchState.touchStartPoint = null;
        this.touchState.touchCurrentPoint = null;
        this.touchState.gestureType = null;
        clearTimeout(this.touchState.longPressTimer);
    }

    handleOrientationChange() {
        // Adjust UI for new orientation
        setTimeout(() => {
            if (window.multiHazardMap) {
                window.multiHazardMap.resize();
            }
        }, 100);
    }

    handleResize() {
        // Handle window resize
        if (window.multiHazardMap) {
            window.multiHazardMap.resize();
        }
    }

    optimizeMobilePerformance() {
        // Disable unnecessary animations on low-end devices
        const isLowEndDevice = navigator.hardwareConcurrency <= 2 || navigator.deviceMemory <= 2;

        if (isLowEndDevice) {
            document.body.classList.add('low-end-device');

            const performanceStyles = document.createElement('style');
            performanceStyles.textContent = `
                .low-end-device * {
                    animation-duration: 0.1s !important;
                    transition-duration: 0.1s !important;
                }
                .low-end-device .touch-point {
                    animation: none !important;
                }
            `;
            document.head.appendChild(performanceStyles);
        }

        // Optimize scrolling performance
        document.body.style.touchAction = 'pan-y';

        // Preload critical resources
        this.preloadCriticalResources();
    }

    preloadCriticalResources() {
        // Preload commonly used icons
        const iconLinks = [
            'fas fa-draw-polygon',
            'fas fa-edit',
            'fas fa-undo',
            'fas fa-trash',
            'fas fa-check',
            'fas fa-plus',
            'fas fa-minus'
        ];

        // This would ideally be handled by Font Awesome's preload system
        // For now, we'll ensure the font is loaded
        const link = document.createElement('link');
        link.rel = 'preload';
        link.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.woff2';
        link.as = 'font';
        link.type = 'font/woff2';
        link.crossOrigin = 'anonymous';
        document.head.appendChild(link);
    }

    cancelDrawing() {
        if (window.enhancedPolygonDrawer) {
            window.enhancedPolygonDrawer.cancelDrawing();
            this.touchState.isDrawing = false;
            this.hideMobileUI();

            // Haptic feedback
            if (this.hapticFeedback) {
                this.hapticFeedback.error();
            }
        }
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
        window.mobilePolygonDrawer = new MobilePolygonDrawer({
            enableTouchGestures: true,
            enableHapticFeedback: true,
            enableTouchGuidance: true,
            zoomOnDraw: true
        });
    }
});