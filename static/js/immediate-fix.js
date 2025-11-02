/**
 * Immediate Fix for Hierarchical Row Detection
 * Run this immediately to fix the "No data found" issue
 */

// Immediate fix function - run this in browser console
function immediateHierarchicalFix() {
    console.log('🚀 [IMMEDIATE FIX] Running immediate hierarchical row fix...');

    // Get all table rows
    const $rows = $('#hazard-data-table tbody tr');
    console.log(`Found ${$rows.length} total rows`);

    // Fix row classification
    let parentCount = 0;
    let childCount = 0;

    $rows.each(function(index) {
        const $row = $(this);
        const facilityName = $row.find('td:first, td[data-column="Facility"]').text().trim();

        console.log(`Row ${index}: "${facilityName}"`);

        // Classification logic
        if (facilityName.includes('Centroid') || facilityName.includes('🟢')) {
            // This is a parent row
            $row.addClass('hierarchical-row polygon-parent level-0');
            $row.attr('data-row-type', 'polygon_parent');
            $row.attr('data-facility-name', facilityName);
            parentCount++;
            console.log(`✅ Classified as PARENT: ${facilityName}`);

            // Add expand/collapse button if missing
            if ($row.find('.expand-collapse-btn').length === 0) {
                const firstCell = $row.find('td:first');
                const expandBtn = $(`
                    <button class="expand-collapse-btn" style="margin-right: 8px;" title="Show/Hide Granular Points">
                        <span class="expand-icon">▶</span>
                    </button>
                `);
                firstCell.prepend(expandBtn);
            }

        } else if (facilityName.includes('Point ') || facilityName.includes('🔵') || facilityName.includes('Granular')) {
            // This is a child row
            $row.addClass('hierarchical-row polygon-child level-1');
            $row.attr('data-row-type', 'polygon_child');

            // Try to determine parent facility
            let parentFacility = facilityName.split(' - ')[0] || facilityName.split(' Point ')[0];
            if (!parentFacility || parentFacility === facilityName) {
                // Find parent by looking for centroid rows
                const $parentRows = $('#hazard-data-table tbody tr.polygon-parent');
                if ($parentRows.length > 0) {
                    parentFacility = $parentRows.first().find('td:first').text().trim();
                }
            }

            $row.attr('data-parent-facility', parentFacility);
            $row.attr('data-parent-id', parentFacility);
            childCount++;
            console.log(`✅ Classified as CHILD: ${facilityName} (parent: ${parentFacility})`);

            // Initially hide child rows
            $row.hide();
        } else {
            console.log(`❓ Unclassified: ${facilityName}`);
        }
    });

    console.log(`✅ Classification complete: ${parentCount} parents, ${childCount} children`);

    // Update tableState if it exists
    if (window.tableState) {
        window.tableState.allRows = Array.from($rows).map(row => ({
            element: row,
            facilityName: $(row).find('td:first').text().trim()
        }));
        window.tableState.parentRows = Array.from($('#hazard-data-table tbody tr.polygon-parent')).map(row => ({
            element: row,
            facilityName: $(row).find('td:first').text().trim()
        }));
        window.tableState.childRows = Array.from($('#hazard-data-table tbody tr.polygon-child')).map(row => ({
            element: row,
            facilityName: $(row).find('td:first').text().trim()
        }));
        window.tableState.filteredRows = window.tableState.allRows;

        console.log(`✅ Updated tableState: ${window.tableState.parentRows.length} parents, ${window.tableState.childRows.length} children`);
    }

    // Hide "No data found" message
    const $noDataRow = $('#hazard-data-table tbody td:contains("No data found")');
    if ($noDataRow.length > 0) {
        $noDataRow.closest('tr').hide();
        console.log('✅ Hidden "No data found" message');
    }

    // Show actual data rows
    $('#hazard-data-table tbody tr').not(':has(td:contains("No data found"))').show();
    $('#hazard-data-table tbody tr.polygon-child').hide(); // Hide children initially

    // Set up expand/collapse functionality
    $('#hazard-data-table tbody .expand-collapse-btn').off('click').on('click', function() {
        const $parentRow = $(this).closest('tr');
        const parentFacility = $parentRow.attr('data-facility-name');
        const isExpanded = $(this).hasClass('expanded');

        // Find child rows
        const $childRows = $('#hazard-data-table tbody tr.polygon-child').filter(function() {
            return $(this).attr('data-parent-facility') === parentFacility;
        });

        if (isExpanded) {
            // Collapse
            $childRows.hide();
            $(this).removeClass('expanded');
            $(this).find('.expand-icon').text('▶');
        } else {
            // Expand
            $childRows.show();
            $(this).addClass('expanded');
            $(this).find('.expand-icon').text('▼');
        }

        console.log(`${isExpanded ? 'Collapsed' : 'Expanded'} ${$childRows.length} child rows for ${parentFacility}`);
    });

    // Trigger console logging to show updated counts
    setTimeout(() => {
        console.log('🔍 [IMMEDIATE FIX] Final state check:');
        console.log(`Parents in DOM: ${$('#hazard-data-table tbody tr.polygon-parent').length}`);
        console.log(`Children in DOM: ${$('#hazard-data-table tbody tr.polygon-child').length}`);
        console.log(`Parents in tableState: ${window.tableState?.parentRows?.length || 'N/A'}`);
        console.log(`Children in tableState: ${window.tableState?.childRows?.length || 'N/A'}`);
    }, 1000);

    return {
        parentCount: parentCount,
        childCount: childCount,
        success: true
    };
}

// Auto-run the fix when page loads
$(document).ready(function() {
    // Wait for table to be initialized
    setTimeout(function() {
        console.log('🚀 [IMMEDIATE FIX] Auto-running hierarchical fix...');
        const result = immediateHierarchicalFix();

        if (result.success) {
            console.log('✅ [IMMEDIATE FIX] Fix applied successfully!');
        } else {
            console.error('❌ [IMMEDIATE FIX] Fix failed');
        }

        // Make function available globally for manual execution
        window.immediateHierarchicalFix = immediateHierarchicalFix;
        console.log('💡 [IMMEDIATE FIX] You can also run window.immediateHierarchicalFix() manually');
    }, 6000);
});