"""
Example usage scripts for court detection

This file demonstrates how to use the 3-layer architecture:
1. API usage (production)
2. Test pipeline usage (development)
3. Core detector usage (direct)
"""

import cv2
import numpy as np
from pathlib import Path

# ============================================================================
# Example 1: API Usage (Production - Recommended for backend integration)
# ============================================================================

def example_api_basic():
    """Basic API usage - no file I/O"""
    print("\n" + "="*70)
    print("Example 1: Basic API Usage")
    print("="*70)
    
    from api import detect_court_api
    
    # Load image
    image = cv2.imread('source_image/pro_court.png')
    
    # Detect (works entirely in memory)
    result = detect_court_api(image)
    
    if result['success']:
        print("\n✓ Detection successful!")
        print(f"\nCorners:")
        for key in ['TL', 'TR', 'BR', 'BL']:
            pt = result['corners'][key]
            print(f"  {key}: ({pt[0]:.2f}, {pt[1]:.2f})")
        
        print(f"\nProcessing time: {result['metadata']['processing_time_seconds']:.3f}s")
    else:
        print(f"\n✗ Detection failed: {result['error']}")


def example_api_with_debug():
    """API usage with debug mode - saves to storage/"""
    print("\n" + "="*70)
    print("Example 2: API Usage with Debug Mode")
    print("="*70)
    
    from api import detect_court_api
    
    image = cv2.imread('source_image/pro_court.png')
    
    # Enable debug mode - will save to storage/
    result = detect_court_api(
        image,
        ensemble_mode='conservative',
        use_extrapolation=False,
        debug=True,  # Enable debug output
        debug_storage_root='/mnt/b/cd_p/bmt_demo/core/storage'
    )
    
    if result['success']:
        print("\n✓ Detection successful!")
        print(f"\nDebug output saved to:")
        print(f"  {result['debug_path']}")
    else:
        print(f"\n✗ Detection failed: {result['error']}")


def example_api_from_file():
    """API convenience function - load from file"""
    print("\n" + "="*70)
    print("Example 3: API from File (Convenience)")
    print("="*70)
    
    from api import detect_from_file
    
    # Convenience wrapper that loads image
    result = detect_from_file(
        'source_image/pro_court.png',
        debug=True
    )
    
    if result['success']:
        print("\n✓ Detection successful!")
        corners = result['corners']
        print(f"\nTL: {corners['TL']}")
        print(f"TR: {corners['TR']}")
        print(f"BR: {corners['BR']}")
        print(f"BL: {corners['BL']}")


# ============================================================================
# Example 2: Test Pipeline Usage (Development)
# ============================================================================

def example_test_pipeline():
    """Test pipeline with full intermediate output"""
    print("\n" + "="*70)
    print("Example 4: Test Pipeline (Full Output)")
    print("="*70)
    
    from test_pipeline import test_court_detection
    
    result = test_court_detection(
        image_path='source_image/pro_court.png',
        output_dir='example_test_results',
        ensemble_mode='conservative',
        use_extrapolation=False,
        verbose=True  # Print detailed progress
    )
    
    print(f"\nTest completed!")
    print(f"Output directory: {result['output_dir']}")


# ============================================================================
# Example 3: Core Detector Usage (Direct)
# ============================================================================

def example_core_detector():
    """Using core detector directly"""
    print("\n" + "="*70)
    print("Example 5: Core Detector (Direct)")
    print("="*70)
    
    from core_detector import CourtDetector
    
    # Load image
    image = cv2.imread('source_image/pro_court.png')
    
    # Create detector
    detector = CourtDetector(
        ensemble_mode='conservative',
        use_extrapolation=False
    )
    
    # Detect
    result = detector.detect(
        image,
        return_mask=True,
        return_metadata=True
    )
    
    print("\n✓ Detection completed!")
    print(f"\nCorners:")
    for key, pt in result['corners'].items():
        print(f"  {key}: ({pt[0]:.2f}, {pt[1]:.2f})")
    
    print(f"\nMetadata:")
    for key, value in result['metadata'].items():
        print(f"  {key}: {value}")
    
    # Access mask
    mask = result['mask']
    print(f"\nMask shape: {mask.shape}")
    print(f"White pixels: {np.sum(mask > 0):,}")


# ============================================================================
# Example 4: Batch Processing
# ============================================================================

def example_batch_processing():
    """Batch processing multiple images"""
    print("\n" + "="*70)
    print("Example 6: Batch Processing")
    print("="*70)
    
    from test_pipeline import batch_test
    
    batch_test(
        image_dir='source_image/',
        output_root='example_batch_results',
        ensemble_mode='conservative',
        use_extrapolation=False
    )


# ============================================================================
# Example 5: Integration with Backend API
# ============================================================================

def example_backend_integration():
    """
    Example of how to integrate with FastAPI/Flask backend
    
    This is pseudocode showing the integration pattern.
    """
    print("\n" + "="*70)
    print("Example 7: Backend Integration (Pseudocode)")
    print("="*70)
    
    code = '''
# FastAPI example
from fastapi import FastAPI, File, UploadFile
from api import detect_from_bytes
import json

app = FastAPI()

@app.post("/detect-court")
async def detect_court_endpoint(file: UploadFile = File(...)):
    """Court detection API endpoint"""
    
    # Read image bytes
    image_bytes = await file.read()
    
    # Detect
    result = detect_from_bytes(
        image_bytes,
        ensemble_mode='conservative',
        debug=False  # No debug in production
    )
    
    return result

# Flask example
from flask import Flask, request, jsonify
from api import detect_from_bytes

app = Flask(__name__)

@app.route('/detect-court', methods=['POST'])
def detect_court_endpoint():
    """Court detection API endpoint"""
    
    # Get image from request
    image_file = request.files['image']
    image_bytes = image_file.read()
    
    # Detect
    result = detect_from_bytes(
        image_bytes,
        ensemble_mode='conservative',
        debug=False
    )
    
    return jsonify(result)
    '''
    
    print(code)


# ============================================================================
# Main - Run all examples
# ============================================================================

def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("COURT DETECTION - USAGE EXAMPLES")
    print("="*70)
    
    # Check if test image exists
    if not Path('source_image/pro_court.png').exists():
        print("\n⚠️  Test image not found: source_image/pro_court.png")
        print("Please ensure test images are available.")
        return
    
    # Run examples
    try:
        # API examples
        example_api_basic()
        # example_api_with_debug()  # Uncomment to test debug mode
        # example_api_from_file()
        
        # Test pipeline
        # example_test_pipeline()  # Uncomment to test full pipeline
        
        # Core detector
        # example_core_detector()
        
        # Batch processing
        # example_batch_processing()  # Uncomment to test batch
        
        # Backend integration
        example_backend_integration()
        
    except Exception as e:
        print(f"\n✗ Example failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print("Examples completed!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
