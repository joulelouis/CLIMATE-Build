/**
 * Progressive loading system for large climate hazard datasets
 * Implements virtual scrolling, lazy loading, and performance optimization
 */

class ProgressiveTableLoader {
    constructor(options = {}) {
        this.options = {
            chunkSize: 50,           // Number of rows to load at once
            preloadChunks: 2,        // Number of chunks to preload ahead
            threshold: 200,          // Pixels from bottom to trigger loading
            maxCacheSize: 1000,      // Maximum rows to keep in memory
            enableVirtualScroll: true,
            ...options
        };

        this.data = [];
        this.displayedRows = [];
        this.loadedChunks = new Set();
        this.isLoading = false;
        this.container = null;
        this.scrollTop = 0;
        this.containerHeight = 0;
        this.rowHeight = 40; // Estimated row height in pixels
        this.totalHeight = 0;
        this.visibleRange = { start: 0, end: 0 };

        this.bindEvents();
    }

    bindEvents() {
        this.onScroll = this.throttle(this.handleScroll.bind(this), 16); // 60fps
        this.onResize = this.throttle(this.handleResize.bind(this), 100);
    }

    initialize(container, data) {
        console.log('Initializing progressive table loader...');

        this.container = container;
        this.data = data || [];

        if (!this.container) {
            throw new Error('Container element is required');
        }

        // Setup container
        this.setupContainer();

        // Calculate total height
        this.totalHeight = this.data.length * this.rowHeight;

        // Load initial chunk
        this.loadInitialChunk();

        // Setup event listeners
        this.container.addEventListener('scroll', this.onScroll);
        window.addEventListener('resize', this.onResize);

        console.log(`Progressive loader initialized with ${this.data.length} total rows`);
    }

    setupContainer() {
        // Create virtual scroll container structure
        const wrapper = document.createElement('div');
        wrapper.className = 'virtual-scroll-wrapper';
        wrapper.style.height = '600px';
        wrapper.style.overflow = 'auto';
        wrapper.style.position = 'relative';

        const spacer = document.createElement('div');
        spacer.className = 'virtual-scroll-spacer';
        spacer.style.height = `${this.totalHeight}px`;
        spacer.style.position = 'absolute';
        spacer.style.top = '0';
        spacer.style.width = '1px';

        const content = document.createElement('div');
        content.className = 'virtual-scroll-content';
        content.style.position = 'absolute';
        content.style.top = '0';
        content.style.width = '100%';

        // Move existing table content to virtual container
        const table = this.container.querySelector('table');
        if (table) {
            const tbody = table.querySelector('tbody');
            if (tbody) {
                content.appendChild(tbody);
            }
            wrapper.appendChild(spacer);
            wrapper.appendChild(content);
            this.container.innerHTML = '';
            this.container.appendChild(wrapper);
        }

        this.virtualWrapper = wrapper;
        this.virtualSpacer = spacer;
        this.virtualContent = content;
    }

    loadInitialChunk() {
        const initialChunk = Math.min(this.options.chunkSize, this.data.length);
        this.displayedRows = this.data.slice(0, initialChunk);
        this.loadedChunks.add(0);
        this.renderRows(0, initialChunk);
    }

    handleScroll() {
        if (!this.options.enableVirtualScroll) return;

        const scrollTop = this.virtualWrapper.scrollTop;
        const containerHeight = this.virtualWrapper.clientHeight;

        // Calculate visible range
        const startRow = Math.floor(scrollTop / this.rowHeight);
        const visibleRowCount = Math.ceil(containerHeight / this.rowHeight);
        const endRow = Math.min(startRow + visibleRowCount + this.options.preloadChunks * this.options.chunkSize, this.data.length);

        // Check if we need to load more data
        if (endRow > this.displayedRows.length && !this.isLoading) {
            this.loadMoreData(endRow);
        }

        // Update visible content position
        this.updateVisibleContent(startRow);
    }

    handleResize() {
        this.containerHeight = this.virtualWrapper.clientHeight;
        this.handleScroll();
    }

    loadMoreData(targetRow) {
        if (this.isLoading || targetRow >= this.data.length) return;

        this.isLoading = true;
        this.showLoadingIndicator();

        // Simulate async loading (in real implementation, this might be an API call)
        setTimeout(() => {
            const currentLength = this.displayedRows.length;
            const newRows = this.data.slice(currentLength, targetRow);

            this.displayedRows.push(...newRows);
            this.renderRows(currentLength, targetRow);

            this.isLoading = false;
            this.hideLoadingIndicator();

            console.log(`Loaded ${newRows.length} additional rows (total: ${this.displayedRows.length})`);
        }, 100);
    }

    renderRows(startIndex, endIndex) {
        const tbody = this.virtualContent.querySelector('tbody') || document.createElement('tbody');

        for (let i = startIndex; i < endIndex && i < this.data.length; i++) {
            if (this.loadedChunks.has(Math.floor(i / this.options.chunkSize))) continue;

            const row = this.data[i];
            const tr = this.createTableRow(row, i);
            tbody.appendChild(tr);
        }

        if (!this.virtualContent.contains(tbody)) {
            this.virtualContent.appendChild(tbody);
        }

        // Mark chunk as loaded
        const chunkIndex = Math.floor(startIndex / this.options.chunkSize);
        this.loadedChunks.add(chunkIndex);
    }

    createTableRow(rowData, index) {
        const tr = document.createElement('tr');
        tr.className = 'custom-table-row';
        tr.style.height = `${this.rowHeight}px`;
        tr.setAttribute('data-row-index', index);

        // Create cells based on current column visibility
        const visibleColumns = this.getVisibleColumns();

        visibleColumns.forEach(columnName => {
            const td = document.createElement('td');
            const value = rowData[columnName] || 'N/A';

            // Apply styling based on column type and value
            const styledContent = this.styleCellValue(value, columnName);
            td.innerHTML = styledContent;

            // Add editable functionality if applicable
            if (this.isEditableColumn(columnName)) {
                td.classList.add('editable-cell');
                td.setAttribute('data-column', columnName);
                td.setAttribute('data-row', index);
                td.setAttribute('data-original-value', value);
            }

            tr.appendChild(td);
        });

        return tr;
    }

    getVisibleColumns() {
        // Get currently visible columns from column selector
        const visibleColumns = ['Facility']; // Always show facility column

        document.querySelectorAll('.base-column:checked, .hazard-column:checked').forEach(checkbox => {
            const columnName = checkbox.getAttribute('data-column');
            if (columnName) {
                visibleColumns.push(columnName);
            }
        });

        return visibleColumns;
    }

    styleCellValue(value, columnName) {
        // Apply the same styling logic as the original table
        if (columnName.startsWith('Water Stress Exposure') && value !== 'N/A') {
            const val = parseFloat(value);
            if (val < 10) {
                return `<span style="color: green; font-weight: bold;">${value}</span>`;
            } else if (val >= 10 && val <= 30) {
                return `<span style="color: orange; font-weight: bold;">${value}</span>`;
            } else if (val > 30) {
                return `<span style="color: red; font-weight: bold;">${value}</span>`;
            }
        }

        // Add other styling rules as needed...
        return value;
    }

    isEditableColumn(columnName) {
        // Facility and Asset Archetype are not editable
        return columnName !== 'Facility' && columnName !== 'Asset Archetype';
    }

    updateVisibleContent(startRow) {
        const offsetY = startRow * this.rowHeight;
        this.virtualContent.style.transform = `translateY(${offsetY}px)`;

        // Hide rows that are outside visible range for performance
        const visibleRowCount = Math.ceil(this.containerHeight / this.rowHeight) + 10; // Buffer
        const rows = this.virtualContent.querySelectorAll('tr');

        rows.forEach((row, index) => {
            const rowIndex = parseInt(row.getAttribute('data-row-index'));
            if (rowIndex < startRow - 5 || rowIndex > startRow + visibleRowCount) {
                row.style.display = 'none';
            } else {
                row.style.display = '';
            }
        });
    }

    showLoadingIndicator() {
        if (!this.loadingIndicator) {
            this.loadingIndicator = document.createElement('div');
            this.loadingIndicator.className = 'text-center py-3';
            this.loadingIndicator.innerHTML = `
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div class="mt-2">Loading more data...</div>
            `;
        }

        this.virtualWrapper.appendChild(this.loadingIndicator);
    }

    hideLoadingIndicator() {
        if (this.loadingIndicator && this.loadingIndicator.parentNode) {
            this.loadingIndicator.parentNode.removeChild(this.loadingIndicator);
        }
    }

    // Utility function for throttling
    throttle(func, delay) {
        let timeoutId;
        let lastExecTime = 0;
        return function (...args) {
            const currentTime = Date.now();

            if (currentTime - lastExecTime > delay) {
                func.apply(this, args);
                lastExecTime = currentTime;
            } else {
                clearTimeout(timeoutId);
                timeoutId = setTimeout(() => {
                    func.apply(this, args);
                    lastExecTime = Date.now();
                }, delay - (currentTime - lastExecTime));
            }
        };
    }

    // Cleanup method
    destroy() {
        if (this.virtualWrapper) {
            this.virtualWrapper.removeEventListener('scroll', this.onScroll);
        }
        window.removeEventListener('resize', this.onResize);

        // Clear memory
        this.data = [];
        this.displayedRows = [];
        this.loadedChunks.clear();
    }
}

// Progressive image loader for map tiles and other assets
class ProgressiveImageLoader {
    constructor() {
        this.loadedImages = new Set();
        this.loadingImages = new Map();
        this.observer = null;
        this.setupIntersectionObserver();
    }

    setupIntersectionObserver() {
        if ('IntersectionObserver' in window) {
            this.observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        this.loadImage(entry.target);
                        this.observer.unobserve(entry.target);
                    }
                });
            }, {
                rootMargin: '50px'
            });
        }
    }

    loadImage(img) {
        const src = img.dataset.src;
        if (!src || this.loadedImages.has(src)) return;

        if (this.loadingImages.has(src)) {
            // If already loading, add to callbacks
            this.loadingImages.get(src).push(img);
            return;
        }

        this.loadingImages.set(src, [img]);

        // Create temporary image to test loading
        const tempImg = new Image();
        tempImg.onload = () => {
            this.loadedImages.add(src);
            const images = this.loadingImages.get(src) || [];
            images.forEach(image => {
                image.src = src;
                image.classList.add('loaded');
            });
            this.loadingImages.delete(src);
        };

        tempImg.onerror = () => {
            console.warn(`Failed to load image: ${src}`);
            const images = this.loadingImages.get(src) || [];
            images.forEach(image => {
                image.classList.add('failed');
                if (image.dataset.fallback) {
                    image.src = image.dataset.fallback;
                }
            });
            this.loadingImages.delete(src);
        };

        tempImg.src = src;
    }

    observe(img) {
        if (this.observer) {
            this.observer.observe(img);
        } else {
            // Fallback for browsers without IntersectionObserver
            this.loadImage(img);
        }
    }
}

// Performance monitor
class PerformanceMonitor {
    constructor() {
        this.metrics = {
            tableRenderTime: 0,
            memoryUsage: 0,
            visibleRows: 0,
            totalRows: 0
        };
        this.startTime = 0;
    }

    startMeasurement() {
        this.startTime = performance.now();
    }

    endMeasurement(operation) {
        const duration = performance.now() - this.startTime;
        this.metrics[operation] = duration;
        console.log(`${operation} took ${duration.toFixed(2)}ms`);
    }

    measureMemoryUsage() {
        if (performance.memory) {
            this.metrics.memoryUsage = performance.memory.usedJSHeapSize / 1024 / 1024; // MB
            console.log(`Memory usage: ${this.metrics.memoryUsage.toFixed(2)}MB`);
        }
    }

    getMetrics() {
        return { ...this.metrics };
    }
}

// Export classes
window.ProgressiveTableLoader = ProgressiveTableLoader;
window.ProgressiveImageLoader = ProgressiveImageLoader;
window.PerformanceMonitor = PerformanceMonitor;