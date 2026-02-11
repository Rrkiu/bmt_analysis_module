---
name: Video Processing Pipeline
description: Standardized pipeline for video analysis, frame extraction, and batch processing
---

# Video Processing Skill

## Purpose
Provide efficient patterns for processing badminton match videos, including frame extraction, batch analysis, and result visualization.

## Video Processing Architecture

```
Video Input → Frame Extraction → Detection → Coordinate Transform → Result Aggregation
     ↓              ↓                ↓              ↓                      ↓
  .mp4/.avi    OpenCV/FFmpeg    YOLO/TrackNet   Homography          JSON/Video Output
```

## Core Components

### 1. Frame Extraction

**Using OpenCV**:
```python
import cv2
from pathlib import Path
from typing import Generator, Tuple
import numpy as np

def extract_frames(
    video_path: str,
    fps: int = None,
    start_time: float = 0,
    end_time: float = None
) -> Generator[Tuple[int, np.ndarray], None, None]:
    """
    Extract frames from video
    
    Args:
        video_path: Path to video file
        fps: Target FPS (None = original FPS)
        start_time: Start time in seconds
        end_time: End time in seconds
    
    Yields:
        (frame_number, frame_image)
    """
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    
    # Get video properties
    original_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Calculate frame skip
    if fps is None:
        frame_skip = 1
    else:
        frame_skip = max(1, int(original_fps / fps))
    
    # Calculate start/end frames
    start_frame = int(start_time * original_fps)
    end_frame = int(end_time * original_fps) if end_time else total_frames
    
    # Seek to start
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    frame_num = start_frame
    while frame_num < end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        
        if (frame_num - start_frame) % frame_skip == 0:
            yield frame_num, frame
        
        frame_num += 1
    
    cap.release()
```

### 2. Batch Video Processing

```python
from typing import List, Dict, Any
from pathlib import Path
import json

class VideoBatchProcessor:
    """Process multiple videos with consistent settings"""
    
    def __init__(
        self,
        detector,
        calibration_transform,
        output_dir: str
    ):
        self.detector = detector
        self.transform = calibration_transform
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def process_video(
        self,
        video_path: str,
        save_visualization: bool = True
    ) -> Dict[str, Any]:
        """
        Process single video
        
        Returns:
            Results dictionary with detections and statistics
        """
        video_path = Path(video_path)
        results = {
            'video_name': video_path.name,
            'frames_processed': 0,
            'detections': [],
            'landings': []
        }
        
        # Setup video writer if visualization needed
        if save_visualization:
            cap = cv2.VideoCapture(str(video_path))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            
            output_video = self.output_dir / f"{video_path.stem}_analyzed.mp4"
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(
                str(output_video),
                fourcc,
                fps,
                (width, height)
            )
        
        # Process frames
        for frame_num, frame in extract_frames(str(video_path)):
            # Detect shuttlecock
            detections = self.detector.detect(frame)
            
            # Transform to world coordinates
            for det in detections:
                world_pos = self.transform.image_to_world((det.x, det.y))
                
                results['detections'].append({
                    'frame': frame_num,
                    'image_pos': [det.x, det.y],
                    'world_pos': list(world_pos),
                    'confidence': det.confidence
                })
                
                # Visualize
                if save_visualization:
                    cv2.circle(frame, (int(det.x), int(det.y)), 10, (0, 255, 255), 2)
                    cv2.putText(
                        frame,
                        f"{det.confidence:.2f}",
                        (int(det.x) + 15, int(det.y)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 255),
                        1
                    )
            
            if save_visualization:
                writer.write(frame)
            
            results['frames_processed'] += 1
        
        if save_visualization:
            writer.release()
        
        # Save JSON results
        json_output = self.output_dir / f"{video_path.stem}_results.json"
        with open(json_output, 'w') as f:
            json.dump(results, f, indent=2)
        
        return results
    
    def process_batch(
        self,
        video_paths: List[str],
        parallel: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Process multiple videos
        
        Args:
            video_paths: List of video file paths
            parallel: Use multiprocessing (not implemented yet)
        
        Returns:
            List of results for each video
        """
        all_results = []
        
        for video_path in video_paths:
            print(f"Processing: {video_path}")
            try:
                result = self.process_video(video_path)
                all_results.append(result)
                print(f"✓ Completed: {result['frames_processed']} frames")
            except Exception as e:
                print(f"✗ Failed: {e}")
                all_results.append({
                    'video_name': Path(video_path).name,
                    'error': str(e)
                })
        
        return all_results
```

### 3. Real-time Frame Processing (API)

```python
# Backend endpoint for frame-by-frame analysis
from fastapi import UploadFile, File

@router.post("/analysis/frame-predict")
async def predict_frame(
    session_id: str,
    file: UploadFile = File(...),
    video_time: float = 0
):
    """
    Analyze single frame from video stream
    
    Used for real-time video playback analysis
    """
    try:
        # Read frame
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Get session calibration
        calibration = get_session_calibration(session_id)
        
        # Detect shuttlecock
        detector = get_detector()
        detections = detector.detect(frame, conf_threshold=0.3)
        
        # Transform coordinates
        result = {
            'success': True,
            'detections': [],
            'landing': None
        }
        
        if detections:
            main_det = detections[0]  # Highest confidence
            world_pos = calibration.image_to_world((main_det.x, main_det.y))
            
            result['detections'].append({
                'x': main_det.x,
                'y': main_det.y,
                'confidence': main_det.confidence,
                'world_x': world_pos[0],
                'world_y': world_pos[1]
            })
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## Performance Optimization

### 1. GPU Batch Processing

```python
# Process multiple frames at once
def batch_detect(detector, frames: List[np.ndarray], batch_size: int = 8):
    """Process frames in batches for GPU efficiency"""
    results = []
    
    for i in range(0, len(frames), batch_size):
        batch = frames[i:i + batch_size]
        batch_results = detector.detect_batch(batch)
        results.extend(batch_results)
    
    return results
```

### 2. Frame Skipping for Speed

```python
# Analyze every Nth frame for faster processing
for frame_num, frame in extract_frames(video_path, fps=10):  # 10 FPS instead of 30
    # Process frame
    pass
```

### 3. Multiprocessing

```python
from multiprocessing import Pool
from functools import partial

def process_video_worker(video_path, detector_config, output_dir):
    """Worker function for parallel processing"""
    # Initialize detector in worker process
    detector = YOLODetector(**detector_config)
    processor = VideoBatchProcessor(detector, None, output_dir)
    return processor.process_video(video_path)

def parallel_process(video_paths, detector_config, output_dir, num_workers=4):
    """Process videos in parallel"""
    worker = partial(
        process_video_worker,
        detector_config=detector_config,
        output_dir=output_dir
    )
    
    with Pool(num_workers) as pool:
        results = pool.map(worker, video_paths)
    
    return results
```

## Common Use Cases

### 1. Extract First Frame (for Calibration)

```python
def get_first_frame(video_path: str) -> np.ndarray:
    """Extract first frame from video"""
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        raise ValueError("Cannot read first frame")
    
    return frame
```

### 2. Video Metadata Extraction

```python
def get_video_info(video_path: str) -> dict:
    """Get video metadata"""
    cap = cv2.VideoCapture(video_path)
    
    info = {
        'fps': cap.get(cv2.CAP_PROP_FPS),
        'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        'duration': cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
    }
    
    cap.release()
    return info
```

### 3. Landing Detection

```python
class LandingDetector:
    """Detect shuttlecock landings"""
    
    def __init__(self, stationary_threshold: float = 5.0):
        self.threshold = stationary_threshold
        self.prev_pos = None
        self.stationary_frames = 0
    
    def update(self, detection) -> bool:
        """
        Update with new detection
        
        Returns:
            True if landing detected
        """
        if detection is None:
            self.prev_pos = None
            self.stationary_frames = 0
            return False
        
        curr_pos = (detection.x, detection.y)
        
        if self.prev_pos is None:
            self.prev_pos = curr_pos
            return False
        
        # Calculate movement
        distance = np.sqrt(
            (curr_pos[0] - self.prev_pos[0])**2 +
            (curr_pos[1] - self.prev_pos[1])**2
        )
        
        if distance < self.threshold:
            self.stationary_frames += 1
            if self.stationary_frames >= 3:  # 3 consecutive stationary frames
                return True
        else:
            self.stationary_frames = 0
        
        self.prev_pos = curr_pos
        return False
```

## Best Practices

1. **Memory Management**: Release video captures and writers properly
2. **Error Handling**: Validate video files before processing
3. **Progress Tracking**: Log progress for long-running batch jobs
4. **Output Organization**: Use structured directories with timestamps
5. **GPU Utilization**: Batch process when possible for efficiency
6. **Frame Rate**: Match detection FPS to use case (real-time vs accuracy)

## Related Files

- Batch script: `.agent/skills/video_processing/scripts/batch_process.py`
- Frame extraction: `experiments/_adutils/get_first_frame.py`
- Video prediction: `experiments/shuttlecock_detection/yolo/scripts/predict_video.py`
- API endpoint: `core/backend/modules/analysis/`

## Quick Reference

```python
# Extract frames
for frame_num, frame in extract_frames('video.mp4', fps=10):
    # Process frame
    pass

# Batch processing
processor = VideoBatchProcessor(detector, transform, 'output/')
results = processor.process_batch(['video1.mp4', 'video2.mp4'])

# Get video info
info = get_video_info('video.mp4')
print(f"Duration: {info['duration']:.2f}s, FPS: {info['fps']}")
```
