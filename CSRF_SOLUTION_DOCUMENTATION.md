# Robust CSRF Handling Solution for Climate Risk Analytics

## Overview

This document describes the comprehensive CSRF (Cross-Site Request Forgery) protection solution implemented to handle scenarios where users clear site data using browser DevTools, which can result in CSRF token loss and subsequent 403 errors.

## Problem Description

When users clear site data using browser DevTools (Application → Clear Storage), the CSRF cookie gets deleted but the Django session may remain active. This causes subsequent form submissions to fail with a 403 CSRF verification error because:

1. The CSRF cookie is missing after storage clearing
2. Django requires a valid CSRF token for POST/PUT/DELETE requests
3. Forms and AJAX requests fail with "CSRF cookie not set" errors

## Solution Architecture

The solution consists of multiple layers working together:

### 1. CSRF Manager (`csrf-manager.js`)

A comprehensive JavaScript module that provides:

- **Token Detection**: Automatically detects when CSRF tokens are missing or invalid
- **Token Regeneration**: Multiple fallback methods to obtain new CSRF tokens
- **Form Protection**: Automatically protects all forms with CSRF validation
- **AJAX Protection**: Intercepts fetch requests to add CSRF headers
- **Error Handling**: User-friendly error messages and recovery mechanisms
- **Session Recovery**: Automatic recovery from storage clearing scenarios

#### Key Features:

```javascript
// Automatic initialization
window.csrfManager = new CSRFManager();

// Token validation
const isValid = await window.csrfManager.validateToken();

// Manual token refresh
await window.csrfManager.forceRefreshToken();

// Get current token
const token = window.csrfManager.getCurrentToken();
```

### 2. Django CSRF Refresh Endpoint

Added a dedicated endpoint to refresh CSRF tokens:

**URL**: `/climate-hazards-analysis-v2/refresh-csrf-token/`

**Response**:
```json
{
    "success": true,
    "csrf_token": "new-token-value",
    "message": "CSRF token refreshed successfully"
}
```

### 3. Enhanced Template Integration

Updated templates with:

- CSRF meta tags for token accessibility
- Enhanced form handling with CSRF validation
- User-friendly error messages
- Automatic fallback mechanisms

### 4. Testing Framework (`csrf-test.js`)

Comprehensive testing suite that validates:

- CSRF Manager presence and initialization
- Token presence and validation
- Token regeneration capabilities
- Form and AJAX protection
- Storage clearing recovery scenarios
- Error recovery mechanisms

## Implementation Details

### Files Modified/Created:

1. **`static/js/csrf-manager.js`** (NEW)
   - Core CSRF management functionality
   - Token detection and regeneration
   - Form and AJAX protection

2. **`static/js/csrf-test.js`** (NEW)
   - Comprehensive testing suite
   - Scenario validation
   - Debug tools

3. **`templates/base.html`** (MODIFIED)
   - Added CSRF manager script inclusion
   - Added optional test script for development

4. **`climate_hazards_analysis_v2/templates/main.html`** (MODIFIED)
   - Added CSRF meta tags
   - Enhanced clearSiteData function with CSRF validation

5. **`climate_hazards_analysis_v2/views.py`** (MODIFIED)
   - Added `refresh_csrf_token` view function
   - Enhanced CSRF handling

6. **`climate_hazards_analysis_v2/urls.py`** (MODIFIED)
   - Added CSRF refresh endpoint

## How It Works

### 1. Initialization

When the page loads, the CSRF Manager automatically:
- Detects existing CSRF tokens (cookies, meta tags, hidden fields)
- Validates current token status
- Sets up event listeners for form submissions and AJAX requests
- Monitors storage changes

### 2. Form Submission Protection

For each form submission:
```javascript
// Before submission
const isValid = await csrfManager.ensureValidToken();
if (!isValid) {
    // Show error and prevent submission
    return;
}
// Add CSRF token to form
csrfManager.updateFormCSRFToken(form);
```

### 3. AJAX Request Protection

For each AJAX request:
```javascript
// Intercept fetch requests
if (shouldProtectRequest(url, options)) {
    // Ensure valid token
    const isValid = await csrfManager.ensureValidToken();
    // Add CSRF header
    options.headers['X-CSRFToken'] = csrfManager.getToken();
}
```

### 4. Token Regeneration Process

When a token is missing or invalid:

1. **Check Hidden Fields**: Look for existing CSRF token in form inputs
2. **Check Meta Tags**: Look for CSRF token in meta tags
3. **AJAX Refresh**: Call dedicated refresh endpoint
4. **Fallback Method**: Parse current page for token
5. **Page Refresh**: Last resort to obtain fresh token

### 5. Storage Clear Recovery

When storage is cleared:
1. Detect missing token on next action
2. Attempt automatic regeneration
3. Show user-friendly error if regeneration fails
4. Provide option to refresh page

## Usage

### For Developers

**Automatic Usage**:
The CSRF Manager works automatically - no additional code needed.

**Manual Token Validation**:
```javascript
// Validate current token
const isValid = await window.csrfManager.validateToken();

// Force refresh token
await window.csrfManager.forceRefreshToken();

// Get current token
const token = window.csrfManager.getCurrentToken();
```

**Testing**:
```javascript
// Run comprehensive tests
window.csrfTester.runAllTests();

// Keyboard shortcut: Ctrl+Shift+C
```

### For Users

**Normal Operation**:
Users don't need to do anything - the system works automatically.

**If Issues Occur**:
- User-friendly error messages appear
- Options to refresh page or retry are provided
- Automatic recovery attempts are made

## Testing

### Running Tests

1. **Manual Test**:
   - Open browser DevTools
   - Press `Ctrl+Shift+C` to run tests
   - Or add `?csrf-test=true` to URL

2. **Storage Clear Test**:
   - Open DevTools → Application → Clear Storage
   - Clear site data
   - Try to submit a form
   - Verify automatic recovery

### Test Scenarios

The testing framework covers:
- ✅ CSRF Manager initialization
- ✅ Token presence detection
- ✅ Token validation
- ✅ Token regeneration
- ✅ Form protection
- ✅ AJAX protection
- ✅ Storage clearing recovery
- ✅ Error recovery

## Security Considerations

### Maintained Security

- **Same Origin Policy**: All requests are same-origin
- **Token Validation**: Tokens are always validated before use
- **Secure Headers**: Proper security headers maintained
- **No Token Exposure**: Tokens are not exposed in URLs or logs (in production)

### Enhanced Security

- **Token Refresh**: Secure token regeneration
- **Error Handling**: Safe error messages without information leakage
- **Session Validation**: Proper session state validation
- **Automatic Recovery**: Prevents security bypass attempts

## Browser Compatibility

- **Modern Browsers**: Full support (Chrome, Firefox, Safari, Edge)
- **IE11**: Basic support (with fallbacks)
- **Mobile Browsers**: Full support

## Configuration Options

The CSRF Manager can be configured with options:

```javascript
new CSRFManager({
    tokenName: 'csrftoken',           // Cookie name
    maxRetries: 3,                    // Max regeneration attempts
    retryDelay: 1000,                 // Delay between retries (ms)
    refreshOnFailure: true,           // Auto-refresh on failure
    debugMode: false                  // Enable debug logging
});
```

## Troubleshooting

### Common Issues

1. **CSRF Manager Not Found**:
   - Verify `csrf-manager.js` is included in base template
   - Check for JavaScript errors in console

2. **Token Regeneration Fails**:
   - Verify CSRF refresh endpoint is accessible
   - Check Django settings for CSRF configuration
   - Verify user session is valid

3. **Forms Still Fail**:
   - Ensure forms have `method="POST"` or other modifying methods
   - Check for conflicting JavaScript
   - Verify Django middleware is properly configured

### Debug Mode

Enable debug mode for detailed logging:
```javascript
// In console
window.csrfManager.options.debugMode = true;

// Or reload with debug parameter
window.location.search = '?csrf-test=true';
```

## Future Enhancements

Potential improvements:
1. **Rate Limiting**: Prevent excessive token refresh requests
2. **Caching**: Cache valid tokens to reduce refresh calls
3. **Metrics**: Track CSRF error rates and recovery success
4. **Enhanced UI**: Better user feedback during token refresh

## Conclusion

This comprehensive CSRF solution provides robust protection against CSRF token loss scenarios while maintaining security and providing excellent user experience. The multi-layered approach ensures automatic recovery from storage clearing while keeping the application secure and user-friendly.