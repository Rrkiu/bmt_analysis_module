#!/usr/bin/env python3
"""
Quick test script to verify YOLO model loading and detection
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from modules.shuttlecock_detection import create_detector
from modules.shuttlecock_detection.models import Detection
import numpy as np
import cv2


def test_model_loading():
    """Test if the model loads successfully"""
    print("=" * 60)
    print("Testing YOLO Model Loading")
    print("=" * 60)
    
    weights_path = Path(__file__).parent / "weights" / "yolo11n_shuttlecock_best.pt"
    
    if not weights_path.exists():
        print(f"❌ Model file not found: {weights_path}")
        return False
    
    print(f"📁 Model path: {weights_path}")
    print(f"📊 Model size: {weights_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    try:
        # Create detector
        print("\n🔄 Loading model...")
        detector = create_detector(
            model_type='yolo',
            model_path=str(weights_path),
            conf_threshold=0.5,
            device='cpu'  # Use CPU for testing
        )
        
        print("✅ Model loaded successfully!")
        
        # Get model info
        info = detector.get_model_info()
        print("\n📋 Model Information:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        # Test with dummy frame
        print("\n🧪 Testing detection with dummy frame...")
        dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
        detections = detector.detect(dummy_frame)
        
        print(f"✅ Detection test passed!")
        print(f"   Detections found: {len(detections)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_detection_with_image(image_path: str = None):
    """Test detection with a real image"""
    if not image_path:
        print("\n⚠️  No test image provided, skipping image detection test")
        return
    
    print("\n" + "=" * 60)
    print("Testing Detection with Real Image")
    print("=" * 60)
    
    image_path = Path(image_path)
    if not image_path.exists():
        print(f"❌ Image not found: {image_path}")
        return
    
    # Load image
    frame = cv2.imread(str(image_path))
    if frame is None:
        print(f"❌ Failed to load image: {image_path}")
        return
    
    print(f"📷 Image: {image_path.name}")
    print(f"   Size: {frame.shape[1]}x{frame.shape[0]}")
    
    # Load detector
    weights_path = Path(__file__).parent / "weights" / "yolo11n_shuttlecock_best.pt"
    detector = create_detector(
        model_type='yolo',
        model_path=str(weights_path),
        conf_threshold=0.3,
        device='cpu'
    )
    
    # Detect
    print("\n🔍 Running detection...")
    detections = detector.detect(frame)
    
    print(f"\n✅ Detection completed!")
    print(f"   Found {len(detections)} shuttlecock(s)")
    
    # Print detection details
    for i, det in enumerate(detections):
        print(f"\n   Detection {i+1}:")
        print(f"     Position: ({det.x:.1f}, {det.y:.1f})")
        print(f"     Size: {det.width:.1f}x{det.height:.1f}")
        print(f"     Confidence: {det.confidence:.3f}")
    
    # Visualize (optional)
    if len(detections) > 0:
        from modules.shuttlecock_detection.utils import draw_detections
        
        vis_frame = draw_detections(frame, detections)
        output_path = Path(__file__).parent / "test_detection_result.jpg"
        cv2.imwrite(str(output_path), vis_frame)
        print(f"\n💾 Visualization saved: {output_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test YOLO shuttlecock detector")
    parser.add_argument("--image", type=str, help="Path to test image (optional)")
    args = parser.parse_args()
    
    # Test model loading
    success = test_model_loading()
    
    if not success:
        print("\n❌ Model loading test failed!")
        sys.exit(1)
    
    # Test with image if provided
    if args.image:
        test_detection_with_image(args.image)
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
