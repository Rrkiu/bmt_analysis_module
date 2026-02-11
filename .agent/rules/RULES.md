---
trigger: model_decision
description: Apply: CV algorithms (detection/calibration), FastAPI endpoints, React video UI, performance code, production. Skip: experiments, docs, formatting. Requirements: 30fps, high accuracy, 80% test coverage.
---

# BMT Analysis Module - Development Rules

## 1. Project Overview
**Mission**: Real-time badminton analysis system (30fps) with court calibration and shuttlecock tracking.

**Tech Stack**:
- Backend: FastAPI, Python 3.10+, OpenCV, PyTorch, Ultralytics YOLO
- Frontend: React 19, TypeScript, TailwindCSS
- ML: YOLOv8m/v11 detection, TrackNetV3, homography transforms

**Performance Targets**:
- Frame processing: <33ms (30fps)
- YOLO inference: <20ms (GPU), <100ms (CPU)
- API response: <200ms (P95)

---

## 2. Critical Constraints

### NEVER
```python
# ❌ Commit model weights
*.pt, *.pth, *.onnx  # Add to .gitignore

# ❌ Block async event loop
async def process():
    time.sleep(5)  # Wrong!
    await asyncio.sleep(5)  # Correct

# ❌ Load entire video
video = cv2.VideoCapture("large.mp4")
frames = [video.read()[1] for _ in range(10000)]  # OOM!

# ❌ Hardcode CUDA
device = torch.device("cuda")  # Crashes on CPU-only!
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  # Correct
```

### ALWAYS
```python
# ✅ Type hints everywhere
def transform_point(
    point: Tuple[float, float],
    H: np.ndarray
) -> Optional[Tuple[float, float]]:
    """Transform image coords to court coords."""
    pass

# ✅ Release resources
cap = cv2.VideoCapture(video_path)
try:
    # process frames
finally:
    cap.release()

# ✅ Validate file uploads
ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mov'}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

if file.size > MAX_FILE_SIZE:
    raise ValueError("File too large")

# ✅ YOLO Training - Shuttlecock Detection (CRITICAL!)
# Based on validated experiments (2026-02-04)
YOLO_TRAINING_CONFIG = {
    'model': 'yolov8m.pt',      # ✅ Best accuracy (mAP 0.87)
    'imgsz': 1280,              # ✅ MANDATORY for shuttlecock (NOT 640!)
    'batch': 4,                 # Optimal for 1280 + GPU memory
    'amp': True,                # ✅ MANDATORY FP16 (40% memory savings)
    'conf': 0.001,              # Low threshold during training
    'epochs': 100,
    'patience': 50
}

# ❌ NEVER use imgsz=640 for shuttlecock (verified poor performance)
# ❌ NEVER disable FP16 (amp=False) unless CPU-only training
```

---

## 3. Architecture
```
core/backend/
├── main.py                    # FastAPI entry
├── modules/
│   ├── analysis/              # Rally analysis
│   ├── calibration/           # Court detection
│   │   ├── calibrator.py
│   │   └── line_detector.py
│   └── shuttlecock_detection/
│       ├── adapters/          # YOLO/TrackNet
│       ├── models/
│       └── weights/           # *.pt (git ignored!)
└── tests/

core/birdie-buddies-frontend/
├── src/
│   ├── components/
│   ├── hooks/
│   └── services/
```

**Key Files**:
- Model weights: `shuttlecock_detection/weights/best.pt` (DO NOT commit)
- Storage: `storage/` (runtime data, git ignored)

---

## 4. Code Style

### Python (PEP 8 + Type Hints)
```python
from typing import Optional, Tuple, List
import numpy as np

def compute_homography(
    src_points: np.ndarray,
    dst_points: np.ndarray
) -> Optional[np.ndarray]:
    """
    Compute homography matrix.
    
    Args:
        src_points: Source points (Nx2)
        dst_points: Destination points (Nx2)
        
    Returns:
        3x3 homography matrix or None if failed
        
    Raises:
        ValueError: If points shape invalid
    """
    if len(src_points) < 4:
        raise ValueError("Need at least 4 points")
    
    try:
        H, _ = cv2.findHomography(src_points, dst_points, cv2.RANSAC)
        return H
    except cv2.error as e:
        logger.error(f"Homography failed: {e}")
        return None
```

### TypeScript (Strict Mode)
```typescript
interface VideoMetadata {
  duration: number;
  fps: number;
  resolution: { width: number; height: number };
}

export const processVideo = async (
  file: File
): Promise<VideoMetadata> => {
  // Implementation
};
```

---

## 5. Performance Optimization

### YOLO Inference
```python
# ✅ Batch processing with validated settings
# Note: YOLOv8m @ 1280px achieves ~30fps on RTX 3090
results = model.predict(
    frames,  # List[np.ndarray]
    batch=4,      # Optimal for 1280 resolution
    imgsz=1280,   # ✅ CRITICAL: Use 1280 for shuttlecock (small object)
    conf=0.3,     # Low threshold for small objects
    device="cuda",
    half=True     # FP16 for memory efficiency (~40% savings)
)

# ✅ Warm-up model
dummy = np.zeros((640, 640, 3), dtype=np.uint8)
model.predict(dummy)  # First inference is slow

# ❌ Frame-by-frame in loop
for frame in frames:
    model.predict(frame)  # Slow!
```

### Video Processing
```python
# ✅ Frame skipping for target FPS
cap = cv2.VideoCapture(video_path)
source_fps = cap.get(cv2.CAP_PROP_FPS)
target_fps = 30
skip = int(source_fps / target_fps)

frame_idx = 0
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    if frame_idx % skip == 0:
        process_frame(frame)
    frame_idx += 1
```

---

## 6. Court Calibration Standards

### BWF Court Dimensions
```python
# Official badminton court (meters) - BWF Standard
COURT_LENGTH = 13.4          # Full court length (baseline to baseline)
COURT_WIDTH_DOUBLES = 6.1    # Doubles court width
COURT_WIDTH_SINGLES = 5.18   # Singles court width
NET_HEIGHT = 1.55            # Net height at posts

# Half court (commonly used in calibration)
HALF_COURT_LENGTH = 6.7      # From net to baseline

# Key lines (distances from baseline)
SHORT_SERVICE_LINE = 1.98
LONG_SERVICE_LINE_DOUBLES = 0.76  # from baseline
```

### Coordinate Systems
```python
# Image coords: (0,0) = top-left, (W,H) = bottom-right (pixels)
# Court coords: Origin at net center (meters)
#   X-axis: -2.59m (left) to +2.59m (right) for singles court
#   Y-axis: 0 (net) to 6.7m (baseline)

def image_to_court(
    point: Tuple[float, float],
    H: np.ndarray
) -> Optional[Tuple[float, float]]:
    """Transform pixel coords to court meters.
    
    Args:
        point: (x, y) in image pixels
        H: 3x3 homography matrix
        
    Returns:
        (x, y) in court meters, origin at net center
    """
    pt = np.array([[point]], dtype=np.float32)
    transformed = cv2.perspectiveTransform(pt, H)
    return tuple(transformed[0, 0])
```

---

## 7. API Patterns

### Pydantic Models
```python
from pydantic import BaseModel, Field, validator

class VideoUploadRequest(BaseModel):
    file: UploadFile
    target_fps: int = Field(default=30, ge=1, le=60)
    
    @validator('file')
    def validate_file(cls, v):
        ext = Path(v.filename).suffix.lower()
        if ext not in {'.mp4', '.avi', '.mov'}:
            raise ValueError(f"Unsupported format: {ext}")
        return v

class DetectionResponse(BaseModel):
    frame_number: int
    detections: List[Dict[str, float]]
    confidence: float
    processing_time_ms: float
```

### Error Handling
```python
class BMTException(Exception):
    """Base exception"""
    pass

class CalibrationError(BMTException):
    """Court calibration failed"""
    pass

class DetectionError(BMTException):
    """Shuttlecock detection failed"""
    pass

# Usage
@app.post("/calibrate")
async def calibrate_court(video: UploadFile):
    try:
        result = calibrator.detect_court(video)
        return result
    except CalibrationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error")
        raise HTTPException(status_code=500, detail="Internal error")
```

---

## 8. Testing Standards

### Unit Tests
```python
import pytest

def test_homography_computation():
    """Test homography with known points."""
    src = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float32)
    dst = np.array([[0, 0], [20, 0], [20, 20], [0, 20]], dtype=np.float32)
    
    H = compute_homography(src, dst)
    
    assert H is not None
    assert H.shape == (3, 3)
    
    # Test transform
    pt = np.array([[5, 5]], dtype=np.float32)
    result = cv2.perspectiveTransform(pt.reshape(1, 1, 2), H)
    expected = np.array([10, 10])
    np.testing.assert_allclose(result[0, 0], expected, atol=0.1)

def test_invalid_points():
    """Test with insufficient points."""
    src = np.array([[0, 0], [10, 0]], dtype=np.float32)  # Only 2 points
    dst = np.array([[0, 0], [20, 0]], dtype=np.float32)
    
    with pytest.raises(ValueError, match="at least 4 points"):
        compute_homography(src, dst)
```

### Integration Tests
```python
@pytest.mark.asyncio
async def test_detection_endpoint(test_client, sample_video):
    """Test full detection pipeline."""
    files = {"file": ("test.mp4", sample_video, "video/mp4")}
    
    response = await test_client.post("/detect", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert "detections" in data
    assert len(data["detections"]) > 0
```

---

## 9. Git & Deployment

### .gitignore
```
# Model weights (CRITICAL!)
*.pt
*.pth
*.onnx
*.weights

# Runtime data
storage/
uploads/
temp/

# Python
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/

# Frontend
node_modules/
dist/
build/

# Environment
.env
.env.local
```

### Pre-commit Checks
```bash
# Backend
pytest tests/ -v
mypy modules/ --strict
black modules/ --check
flake8 modules/

# Frontend
npm run test
npm run type-check
npm run lint
```

---

## 10. Common Pitfalls

### Memory Leaks
```python
# ❌ Not releasing VideoCapture
cap = cv2.VideoCapture("video.mp4")
frames = process_all(cap)  # Leak if exception!

# ✅ Always use context manager or finally
cap = cv2.VideoCapture("video.mp4")
try:
    frames = process_all(cap)
finally:
    cap.release()
```

### CUDA OOM
```python
# ❌ No error handling
model = YOLO("best.pt")
results = model.predict(large_batch, device="cuda")  # Crash!

# ✅ Catch and fallback
try:
    results = model.predict(batch, device="cuda")
except RuntimeError as e:
    if "out of memory" in str(e):
        logger.warning("CUDA OOM, falling back to CPU")
        results = model.predict(batch, device="cpu")
    else:
        raise
```

### Coordinate Confusion
```python
# ❌ Mixing coordinate systems
image_x, image_y = detect_shuttlecock(frame)
is_in = check_bounds(image_x, image_y, COURT_WIDTH, COURT_LENGTH)  # Wrong!

# ✅ Transform first
image_point = (x, y)
court_point = image_to_court(image_point, homography_matrix)
is_in = check_bounds(court_point[0], court_point[1], COURT_WIDTH, COURT_LENGTH)
```

---

## Quick Reference

**Performance**: 30fps → <33ms/frame  
**YOLO**: YOLOv8m, 1280x1280, batch=4, conf=0.3, FP16 enabled  
**Court**: BWF 6.1m × 13.4m (doubles), 5.18m × 13.4m (singles)  
**Types**: Always use type hints  
**Tests**: pytest, 80%+ coverage goal  
**Git**: NEVER commit *.pt files