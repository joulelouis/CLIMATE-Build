/**
 * Main Page Utility Functions
 * Provides core functionality for the climate hazards analysis main page
 */

// Preview file function - will be properly configured after page load
window.previewFile = function() {
    console.log("previewFile called");

    // Show loading indicator while fetching
    const loadingEl = document.getElementById('preview-loading');
    const containerEl = document.getElementById('preview-table-container');

    if (loadingEl) loadingEl.style.display = 'block';
    if (containerEl) containerEl.style.display = 'none';

    // Get the preview URL from the page's data attribute or fallback
    const dataDiv = document.getElementById('main-page-data');
    const previewUrl = (dataDiv && dataDiv.getAttribute('data-preview-url')) ||
                      '/climate-hazards-analysis-v2/api/preview-upload/';

    fetch(previewUrl)
        .then(function(response) {
            if (!response.ok) {
                throw new Error('No uploaded file found');
            }
            return response.text();
        })
        .then(function(fileData) {
            if (loadingEl) loadingEl.style.display = 'none';
            if (containerEl) containerEl.style.display = 'block';

            var lines = fileData.split("\n");
            var headerHtml = "";
            var bodyHtml = "";

            if (lines.length > 0) {
                var headers = lines[0].split(",");
                headerHtml += headers.map(function(header) {
                    return "<th>" + header.trim() + "</th>";
                }).join("");
            }

            for (var i = 1; i < lines.length; i++) {
                if (lines[i].trim() === "") continue;
                var cells = lines[i].split(",");
                var rowHtml = cells.map(function(cell) {
                    return "<td>" + cell.trim() + "</td>";
                }).join("");
                bodyHtml += "<tr>" + rowHtml + "</tr>";
            }

            const headerEl = document.getElementById("preview-table-header");
            const bodyEl = document.getElementById("preview-table-body");

            if (headerEl) headerEl.innerHTML = headerHtml;
            if (bodyEl) bodyEl.innerHTML = bodyHtml;
        })
        .catch(function(error) {
            if (loadingEl) loadingEl.style.display = 'none';
            alert('Preview Error: ' + (error.message || 'No uploaded file found'));
            console.error('Preview error:', error);
        });
};

window.proceedToSelectHazards = function() {
    console.log("proceedToSelectHazards called");

    try {
        // Update the progress steps
        const stepItems = document.querySelectorAll('.step-item');
        if (stepItems.length > 1) {
            const step2 = stepItems[1];
            const circle = step2.querySelector('.step-circle');
            const label = step2.querySelector('.step-label');

            if (circle) {
                circle.style.backgroundColor = '#F1D500';
                circle.style.color = '#000';
            }
            if (label) {
                label.style.color = '#000';
            }
        }

        // Navigate to the hazard selection page
        const dataDiv = document.getElementById('main-page-data');
        const selectHazardsUrl = (dataDiv && dataDiv.getAttribute('data-select-hazards-url')) ||
                               '/climate-hazards-analysis-v2/select-hazards/';
        window.location.href = selectHazardsUrl;
    } catch (error) {
        console.error('Error in proceedToSelectHazards:', error);
        alert('Navigation error. Please try again.');
    }
};

// Clear Site Data function
window.clearSiteData = function() {
    console.log("clearSiteData called");

    // Prevent multiple concurrent calls
    const clearBtn = document.getElementById('clear-site-data-btn');
    if (!clearBtn || clearBtn.disabled) {
        return;
    }

    // Show confirmation dialog using browser confirm
    const userConfirmed = confirm('Are you sure you want to clear all site data? This will remove all uploaded facility files, clear selected hazards, remove analysis results, and reset all progress. This action cannot be undone.');

    if (userConfirmed) {
        window.performClearData().then((result) => {
            // Show success message and reload page
            alert('Site data cleared successfully! Page will reload...');
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        }).catch((error) => {
            alert('Error: ' + (error.message || 'Failed to clear site data. Please try again.'));
            console.error('Clear site data error:', error);
        });
    }
};

// Function to perform the actual data clearing
window.performClearData = async function() {
    const clearBtn = document.getElementById('clear-site-data-btn');
    if (!clearBtn) {
        throw new Error('Clear site data button not found');
    }

    // Show loading state
    const originalText = clearBtn.innerHTML;
    clearBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i><strong>Clearing...</strong>';
    clearBtn.disabled = true;

    try {
        // Get clear site data URL from data attributes
        const dataDiv = document.getElementById('main-page-data');
        const clearSiteDataUrl = (dataDiv && dataDiv.getAttribute('data-clear-site-data-url')) ||
                               '/climate-hazards-analysis-v2/clear-site-data/';

        // Ensure CSRF token is valid before proceeding
        const ensureCSRFToken = async () => {
            try {
                // Use CSRF Manager if available, otherwise fallback to getCookie
                if (window.csrfManager) {
                    const isValid = await window.csrfManager.validateToken();
                    if (!isValid) {
                        throw new Error('CSRF token validation failed');
                    }
                    return window.csrfManager.getCurrentToken();
                } else {
                    // Fallback to original method
                    const token = window.getCookie('csrftoken');
                    if (!token) {
                        throw new Error('CSRF token not found');
                    }
                    return token;
                }
            } catch (error) {
                console.error('CSRF token validation error:', error);
                throw error;
            }
        };

        // Get CSRF token
        const csrfToken = await ensureCSRFToken();

        // Send AJAX request to clear session data
        const response = await fetch(clearSiteDataUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            }
        });

        const data = await response.json();

        if (data.success) {
            // Reset UI elements immediately
            const fileNameEl = document.getElementById('file-name');
            const facilityCsvEl = document.getElementById('facilityCsv');
            if (fileNameEl) fileNameEl.textContent = 'No file chosen';
            if (facilityCsvEl) facilityCsvEl.value = '';

            // Clear map markers and polygons if the function exists
            if (typeof window.clearFacilityMarkers === 'function') {
                window.clearFacilityMarkers();
            }

            // Clear any drawing state
            if (typeof window.draw !== 'undefined') {
                window.draw.deleteAll();
            }
            if (typeof window.isDrawMode !== 'undefined') {
                window.isDrawMode = false;
            }
            if (typeof window.drawnPolygonData !== 'undefined') {
                window.drawnPolygonData = null;
            }

            // Reset draw button state
            const drawButton = document.getElementById('toggle-draw-mode');
            if (drawButton) {
                drawButton.classList.remove('btn-danger');
                drawButton.classList.add('btn-warning');
                drawButton.innerHTML = '<i class="fas fa-draw-polygon"></i> Draw Polygon Asset';
            }

            // Hide drawing instructions
            const instructions = document.getElementById('draw-instructions');
            if (instructions) {
                instructions.style.display = 'none';
            }

            // Hide proceed button
            const proceedBtn = document.getElementById('proceed-button');
            if (proceedBtn) {
                proceedBtn.style.display = 'none';
            }

            // Reset progress steps
            if (typeof window.resetProgressSteps === 'function') {
                window.resetProgressSteps();
            }

            // Return success message
            return data.message || 'Site data cleared successfully!';

        } else {
            // Throw error to be caught by error handler
            throw new Error(data.error || 'Failed to clear site data. Please try again.');
        }

    } catch (error) {
        console.error('Error clearing site data:', error);

        // Re-throw the error for error handler
        if (error.message && error.message.includes('CSRF')) {
            throw new Error('Security token error. Please refresh the page and try again.');
        } else {
            throw new Error('An error occurred while clearing site data. Please try again.');
        }
    } finally {
        // Restore button state after a short delay
        setTimeout(() => {
            if (clearBtn) {
                clearBtn.innerHTML = originalText;
                clearBtn.disabled = false;
            }
        }, 1000);
    }
};

// Helper function to get cookies (fallback)
window.getCookie = function(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
};

// Initialize functions when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log("Main page utilities loaded");

    // Make sure the proceed button is visible
    const proceedBtn = document.getElementById('proceed-button');
    if (proceedBtn) {
        proceedBtn.style.display = 'block';
        console.log("Proceed button display set to block");
    }
});