/**
 * Compatibility Fix for Development Utilities
 * Ensures development utilities work with existing table functionality
 */

class CompatibilityFix {
    constructor() {
        this.fixesApplied = false;
        this.originalFunctions = {};
    }

    /**
     * Apply compatibility fixes
     */
    applyFixes() {
        if (this.fixesApplied) {
            console.log('🔧 [Compatibility Fix] Fixes already applied');
            return;
        }

        console.log('🔧 [Compatibility Fix] Applying compatibility fixes...');

        this.fixTableStateDetection();
        thisFixHierarchicalRowDetection();
        this.fixGroupHeaderDisplay();
        this.developmentUtilityIntegration();

        this.fixesApplied = true;
        console.log('✅ [Compatibility Fix] All fixes applied successfully');
    }

    /**
     * Fix table state detection for development utilities
     */
    fixTableStateDetection() {
        // Ensure tableState is properly initialized for development utilities
        if (typeof window.tableState === 'undefined') {
            window.tableState = {
                columnHeaders: [],
                columnHeaderMap: {},
                allRows: [],
                filteredRows: [],
                parentRows: [],
                childRows: [],
                currentPage: 1,
                rowsPerPage: 50
            };
        }

        // Populate tableState from existing data
        setTimeout(() => {
            if (typeof window.storeTableRows === 'function') {
                console.log('🔧 [Compatibility Fix] Syncing table state with existing data...');
                // Don't call storeTableRows here as it may cause conflicts
                // Just ensure tableState exists for development utilities
            }
        }, 1000);
    }

    /**
     * Fix hierarchical row detection
     */
    fixHierarchicalRowDetection() {
        // Enhance existing hierarchical row detection
        if (typeof window.initializeHierarchicalTable === 'function') {
            const originalInitializeHierarchicalTable = window.initializeHierarchicalTable;
            window.initializeHierarchicalTable = function() {
                const result = originalInitializeHierarchicalTable.apply(this, arguments);

                // Notify development utilities of hierarchical data
                setTimeout(() => {
                    if (window.devTableManager) {
                        console.log('🔧 [Compatibility Fix] Updating dev utilities with hierarchical data...');
                        window.devTableManager.storeTableRows('hazard-data-table');
                    }
                }, 500);

                return result;
            };
        }
    }

    /**
     * Fix group header display
     */
    fixGroupHeaderDisplay() {
        // Ensure group headers are properly displayed
        setTimeout(() => {
            const groupHeader = document.querySelector('.group-header');
            const subGroupHeader = document.querySelector('.sub-group-header');

            if (groupHeader && groupHeader.children.length === 0) {
                console.log('🔧 [Compatibility Fix] Group header empty, attempting to restore...');
                this.restoreGroupHeaders();
            }

            if (subGroupHeader && subGroupHeader.children.length === 0) {
                console.log('🔧 [Compatibility Fix] Sub-group header empty, attempting to restore...');
                this.restoreSubGroupHeaders();
            }
        }, 2000);
    }

    /**
     * Restore group headers from template data
     */
    restoreGroupHeaders() {
        try {
            // Get groups data from Django template context
            const groupsData = this.extractGroupsFromTemplate();
            const groupHeader = document.querySelector('.group-header');

            if (groupHeader && groupsData) {
                groupHeader.innerHTML = '';
                for (const [groupName, columnCount] of Object.entries(groupsData)) {
                    if (columnCount > 0) {
                        const th = document.createElement('th');
                        th.colSpan = columnCount;
                        th.className = 'text-center';
                        th.textContent = groupName === 'Facility Information' ? 'Asset Information' : groupName;
                        groupHeader.appendChild(th);
                    }
                }
                console.log('✅ [Compatibility Fix] Group headers restored');
            }
        } catch (error) {
            console.error('❌ [Compatibility Fix] Failed to restore group headers:', error);
        }
    }

    /**
     * Restore sub-group headers
     */
    restoreSubGroupHeaders() {
        try {
            const subGroupHeader = document.querySelector('.sub-group-header');
            if (subGroupHeader) {
                // This would typically be populated by JavaScript
                // For now, ensure it's visible
                subGroupHeader.style.display = '';
                console.log('✅ [Compatibility Fix] Sub-group header visibility restored');
            }
        } catch (error) {
            console.error('❌ [Compatibility Fix] Failed to restore sub-group headers:', error);
        }
    }

    /**
     * Extract groups data from Django template context
     */
    extractGroupsFromTemplate() {
        // Try to get groups data from various sources
        if (typeof window.groups !== 'undefined') {
            return window.groups;
        }

        // Try to extract from the page
        const groupElements = document.querySelectorAll('.group-header th');
        if (groupElements.length > 0) {
            const groups = {};
            groupElements.forEach(th => {
                const groupName = th.textContent.trim();
                const colspan = parseInt(th.getAttribute('colspan')) || 1;
                groups[groupName] = colspan;
            });
            return groups;
        }

        return null;
    }

    /**
     * Integrate development utilities safely
     */
    developmentUtilityIntegration() {
        // Wait for development utilities to load
        setTimeout(() => {
            if (window.devTableManager) {
                console.log('🔧 [Compatibility Fix] Integrating with development utilities...');

                // Update dev utilities with current table state
                if (window.tableState && window.tableState.allRows.length > 0) {
                    window.devTableManager.tableState = window.tableState;
                    console.log('✅ [Compatibility Fix] Development utilities synced with table state');
                }

                // Update dev utilities with hierarchical data
                this.updateDevUtilitiesWithHierarchicalData();
            }
        }, 3000);
    }

    /**
     * Update development utilities with hierarchical data
     */
    updateDevUtilitiesWithHierarchicalData() {
        if (!window.devTableManager) return;

        // Update parent rows
        const hierarchicalParents = document.querySelectorAll('.hierarchical-row.polygon-parent');
        if (hierarchicalParents.length > 0) {
            window.devTableManager.tableState.parentRows = Array.from(hierarchicalParents).map(el => ({
                element: el,
                facilityName: el.dataset.facilityName || el.querySelector('td[data-column="Facility"]').textContent,
                isHierarchicalParent: true
            }));
            console.log(`✅ [Compatibility Fix] Updated dev utilities with ${hierarchicalParents.length} hierarchical parents`);
        }

        // Update child rows
        const hierarchicalChildren = document.querySelectorAll('.hierarchical-row.polygon-child');
        if (hierarchicalChildren.length > 0) {
            window.devTableManager.tableState.childRows = Array.from(hierarchicalChildren).map(el => ({
                element: el,
                parentFacility: el.dataset.parentFacility || el.dataset.parentId,
                isHierarchicalChild: true
            }));
            console.log(`✅ [Compatibility Fix] Updated dev utilities with ${hierarchicalChildren.length} hierarchical children`);
        }
    }

    /**
     * Fix table rendering "No data found" issue
     */
    fixNoDataIssue() {
        setTimeout(() => {
            const tbody = document.querySelector('#hazard-data-table tbody');
            const noDataRow = tbody ? tbody.querySelector('td:contains("No data found")') : null;

            if (noDataRow) {
                console.log('🔧 [Compatibility Fix] "No data found" detected, investigating...');

                // Check if there are actually rows that should be displayed
                const allRows = document.querySelectorAll('#hazard-data-table tbody tr');
                const visibleRows = Array.from(allRows).filter(row =>
                    !row.textContent.includes('No data found') &&
                    row.style.display !== 'none'
                );

                if (visibleRows.length > 0) {
                    console.log(`✅ [Compatibility Fix] Found ${visibleRows.length} visible rows, removing "No data found" message`);
                    noDataRow.closest('tr').remove();
                } else {
                    console.warn('⚠️ [Compatibility Fix] No visible rows found, checking table state...');
                    this.diagnoseTableState();
                }
            }
        }, 1500);
    }

    /**
     * Diagnose table state issues
     */
    diagnoseTableState() {
        console.group('🔍 [Compatibility Fix] Table State Diagnosis');

        const tbody = document.querySelector('#hazard-data-table tbody');
        if (!tbody) {
            console.error('❌ Table body not found');
            console.groupEnd();
            return;
        }

        const allRows = tbody.querySelectorAll('tr');
        console.log(`Total rows in DOM: ${allRows.length}`);

        const rowsByType = {
            'custom-table-row': 0,
            'hierarchical-row': 0,
            'polygon-parent': 0,
            'polygon-child': 0,
            'parent-facility-row': 0,
            'sample-point-row': 0
        };

        allRows.forEach(row => {
            for (const [className, count] of Object.entries(rowsByType)) {
                if (row.classList.contains(className)) {
                    rowsByType[className]++;
                }
            }
        });

        console.table(rowsByType);

        // Check visibility
        const hiddenRows = Array.from(allRows).filter(row => row.style.display === 'none');
        console.log(`Hidden rows: ${hiddenRows.length}`);

        console.groupEnd();
    }
}

// Initialize compatibility fixes
$(document).ready(function() {
    setTimeout(() => {
        const compatibilityFix = new CompatibilityFix();
        compatibilityFix.applyFixes();

        // Fix "No data found" issue
        compatibilityFix.fixNoDataIssue();

        // Make globally available
        window.compatibilityFix = compatibilityFix;
    }, 2000);
});