#!/usr/bin/env python3
"""
Batch Video Processing Script

Process multiple videos with shuttlecock detection and analysis.
"""

import argparse
from pathlib import Path
import json
import cv2
import numpy as np
from typing import List, Dict, Any
from datetime import datetime


def process_video_batch(
    video_paths: List[str],
    weights_path: str,
    output_dir: str,
    imgsz: int = 1280,
    conf: float = 0.3,
    save_video: bool = True,
    save_json: bool = True
) -> List[Dict[str, Any]]:
    """
    Process batch of videos
    
    Args:
        video_paths: List of video file paths
        weights_path: YOLO model weights path
        output_dir: Output directory
        imgsz: Inference image size
        conf: Confidence threshold
        save_video: Save annotated video
        save_json: Save JSON results
    
    Returns:
        List of processing results
    """
    from ultralytics import YOLO
    
    # Load model
    print(f"Loading model: {weights_path}")
    model = YOLO(weights_path)
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Process each video
    all_results = []
    
    for video_path in video_paths:
        video_path = Path(video_path)
        
        if not video_path.exists():
            print(f"⚠ Video not found: {video_path}")
            continue
        
        print(f"\n{'='*60}")
        print(f"Processing: {video_path.name}")
        print(f"{'='*60}")
        
        try:
            # Run inference
            results = model.predict(
                source=str(video_path),
                imgsz=imgsz,
                conf=conf,
                save=save_video,
                project=str(output_path),
                name=video_path.stem,
                exist_ok=True,
                verbose=False
            )
            
            # Extract detection data
            detections = []
            for frame_idx, result in enumerate(results):
                frame_detections = []
                
                if result.boxes is not None:
                    for box in result.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = float(box.conf[0].cpu().numpy())
                        
                        frame_detections.append({
                            'bbox': [float(x1), float(y1), float(x2), float(y2)],
                            'center': [float((x1+x2)/2), float((y1+y2)/2)],
                            'confidence': confidence
                        })
                
                detections.append({
                    'frame': frame_idx,
                    'detections': frame_detections
                })
            
            # Compile results
            video_result = {
                'video_name': video_path.name,
                'frames_processed': len(results),
                'total_detections': sum(len(d['detections']) for d in detections),
                'detections': detections,
                'timestamp': datetime.now().isoformat()
            }
            
            # Save JSON
            if save_json:
                json_path = output_path / f"{video_path.stem}_results.json"
                with open(json_path, 'w') as f:
                    json.dump(video_result, f, indent=2)
                print(f"✓ JSON saved: {json_path}")
            
            all_results.append(video_result)
            
            print(f"✓ Processed {len(results)} frames")
            print(f"✓ Total detections: {video_result['total_detections']}")
            
        except Exception as e:
            print(f"✗ Error processing {video_path.name}: {e}")
            all_results.append({
                'video_name': video_path.name,
                'error': str(e)
            })
    
    # Save summary
    summary_path = output_path / "batch_summary.json"
    with open(summary_path, 'w') as f:
        json.dump({
            'total_videos': len(video_paths),
            'successful': len([r for r in all_results if 'error' not in r]),
            'failed': len([r for r in all_results if 'error' in r]),
            'results': all_results,
            'timestamp': datetime.now().isoformat()
        }, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Batch processing complete!")
    print(f"Summary saved: {summary_path}")
    print(f"{'='*60}\n")
    
    return all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch video processing with YOLO")
    
    parser.add_argument(
        '--videos',
        type=str,
        nargs='+',
        required=True,
        help='Video file paths (space-separated)'
    )
    
    parser.add_argument(
        '--weights',
        type=str,
        required=True,
        help='YOLO model weights path'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='./batch_output',
        help='Output directory'
    )
    
    parser.add_argument(
        '--imgsz',
        type=int,
        default=1280,
        help='Inference image size'
    )
    
    parser.add_argument(
        '--conf',
        type=float,
        default=0.3,
        help='Confidence threshold'
    )
    
    parser.add_argument(
        '--no-video',
        action='store_true',
        help='Skip saving annotated videos'
    )
    
    parser.add_argument(
        '--no-json',
        action='store_true',
        help='Skip saving JSON results'
    )
    
    args = parser.parse_args()
    
    # Process batch
    results = process_video_batch(
        video_paths=args.videos,
        weights_path=args.weights,
        output_dir=args.output,
        imgsz=args.imgsz,
        conf=args.conf,
        save_video=not args.no_video,
        save_json=not args.no_json
    )
    
    print(f"\nProcessed {len(results)} videos")


"""
Usage Examples:

# Process single video
python batch_process.py \
    --videos /path/to/video.mp4 \
    --weights /path/to/best.pt \
    --output ./output

# Process multiple videos
python batch_process.py \
    --videos video1.mp4 video2.mp4 video3.mp4 \
    --weights /path/to/best.pt \
    --imgsz 1280 \
    --conf 0.3

# Process with wildcard (bash)
python batch_process.py \
    --videos /path/to/videos/*.mp4 \
    --weights /path/to/best.pt \
    --no-video  # Only save JSON, skip video rendering
"""
