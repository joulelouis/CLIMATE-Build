/**
 * State persistence and recovery system for climate hazards results page
 * Preserves user preferences, table state, and unsaved changes across sessions
 */

class StateManager {
    constructor(options = {}) {
        this.options = {
            storageKey: 'climaterisk_state',
            autoSave: true,
            autoSaveInterval: 30000, // 30 seconds
            maxStateSize: 1024 * 1024, // 1MB
            compressionEnabled: true,
            encryptionEnabled: false, // Set to true if sensitive data
            ...options
        };

        this.state = this.getDefaultState();
        this.isDirty = false;
        this.autoSaveTimer = null;
        this.version = '1.0.0';

        this.loadState();
        this.setupAutoSave();
        this.setupEventListeners();
    }

    getDefaultState() {
        return {
            version: this.version,
            timestamp: null,
            sessionData: {
                selectedHazards: [],
                facilityCount: 0,
                analysisDate: null
            },
            tableState: {
                currentPage: 1,
                rowsPerPage: 25,
                sortColumn: null,
                sortDirection: 'asc',
                searchTerm: '',
                columnVisibility: {},
                scrollPosition: 0
            },
            userPreferences: {
                theme: 'default',
                autoSaveEnabled: true,
                showNotifications: true,
                language: 'en'
            },
            unsavedChanges: {},
            uiState: {
                activeTab: 'table-content',
                sidebarCollapsed: false,
                selectedRows: [],
                filters: {}
            },
            performance: {
                lastRenderTime: 0,
                totalRows: 0,
                memoryUsage: 0
            }
        };
    }

    loadState() {
        try {
            const storedState = localStorage.getItem(this.options.storageKey);

            if (!storedState) {
                console.log('No saved state found, using defaults');
                return;
            }

            let parsedState;
            if (this.options.compressionEnabled) {
                parsedState = this.decompressState(storedState);
            } else {
                parsedState = JSON.parse(storedState);
            }

            // Validate and migrate state if needed
            const validatedState = this.validateAndMigrateState(parsedState);

            if (validatedState) {
                this.state = { ...this.state, ...validatedState };
                this.restoreState();
                console.log('State loaded successfully');
            } else {
                console.warn('Invalid state detected, using defaults');
                this.clearState();
            }

        } catch (error) {
            console.error('Failed to load state:', error);
            this.clearState();
        }
    }

    saveState(force = false) {
        if (!this.isDirty && !force) return;

        try {
            // Update timestamp
            this.state.timestamp = Date.now();

            // Prepare state for storage
            const stateToSave = this.prepareStateForStorage();

            // Check size limit
            const stateSize = new Blob([JSON.stringify(stateToSave)]).size;
            if (stateSize > this.options.maxStateSize) {
                console.warn('State size exceeds limit, cleaning up...');
                this.cleanupState();
                return this.saveState(true); // Retry after cleanup
            }

            // Serialize and store
            let serializedState;
            if (this.options.compressionEnabled) {
                serializedState = this.compressState(stateToSave);
            } else {
                serializedState = JSON.stringify(stateToSave);
            }

            if (this.options.encryptionEnabled) {
                serializedState = this.encryptState(serializedState);
            }

            localStorage.setItem(this.options.storageKey, serializedState);
            this.isDirty = false;

            console.log('State saved successfully');

        } catch (error) {
            console.error('Failed to save state:', error);
            // Try to save a minimal state as fallback
            this.saveMinimalState();
        }
    }

    prepareStateForStorage() {
        // Create a clean copy for storage
        const stateToSave = JSON.parse(JSON.stringify(this.state));

        // Remove sensitive or temporary data
        delete stateToSave.performance;
        delete stateToSave.uiState.selectedRows; // Don't persist selected rows

        // Limit unsaved changes history
        if (Object.keys(stateToSave.unsavedChanges).length > 100) {
            const changes = Object.entries(stateToSave.unsavedChanges);
            changes.splice(0, changes.length - 100); // Keep only last 100 changes
            stateToSave.unsavedChanges = Object.fromEntries(changes);
        }

        return stateToSave;
    }

    compressState(state) {
        // Simple compression using JSON stringification with replacer
        return JSON.stringify(state, (key, value) => {
            if (typeof value === 'string' && value.length > 100) {
                // For long strings, use basic compression
                return value.replace(/\s+/g, ' ').trim();
            }
            return value;
        });
    }

    decompressState(compressedState) {
        return JSON.parse(compressedState);
    }

    encryptState(state) {
        // Basic XOR encryption (replace with stronger encryption for production)
        const key = 'climaterisk2023';
        return state.split('').map((char, index) => {
            return String.fromCharCode(char.charCodeAt(0) ^ key.charCodeAt(index % key.length));
        }).join('');
    }

    decryptState(encryptedState) {
        // Basic XOR decryption
        const key = 'climaterisk2023';
        return encryptedState.split('').map((char, index) => {
            return String.fromCharCode(char.charCodeAt(0) ^ key.charCodeAt(index % key.length));
        }).join('');
    }

    validateAndMigrateState(state) {
        if (!state || typeof state !== 'object') {
            return null;
        }

        // Check version compatibility
        if (state.version && this.isVersionOlder(state.version, this.version)) {
            console.log('Migrating state from version', state.version, 'to', this.version);
            state = this.migrateState(state, state.version, this.version);
        }

        // Validate structure
        const requiredKeys = ['tableState', 'userPreferences', 'unsavedChanges'];
        for (const key of requiredKeys) {
            if (!state[key] || typeof state[key] !== 'object') {
                console.warn(`Invalid state structure: missing or invalid ${key}`);
                return null;
            }
        }

        return state;
    }

    isVersionOlder(version1, version2) {
        const v1parts = version1.split('.').map(Number);
        const v2parts = version2.split('.').map(Number);

        for (let i = 0; i < Math.max(v1parts.length, v2parts.length); i++) {
            const v1part = v1parts[i] || 0;
            const v2part = v2parts[i] || 0;

            if (v1part < v2part) return true;
            if (v1part > v2part) return false;
        }

        return false;
    }

    migrateState(state, fromVersion, toVersion) {
        // Add migration logic here when state structure changes
        const migratedState = { ...state };

        // Example migration from 0.9.0 to 1.0.0
        if (this.isVersionOlder(fromVersion, '1.0.0')) {
            if (!migratedState.uiState) {
                migratedState.uiState = {
                    activeTab: 'table-content',
                    sidebarCollapsed: false,
                    filters: {}
                };
            }
        }

        migratedState.version = toVersion;
        return migratedState;
    }

    restoreState() {
        // Restore table state
        if (this.state.tableState) {
            this.restoreTableState();
        }

        // Restore user preferences
        if (this.state.userPreferences) {
            this.restoreUserPreferences();
        }

        // Restore UI state
        if (this.state.uiState) {
            this.restoreUIState();
        }

        // Restore unsaved changes
        if (this.state.unsavedChanges && Object.keys(this.state.unsavedChanges).length > 0) {
            this.restoreUnsavedChanges();
        }
    }

    restoreTableState() {
        const tableState = this.state.tableState;

        // Restore pagination
        if (tableState.currentPage && window.tableState) {
            window.tableState.currentPage = tableState.currentPage;
        }

        if (tableState.rowsPerPage && window.tableState) {
            window.tableState.rowsPerPage = tableState.rowsPerPage;
        }

        // Restore sorting
        if (tableState.sortColumn && window.tableState) {
            window.tableState.sortColumn = tableState.sortColumn;
            window.tableState.sortDirection = tableState.sortDirection;
        }

        // Restore search
        if (tableState.searchTerm && document.getElementById('search-input')) {
            document.getElementById('search-input').value = tableState.searchTerm;
            if (window.performSearch) {
                window.performSearch(tableState.searchTerm);
            }
        }

        // Restore column visibility
        if (tableState.columnVisibility) {
            this.restoreColumnVisibility(tableState.columnVisibility);
        }

        // Restore scroll position
        if (tableState.scrollPosition) {
            setTimeout(() => {
                const tableContainer = document.querySelector('.virtual-scroll-wrapper') ||
                                    document.querySelector('.table-responsive');
                if (tableContainer) {
                    tableContainer.scrollTop = tableState.scrollPosition;
                }
            }, 100);
        }
    }

    restoreColumnVisibility(columnVisibility) {
        Object.entries(columnVisibility).forEach(([column, isVisible]) => {
            const checkbox = document.querySelector(`[data-column="${column}"]`);
            if (checkbox && checkbox.type === 'checkbox') {
                checkbox.checked = isVisible;
            }
        });

        // Trigger visibility update
        if (window.updateColumnVisibility) {
            window.updateColumnVisibility();
        }
    }

    restoreUserPreferences() {
        const prefs = this.state.userPreferences;

        // Restore theme
        if (prefs.theme && prefs.theme !== 'default') {
            document.body.setAttribute('data-theme', prefs.theme);
        }

        // Restore auto-save setting
        if (prefs.autoSaveEnabled !== undefined) {
            this.options.autoSave = prefs.autoSaveEnabled;
        }
    }

    restoreUIState() {
        const uiState = this.state.uiState;

        // Restore active tab
        if (uiState.activeTab) {
            const tabButton = document.querySelector(`[data-bs-target="#${uiState.activeTab}"]`);
            if (tabButton) {
                const tab = new bootstrap.Tab(tabButton);
                tab.show();
            }
        }

        // Restore sidebar state
        if (uiState.sidebarCollapsed) {
            document.body.classList.add('sidebar-collapsed');
        }

        // Restore filters
        if (uiState.filters && window.applyFilters) {
            window.applyFilters(uiState.filters);
        }
    }

    restoreUnsavedChanges() {
        const unsavedChanges = this.state.unsavedChanges;

        if (Object.keys(unsavedChanges).length > 0) {
            // Show notification about unsaved changes
            this.showUnsavedChangesNotification(Object.keys(unsavedChanges).length);

            // Restore cell changes
            Object.entries(unsavedChanges).forEach(([key, change]) => {
                if (window.cellChanges) {
                    window.cellChanges[key] = change;
                }
            });

            // Update UI indicators
            if (window.updateChangeIndicator) {
                window.updateChangeIndicator();
            }
        }
    }

    showUnsavedChangesNotification(count) {
        const notification = document.createElement('div');
        notification.className = 'alert alert-warning alert-dismissible fade show';
        notification.innerHTML = `
            <strong>Unsaved Changes Detected</strong>
            <p class="mb-0">${count} unsaved change(s) were restored from your previous session.</p>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        const container = document.querySelector('.container-fluid');
        if (container) {
            container.insertBefore(notification, container.firstChild);
        }

        // Auto-dismiss after 10 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 10000);
    }

    setupAutoSave() {
        if (!this.options.autoSave) return;

        this.autoSaveTimer = setInterval(() => {
            this.saveState();
        }, this.options.autoSaveInterval);
    }

    setupEventListeners() {
        // Save state before page unload
        window.addEventListener('beforeunload', () => {
            this.saveState(true);
        });

        // Save state on page visibility change
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.saveState(true);
            }
        });

        // Listen for table changes
        if (window.addEventListener) {
            window.addEventListener('tableStateChanged', (event) => {
                this.handleTableStateChange(event.detail);
            });

            window.addEventListener('cellChanged', (event) => {
                this.handleCellChange(event.detail);
            });
        }
    }

    handleTableStateChange(changes) {
        if (changes.page) {
            this.state.tableState.currentPage = changes.page;
        }
        if (changes.rowsPerPage) {
            this.state.tableState.rowsPerPage = changes.rowsPerPage;
        }
        if (changes.sort) {
            this.state.tableState.sortColumn = changes.sort.column;
            this.state.tableState.sortDirection = changes.sort.direction;
        }
        if (changes.search) {
            this.state.tableState.searchTerm = changes.search;
        }
        if (changes.scrollPosition !== undefined) {
            this.state.tableState.scrollPosition = changes.scrollPosition;
        }

        this.markDirty();
    }

    handleCellChange(change) {
        const key = `${change.rowIndex}-${change.column}`;
        this.state.unsavedChanges[key] = change;
        this.markDirty();
    }

    markDirty() {
        this.isDirty = true;

        // Trigger auto-save if enabled
        if (this.options.autoSave) {
            clearTimeout(this.autoSaveTimer);
            this.autoSaveTimer = setTimeout(() => {
                this.saveState();
            }, this.options.autoSaveInterval);
        }
    }

    updateColumnVisibility(columnName, isVisible) {
        this.state.tableState.columnVisibility[columnName] = isVisible;
        this.markDirty();
    }

    updateSessionData(sessionData) {
        this.state.sessionData = {
            ...this.state.sessionData,
            ...sessionData
        };
        this.markDirty();
    }

    clearUnsavedChanges() {
        this.state.unsavedChanges = {};
        this.markDirty();
    }

    cleanupState() {
        // Remove old or unnecessary data
        const now = Date.now();
        const maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days

        // Remove old unsaved changes
        Object.keys(this.state.unsavedChanges).forEach(key => {
            const change = this.state.unsavedChanges[key];
            if (change.timestamp && (now - change.timestamp) > maxAge) {
                delete this.state.unsavedChanges[key];
            }
        });

        // Compress large arrays or objects
        if (this.state.tableState.columnVisibility) {
            const visibility = this.state.tableState.columnVisibility;
            const compressed = {};
            Object.keys(visibility).forEach(key => {
                if (visibility[key]) {
                    compressed[key] = true;
                }
            });
            this.state.tableState.columnVisibility = compressed;
        }
    }

    saveMinimalState() {
        try {
            const minimalState = {
                version: this.version,
                timestamp: Date.now(),
                tableState: {
                    currentPage: this.state.tableState.currentPage,
                    rowsPerPage: this.state.tableState.rowsPerPage
                }
            };

            localStorage.setItem(this.options.storageKey + '_minimal', JSON.stringify(minimalState));
            console.log('Minimal state saved as fallback');
        } catch (error) {
            console.error('Failed to save minimal state:', error);
        }
    }

    clearState() {
        localStorage.removeItem(this.options.storageKey);
        localStorage.removeItem(this.options.storageKey + '_minimal');
        this.state = this.getDefaultState();
        console.log('State cleared');
    }

    exportState() {
        const stateCopy = JSON.parse(JSON.stringify(this.state));
        const blob = new Blob([JSON.stringify(stateCopy, null, 2)], {
            type: 'application/json'
        });

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `climaterisk-state-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    importState(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (event) => {
                try {
                    const importedState = JSON.parse(event.target.result);
                    const validatedState = this.validateAndMigrateState(importedState);

                    if (validatedState) {
                        this.state = { ...this.state, ...validatedState };
                        this.restoreState();
                        this.saveState(true);
                        resolve(validatedState);
                    } else {
                        reject(new Error('Invalid state file'));
                    }
                } catch (error) {
                    reject(error);
                }
            };
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.readAsText(file);
        });
    }

    getState() {
        return { ...this.state };
    }

    getStats() {
        return {
            stateSize: new Blob([JSON.stringify(this.state)]).size,
            unsavedChanges: Object.keys(this.state.unsavedChanges).length,
            lastSaved: this.state.timestamp,
            isDirty: this.isDirty,
            version: this.state.version
        };
    }
}

// Export and initialize
window.StateManager = StateManager;

// Auto-initialize
document.addEventListener('DOMContentLoaded', function() {
    window.stateManager = new StateManager({
        autoSave: true,
        autoSaveInterval: 30000
    });

    console.log('State manager initialized');

    // Add export/import functionality
    const exportBtn = document.createElement('button');
    exportBtn.className = 'btn btn-sm btn-outline-secondary me-2';
    exportBtn.innerHTML = '<i class="fas fa-download"></i> Export State';
    exportBtn.onclick = () => window.stateManager.exportState();

    const importBtn = document.createElement('input');
    importBtn.type = 'file';
    importBtn.accept = '.json';
    importBtn.style.display = 'none';
    importBtn.onchange = (event) => {
        if (event.target.files[0]) {
            window.stateManager.importState(event.target.files[0])
                .then(() => {
                    alert('State imported successfully');
                    location.reload();
                })
                .catch(error => {
                    alert('Failed to import state: ' + error.message);
                });
        }
    };

    const importBtnLabel = document.createElement('label');
    importBtnLabel.className = 'btn btn-sm btn-outline-secondary';
    importBtnLabel.innerHTML = '<i class="fas fa-upload"></i> Import State';
    importBtnLabel.setAttribute('for', 'state-import');

    importBtn.id = 'state-import';

    // Add buttons to interface
    const controlsContainer = document.querySelector('.table-controls') ||
                             document.querySelector('.card-header');
    if (controlsContainer) {
        const buttonGroup = document.createElement('div');
        buttonGroup.className = 'btn-group ms-auto';
        buttonGroup.appendChild(exportBtn);
        buttonGroup.appendChild(importBtn);
        buttonGroup.appendChild(importBtnLabel);
        controlsContainer.appendChild(buttonGroup);
    }
});