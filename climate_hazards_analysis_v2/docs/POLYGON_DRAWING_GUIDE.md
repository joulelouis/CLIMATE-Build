# Enhanced Polygon Drawing System Documentation

## Overview

The Enhanced Polygon Drawing System is a comprehensive frontend solution for drawing polygon assets in the Climate Hazards Analysis Django application. It provides an intuitive, accessible, and mobile-optimized interface for creating and managing geospatial polygons.

## Features

### Core Drawing Capabilities
- **Interactive Polygon Drawing**: Click-to-add points interface with real-time visual feedback
- **Polygon Editing**: Modify existing polygons with intuitive controls
- **Coordinate Display**: Real-time coordinate tracking as you draw
- **Area Calculation**: Automatic area calculation in square kilometers
- **Undo/Redo**: Full history management with keyboard shortcuts
- **Multiple Drawing Modes**: Draw, Edit, and Delete modes

### Accessibility Features
- **Screen Reader Support**: Complete ARIA labeling and live regions
- **Keyboard Navigation**: Full keyboard control with Tab, Arrow keys, and shortcuts
- **Focus Management**: Visible focus indicators and logical tab order
- **Audio Cues**: Optional audio feedback for actions
- **High Contrast Mode**: Enhanced visibility for visually impaired users
- **Reduced Motion**: Respects user motion preferences

### Mobile Optimization
- **Touch Controls**: Optimized touch targets and gestures
- **Mobile Toolbar**: Dedicated mobile interface with large buttons
- **Touch Guidance**: Contextual help for mobile users
- **Haptic Feedback**: Vibration feedback on supported devices
- **Responsive Design**: Adapts to all screen sizes

### Advanced Validation
- **Geometry Validation**: Comprehensive polygon validity checks
- **Coordinate Validation**: Range and format validation
- **Self-Intersection Detection**: Prevents invalid geometries
- **Area Limits**: Configurable minimum and maximum area constraints
- **Topology Validation**: Advanced geospatial checks

## Installation and Setup

### File Structure
```
static/
├── css/
│   └── enhanced-polygon-drawer.css
├── js/
│   ├── enhanced-polygon-drawer.js
│   ├── polygon-validator.js
│   ├── mobile-polygon-drawer.js
│   └── accessibility-enhancer.js
templates/
└── climate_hazards_analysis_v2/
    └── climate_hazard_map.html
```

### Required Dependencies

#### External Libraries
- **Mapbox GL JS**: Interactive mapping library
- **Mapbox GL Draw**: Drawing tools for Mapbox
- **Turf.js**: Geospatial analysis library
- **Font Awesome**: Icon library
- **Bootstrap 5**: UI framework

#### Internal Dependencies
- **polygon-draw-handler.js**: Existing polygon handling logic
- **csrf-manager.js**: CSRF token management
- **main-page-utils.js**: Main page utilities

### Template Integration

The system is automatically loaded when the climate hazard map template is rendered. Include the following in your template:

```html
<!-- CSS -->
<link rel="stylesheet" href="{% static 'css/enhanced-polygon-drawer.css' %}" type="text/css">

<!-- JavaScript -->
<script src="{% static 'js/polygon-validator.js' %}"></script>
<script src="{% static 'js/enhanced-polygon-drawer.js' %}"></script>
<script src="{% static 'js/mobile-polygon-drawer.js' %}"></script>
<script src="{% static 'js/accessibility-enhancer.js' %}"></script>
```

## Usage Guide

### Basic Drawing

1. **Enter Drawing Mode**:
   - Click the "Draw" button in the control panel
   - Press 'D' key (keyboard shortcut)
   - On mobile: Use the mobile toolbar

2. **Add Points**:
   - Click on the map to add vertices
   - Minimum 3 points required for a valid polygon
   - Visual feedback shows temporary markers

3. **Complete Polygon**:
   - Click on the first point to close
   - Press 'Enter' key
   - On mobile: Tap the "Done" button

4. **Save Asset**:
   - Fill in the asset name in the modal
   - Optional: Add archetype information
   - Click "Add Asset" to save

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| D | Enter drawing mode |
| E | Enter editing mode |
| Escape | Cancel current operation |
| Enter | Finish drawing polygon |
| Ctrl+Z | Undo last action |
| Ctrl+Y | Redo last action |
| Delete | Delete selected polygons |
| F6 | Toggle accessibility panel |
| F7 | Toggle high contrast mode |
| F8 | Toggle reduced motion |

### Mobile Controls

#### Touch Gestures
- **Single Tap**: Add drawing point
- **Long Press**: Show context menu
- **Pinch**: Zoom in/out
- **Drag**: Pan map

#### Mobile Toolbar
- **Draw Button**: Start drawing mode
- **Edit Button**: Enter editing mode
- **Undo Button**: Undo last action
- **Clear Button**: Clear all drawings
- **Done Button**: Finish current drawing

### Accessibility Features

#### Screen Reader Support
- All controls have proper ARIA labels
- Live regions announce important events
- Coordinate and area announcements
- Keyboard navigation fully supported

#### Accessibility Panel (F6)
- Toggle high contrast mode
- Toggle reduced motion
- Adjust text size
- Enable/disable audio cues

#### Keyboard Navigation
- Tab: Navigate between controls
- Arrow Keys: Navigate within control groups
- Enter/Space: Activate buttons and checkboxes
- Escape: Cancel operations

## API Reference

### EnhancedPolygonDrawer

Main class for polygon drawing functionality.

#### Constructor Options
```javascript
const drawer = new EnhancedPolygonDrawer({
    mapContainer: '#climate-hazard-map',      // Map container selector
    minVertices: 3,                           // Minimum vertices required
    maxVertices: 500,                         // Maximum vertices allowed
    minArea: 0.0001,                         // Minimum area (square degrees)
    maxArea: 5,                               // Maximum area (square degrees)
    enableSnapToGrid: false,                  // Enable coordinate snapping
    gridSize: 0.001,                          // Grid size for snapping
    enableKeyboardShortcuts: true,            // Enable keyboard shortcuts
    enableUndoRedo: true,                     // Enable undo/redo
    showCoordinateDisplay: true,              // Show coordinate display
    showAreaCalculation: true,                // Show area calculation
    mobileOptimized: true,                    // Mobile optimizations
    accessibilityMode: false                  // Accessibility mode
});
```

#### Public Methods

##### Drawing Control
```javascript
// Start drawing mode
drawer.startDrawing();

// Start editing mode
drawer.startEditing();

// Cancel current drawing
drawer.cancelDrawing();

// Finish current drawing
drawer.finishDrawing();

// Delete all polygons
drawer.clearAll();
```

##### History Management
```javascript
// Undo last action
drawer.undo();

// Redo last action
drawer.redo();

// Add point to current drawing
drawer.addPoint(lng, lat);
```

##### State Information
```javascript
// Check if currently drawing
drawer.isDrawing;  // boolean

// Get current points
drawer.currentPoints;  // Array of [lng, lat] pairs

// Get drawing history
drawer.getHistory();  // Array of history items
```

### PolygonValidator

Comprehensive polygon validation system.

#### Constructor Options
```javascript
const validator = new PolygonValidator({
    minVertices: 3,                    // Minimum vertices
    maxVertices: 500,                  // Maximum vertices
    minArea: 0.0001,                   // Minimum area
    maxArea: 5,                        // Maximum area
    allowSelfIntersection: false,      // Allow self-intersecting polygons
    strictMode: false                  // Enable strict validation
});
```

#### Validation Methods

##### validatePolygon(polygon)
Validates a polygon and returns detailed results.

```javascript
const result = validator.validatePolygon(polygon);
// Returns:
// {
//     valid: boolean,
//     errors: Array,
//     warnings: Array,
//     metadata: {
//         vertices: number,
//         area: number,
//         perimeter: number,
//         centroid: [lng, lat],
//         boundingBox: {...}
//     }
// }
```

##### Error Display
```javascript
// Show error message
validator.showError('Invalid polygon geometry');

// Show warning message
validator.showWarning('Polygon is very large');

// Show success message
validator.showSuccess('Polygon created successfully');
```

### MobilePolygonDrawer

Mobile-specific enhancements for polygon drawing.

#### Constructor Options
```javascript
const mobileDrawer = new MobilePolygonDrawer({
    enableTouchGestures: true,         // Enable touch gestures
    touchThreshold: 10,                // Minimum touch movement
    longPressThreshold: 500,           // Long press duration
    enableHapticFeedback: true,        // Enable vibration
    enableTouchGuidance: true,         // Show touch guidance
    zoomOnDraw: true,                  // Auto-zoom when drawing
    autoCenterOnTouch: true           // Auto-center on touch
});
```

#### Mobile-Specific Methods
```javascript
// Start mobile drawing mode
mobileDrawer.startMobileDrawing();

// Start mobile editing mode
mobileDrawer.startMobileEditing();

// Show touch guidance
mobileDrawer.updateTouchGuidance('Tap to add points');

// Handle specific gestures
mobileDrawer.handlePinchGesture(event);
mobileDrawer.handlePanGesture(event);
```

### AccessibilityEnhancer

Comprehensive accessibility features.

#### Constructor Options
```javascript
const accessibility = new AccessibilityEnhancer({
    enableScreenReaderSupport: true,    // Screen reader support
    enableKeyboardNavigation: true,     // Keyboard navigation
    enableHighContrastMode: false,      // High contrast mode
    enableReducedMotion: false,         // Reduced motion
    enableFocusManagement: true,        // Focus management
    enableAudioCues: false,             // Audio cues
    announcementDelay: 100              // Screen reader announcement delay
});
```

#### Accessibility Methods

##### Screen Reader Announcements
```javascript
// Announce message to screen readers
accessibility.announce('Polygon drawing started', 'polite');

// Announce coordinates
accessibility.announceCoordinates(120.5, 14.2, 'Point added');

// Announce area
accessibility.announceArea(1.234, 'square kilometers');
```

##### Visual Accessibility
```javascript
// Toggle high contrast mode
accessibility.toggleHighContrast(true);

// Toggle reduced motion
accessibility.toggleReducedMotion(true);

// Set text size
accessibility.setTextSize('large');
```

##### Focus Management
```javascript
// Set focus to element
accessibility.setFocus(element);

// Check if element is in viewport
accessibility.isElementInViewport(element);
```

## Integration with Django Backend

### CSRF Protection

The system integrates with the existing CSRF management system:

```javascript
// Automatic CSRF token handling
const csrfToken = window.csrfManager ?
    window.csrfManager.getCurrentToken() :
    getCookie('csrftoken');

// Include in all AJAX requests
fetch('/api/save-polygon/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
    },
    body: JSON.stringify(polygonData)
});
```

### API Endpoints

The system expects the following API endpoints:

#### Save Polygon Asset
```
POST /climate-hazards-analysis-v2/api/add-facility/
Content-Type: application/json

{
    "name": "Asset Name",
    "archetype": "Asset Archetype",
    "lat": 14.5,
    "lng": 121.0,
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[lng1, lat1], [lng2, lat2], ...]]
    }
}
```

#### Load Facility Data
```
GET /climate-hazards-analysis-v2/api/facility-data/
Response: {
    "success": true,
    "facilities": [
        {
            "Facility": "Asset Name",
            "Lat": 14.5,
            "Long": 121.0,
            "geometry": {...}
        }
    ]
}
```

## Customization

### Styling Customization

Override CSS variables to customize appearance:

```css
:root {
    --polygon-draw-primary-color: #007bff;
    --polygon-draw-success-color: #28a745;
    --polygon-draw-warning-color: #ffc107;
    --polygon-draw-danger-color: #dc3545;
    --polygon-draw-border-radius: 12px;
    --polygon-draw-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}
```

### Validation Rules Customization

Customize validation rules:

```javascript
const customValidator = new PolygonValidator({
    minVertices: 4,          // Require at least quadrilaterals
    maxArea: 2,             // Smaller maximum area
    allowSelfIntersection: true,
    strictMode: true        // Enable strict validation
});
```

### Mobile Behavior Customization

Adjust mobile-specific settings:

```javascript
const mobileDrawer = new MobilePolygonDrawer({
    touchThreshold: 5,           // More sensitive touch
    longPressThreshold: 300,     // Shorter long press
    enableHapticFeedback: false, // Disable vibration
    zoomOnDraw: false           // Don't auto-zoom
});
```

## Troubleshooting

### Common Issues

#### Drawing Controls Not Visible
- Ensure map container has correct ID: `#climate-hazard-map`
- Check that Mapbox and Draw libraries are loaded
- Verify CSS files are included

#### Mobile Toolbar Not Appearing
- Check if device is detected as mobile
- Ensure touch events are supported
- Verify mobile drawer initialization

#### Screen Reader Announcements Not Working
- Ensure accessibility script is loaded
- Check for proper ARIA attributes
- Verify live regions are created

#### Validation Errors Not Showing
- Check validator initialization
- Verify error display container exists
- Ensure CSS styling for messages

### Debug Mode

Enable debug logging:

```javascript
// Enable debug mode for enhanced drawer
window.enhancedPolygonDrawer.options.debugMode = true;

// Enable debug mode for validator
window.polygonValidator.options.debugMode = true;
```

### Browser Compatibility

#### Supported Browsers
- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

#### Mobile Support
- iOS Safari 13+
- Chrome Mobile 80+
- Samsung Internet 12+

## Performance Optimization

### Large Numbers of Polygons
- Implement polygon clustering
- Use level-of-detail rendering
- Consider server-side rendering

### Memory Management
- Clear drawing history regularly
- Remove unused event listeners
- Optimize coordinate storage

### Network Optimization
- Batch polygon saves
- Compress geometry data
- Implement local caching

## Security Considerations

### Input Validation
- All coordinates validated on client and server
- Geometry sanitization before storage
- CSRF protection on all API calls

### Data Privacy
- No unnecessary data collection
- Local storage only for settings
- Secure transmission of geospatial data

## Future Enhancements

### Planned Features
- Advanced snapping to existing features
- Polygon boolean operations
- Import/export functionality
- Advanced measurement tools
- Multi-user collaboration

### Performance Improvements
- WebGL rendering for large datasets
- Progressive loading
- Background processing

### Accessibility Improvements
- Voice control support
- Advanced screen reader features
- More audio cue options

## Support and Contributing

### Getting Help
- Check the troubleshooting section
- Review browser console for errors
- Verify all dependencies are loaded

### Contributing
When contributing to the polygon drawing system:

1. Follow existing code style
2. Add comprehensive tests
3. Update documentation
4. Consider accessibility implications
5. Test on mobile devices
6. Verify screen reader compatibility

### License
This Enhanced Polygon Drawing System is part of the CLIMATE-Build project and follows the same licensing terms.