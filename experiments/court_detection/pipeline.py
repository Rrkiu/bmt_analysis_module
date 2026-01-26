"""End-to-end court detection pipeline

This script provides a unified interface for court detection from RGB images.
It combines mask generation and point detection into a single pipeline.

Usage:
    python pipeline.py --input court.png --output results/
"""

import argparse
import cv2
from pathlib import Path
from modules import MaskGenerator, PointDetector
from modules.utils import make_output_dir, save_image
from config import DEFAULT_CONFIG


def detect_court_from_image(image_path: str,
                            output_dir: str,
                            ensemble_mode: str = 'conservative',
                            use_extrapolation: bool = False,
                            save_intermediate: bool = True) -> dict:
    """
    End-to-end court detection pipeline.
    
    Args:
        image_path: Path to input image
        output_dir: Directory to save results
        ensemble_mode: Mask generation mode ('conservative', 'moderate', 'aggressive')
        use_extrapolation: Enable line extrapolation for endpoint detection
        save_intermediate: Save intermediate results (masks, visualizations)
        
    Returns:
        Dictionary with detection results:
        {
            'corners': {'TL': [x,y], 'TR': [x,y], 'BR': [x,y], 'BL': [x,y]},
            'output_dir': str
        }
    """
    # 1. Load image
    print(f"[INFO] Loading image: {image_path}")
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Failed to load image: {image_path}")
    
    H, W = img.shape[:2]
    print(f"[INFO] Image size: {W}x{H}")
    
    # 2. Create output directory
    out_dir = make_output_dir(output_dir)
    print(f"[INFO] Output directory: {out_dir}")
    
    # 3. Generate mask
    print("\n[STEP 1] Generating court line mask...")
    mask_gen = MaskGenerator(
        ensemble_mode=ensemble_mode,
        save_intermediate=save_intermediate
    )
    mask = mask_gen.generate(img, out_dir if save_intermediate else None)
    save_image(out_dir, "mask_final", mask)
    print(f"[STEP 1] Mask generated successfully")
    
    # 4. Detect corner points
    print("\n[STEP 2] Detecting corner points...")
    detector = PointDetector(
        use_extrapolation=use_extrapolation,
        save_intermediate=save_intermediate
    )
    corners = detector.detect(mask, img, out_dir if save_intermediate else None)
    print(f"[STEP 2] Corner points detected successfully")
    
    # 5. Save results
    print("\n[STEP 3] Saving results...")
    save_results(corners, out_dir)
    
    print(f"\n{'='*60}")
    print("[RESULT] Detected corner points:")
    print(f"{'='*60}")
    for key in ['TL', 'TR', 'BR', 'BL']:
        pt = corners[key]
        print(f"  {key}: ({pt[0]:.2f}, {pt[1]:.2f})")
    
    print(f"\n[DONE] All results saved to: {out_dir}")
    print(f"{'='*60}")
    
    return {
        'corners': corners,
        'output_dir': str(out_dir)
    }


def save_results(corners: dict, out_dir: Path):
    """
    Save corner coordinates to text file.
    
    Args:
        corners: Dictionary with corner points
        out_dir: Output directory
    """
    # Detailed text file
    txt_file = out_dir / "corners.txt"
    with open(txt_file, 'w') as f:
        f.write("Court Corner Points\n")
        f.write("===================\n\n")
        for key in ['TL', 'TR', 'BR', 'BL']:
            pt = corners[key]
            f.write(f"{key}: ({pt[0]:.2f}, {pt[1]:.2f})\n")
    print(f"[SAVED] {txt_file}")
    
    # Compact JSON-like file
    txt_compact = out_dir / "corners_compact.txt"
    with open(txt_compact, 'w') as f:
        parts = [f'"{k}":[{corners[k][0]:.3f},{corners[k][1]:.3f}]' 
                 for k in ['TL', 'TR', 'BR', 'BL']]
        f.write("{" + ", ".join(parts) + "}\n")
    print(f"[SAVED] {txt_compact}")


def main():
    """Main entry point for CLI usage"""
    parser = argparse.ArgumentParser(
        description="Court detection pipeline - detect 4 corner points from RGB image",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python pipeline.py --input court.png --output results/
  
  # With extrapolation enabled
  python pipeline.py --input court.png --output results/ --extrapolation
  
  # Aggressive mask mode (higher recall)
  python pipeline.py --input court.png --output results/ --ensemble aggressive
  
  # Minimal output (no intermediate files)
  python pipeline.py --input court.png --output results/ --no-intermediate
        """
    )
    
    parser.add_argument("--input", required=True,
                       help="Input image path")
    parser.add_argument("--output", required=True,
                       help="Output directory for results")
    parser.add_argument("--ensemble", default='conservative',
                       choices=['conservative', 'moderate', 'aggressive'],
                       help="Mask generation mode (default: conservative)")
    parser.add_argument("--extrapolation", action='store_true',
                       help="Enable line extrapolation for endpoint detection")
    parser.add_argument("--no-intermediate", action='store_true',
                       help="Don't save intermediate results (only final output)")
    
    args = parser.parse_args()
    
    try:
        detect_court_from_image(
            image_path=args.input,
            output_dir=args.output,
            ensemble_mode=args.ensemble,
            use_extrapolation=args.extrapolation,
            save_intermediate=not args.no_intermediate
        )
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
