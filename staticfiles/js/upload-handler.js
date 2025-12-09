/**
 * Enhanced Upload Handler for Asset Data
 * Provides robust file validation, progress tracking, and error handling
 */

class AssetUploadHandler {
    constructor() {
        this.maxFileSize = 50 * 1024 * 1024; // 50MB max file size
        this.allowedTypes = ['.csv', '.xlsx', '.xls', '.zip', '.shp'];
        this.isUploading = false;
        this.retryCount = 0;
        this.maxRetries = 3;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupCSRFProtection();
    }

    setupEventListeners() {
        const fileInput = document.getElementById('facilityCsv');
        const uploadForm = document.getElementById('upload-form');

        if (fileInput) {
            fileInput.addEventListener('change', (e) => this.handleFileSelection(e));
        }

        if (uploadForm) {
            uploadForm.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }

        // Add drag and drop support
        const uploadBox = document.querySelector('.file-upload-box');
        if (uploadBox) {
            this.setupDragAndDrop(uploadBox);
        }
    }

    setupCSRFProtection() {
        // Ensure CSRF token is available for AJAX requests
        if (!window.csrfManager) {
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
        }
    }

    setupDragAndDrop(uploadBox) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadBox.addEventListener(eventName, this.preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadBox.addEventListener(eventName, () => uploadBox.classList.add('drag-over'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadBox.addEventListener(eventName, () => uploadBox.classList.remove('drag-over'), false);
        });

        uploadBox.addEventListener('drop', (e) => this.handleDrop(e), false);
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length > 0) {
            this.validateAndProcessFile(files[0]);
        }
    }

    handleFileSelection(e) {
        const file = e.target.files[0];
        if (file) {
            this.validateAndProcessFile(file);
        }
    }

    validateAndProcessFile(file) {
        const validation = this.validateFile(file);

        if (!validation.valid) {
            this.showError(validation.error);
            return;
        }

        this.updateFileName(file.name);
        this.showFileDetails(file);

        // Auto-submit after validation
        setTimeout(() => {
            this.submitFile(file);
        }, 500);
    }

    validateFile(file) {
        // Check file size
        if (file.size > this.maxFileSize) {
            return {
                valid: false,
                error: `File size too large. Maximum size is ${this.formatFileSize(this.maxFileSize)}.`
            };
        }

        // Check file extension
        const fileName = file.name.toLowerCase();
        const fileExtension = '.' + fileName.split('.').pop();

        if (!this.allowedTypes.includes(fileExtension)) {
            return {
                valid: false,
                error: `Invalid file type. Allowed types: ${this.allowedTypes.join(', ')}`
            };
        }

        // Additional validation for specific file types
        if (fileExtension === '.zip') {
            return this.validateZipFile(file);
        }

        return { valid: true };
    }

    async validateZipFile(file) {
        try {
            // Check if it's a valid ZIP file by reading the first few bytes
            const buffer = await file.slice(0, 4).arrayBuffer();
            const view = new Uint8Array(buffer);

            // ZIP files start with PK (0x50 0x4B)
            if (view[0] !== 0x50 || view[1] !== 0x4B) {
                return {
                    valid: false,
                    error: 'Invalid ZIP file format.'
                };
            }

            return { valid: true };
        } catch (error) {
            return {
                valid: false,
                error: 'Error validating ZIP file: ' + error.message
            };
        }
    }

    updateFileName(fileName) {
        const fileNameDisplay = document.getElementById('file-name');
        if (fileNameDisplay) {
            fileNameDisplay.textContent = fileName;
        }
    }

    showFileDetails(file) {
        const detailsHtml = `
            <div class="file-details mt-2">
                <small class="text-muted">
                    <strong>Size:</strong> ${this.formatFileSize(file.size)} |
                    <strong>Type:</strong> ${file.type || 'Unknown'}
                </small>
            </div>
        `;

        // Add details to upload area
        const uploadArea = document.querySelector('.file-upload-box');
        if (uploadArea) {
            const existingDetails = uploadArea.querySelector('.file-details');
            if (existingDetails) {
                existingDetails.remove();
            }
            uploadArea.insertAdjacentHTML('beforeend', detailsHtml);
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async submitFile(file) {
        if (this.isUploading) {
            this.showError('Upload already in progress. Please wait...');
            return;
        }

        this.isUploading = true;
        this.showProgress();
        this.setUploadButtonState(true);

        const formData = new FormData();
        formData.append('facility_csv', file);
        formData.append('csrfmiddlewaretoken', this.getCSRFToken());

        try {
            await this.uploadWithRetry(formData);
        } catch (error) {
            console.error('Upload failed:', error);
            this.showError('Upload failed: ' + error.message);
            this.hideProgress();
            this.setUploadButtonState(false);
        } finally {
            this.isUploading = false;
        }
    }

    async uploadWithRetry(formData) {
        for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
            try {
                await this.performUpload(formData);
                return; // Success, exit retry loop
            } catch (error) {
                if (attempt === this.maxRetries) {
                    throw error;
                }

                this.updateProgress(`Retrying... (${attempt}/${this.maxRetries})`);
                await this.delay(1000 * attempt); // Exponential backoff
            }
        }
    }

    async performUpload(formData) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();

            // Track upload progress
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    this.updateProgress(`Uploading... ${Math.round(percentComplete)}%`);
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    this.hideProgress();
                    this.showSuccess('File uploaded successfully!');
                    this.reloadPage();
                    resolve();
                } else {
                    reject(new Error(`Server error: ${xhr.status}`));
                }
            });

            xhr.addEventListener('error', () => {
                reject(new Error('Network error during upload'));
            });

            xhr.open('POST', window.location.href);
            xhr.send(formData);
        });
    }

    getCSRFToken() {
        if (window.csrfManager) {
            return window.csrfManager.getCurrentToken();
        }
        return window.getCookie('csrftoken');
    }

    showProgress() {
        const progressHtml = `
            <div id="upload-progress" class="upload-progress mt-3">
                <div class="progress">
                    <div class="progress-bar progress-bar-striped progress-bar-animated bg-warning"
                         role="progressbar" style="width: 0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                        0%
                    </div>
                </div>
                <small class="progress-text text-muted mt-1">Preparing upload...</small>
            </div>
        `;

        const uploadArea = document.querySelector('.file-upload-box');
        if (uploadArea) {
            uploadArea.insertAdjacentHTML('afterend', progressHtml);
        }
    }

    updateProgress(message) {
        const progressBar = document.querySelector('#upload-progress .progress-bar');
        const progressText = document.querySelector('#upload-progress .progress-text');

        if (progressBar) {
            const match = message.match(/(\d+)%/);
            if (match) {
                const percentage = match[1];
                progressBar.style.width = percentage + '%';
                progressBar.setAttribute('aria-valuenow', percentage);
                progressBar.textContent = percentage + '%';
            }
        }

        if (progressText) {
            progressText.textContent = message;
        }
    }

    hideProgress() {
        const progressElement = document.getElementById('upload-progress');
        if (progressElement) {
            progressElement.remove();
        }
    }

    setUploadButtonState(disabled) {
        const uploadForm = document.getElementById('upload-form');
        if (uploadForm) {
            const submitButton = uploadForm.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = disabled;
                if (disabled) {
                    submitButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Uploading...';
                } else {
                    submitButton.innerHTML = '<strong>Preview File Upload</strong>';
                }
            }
        }
    }

    showError(message) {
        this.showAlert(message, 'danger');
        console.error('Upload Error:', message);
    }

    showSuccess(message) {
        this.showAlert(message, 'success');
        console.log('Upload Success:', message);
    }

    showAlert(message, type) {
        // Remove existing alerts
        const existingAlerts = document.querySelectorAll('.upload-alert');
        existingAlerts.forEach(alert => alert.remove());

        const alertHtml = `
            <div class="alert alert-${type} alert-dismissible fade show upload-alert" role="alert">
                <i class="fas fa-${type === 'danger' ? 'exclamation-triangle' : 'check-circle'} me-2"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;

        const uploadCard = document.querySelector('.upload-card-body');
        if (uploadCard) {
            uploadCard.insertAdjacentHTML('afterbegin', alertHtml);

            // Auto-hide after 5 seconds
            setTimeout(() => {
                const alert = uploadCard.querySelector('.upload-alert');
                if (alert) {
                    alert.remove();
                }
            }, 5000);
        }
    }

    reloadPage() {
        // Reload page after a short delay to show success message
        setTimeout(() => {
            window.location.reload();
        }, 1000);
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    handleFormSubmit(e) {
        // Let the normal form submission handle this
        // We've already validated and processed the file
    }
}

// Initialize the upload handler when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.assetUploadHandler = new AssetUploadHandler();
});