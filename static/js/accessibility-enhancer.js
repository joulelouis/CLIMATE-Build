/**
 * Accessibility Enhancement System for Polygon Drawing
 * Provides comprehensive accessibility features including screen reader support,
 * keyboard navigation, and visual accessibility improvements
 */

class AccessibilityEnhancer {
    constructor(options = {}) {
        this.options = {
            enableScreenReaderSupport: true,
            enableKeyboardNavigation: true,
            enableHighContrastMode: false,
            enableReducedMotion: false,
            enableFocusManagement: true,
            enableAudioCues: false,
            announcementDelay: 100,
            focusTimeout: 300,
            ...options
        };

        // Accessibility state
        this.focusStack = [];
        this.currentFocusElement = null;
        this.announcementQueue = [];
        this.isKeyboardUser = false;
        this.screenReaderActive = false;

        // Detect user preferences
        this.detectAccessibilityPreferences();

        this.init();
    }

    init() {
        console.log('AccessibilityEnhancer: Initializing accessibility features');
        this.setupScreenReaderSupport();
        this.setupKeyboardNavigation();
        this.setupFocusManagement();
        this.setupVisualAccessibility();
        this.setupAudioCues();
        this.setupPreferenceDetection();
        this.createAccessibilityPanel();
    }

    detectAccessibilityPreferences() {
        // Detect reduced motion preference
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            this.options.enableReducedMotion = true;
            document.body.classList.add('reduced-motion');
        }

        // Detect high contrast preference
        if (window.matchMedia('(prefers-contrast: high)').matches) {
            this.options.enableHighContrastMode = true;
            document.body.classList.add('high-contrast');
        }

        // Detect screen reader usage
        this.detectScreenReader();

        // Detect keyboard navigation
        this.detectKeyboardUsage();
    }

    detectScreenReader() {
        // Multiple methods to detect screen readers
        const methods = [
            // Method 1: Check for screen reader specific elements
            () => {
                const srElements = document.querySelectorAll('[aria-live], [role="alert"], [role="status"]');
                return srElements.length > 0;
            },
            // Method 2: Check for common screen reader browsers
            () => {
                const userAgent = navigator.userAgent.toLowerCase();
                return userAgent.includes('nvda') || userAgent.includes('jaws') || userAgent.includes('voiceover');
            },
            // Method 3: Check for touch/no-touch ratio
            () => {
                return !('ontouchstart' in window) && navigator.maxTouchPoints === 0;
            }
        ];

        this.screenReaderActive = methods.some(method => method());

        if (this.screenReaderActive) {
            document.body.classList.add('screen-reader-active');
            console.log('Screen reader detected');
        }
    }

    detectKeyboardUsage() {
        let keyboardTimer;

        document.addEventListener('keydown', (e) => {
            // Only consider Tab, Enter, Space, Arrow keys as keyboard navigation
            if ([9, 13, 32, 37, 38, 39, 40].includes(e.keyCode)) {
                this.isKeyboardUser = true;
                document.body.classList.add('keyboard-user');

                clearTimeout(keyboardTimer);
                keyboardTimer = setTimeout(() => {
                    this.isKeyboardUser = false;
                    document.body.classList.remove('keyboard-user');
                }, 1000);
            }
        });

        // Mouse usage detection
        document.addEventListener('mousedown', () => {
            this.isKeyboardUser = false;
            document.body.classList.remove('keyboard-user');
        });
    }

    setupScreenReaderSupport() {
        if (!this.options.enableScreenReaderSupport) return;

        // Create live regions for announcements
        this.createLiveRegions();

        // Enhance existing drawing controls with ARIA attributes
        this.enhanceDrawingControls();

        // Add screen reader specific instructions
        this.addScreenReaderInstructions();

        // Setup coordinate announcements
        this.setupCoordinateAnnouncements();
    }

    createLiveRegions() {
        // Polite live region for general announcements
        const politeRegion = document.createElement('div');
        politeRegion.setAttribute('aria-live', 'polite');
        politeRegion.setAttribute('aria-atomic', 'true');
        politeRegion.className = 'sr-only';
        politeRegion.id = 'sr-polite-region';
        document.body.appendChild(politeRegion);

        // Assertive live region for important announcements
        const assertiveRegion = document.createElement('div');
        assertiveRegion.setAttribute('aria-live', 'assertive');
        assertiveRegion.setAttribute('aria-atomic', 'true');
        assertiveRegion.className = 'sr-only';
        assertiveRegion.id = 'sr-assertive-region';
        document.body.appendChild(assertiveRegion);

        // Status region for status updates
        const statusRegion = document.createElement('div');
        statusRegion.setAttribute('role', 'status');
        statusRegion.setAttribute('aria-live', 'polite');
        statusRegion.className = 'sr-only';
        statusRegion.id = 'sr-status-region';
        document.body.appendChild(statusRegion);

        this.liveRegions = {
            polite: politeRegion,
            assertive: assertiveRegion,
            status: statusRegion
        };
    }

    enhanceDrawingControls() {
        const controls = [
            { id: 'draw-polygon-btn', label: 'Draw Polygon - Press D to activate drawing mode' },
            { id: 'edit-polygon-btn', label: 'Edit Polygon - Press E to activate editing mode' },
            { id: 'delete-polygon-btn', label: 'Delete Polygon - Press Delete to remove selected polygons' },
            { id: 'undo-btn', label: 'Undo - Press Ctrl+Z to undo last action' },
            { id: 'redo-btn', label: 'Redo - Press Ctrl+Y to redo last action' },
            { id: 'clear-all-btn', label: 'Clear All - Remove all polygons from the map' },
            { id: 'snap-to-grid', label: 'Snap to Grid - Toggle coordinate snapping' },
            { id: 'show-coordinates', label: 'Show Coordinates - Toggle coordinate display' },
            { id: 'show-area', label: 'Show Area - Toggle area calculation display' }
        ];

        controls.forEach(control => {
            const element = document.getElementById(control.id);
            if (element) {
                if (!element.getAttribute('aria-label')) {
                    element.setAttribute('aria-label', control.label);
                }
                element.setAttribute('role', 'button');
                element.setAttribute('tabindex', '0');

                // Add keyboard event handlers
                if (element.tagName !== 'INPUT') {
                    element.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            element.click();
                        }
                    });
                }
            }
        });

        // Enhance the map container
        const mapContainer = document.getElementById('climate-hazard-map');
        if (mapContainer) {
            mapContainer.setAttribute('role', 'application');
            mapContainer.setAttribute('aria-label', 'Interactive map for drawing polygon assets');
            mapContainer.setAttribute('tabindex', '0');
        }
    }

    addScreenReaderInstructions() {
        const instructions = document.createElement('div');
        instructions.className = 'sr-only';
        instructions.setAttribute('role', 'complementary');
        instructions.setAttribute('aria-label', 'Drawing Instructions');
        instructions.innerHTML = `
            <h3>Polygon Drawing Instructions</h3>
            <ul>
                <li>Press D to enter drawing mode</li>
                <li>Press E to enter editing mode</li>
                <li>Press Escape to cancel current operation</li>
                <li>Press Enter to finish drawing polygon</li>
                <li>Press Ctrl+Z to undo last action</li>
                <li>Press Ctrl+Y to redo last action</li>
                <li>Press Delete to remove selected polygons</li>
                <li>Use Tab to navigate between controls</li>
                <li>Use arrow keys for map navigation when focused</li>
            </ul>
            <h3>Map Navigation</h3>
            <ul>
                <li>When map is focused, use arrow keys to pan</li>
                <li>Press Plus or Equals to zoom in</li>
                <li>Press Minus to zoom out</li>
                <li>Press Home to return to initial view</li>
            </ul>
        `;
        document.body.appendChild(instructions);
    }

    setupCoordinateAnnouncements() {
        // Announce coordinates when drawing
        this.announceToScreenReader = (message, priority = 'polite') => {
            if (!this.options.enableScreenReaderSupport) return;

            const region = this.liveRegions[priority] || this.liveRegions.polite;
            if (region) {
                setTimeout(() => {
                    region.textContent = message;

                    // Clear after announcement
                    setTimeout(() => {
                        region.textContent = '';
                    }, 1000);
                }, this.options.announcementDelay);
            }
        };

        // Enhanced coordinate announcement
        this.announceCoordinates = (lng, lat, context = '') => {
            const message = `Coordinates: ${lat.toFixed(6)} latitude, ${lng.toFixed(6)} longitude${context ? ', ' + context : ''}`;
            this.announceToScreenReader(message);
        };

        // Area announcement
        this.announceArea = (area, unit = 'square kilometers') => {
            const message = `Area: ${area.toFixed(3)} ${unit}`;
            this.announceToScreenReader(message);
        };
    }

    setupKeyboardNavigation() {
        if (!this.options.enableKeyboardNavigation) return;

        document.addEventListener('keydown', (e) => {
            // Map navigation when map is focused
            if (document.activeElement === document.getElementById('climate-hazard-map')) {
                this.handleMapKeyboardNavigation(e);
            }

            // Global shortcuts
            this.handleGlobalKeyboardShortcuts(e);
        });

        // Add keyboard navigation to drawing controls
        this.setupControlKeyboardNavigation();
    }

    handleMapKeyboardNavigation(e) {
        if (!window.multiHazardMap) return;

        const step = e.shiftKey ? 10 : 1; // Larger steps with Shift
        let handled = false;

        switch(e.key) {
            case 'ArrowUp':
                e.preventDefault();
                window.multiHazardMap.panBy([0, -step]);
                handled = true;
                break;
            case 'ArrowDown':
                e.preventDefault();
                window.multiHazardMap.panBy([0, step]);
                handled = true;
                break;
            case 'ArrowLeft':
                e.preventDefault();
                window.multiHazardMap.panBy([-step, 0]);
                handled = true;
                break;
            case 'ArrowRight':
                e.preventDefault();
                window.multiHazardMap.panBy([step, 0]);
                handled = true;
                break;
            case '+':
            case '=':
            case 'Add':
                e.preventDefault();
                window.multiHazardMap.zoomIn();
                handled = true;
                break;
            case '-':
            case '_':
            case 'Subtract':
                e.preventDefault();
                window.multiHazardMap.zoomOut();
                handled = true;
                break;
            case 'Home':
                e.preventDefault();
                window.multiHazardMap.flyTo({
                    center: [121.7740, 12.8797],
                    zoom: 4.5,
                    essential: true
                });
                handled = true;
                break;
        }

        if (handled) {
            this.announceToScreenReader(`Map ${e.key} key pressed`);
        }
    }

    handleGlobalKeyboardShortcuts(e) {
        // Avoid conflicts with form inputs
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.contentEditable === 'true') {
            return;
        }

        // Accessibility-specific shortcuts
        switch(e.key) {
            case 'F6':
                e.preventDefault();
                this.toggleAccessibilityPanel();
                break;
            case 'F7':
                e.preventDefault();
                this.toggleHighContrast();
                break;
            case 'F8':
                e.preventDefault();
                this.toggleReducedMotion();
                break;
        }
    }

    setupControlKeyboardNavigation() {
        const controlsContainer = document.querySelector('.enhanced-drawing-controls');
        if (!controlsContainer) return;

        const focusableElements = controlsContainer.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );

        // Add trap focus functionality
        controlsContainer.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                const firstElement = focusableElements[0];
                const lastElement = focusableElements[focusableElements.length - 1];

                if (e.shiftKey) {
                    if (document.activeElement === firstElement) {
                        e.preventDefault();
                        lastElement.focus();
                    }
                } else {
                    if (document.activeElement === lastElement) {
                        e.preventDefault();
                        firstElement.focus();
                    }
                }
            }
        });
    }

    setupFocusManagement() {
        if (!this.options.enableFocusManagement) return;

        // Enhanced focus styles
        const focusStyles = document.createElement('style');
        focusStyles.textContent = `
            .keyboard-user *:focus {
                outline: 3px solid #007bff !important;
                outline-offset: 2px !important;
                border-radius: 4px !important;
            }

            .keyboard-user .btn:focus {
                outline: 3px solid #007bff !important;
                outline-offset: 2px !important;
            }

            .high-contrast *:focus {
                outline: 3px solid #ffffff !important;
                outline-offset: 2px !important;
                background-color: #000000 !important;
                color: #ffffff !important;
            }

            .sr-only:focus {
                position: static !important;
                width: auto !important;
                height: auto !important;
                padding: 10px !important;
                margin: 10px !important;
                background: #ffffff !important;
                border: 2px solid #007bff !important;
                color: #000000 !important;
                clip: auto !important;
                clip-path: none !important;
                overflow: visible !important;
            }

            /* Skip to main content link */
            .skip-link {
                position: absolute;
                top: -40px;
                left: 6px;
                background: #007bff;
                color: white;
                padding: 8px;
                text-decoration: none;
                border-radius: 4px;
                z-index: 10000;
                transition: top 0.3s ease;
            }

            .skip-link:focus {
                top: 6px;
            }

            /* Visible focus indicators */
            .visible-focus {
                position: relative;
            }

            .visible-focus::after {
                content: '';
                position: absolute;
                top: -4px;
                left: -4px;
                right: -4px;
                bottom: -4px;
                border: 2px solid #007bff;
                border-radius: 6px;
                pointer-events: none;
                opacity: 0;
                transition: opacity 0.2s ease;
            }

            .visible-focus:focus::after {
                opacity: 1;
            }
        `;
        document.head.appendChild(focusStyles);

        // Add skip to main content link
        this.addSkipLink();
    }

    addSkipLink() {
        const skipLink = document.createElement('a');
        skipLink.href = '#climate-hazard-map';
        skipLink.className = 'skip-link';
        skipLink.textContent = 'Skip to main map content';
        document.body.insertBefore(skipLink, document.body.firstChild);
    }

    setupVisualAccessibility() {
        // Add accessibility CSS classes
        const accessibilityStyles = document.createElement('style');
        accessibilityStyles.textContent = `
            /* Screen reader only content */
            .sr-only {
                position: absolute;
                width: 1px;
                height: 1px;
                padding: 0;
                margin: -1px;
                overflow: hidden;
                clip: rect(0, 0, 0, 0);
                white-space: nowrap;
                border: 0;
            }

            /* High contrast mode */
            .high-contrast {
                filter: contrast(1.5);
            }

            .high-contrast .enhanced-drawing-controls {
                background: #000000 !important;
                color: #ffffff !important;
                border: 2px solid #ffffff !important;
            }

            .high-contrast .btn {
                background: #000000 !important;
                color: #ffffff !important;
                border: 2px solid #ffffff !important;
            }

            .high-contrast .btn:hover {
                background: #ffffff !important;
                color: #000000 !important;
            }

            /* Reduced motion */
            .reduced-motion *,
            .reduced-motion *::before,
            .reduced-motion *::after {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
                scroll-behavior: auto !important;
            }

            /* Large touch targets for mobile accessibility */
            @media (pointer: coarse) {
                .enhanced-drawing-controls .btn {
                    min-height: 44px;
                    min-width: 44px;
                }

                .enhanced-drawing-controls input[type="checkbox"] {
                    min-width: 44px;
                    min-height: 44px;
                }
            }

            /* Enhanced text sizing */
            .accessibility-text-large {
                font-size: 1.2em !important;
            }

            .accessibility-text-extra-large {
                font-size: 1.4em !important;
            }

            /* Color blind friendly palette */
            .colorblind-friendly {
                --primary-color: #0066cc;
                --success-color: #00aa00;
                --warning-color: #ff8800;
                --danger-color: #cc0000;
            }

            /* Focus visible enhancement */
            .focus-visible {
                outline: 3px solid #007bff;
                outline-offset: 2px;
                border-radius: 4px;
            }

            /* ARIA current indicator */
            [aria-current="page"] {
                font-weight: bold;
                text-decoration: underline;
            }

            /* Landmark regions */
            [role="banner"],
            [role="navigation"],
            [role="main"],
            [role="contentinfo"],
            [role="complementary"] {
                position: relative;
            }

            [role="banner"]::before,
            [role="navigation"]::before,
            [role="main"]::before,
            [role="contentinfo"]::before,
            [role="complementary"]::before {
                content: attr(role);
                position: absolute;
                top: -20px;
                left: -9999px;
                font-size: 0;
            }
        `;
        document.head.appendChild(accessibilityStyles);
    }

    setupAudioCues() {
        if (!this.options.enableAudioCues) return;

        // Create audio context for sound cues
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        } catch (e) {
            console.log('Audio context not available');
            return;
        }

        // Sound cue functions
        this.audioCues = {
            playFocus: () => this.playTone(800, 50),
            playClick: () => this.playTone(1000, 100),
            playSuccess: () => this.playTone(1200, 200),
            playError: () => this.playTone(400, 300),
            playNotification: () => this.playTone(600, 150)
        };

        // Add sound cues to interactive elements
        document.addEventListener('focusin', (e) => {
            if (this.isKeyboardUser) {
                this.audioCues.playFocus();
            }
        });

        document.addEventListener('click', () => {
            this.audioCues.playClick();
        });
    }

    playTone(frequency, duration) {
        if (!this.audioContext) return;

        try {
            const oscillator = this.audioContext.createOscillator();
            const gainNode = this.audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(this.audioContext.destination);

            oscillator.frequency.value = frequency;
            oscillator.type = 'sine';

            gainNode.gain.setValueAtTime(0.3, this.audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + duration / 1000);

            oscillator.start(this.audioContext.currentTime);
            oscillator.stop(this.audioContext.currentTime + duration / 1000);
        } catch (e) {
            console.log('Error playing tone:', e);
        }
    }

    setupPreferenceDetection() {
        // Monitor for changes in user preferences
        const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
        motionQuery.addListener((e) => {
            this.options.enableReducedMotion = e.matches;
            document.body.classList.toggle('reduced-motion', e.matches);
        });

        const contrastQuery = window.matchMedia('(prefers-contrast: high)');
        contrastQuery.addListener((e) => {
            this.options.enableHighContrastMode = e.matches;
            document.body.classList.toggle('high-contrast', e.matches);
        });
    }

    createAccessibilityPanel() {
        const panel = document.createElement('div');
        panel.id = 'accessibility-panel';
        panel.className = 'accessibility-panel';
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-labelledby', 'accessibility-panel-title');
        panel.setAttribute('aria-hidden', 'true');
        panel.innerHTML = `
            <div class="accessibility-panel-content bg-white rounded shadow-lg p-4" style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 10000; min-width: 300px; max-width: 400px; display: none;">
                <h3 id="accessibility-panel-title" class="h5 mb-3">Accessibility Options</h3>

                <div class="mb-3">
                    <div class="form-check form-switch">
                        <input class="form-check-input" type="checkbox" id="access-high-contrast" ${this.options.enableHighContrastMode ? 'checked' : ''}>
                        <label class="form-check-label" for="access-high-contrast">
                            High Contrast Mode
                        </label>
                    </div>
                </div>

                <div class="mb-3">
                    <div class="form-check form-switch">
                        <input class="form-check-input" type="checkbox" id="access-reduced-motion" ${this.options.enableReducedMotion ? 'checked' : ''}>
                        <label class="form-check-label" for="access-reduced-motion">
                            Reduced Motion
                        </label>
                    </div>
                </div>

                <div class="mb-3">
                    <div class="form-check form-switch">
                        <input class="form-check-input" type="checkbox" id="access-audio-cues" ${this.options.enableAudioCues ? 'checked' : ''}>
                        <label class="form-check-label" for="access-audio-cues">
                            Audio Cues
                        </label>
                    </div>
                </div>

                <div class="mb-3">
                    <label class="form-label">Text Size</label>
                    <select class="form-select" id="access-text-size">
                        <option value="normal">Normal</option>
                        <option value="large">Large</option>
                        <option value="extra-large">Extra Large</option>
                    </select>
                </div>

                <div class="d-flex justify-content-end">
                    <button type="button" class="btn btn-secondary me-2" onclick="window.accessibilityEnhancer.closeAccessibilityPanel()">Close</button>
                    <button type="button" class="btn btn-primary" onclick="window.accessibilityEnhancer.saveAccessibilitySettings()">Save</button>
                </div>
            </div>

            <div class="accessibility-panel-backdrop" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.5); z-index: 9999; display: none;" onclick="window.accessibilityEnhancer.closeAccessibilityPanel()"></div>
        `;

        document.body.appendChild(panel);

        // Setup event listeners
        document.getElementById('access-high-contrast')?.addEventListener('change', (e) => {
            this.toggleHighContrast(e.target.checked);
        });

        document.getElementById('access-reduced-motion')?.addEventListener('change', (e) => {
            this.toggleReducedMotion(e.target.checked);
        });

        document.getElementById('access-audio-cues')?.addEventListener('change', (e) => {
            this.toggleAudioCues(e.target.checked);
        });

        document.getElementById('access-text-size')?.addEventListener('change', (e) => {
            this.setTextSize(e.target.value);
        });
    }

    toggleAccessibilityPanel() {
        const panel = document.getElementById('accessibility-panel');
        const content = panel.querySelector('.accessibility-panel-content');
        const backdrop = panel.querySelector('.accessibility-panel-backdrop');

        if (panel.getAttribute('aria-hidden') === 'true') {
            panel.setAttribute('aria-hidden', 'false');
            content.style.display = 'block';
            backdrop.style.display = 'block';
            content.querySelector('button').focus();
            this.announceToScreenReader('Accessibility panel opened');
        } else {
            this.closeAccessibilityPanel();
        }
    }

    closeAccessibilityPanel() {
        const panel = document.getElementById('accessibility-panel');
        const content = panel.querySelector('.accessibility-panel-content');
        const backdrop = panel.querySelector('.accessibility-panel-backdrop');

        panel.setAttribute('aria-hidden', 'true');
        content.style.display = 'none';
        backdrop.style.display = 'none';
        this.announceToScreenReader('Accessibility panel closed');
    }

    toggleHighContrast(enable) {
        this.options.enableHighContrastMode = enable;
        document.body.classList.toggle('high-contrast', enable);
        document.getElementById('access-high-contrast').checked = enable;
        this.announceToScreenReader(`High contrast ${enable ? 'enabled' : 'disabled'}`);
    }

    toggleReducedMotion(enable) {
        this.options.enableReducedMotion = enable;
        document.body.classList.toggle('reduced-motion', enable);
        document.getElementById('access-reduced-motion').checked = enable;
        this.announceToScreenReader(`Reduced motion ${enable ? 'enabled' : 'disabled'}`);
    }

    toggleAudioCues(enable) {
        this.options.enableAudioCues = enable;
        document.getElementById('access-audio-cues').checked = enable;
        this.announceToScreenReader(`Audio cues ${enable ? 'enabled' : 'disabled'}`);
    }

    setTextSize(size) {
        document.body.classList.remove('accessibility-text-large', 'accessibility-text-extra-large');

        switch(size) {
            case 'large':
                document.body.classList.add('accessibility-text-large');
                break;
            case 'extra-large':
                document.body.classList.add('accessibility-text-extra-large');
                break;
        }

        this.announceToScreenReader(`Text size set to ${size}`);
    }

    saveAccessibilitySettings() {
        const settings = {
            highContrast: this.options.enableHighContrastMode,
            reducedMotion: this.options.enableReducedMotion,
            audioCues: this.options.enableAudioCues,
            textSize: document.getElementById('access-text-size')?.value || 'normal'
        };

        // Save to localStorage
        localStorage.setItem('accessibility-settings', JSON.stringify(settings));

        // Apply settings
        this.toggleHighContrast(settings.highContrast);
        this.toggleReducedMotion(settings.reducedMotion);
        this.toggleAudioCues(settings.audioCues);
        this.setTextSize(settings.textSize);

        this.closeAccessibilityPanel();
        this.announceToScreenReader('Accessibility settings saved');
    }

    loadAccessibilitySettings() {
        try {
            const settings = JSON.parse(localStorage.getItem('accessibility-settings') || '{}');

            if (settings.highContrast !== undefined) {
                this.toggleHighContrast(settings.highContrast);
            }
            if (settings.reducedMotion !== undefined) {
                this.toggleReducedMotion(settings.reducedMotion);
            }
            if (settings.audioCues !== undefined) {
                this.toggleAudioCues(settings.audioCues);
            }
            if (settings.textSize) {
                this.setTextSize(settings.textSize);
                document.getElementById('access-text-size').value = settings.textSize;
            }
        } catch (e) {
            console.log('Error loading accessibility settings:', e);
        }
    }

    // Public methods for external use
    announce(message, priority = 'polite') {
        this.announceToScreenReader(message, priority);
    }

    announceCoordinates(lng, lat, context = '') {
        this.announceCoordinates(lng, lat, context);
    }

    announceArea(area, unit = 'square kilometers') {
        this.announceArea(area, unit);
    }

    setFocus(element) {
        if (element && typeof element.focus === 'function') {
            element.focus();

            // Scroll into view if needed
            if (!this.isElementInViewport(element)) {
                element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    }

    isElementInViewport(element) {
        const rect = element.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.accessibilityEnhancer = new AccessibilityEnhancer({
        enableScreenReaderSupport: true,
        enableKeyboardNavigation: true,
        enableFocusManagement: true,
        enableAudioCues: false
    });

    // Load saved settings
    setTimeout(() => {
        window.accessibilityEnhancer.loadAccessibilitySettings();
    }, 100);
});