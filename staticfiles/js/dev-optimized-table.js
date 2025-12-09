/**
 * Development-Optimized Polygon Asset Table Manager
 * Optimized for performance and debugging during development
 */

class DevOptimizedTableManager {
    constructor() {
        this.tableState = {
            columnHeaders: [],
            columnHeaderMap: {},
            allRows: [],
            filteredRows: [],
            parentRows: [],
            childRows: [],
            currentPage: 1,
            rowsPerPage: 50,
            sortColumn: null,
            sortDirection: 'asc'
        };

        this.performanceMetrics = {
            initTime: 0,
            renderTime: 0,
            sortTime: 0,
            filterTime: 0
        };

        this.debugMode = true;
    }

    /**
     * Enhanced initialization with performance tracking
     */
    initialize(tableId = 'hazard-data-table') {
        const startTime = performance.now();

        console.log('🚀 [Dev Table Manager] Initializing optimized table...');

        // Check if existing table initialization is already present
        if (typeof window.initializeEnhancedManualTable !== 'undefined') {
            console.log('📋 [Dev Table Manager] Existing table initialization detected, enhancing instead of replacing...');
            this.enhanceExistingTable(tableId);
        } else {
            console.log('🆕 [Dev Table Manager] No existing table found, creating new...');
            this.createNewTable(tableId);
        }

        this.performanceMetrics.initTime = performance.now() - startTime;
        console.log(`✅ [Dev Table Manager] Initialized in ${this.performanceMetrics.initTime.toFixed(2)}ms`);

        // Add development utilities after existing table is ready
        setTimeout(() => {
            this.addDevUtilities();
            this.autoExpandFirstPolygon();
        }, 500);
    }

    /**
     * Enhance existing table functionality
     */
    enhanceExistingTable(tableId) {
        console.log('🔧 [Dev Table Manager] Enhancing existing table functionality...');

        try {
            this.buildHeaderMap(tableId);
            this.storeTableRows(tableId);

            // Add performance monitoring to existing functions
            this.addPerformanceMonitoring();

            console.log('✅ [Dev Table Manager] Existing table enhanced successfully');
        } catch (error) {
            console.error('❌ [Dev Table Manager] Failed to enhance existing table:', error);
        }
    }

    /**
     * Create new table if no existing table found
     */
    createNewTable(tableId) {
        console.log('🆕 [Dev Table Manager] Creating new table management system...');

        try {
            this.buildHeaderMap(tableId);
            this.storeTableRows(tableId);
            this.setupOptimizedPagination();
            this.setupEnhancedSearch();
            this.setupColumnSelector();

            console.log('✅ [Dev Table Manager] New table system created successfully');
        } catch (error) {
            console.error('❌ [Dev Table Manager] Failed to create new table:', error);
        }
    }

    /**
     * Add performance monitoring to existing table functions
     */
    addPerformanceMonitoring() {
        // Monitor existing renderTable function
        if (typeof window.renderTable === 'function') {
            const originalRenderTable = window.renderTable;
            window.renderTable = function() {
                const startTime = performance.now();
                const result = originalRenderTable.apply(this, arguments);
                const duration = performance.now() - startTime;
                console.log(`⚡ [Dev Table Manager] renderTable took ${duration.toFixed(2)}ms`);
                return result;
            };
        }

        // Monitor existing buildColumnHeaderMap function
        if (typeof window.buildColumnHeaderMap === 'function') {
            const originalBuildColumnHeaderMap = window.buildColumnHeaderMap;
            window.buildColumnHeaderMap = function() {
                const startTime = performance.now();
                const result = originalBuildColumnHeaderMap.apply(this, arguments);
                const duration = performance.now() - startTime;
                console.log(`⚡ [Dev Table Manager] buildColumnHeaderMap took ${duration.toFixed(2)}ms`);
                return result;
            };
        }

        // Monitor existing storeTableRows function
        if (typeof window.storeTableRows === 'function') {
            const originalStoreTableRows = window.storeTableRows;
            window.storeTableRows = function() {
                const startTime = performance.now();
                const result = originalStoreTableRows.apply(this, arguments);
                const duration = performance.now() - startTime;
                console.log(`⚡ [Dev Table Manager] storeTableRows took ${duration.toFixed(2)}ms`);
                return result;
            };
        }

        console.log('📊 [Dev Table Manager] Performance monitoring added to existing functions');
    }

    /**
     * Optimized header mapping with caching
     */
    buildHeaderMap(tableId) {
        console.log('📊 [Dev Table Manager] Building optimized header map...');

        const startTime = performance.now();
        const $headers = $(`#${tableId} thead tr.custom-table-header th`);

        this.tableState.columnHeaders = [];
        this.tableState.columnHeaderMap = {};

        $headers.each((index, header) => {
            const $header = $(header);
            const columnName = $header.attr('data-column-name') || $header.text().trim();

            this.tableState.columnHeaderMap[columnName] = index;
            this.tableState.columnHeaders.push({
                name: columnName,
                index: index,
                visible: true,
                dataType: this.detectDataType(columnName)
            });
        });

        const buildTime = performance.now() - startTime;
        console.log(`✅ [Dev Table Manager] Mapped ${$headers.length} columns in ${buildTime.toFixed(2)}ms`);
        console.log('📋 [Dev Table Manager] Column map:', this.tableState.columnHeaderMap);

        // Store column map globally for debugging
        window.devTableColumnMap = this.tableState.columnHeaderMap;
    }

    /**
     * Optimized row storage with hierarchical support
     */
    storeTableRows(tableId) {
        console.log('🗂️ [Dev Table Manager] Storing table rows with hierarchical structure...');

        const startTime = performance.now();
        const $rows = $(`#${tableId} tbody tr`);

        this.tableState.allRows = [];
        this.tableState.parentRows = [];
        this.tableState.childRows = [];

        $rows.each((index, row) => {
            const $row = $(row);
            const rowData = this.extractRowData($row);

            // Enhanced row type detection
            const rowType = this.detectRowType($row);
            rowData.rowType = rowType;
            rowData.originalIndex = index;

            if (rowType === 'polygon_parent') {
                this.tableState.parentRows.push(rowData);
            } else if (rowType === 'polygon_child' || rowType === 'sample_point') {
                this.tableState.childRows.push(rowData);
            }

            this.tableState.allRows.push(rowData);
        });

        const storeTime = performance.now() - startTime;
        console.log(`✅ [Dev Table Manager] Stored ${this.tableState.allRows.length} rows in ${storeTime.toFixed(2)}ms`);
        console.log(`📊 [Dev Table Manager] Found ${this.tableState.parentRows.length} parent rows, ${this.tableState.childRows.length} child rows`);

        // Store data globally for debugging
        window.devTableData = {
            allRows: this.tableState.allRows,
            parentRows: this.tableState.parentRows,
            childRows: this.tableState.childRows
        };
    }

    /**
     * Enhanced row type detection
     */
    detectRowType($row) {
        if ($row.hasClass('hierarchical-row') && $row.hasClass('polygon-parent')) {
            return 'polygon_parent';
        } else if ($row.hasClass('hierarchical-row') && $row.hasClass('polygon-child')) {
            return 'polygon_child';
        } else if ($row.hasClass('sample-point-row')) {
            return 'sample_point';
        } else if ($row.hasClass('parent-facility-row')) {
            return 'facility_parent';
        }
        return 'regular';
    }

    /**
     * Optimized data extraction from table row
     */
    extractRowData($row) {
        const $cells = $row.find('td');
        const rowData = {
            element: $row[0],
            cells: [],
            visible: $row.is(':visible')
        };

        $cells.each((cellIndex, cell) => {
            const $cell = $(cell);
            const cellValue = $cell.text().trim();

            rowData.cells.push({
                value: cellValue,
                numericValue: this.parseNumericValue(cellValue),
                element: cell,
                columnName: this.tableState.columnHeaders[cellIndex]?.name || `Column ${cellIndex}`
            });
        });

        return rowData;
    }

    /**
     * Smart data type detection for columns
     */
    detectDataType(columnName) {
        const lowerName = columnName.toLowerCase();

        if (lowerName.includes('lat') || lowerName.includes('latitude')) return 'latitude';
        if (lowerName.includes('long') || lowerName.includes('longitude')) return 'longitude';
        if (lowerName.includes('depth') || lowerName.includes('meters') || lowerName.includes('rise')) return 'depth';
        if (lowerName.includes('exposure') || lowerName.includes('stress') || lowerName.includes('%')) return 'percentage';
        if (lowerName.includes('windspeed') || lowerName.includes('km/h')) return 'speed';
        if (lowerName.includes('days')) return 'count';
        if (lowerName.includes('temperature') || lowerName.includes('celsius') || lowerName.includes('°')) return 'temperature';
        if (lowerName.includes('factor') || lowerName.includes('safety')) return 'factor';

        return 'text';
    }

    /**
     * Optimized numeric value parsing
     */
    parseNumericValue(text) {
        const cleanText = text.replace(/[^\d.-]/g, '');
        const numValue = parseFloat(cleanText);
        return isNaN(numValue) ? null : numValue;
    }

    /**
     * Optimized rendering with virtual pagination
     */
    renderTable(page = 1) {
        const startTime = performance.now();

        console.log(`🎨 [Dev Table Manager] Rendering page ${page}...`);

        const startIndex = (page - 1) * this.tableState.rowsPerPage;
        const endIndex = Math.min(startIndex + this.tableState.rowsPerPage, this.tableState.filteredRows.length);

        // Hide all rows first
        this.tableState.allRows.forEach(rowData => {
            $(rowData.element).hide();
        });

        // Show rows for current page
        for (let i = startIndex; i < endIndex; i++) {
            const rowData = this.tableState.filteredRows[i];
            if (rowData) {
                $(rowData.element).show();

                // Show child rows if parent is expanded
                if (rowData.rowType === 'polygon_parent' && rowData.expanded) {
                    this.showChildRows(rowData);
                }
            }
        }

        this.performanceMetrics.renderTime = performance.now() - startTime;
        console.log(`✅ [Dev Table Manager] Rendered ${endIndex - startIndex} rows in ${this.performanceMetrics.renderTime.toFixed(2)}ms`);

        this.updatePaginationInfo();
    }

    /**
     * Show child rows for expanded parent
     */
    showChildRows(parentRow) {
        const parentName = this.getRowFacilityName(parentRow);
        const childRows = this.tableState.childRows.filter(child =>
            this.isChildOfParent(child, parentName)
        );

        childRows.forEach(childRow => {
            $(childRow.element).show();
        });
    }

    /**
     * Enhanced search with debouncing and multi-column support
     */
    setupEnhancedSearch() {
        let searchTimeout;

        $('#table-search').off('input').on('input', (e) => {
            clearTimeout(searchTimeout);
            const searchTerm = $(e.target).val().trim();

            searchTimeout = setTimeout(() => {
                this.performOptimizedSearch(searchTerm);
            }, 300); // Debounce for performance
        });
    }

    /**
     * Optimized search implementation
     */
    performOptimizedSearch(searchTerm) {
        const startTime = performance.now();

        if (!searchTerm) {
            this.tableState.filteredRows = [...this.tableState.allRows];
        } else {
            const lowerSearchTerm = searchTerm.toLowerCase();
            this.tableState.filteredRows = this.tableState.allRows.filter(rowData => {
                return rowData.cells.some(cell =>
                    cell.value.toLowerCase().includes(lowerSearchTerm)
                );
            });
        }

        this.performanceMetrics.filterTime = performance.now() - startTime;
        console.log(`🔍 [Dev Table Manager] Filtered ${this.tableState.filteredRows.length} rows in ${this.performanceMetrics.filterTime.toFixed(2)}ms`);

        this.tableState.currentPage = 1;
        this.renderTable(1);
    }

    /**
     * Optimized sorting with type-aware comparison
     */
    sortTable(columnName) {
        const startTime = performance.now();
        const column = this.tableState.columnHeaders.find(col => col.name === columnName);

        if (!column) return;

        // Toggle sort direction
        if (this.tableState.sortColumn === columnName) {
            this.tableState.sortDirection = this.tableState.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.tableState.sortColumn = columnName;
            this.tableState.sortDirection = 'asc';
        }

        const columnIndex = column.index;

        this.tableState.filteredRows.sort((a, b) => {
            const aValue = a.cells[columnIndex]?.numericValue || a.cells[columnIndex]?.value || '';
            const bValue = b.cells[columnIndex]?.numericValue || b.cells[columnIndex]?.value || '';

            // Type-aware sorting
            if (column.dataType !== 'text' && typeof aValue === 'number' && typeof bValue === 'number') {
                return this.tableState.sortDirection === 'asc' ? aValue - bValue : bValue - aValue;
            } else {
                const aStr = String(aValue).toLowerCase();
                const bStr = String(bValue).toLowerCase();
                const comparison = aStr.localeCompare(bStr);
                return this.tableState.sortDirection === 'asc' ? comparison : -comparison;
            }
        });

        this.performanceMetrics.sortTime = performance.now() - startTime;
        console.log(`📊 [Dev Table Manager] Sorted by ${columnName} in ${this.performanceMetrics.sortTime.toFixed(2)}ms`);

        this.renderTable(this.tableState.currentPage);
    }

    /**
     * Development utilities for debugging
     */
    addDevUtilities() {
        // Add dev controls panel
        const devPanel = $(`
            <div id="dev-table-controls" style="position: fixed; top: 10px; right: 10px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; padding: 15px; z-index: 1000; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h6 style="margin: 0 0 10px 0; font-weight: bold;">🛠️ Dev Table Controls</h6>
                <div style="font-size: 12px;">
                    <div>Rows: ${this.tableState.allRows.length} | Parents: ${this.tableState.parentRows.length} | Children: ${this.tableState.childRows.length}</div>
                    <div>Init: ${this.performanceMetrics.initTime.toFixed(2)}ms</div>
                    <button onclick="window.devTableManager.exportData()" style="margin-top: 5px; padding: 2px 8px; font-size: 11px;">Export Data</button>
                    <button onclick="window.devTableManager.showPerformanceMetrics()" style="margin-top: 5px; padding: 2px 8px; font-size: 11px;">Metrics</button>
                    <button onclick="window.devTableManager.toggleDebugMode()" style="margin-top: 5px; padding: 2px 8px; font-size: 11px;">Debug</button>
                </div>
            </div>
        `);

        $('body').append(devPanel);

        // Make globally accessible
        window.devTableManager = this;
    }

    /**
     * Export table data for debugging
     */
    exportData() {
        const exportData = {
            timestamp: new Date().toISOString(),
            tableState: this.tableState,
            performanceMetrics: this.performanceMetrics,
            columnHeaders: this.tableState.columnHeaders,
            parentRows: this.tableState.parentRows.map(row => ({
                facility: this.getRowFacilityName(row),
                type: row.rowType,
                cellCount: row.cells.length
            }))
        };

        const dataStr = JSON.stringify(exportData, null, 2);
        const dataBlob = new Blob([dataStr], {type: 'application/json'});
        const url = URL.createObjectURL(dataBlob);

        const link = document.createElement('a');
        link.href = url;
        link.download = `polygon-table-data-${Date.now()}.json`;
        link.click();

        URL.revokeObjectURL(url);
        console.log('📁 [Dev Table Manager] Data exported successfully');
    }

    /**
     * Show performance metrics
     */
    showPerformanceMetrics() {
        console.table(this.performanceMetrics);
        alert(`Performance Metrics:\nInit: ${this.performanceMetrics.initTime.toFixed(2)}ms\nRender: ${this.performanceMetrics.renderTime.toFixed(2)}ms\nSort: ${this.performanceMetrics.sortTime.toFixed(2)}ms\nFilter: ${this.performanceMetrics.filterTime.toFixed(2)}ms`);
    }

    /**
     * Toggle debug mode
     */
    toggleDebugMode() {
        this.debugMode = !this.debugMode;
        console.log(`🐛 [Dev Table Manager] Debug mode ${this.debugMode ? 'ENABLED' : 'DISABLED'}`);

        if (this.debugMode) {
            this.addDebugOverlays();
        } else {
            this.removeDebugOverlays();
        }
    }

    /**
     * Add debug overlays to table
     */
    addDebugOverlays() {
        this.tableState.parentRows.forEach((row, index) => {
            const $row = $(row.element);
            $row.attr('title', `Debug: Parent row ${index + 1}, Type: ${row.rowType}`);
            $row.css('border-left', '3px solid #007bff');
        });

        this.tableState.childRows.forEach((row, index) => {
            const $row = $(row.element);
            $row.attr('title', `Debug: Child row ${index + 1}, Type: ${row.rowType}`);
            $row.css('border-left', '3px solid #28a745');
        });
    }

    /**
     * Remove debug overlays
     */
    removeDebugOverlays() {
        $(`#${this.tableId} tbody tr`).css('border-left', '').removeAttr('title');
    }

    /**
     * Auto-expand first polygon for debugging
     */
    autoExpandFirstPolygon() {
        if (this.tableState.parentRows.length > 0) {
            const firstParent = this.tableState.parentRows[0];
            console.log('🔄 [Dev Table Manager] Auto-expanding first polygon:', this.getRowFacilityName(firstParent));

            const $expandBtn = $(firstParent.element).find('.expand-collapse-btn');
            if ($expandBtn.length > 0) {
                $expandBtn.click();
            }
        }
    }

    /**
     * Helper functions
     */
    getRowFacilityName(rowData) {
        const facilityCell = rowData.cells.find(cell => cell.columnName === 'Facility');
        return facilityCell ? facilityCell.value : '';
    }

    isChildOfParent(childRow, parentName) {
        const childElement = $(childRow.element);
        return childElement.attr('data-parent-id') === parentName ||
               childElement.attr('data-parent-facility') === parentName ||
               childElement.attr('data-facility-name') === parentName;
    }

    setupOptimizedPagination() {
        // Implementation for pagination controls
        console.log('📄 [Dev Table Manager] Setting up optimized pagination...');
    }

    setupColumnSelector() {
        // Implementation for column visibility controls
        console.log('👁️ [Dev Table Manager] Setting up column selector...');
    }

    updatePaginationInfo() {
        const totalPages = Math.ceil(this.tableState.filteredRows.length / this.tableState.rowsPerPage);
        console.log(`📄 [Dev Table Manager] Page ${this.tableState.currentPage} of ${totalPages} (${this.tableState.filteredRows.length} total rows)`);
    }
}

// Initialize when DOM is ready
$(document).ready(function() {
    console.log('🚀 [Dev Table Manager] Document ready, initializing optimized table manager...');

    // Wait a bit for other scripts to load
    setTimeout(() => {
        if (typeof window.devTableManager === 'undefined') {
            window.devTableManager = new DevOptimizedTableManager();
            window.devTableManager.initialize();
        }
    }, 1000);
});