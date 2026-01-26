"""Test pipeline for court detection

Full-featured pipeline for testing and development.
Saves all intermediate results for debugging and analysis.

This pipeline is designed for:
- Development and debugging
- Performance testing
- Visual inspection of intermediate results
- Batch processing with full output
"""

import argparse
import cv2
import numpy as np
from pathlib import Path
import sys
import json
from datetime import datetime
from typing import Dict

from core_detector import CourtDetector
from modules import MaskGenerator, PointDetector
from modules.utils import make_output_dir, save_image, to_bgr
from config import DEFAULT_CONFIG


def test_court_detection(image_path: str,
                         output_dir: str,
                         ensemble_mode: str = 'conservative',
                         use_extrapolation: bool = False,
                         verbose: bool = True) -> Dict:
    """
    Test pipeline with full intermediate output.
    
    This function runs the complete detection pipeline and saves all
    intermediate results for debugging and analysis.
    
    Args:
        image_path: Path to input image
        output_dir: Directory to save all results
        ensemble_mode: Mask generation mode
        use_extrapolation: Enable line extrapolation
        verbose: Print detailed progress information
        
    Returns:
        Detection results dictionary with additional test metadata
    """
    if verbose:
        print(f"\n{'='*70}")
        print("COURT DETECTION TEST PIPELINE")
        print(f"{'='*70}")
    
    start_time = datetime.now()
    
    # ========================================
    # Step 1: Load Image
    # ========================================
    if verbose:
        print(f"\n[1/5] Loading image...")
        print(f"  Input: {image_path}")
    
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Failed to load image: {image_path}")
    
    H, W = image.shape[:2]
    if verbose:
        print(f"  Size: {W}x{H}")
        print(f"  Channels: {image.shape[2]}")
        print(f"  Dtype: {image.dtype}")
    
    # ========================================
    # Step 2: Create Output Directory
    # ========================================
    if verbose:
        print(f"\n[2/5] Creating output directory...")
    
    out_dir = make_output_dir(output_dir)
    
    if verbose:
        print(f"  Output: {out_dir}")
    
    # Save original image
    save_image(out_dir, "00_original", image)
    
    # Save test configuration
    config_data = {
        'input_image': str(image_path),
        'image_size': [W, H],
        'ensemble_mode': ensemble_mode,
        'use_extrapolation': use_extrapolation,
        'timestamp': datetime.now().isoformat()
    }
    
    with open(out_dir / "test_config.json", 'w') as f:
        json.dump(config_data, f, indent=2)
    
    # ========================================
    # Step 3: Generate Mask (with intermediates)
    # ========================================
    if verbose:
        print(f"\n[3/5] Generating court line mask...")
        print(f"  Ensemble mode: {ensemble_mode}")
    
    mask_gen = MaskGenerator(
        ensemble_mode=ensemble_mode,
        save_intermediate=True  # Save all intermediate steps
    )
    
    mask_start = datetime.now()
    mask = mask_gen.generate(image, out_dir)
    mask_time = (datetime.now() - mask_start).total_seconds()
    
    save_image(out_dir, "10_mask_final", mask)
    
    if verbose:
        white_pixels = np.sum(mask > 0)
        coverage = white_pixels / (H * W) * 100
        print(f"  Mask generated in {mask_time:.3f}s")
        print(f"  White pixels: {white_pixels:,} ({coverage:.2f}%)")
    
    # ========================================
    # Step 4: Detect Corners (with intermediates)
    # ========================================
    if verbose:
        print(f"\n[4/5] Detecting corner points...")
        print(f"  Extrapolation: {use_extrapolation}")
    
    point_detector = PointDetector(
        use_extrapolation=use_extrapolation,
        save_intermediate=True  # Save all intermediate steps
    )
    
    detect_start = datetime.now()
    corners = point_detector.detect(mask, image, out_dir)
    detect_time = (datetime.now() - detect_start).total_seconds()
    
    if verbose:
        print(f"  Corners detected in {detect_time:.3f}s")
    
    # ========================================
    # Step 5: Save Final Results
    # ========================================
    if verbose:
        print(f"\n[5/5] Saving final results...")
    
    # Create comprehensive visualization
    vis = image.copy()
    
    # Draw corners with labels
    for key, pt in corners.items():
        # Color coding: red for left, green for right
        color = (0, 0, 255) if key in ['TL', 'BL'] else (0, 255, 0)
        
        # Draw filled circle
        cv2.circle(vis, (int(pt[0]), int(pt[1])), 12, color, -1, cv2.LINE_AA)
        
        # Draw white outline
        cv2.circle(vis, (int(pt[0]), int(pt[1])), 14, (255, 255, 255), 2, cv2.LINE_AA)
        
        # Draw label with background
        label_pos = (int(pt[0]) + 20, int(pt[1]) - 20)
        cv2.putText(vis, key, label_pos,
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 5, cv2.LINE_AA)
        cv2.putText(vis, key, label_pos,
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3, cv2.LINE_AA)
    
    # Draw quadrilateral
    quad_pts = np.array([
        corners['TL'], corners['TR'], 
        corners['BR'], corners['BL']
    ], dtype=np.int32)
    cv2.polylines(vis, [quad_pts], True, (255, 0, 255), 5, cv2.LINE_AA)
    
    save_image(out_dir, "99_final_result", vis)
    
    # Save corner coordinates (multiple formats)
    
    # 1. JSON format
    corners_json = {
        k: v.tolist() if isinstance(v, np.ndarray) else list(v)
        for k, v in corners.items()
    }
    
    with open(out_dir / "corners.json", 'w') as f:
        json.dump(corners_json, f, indent=2)
    
    # 2. Text format (human-readable)
    with open(out_dir / "corners.txt", 'w') as f:
        f.write("Court Corner Points\n")
        f.write("=" * 50 + "\n\n")
        for key in ['TL', 'TR', 'BR', 'BL']:
            pt = corners[key]
            f.write(f"{key}: ({pt[0]:8.2f}, {pt[1]:8.2f})\n")
    
    # 3. Compact format (for copy-paste)
    with open(out_dir / "corners_compact.txt", 'w') as f:
        parts = [f'"{k}":[{corners[k][0]:.3f},{corners[k][1]:.3f}]' 
                 for k in ['TL', 'TR', 'BR', 'BL']]
        f.write("{" + ", ".join(parts) + "}\n")
    
    # Save test summary
    total_time = (datetime.now() - start_time).total_seconds()
    
    summary = {
        'test_info': config_data,
        'results': {
            'corners': corners_json,
            'image_size': [W, H]
        },
        'performance': {
            'total_time_seconds': round(total_time, 3),
            'mask_generation_seconds': round(mask_time, 3),
            'corner_detection_seconds': round(detect_time, 3)
        },
        'mask_stats': {
            'white_pixels': int(np.sum(mask > 0)),
            'coverage_percent': round(np.sum(mask > 0) / (H * W) * 100, 2)
        }
    }
    
    with open(out_dir / "test_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Print results
    if verbose:
        print(f"\n{'='*70}")
        print("DETECTION RESULTS")
        print(f"{'='*70}")
        for key in ['TL', 'TR', 'BR', 'BL']:
            pt = corners[key]
            print(f"  {key}: ({pt[0]:8.2f}, {pt[1]:8.2f})")
        
        print(f"\n{'='*70}")
        print("PERFORMANCE")
        print(f"{'='*70}")
        print(f"  Total time:      {total_time:.3f}s")
        print(f"  Mask generation: {mask_time:.3f}s")
        print(f"  Corner detection: {detect_time:.3f}s")
        
        print(f"\n{'='*70}")
        print(f"All results saved to: {out_dir}")
        print(f"{'='*70}\n")
    
    return {
        'corners': corners,
        'output_dir': str(out_dir),
        'image_size': (W, H),
        'performance': summary['performance'],
        'mask_stats': summary['mask_stats']
    }


def batch_test(image_dir: str,
               output_root: str,
               ensemble_mode: str = 'conservative',
               use_extrapolation: bool = False):
    """
    Run test pipeline on multiple images.
    
    Args:
        image_dir: Directory containing input images
        output_root: Root directory for outputs
        ensemble_mode: Mask generation mode
        use_extrapolation: Enable line extrapolation
    """
    image_dir = Path(image_dir)
    
    # Find all images
    image_extensions = ['.png', '.jpg', '.jpeg', '.bmp']
    images = []
    for ext in image_extensions:
        images.extend(image_dir.glob(f'*{ext}'))
        images.extend(image_dir.glob(f'*{ext.upper()}'))
    
    if not images:
        print(f"No images found in: {image_dir}")
        return
    
    print(f"\nFound {len(images)} images")
    print(f"{'='*70}\n")
    
    results = []
    
    for i, img_path in enumerate(images, 1):
        print(f"[{i}/{len(images)}] Processing: {img_path.name}")
        
        try:
            result = test_court_detection(
                image_path=str(img_path),
                output_dir=output_root,
                ensemble_mode=ensemble_mode,
                use_extrapolation=use_extrapolation,
                verbose=False
            )
            
            results.append({
                'image': img_path.name,
                'success': True,
                'output_dir': result['output_dir'],
                'performance': result['performance']
            })
            
            print(f"  ✓ Success (took {result['performance']['total_time_seconds']:.3f}s)")
            
        except Exception as e:
            results.append({
                'image': img_path.name,
                'success': False,
                'error': str(e)
            })
            print(f"  ✗ Failed: {e}")
    
    # Save batch summary
    batch_summary = {
        'total_images': len(images),
        'successful': sum(1 for r in results if r['success']),
        'failed': sum(1 for r in results if not r['success']),
        'results': results
    }
    
    summary_path = Path(output_root) / f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_path, 'w') as f:
        json.dump(batch_summary, f, indent=2)
    
    print(f"\n{'='*70}")
    print(f"Batch processing complete: {batch_summary['successful']}/{batch_summary['total_images']} successful")
    print(f"Summary saved to: {summary_path}")
    print(f"{'='*70}\n")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Test pipeline for court detection with full intermediate output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single image test
  python test_pipeline.py --input court.png --output test_results/
  
  # With extrapolation
  python test_pipeline.py --input court.png --output test_results/ --extrapolation
  
  # Aggressive mode
  python test_pipeline.py --input court.png --output test_results/ --ensemble aggressive
  
  # Batch processing
  python test_pipeline.py --batch source_image/ --output batch_results/
        """
    )
    
    parser.add_argument("--input", 
                       help="Input image path (for single image)")
    parser.add_argument("--batch",
                       help="Input directory (for batch processing)")
    parser.add_argument("--output", required=True,
                       help="Output directory")
    parser.add_argument("--ensemble", default='conservative',
                       choices=['conservative', 'moderate', 'aggressive'],
                       help="Mask generation mode (default: conservative)")
    parser.add_argument("--extrapolation", action='store_true',
                       help="Enable line extrapolation")
    parser.add_argument("--quiet", action='store_true',
                       help="Suppress verbose output")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.input and not args.batch:
        parser.error("Either --input or --batch must be specified")
    
    if args.input and args.batch:
        parser.error("Cannot specify both --input and --batch")
    
    try:
        if args.batch:
            # Batch processing
            batch_test(
                image_dir=args.batch,
                output_root=args.output,
                ensemble_mode=args.ensemble,
                use_extrapolation=args.extrapolation
            )
        else:
            # Single image
            test_court_detection(
                image_path=args.input,
                output_dir=args.output,
                ensemble_mode=args.ensemble,
                use_extrapolation=args.extrapolation,
                verbose=not args.quiet
            )
        
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        if not args.quiet:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
