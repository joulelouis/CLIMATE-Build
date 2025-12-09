/**
 * Hierarchical Row Detection Fix
 * Fixes the issue where rows are stored but not detected as hierarchical
 */

class HierarchicalDetectionFix {
    constructor() {
        this.applied = false;
    }

    /**
     * Apply hierarchical detection fixes
     */
    applyFixes() {
        if (this.applied) return;

        console.log('🔧 [Hierarchical Fix] Applying hierarchical detection fixes...');

        this.fixStoreTableRowsFunction();
        this.fixHierarchicalRowDetection();
        this.manualRowClassification();
        this.enhancedDebugOutput();

        this.applied = true;
        console.log('✅ [Hierarchical Fix] Hierarchical detection fixes applied');
    }

    /**
     * Fix the storeTableRows function to properly detect hierarchical rows
     */
    fixStoreTableRowsFunction() {
        // Wait for existing storeTableRows to be available
        setTimeout(() => {
            if (typeof window.storeTableRows === 'function') {
                const originalStoreTableRows = window.storeTableRows;

                window.storeTableRows = function() {
                    // Call original function first
                    const result = originalStoreTableRows.apply(this, arguments);

                    // Then fix hierarchical detection
                    window.hierarchicalFix.fixHierarchicalRowDetection();

                    return result;
                };

                console.log('✅ [Hierarchical Fix] Enhanced storeTableRows function');
            }
        }, 2000);
    }

    /**
     * Fix hierarchical row detection logic
     */
    fixHierarchicalRowDetection() {
        const $rows = $('#hazard-data-table tbody tr');

        console.log(`🔍 [Hierarchical Fix] Analyzing ${$rows.length} rows for hierarchical detection...`);

        // Reset counts
        tableState.parentRows = [];
        tableState.childRows = [];
        tableState.allRows = [];

        let parentCount = 0;
        let childCount = 0;

        $rows.each(function(index) {
            const $row = $(this);
            const rowData = window.hierarchicalFix.extractRowData($row);

            // Enhanced row type detection
            const rowType = window.hierarchicalFix.detectRowTypeEnhanced($row);
            rowData.rowType = rowType;
            rowData.originalIndex = index;

            console.log(`🔍 [Hierarchical Fix] Row ${index}: type=${rowType}, facility=${rowData.facilityName || 'N/A'}`);

            if (rowType === 'polygon_parent' || rowType === 'parent_facility') {
                tableState.parentRows.push(rowData);
                parentCount++;
                console.log(`✅ [Hierarchical Fix] Found parent: ${rowData.facilityName}`);
            } else if (rowType === 'polygon_child' || rowType === 'sample_point') {
                tableState.childRows.push(rowData);
                childCount++;
                console.log(`✅ [Hierarchical Fix] Found child: ${rowData.facilityName} (parent: ${rowData.parentFacility})`);
            }

            tableState.allRows.push(rowData);
        });

        // Update tableState with corrected counts
        tableState.parentRowsCount = parentCount;
        tableState.childRowsCount = childCount;

        console.log(`✅ [Hierarchical Fix] Corrected hierarchical detection: ${parentCount} parents, ${childCount} children`);

        // Update filtered rows
        tableState.filteredRows = [...tableState.allRows];

        // Trigger table re-render if needed
        if (typeof window.renderTable === 'function') {
            window.renderTable(1);
        }

        return { parentCount, childCount };
    }

    /**
     * Enhanced row type detection
     */
    detectRowTypeEnhanced($row) {
        // Method 1: Check CSS classes
        if ($row.hasClass('hierarchical-row') && $row.hasClass('polygon-parent')) {
            return 'polygon_parent';
        } else if ($row.hasClass('hierarchical-row') && $row.hasClass('polygon-child')) {
            return 'polygon_child';
        } else if ($row.hasClass('sample-point-row')) {
            return 'sample_point';
        } else if ($row.hasClass('parent-facility-row')) {
            return 'parent_facility';
        }

        // Method 2: Check data attributes
        const rowType = $row.data('row-type') || $row.attr('data-row-type');
        if (rowType) {
            return rowType;
        }

        // Method 3: Infer from facility name pattern
        const facilityName = this.extractFacilityName($row);
        if (facilityName) {
            // Check for centroid patterns
            if (facilityName.includes('Centroid') || facilityName.includes('🟢')) {
                return 'polygon_parent';
            }
            // Check for child patterns
            if (facilityName.includes('Point ') || facilityName.includes('🔵') || facilityName.includes('└─')) {
                return 'polygon_child';
            }
            // Check for sample point patterns
            if (facilityName.includes('Granular Point') || facilityName.includes('Sample Point')) {
                return 'sample_point';
            }
        }

        // Method 4: Check for expand/collapse button
        if ($row.find('.expand-collapse-btn').length > 0) {
            return 'polygon_parent';
        }

        // Method 5: Check for hierarchical attributes
        if ($row.attr('data-parent-id') || $row.attr('data-parent-facility')) {
            return 'polygon_child';
        }

        // Default to regular if no hierarchical indicators found
        return 'regular';
    }

    /**
     * Extract row data with enhanced facility name detection
     */
    extractRowData($row) {
        const $cells = $row.find('td');
        const rowData = {
            element: $row[0],
            cells: [],
            visible: $row.is(':visible'),
            facilityName: this.extractFacilityName($row),
            parentFacility: $row.attr('data-parent-facility') || $row.attr('data-parent-id')
        };

        $cells.each((cellIndex, cell) => {
            const $cell = $(cell);
            const cellValue = $cell.text().trim();

            rowData.cells.push({
                value: cellValue,
                numericValue: this.parseNumericValue(cellValue),
                element: cell,
                columnName: this.getColumnName(cellIndex)
            });
        });

        return rowData;
    }

    /**
     * Extract facility name from row
     */
    extractFacilityName($row) {
        // Method 1: Get from data attributes
        let facilityName = $row.attr('data-facility-name') || $row.data('facility-name');
        if (facilityName) return facilityName;

        // Method 2: Get from Facility column
        const facilityCell = $row.find('td[data-column="Facility"]');
        if (facilityCell.length > 0) {
            return facilityCell.text().trim();
        }

        // Method 3: Get from first cell (usually Facility)
        const firstCell = $row.find('td:first');
        if (firstCell.length > 0) {
            return firstCell.text().trim();
        }

        return 'Unknown';
    }

    /**
     * Get column name by index
     */
    getColumnName(index) {
        if (window.tableState && window.tableState.columnHeaderMap) {
            const columnMap = window.tableState.columnHeaderMap;
            for (const [name, idx] of Object.entries(columnMap)) {
                if (idx === index) return name;
            }
        }
        return `Column ${index}`;
    }

    /**
     * Parse numeric value from text
     */
    parseNumericValue(text) {
        const cleanText = text.replace(/[^\d.-]/g, '');
        const numValue = parseFloat(cleanText);
        return isNaN(numValue) ? null : numValue;
    }

    /**
     * Manual row classification as fallback
     */
    manualRowClassification() {
        setTimeout(() => {
            console.log('🔧 [Hierarchical Fix] Running manual row classification...');

            const $rows = $('#hazard-data-table tbody tr');
            let manualParents = 0;
            let manualChildren = 0;

            $rows.each(function(index) {
                const $row = $(this);
                const facilityName = window.hierarchicalFix.extractFacilityName($row);

                // Manual classification based on facility name patterns
                if (facilityName.includes('Centroid') || facilityName.includes('🟢')) {
                    if (!$row.hasClass('hierarchical-row')) {
                        $row.addClass('hierarchical-row polygon-parent level-0');
                        $row.attr('data-row-type', 'polygon_parent');
                        manualParents++;
                        console.log(`🔧 [Hierarchical Fix] Manually classified as parent: ${facilityName}`);
                    }
                } else if (facilityName.includes('Point ') || facilityName.includes('🔵') || facilityName.includes('└─')) {
                    if (!$row.hasClass('hierarchical-row')) {
                        $row.addClass('hierarchical-row polygon-child level-1');
                        $row.attr('data-row-type', 'polygon_child');
                        manualChildren++;
                        console.log(`🔧 [Hierarchical Fix] Manually classified as child: ${facilityName}`);
                    }
                }
            });

            if (manualParents > 0 || manualChildren > 0) {
                console.log(`✅ [Hierarchical Fix] Manual classification: ${manualParents} parents, ${manualChildren} children`);

                // Re-run hierarchical detection after manual classification
                setTimeout(() => {
                    window.hierarchicalFix.fixHierarchicalRowDetection();
                }, 500);
            }
        }, 3000);
    }

    /**
     * Enhanced debug output
     */
    enhancedDebugOutput() {
        setTimeout(() => {
            console.group('🔍 [Hierarchical Fix] Enhanced Debug Analysis');

            // Analyze all rows
            const $rows = $('#hazard-data-table tbody tr');
            console.log(`Total DOM rows: ${$rows.length}`);

            // Analyze table state
            if (window.tableState) {
                console.log(`Table state - All rows: ${window.tableState.allRows.length}`);
                console.log(`Table state - Parent rows: ${window.tableState.parentRows.length}`);
                console.log(`Table state - Child rows: ${window.tableState.childRows.length}`);
            }

            // Analyze row types in DOM
            const rowTypes = {};
            $rows.each(function() {
                const $row = $(this);
                const rowType = window.hierarchicalFix.detectRowTypeEnhanced($row);
                rowTypes[rowType] = (rowTypes[rowType] || 0) + 1;
            });
            console.table(rowTypes);

            // Show first few rows with details
            console.log('First 5 rows detailed analysis:');
            $rows.slice(0, 5).each(function(index) {
                const $row = $(this);
                const facilityName = window.hierarchicalFix.extractFacilityName($row);
                const rowType = window.hierarchicalFix.detectRowTypeEnhanced($row);
                console.log(`Row ${index}: ${rowType} - ${facilityName}`);
            });

            console.groupEnd();
        }, 4000);
    }

    /**
     * Quick fix function to run immediately
     */
    quickFix() {
        console.log('🚀 [Hierarchical Fix] Running quick fix...');

        // Immediate re-detection
        this.fixHierarchicalRowDetection();

        // Force table re-render
        setTimeout(() => {
            if (typeof window.renderTable === 'function') {
                window.renderTable(1);
            }

            // Hide "No data found" if it exists
            const noDataElement = $('#hazard-data-table tbody td:contains("No data found")');
            if (noDataElement.length > 0) {
                noDataElement.closest('tr').hide();
                console.log('🔧 [Hierarchical Fix] Hidden "No data found" message');
            }
        }, 1000);
    }
}

// Initialize and apply fixes
$(document).ready(function() {
    setTimeout(() => {
        window.hierarchicalFix = new HierarchicalDetectionFix();
        window.hierarchicalFix.applyFixes();

        // Run quick fix after table is fully initialized
        setTimeout(() => {
            window.hierarchicalFix.quickFix();
        }, 5000);

        // Make available for manual triggering
        console.log('🔧 [Hierarchical Fix] Available commands:');
        console.log('  - window.hierarchicalFix.quickFix()');
        console.log('  - window.hierarchicalFix.fixHierarchicalRowDetection()');
        console.log('  - window.hierarchicalFix.enhancedDebugOutput()');
    }, 2000);
});