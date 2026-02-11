---
name: Court Calibration Logic
description: Homography-based court calibration for badminton court detection and coordinate transformation
---

# Court Calibration Skill

## Purpose
Provide standardized methods for badminton court calibration using homography transformation. This enables accurate conversion between image coordinates and real-world court coordinates for shuttlecock tracking and line-call judgment.

## Core Concepts

### Homography Transformation
Homography is a projective transformation that maps points from one plane to another. In our case:
- **Source Plane**: Camera image (pixels)
- **Destination Plane**: Real-world court (meters)

### Badminton Court Dimensions (BWF Official)
```
Singles Court:
- Width: 5.18m
- Length: 13.4m (6.7m per half)

Doubles Court:
- Width: 6.1m
- Length: 13.4m

Reference Point: Center of net (0, 0)
```

## Implementation

### Location
`core/backend/modules/calibration/`

### Key Files
1. **`geometry.py`**: Homography transformation logic
2. **`calibration_service.py`**: Calibration service
3. **`calibration_profile_service.py`**: Profile management

## Usage Patterns

### 1. Manual 4-Point Calibration

**Frontend Flow**:
```typescript
// 1. Upload image
const uploadRes = await uploadImage(file);
const sessionId = uploadRes.session_id;

// 2. User clicks 4 corners (TL, TR, BR, BL)
const corners = [
    [x1, y1],  // Top-left
    [x2, y2],  // Top-right
    [x3, y3],  // Bottom-right
    [x4, y4]   // Bottom-left
];

// 3. Send calibration request
const calibRes = await alignCorners({
    session_id: sessionId,
    corners: corners,
    image_width: 1920,
    image_height: 1080
});

// 4. Receive homography matrix
const H = calibRes.data.homography_matrix;
```

**Backend Processing**:
```python
from modules.calibration.geometry import HomographyTransform
from modules.calibration.constants import CourtDimensions

# Define real-world court corners (meters)
court_corners = [
    (-CourtDimensions.SINGLES_WIDTH / 2, 0),                    # TL
    (CourtDimensions.SINGLES_WIDTH / 2, 0),                     # TR
    (CourtDimensions.SINGLES_WIDTH / 2, CourtDimensions.BACK_BOUNDARY_LINE),  # BR
    (-CourtDimensions.SINGLES_WIDTH / 2, CourtDimensions.BACK_BOUNDARY_LINE)  # BL
]

# Compute homography
transform = HomographyTransform()
success = transform.compute_homography(
    src_points=np.array(image_corners),
    dst_points=np.array(court_corners)
)

# Transform shuttlecock position
world_pos = transform.image_to_world((pixel_x, pixel_y))
```

### 2. Automatic Court Detection

**API Endpoint**: `POST /api/detect-court-auto`

```python
# Request
{
    "session_id": "abc123",
    "include_doubles": false,
    "roi": {  # Optional region of interest
        "x": 100,
        "y": 100,
        "width": 1720,
        "height": 880
    }
}

# Response
{
    "success": true,
    "corners": {
        "TL": [245, 120],
        "TR": [1675, 118],
        "BR": [1720, 960],
        "BL": [200, 962]
    },
    "calibration": {
        "pixels_per_meter": 285.4,
        "homography_matrix": [[...], [...], [...]]
    },
    "confidence": {
        "overall": 0.92
    }
}
```

### 3. Coordinate Transformation

```python
# Image → World (for shuttlecock landing detection)
image_point = (640, 480)  # Pixel coordinates
world_point = transform.image_to_world(image_point)
# Output: (1.2, 3.5) meters from court center

# World → Image (for minimap visualization)
world_point = (0.5, 2.0)  # Meters
image_point = transform.world_to_image(world_point)
# Output: (650, 420) pixels

# Batch transformation
image_points = [(x1, y1), (x2, y2), (x3, y3)]
world_points = transform.transform_points(image_points, to_world=True)
```

## Common Issues & Solutions

### ❌ Issue: Shuttlecock Position Incorrect on Minimap

**Symptom**: Shuttlecock appears outside court boundaries on minimap

**Root Cause** (2026-02-02 Bug):
- Frame batching vs single-frame processing logic mismatch
- Homography matrix not applied correctly to detection coordinates

**Solution**:
```python
# Ensure consistent frame processing
# BAD: Mixing batch and single-frame logic
results = detector.detect_batch(frames)  # Returns batch coordinates
landing_pos = transform.image_to_world(results[0])  # Wrong reference frame

# GOOD: Consistent single-frame processing
result = detector.detect(frame)  # Single frame
landing_pos = transform.image_to_world((result.x, result.y))  # Correct
```

### ❌ Issue: Calibration Image Not Displaying

**Symptom** (2026-02-01 Bug): Uploaded image doesn't show on calibration page

**Root Cause**: Image URL path construction error

**Solution**:
```typescript
// BAD: Incorrect URL construction
const imageUrl = `/api/image/${sessionId}`;

// GOOD: Use helper function
import { getImageUrl } from '@/services/analysisAPI';
const imageUrl = getImageUrl(sessionId, 'original');
// Returns: http://localhost:8000/api/image/{sessionId}/original
```

### ❌ Issue: Court Validation Fails

**Symptom**: Valid court corners rejected by validation

**Solution**: Adjust tolerance in `geometry.py`
```python
# geometry.py - CourtGeometry.is_valid_court_shape()
tolerance: float = 0.8  # Increased from 0.3 for more flexibility
```

## Validation & Quality Checks

### Reprojection Error
```python
# Measure calibration accuracy
error = transform.get_reprojection_error(
    src_points=image_corners,
    dst_points=court_corners
)
# Good: error < 5 pixels
# Warning: 5 < error < 10 pixels
# Bad: error > 10 pixels
```

### Court Shape Validation
```python
from modules.calibration.geometry import CourtGeometry

is_valid, message = CourtGeometry.is_valid_court_shape(corners)
if not is_valid:
    print(f"Invalid court: {message}")
```

### Point-in-Court Check
```python
# Check if shuttlecock landed in court
is_in = CourtGeometry.is_point_in_court(
    world_point=(1.5, 3.2),  # meters
    margin=0.1  # 10cm tolerance
)
```

## Integration with Shuttlecock Detection

```python
# Complete workflow
from modules.shuttlecock_detection.models import YOLODetector
from modules.calibration.geometry import HomographyTransform

# 1. Initialize detector
detector = YOLODetector(
    model_path="weights/best.pt",
    conf_threshold=0.3,
    img_size=1280
)

# 2. Setup calibration
transform = HomographyTransform()
transform.compute_homography(image_corners, court_corners)

# 3. Process frame
detections = detector.detect(frame)

# 4. Transform to world coordinates
for det in detections:
    world_pos = transform.image_to_world((det.x, det.y))
    is_in_court = CourtGeometry.is_point_in_court(world_pos)
    
    print(f"Shuttlecock at {world_pos} - In court: {is_in_court}")
```

## Best Practices

1. **Always validate corners** before computing homography
2. **Check reprojection error** after calibration (< 5px is good)
3. **Use consistent coordinate systems**:
   - Image: Top-left origin, pixels
   - World: Court center origin, meters
4. **Handle edge cases**:
   - Shuttlecock outside camera view
   - Extreme camera angles (high reprojection error)
5. **Cache calibration profiles** for repeated use on same court

## Constants Reference

```python
# modules/calibration/constants.py
class CourtDimensions:
    SINGLES_WIDTH = 5.18  # meters
    DOUBLES_WIDTH = 6.1
    BACK_BOUNDARY_LINE = 6.7  # Half court length
    NET_HEIGHT = 1.55  # meters (at posts)
    SERVICE_LINE = 1.98  # meters from net
```

## Related Files

- Core logic: `core/backend/modules/calibration/geometry.py`
- Service: `core/backend/modules/calibration/calibration_service.py`
- Frontend API: `core/birdie-buddies-frontend/src/services/analysisAPI.ts`
- Frontend hook: `core/birdie-buddies-frontend/src/hooks/useCalibration.ts`

## Quick Reference

```python
# Initialize
from modules.calibration.geometry import HomographyTransform
transform = HomographyTransform()

# Calibrate
transform.compute_homography(image_corners, court_corners)

# Transform
world_pos = transform.image_to_world((x_pixel, y_pixel))
image_pos = transform.world_to_image((x_meter, y_meter))

# Validate
error = transform.get_reprojection_error(src, dst)
is_valid, msg = CourtGeometry.is_valid_court_shape(corners)
```
