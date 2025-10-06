// Initialize column selector functionality for sensitivity results
$(document).ready(function() {
    console.log("Initializing sensitivity column selector");

    // Helper function to safely update column visibility
    function safeUpdateColumnVisibility() {
        // Try using the utility function first
        if (typeof window.sensitivityTableUtils !== 'undefined' && window.sensitivityTableUtils.updateColumns) {
            window.sensitivityTableUtils.updateColumns().catch(function(error) {
                console.warn("Error using utility function, trying fallback:", error);
                fallbackUpdateColumnVisibility();
            });
        } else if (typeof dtStateManager !== 'undefined' && dtStateManager.isReady('sensitivity-data-table')) {
            // Use state manager for ready tables
            dtStateManager.whenReady('sensitivity-data-table', function(dataTable, element) {
                if (typeof updateColumnVisibility === 'function') {
                    updateColumnVisibility();
                } else {
                    console.warn("updateColumnVisibility function not available");
                }
            }, { name: 'updateColumnVisibility' }).catch(function(error) {
                console.error("Error updating column visibility via state manager:", error);
                fallbackUpdateColumnVisibility();
            });
        } else {
            fallbackUpdateColumnVisibility();
        }
    }

    // Fallback column visibility update
    function fallbackUpdateColumnVisibility() {
        console.log("Using fallback column visibility update");
        setTimeout(function() {
            if (typeof updateColumnVisibility === 'function') {
                updateColumnVisibility();
            } else {
                console.warn("updateColumnVisibility function not available, using basic visibility");
                updateBasicColumnVisibility();
            }
        }, 200);
    }

    // Basic column visibility for when DataTables is not available
    function updateBasicColumnVisibility() {
        const visibleColumns = new Set(['Facility', 'Asset Archetype']);

        $('.hazard-column').each(function() {
            const columnName = $(this).data('column');
            if ($(this).prop('checked')) {
                visibleColumns.add(columnName);
            }
        });

        // Hide/show columns in all header rows and body
        $('#sensitivity-data-table thead tr.custom-table-header th').each(function(index) {
            const headerText = $(this).text().trim();
            const shouldShow = visibleColumns.has(headerText);

            $(this).toggle(shouldShow);

            // Also hide corresponding body cells
            $(`#sensitivity-data-table tbody tr td:nth-child(${index + 1})`).toggle(shouldShow);
        });

        // Try to update group header colspans if function is available
        if (typeof updateGroupHeaderColspans === 'function') {
            setTimeout(updateGroupHeaderColspans, 50);
        }
    }

    // Update hazard group checkbox handler
    $('.hazard-group').on('change', function() {
        const isChecked = $(this).prop('checked');
        const hazardClass = $(this).data('hazard');

        console.log(`Group checkbox changed: ${hazardClass}, checked: ${isChecked}`);

        // Update all child checkboxes without triggering individual change events
        $(`.hazard-column.${hazardClass}`).prop('checked', isChecked);

        // Update parent states and column visibility
        updateParentCheckboxes();

        // Safely update column visibility
        safeUpdateColumnVisibility();
    });

    // Individual column checkbox handler
    $('.hazard-column').on('change', function() {
        const columnName = $(this).data('column');
        const isChecked = $(this).prop('checked');

        console.log(`Column checkbox changed: ${columnName}, checked: ${isChecked}`);

        // Update parent checkbox state
        updateParentCheckboxState($(this));

        // Safely update column visibility
        safeUpdateColumnVisibility();
    });

    // Make show/hide all buttons more reliable using delegated events
    $(document).off('click', '#show-all-columns');
    $(document).on('click', '#show-all-columns', function(e) {
        e.preventDefault();
        console.log("Show all columns clicked");

        $('.hazard-column').prop('checked', true);
        updateParentCheckboxes();

        // Safely update column visibility
        safeUpdateColumnVisibility();
    });

    $(document).off('click', '#hide-all-columns');
    $(document).on('click', '#hide-all-columns', function(e) {
        e.preventDefault();
        console.log("Hide all columns clicked");

        $('.hazard-column').prop('checked', false);
        updateParentCheckboxes();

        // Safely update column visibility
        safeUpdateColumnVisibility();
    });

    // Helper function to update a specific parent checkbox state
    function updateParentCheckboxState(changedCheckbox) {
        const hazardClasses = changedCheckbox.attr('class').split(' ').filter(cls =>
            cls !== 'form-check-input' && cls !== 'hazard-column');

        hazardClasses.forEach(function(hazardClass) {
            const parentCheckbox = $(`[data-hazard="${hazardClass}"]`);
            const childCheckboxes = $(`.hazard-column.${hazardClass}`);
            const checkedChilds = $(`.hazard-column.${hazardClass}:checked`);

            parentCheckbox.prop('checked', checkedChilds.length > 0);
            parentCheckbox.prop('indeterminate',
                checkedChilds.length > 0 && checkedChilds.length < childCheckboxes.length);
        });
    }

    // Helper function to update all parent checkbox states
    function updateParentCheckboxes() {
        $('.hazard-group').each(function() {
            const hazardClass = $(this).data('hazard');
            const childCheckboxes = $(`.hazard-column.${hazardClass}`);
            const checkedChilds = $(`.hazard-column.${hazardClass}:checked`);

            $(this).prop('checked', checkedChilds.length > 0);
            $(this).prop('indeterminate',
                checkedChilds.length > 0 && checkedChilds.length < childCheckboxes.length);
        });
    }

    // Initialize default state - ensure essential columns are always visible
    function initializeDefaultState() {
        console.log("Setting up initial column visibility");

        // Ensure Facility and Asset Archetype are always checked and visible
        $('.hazard-column[data-column="Facility"], .hazard-column[data-column="Asset Archetype"]').prop('checked', true);
        updateParentCheckboxes();

        // Safely update column visibility
        safeUpdateColumnVisibility();
    }

    // Try to initialize immediately, but also queue for when DataTables is ready
    if (typeof dtStateManager !== 'undefined') {
        dtStateManager.whenReady('sensitivity-data-table', function() {
            initializeDefaultState();
        }, { name: 'initializeDefaultState' }).catch(function(error) {
            console.warn("DataTables not ready, using timeout fallback:", error);
            setTimeout(initializeDefaultState, 200);
        });
    } else {
        // Fallback if state manager not available
        setTimeout(initializeDefaultState, 200);
    }
});