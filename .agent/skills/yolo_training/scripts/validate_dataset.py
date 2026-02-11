#!/usr/bin/env python3
"""
Dataset Validation Script for YOLO Training

Validates:
1. Dataset structure (train/val folders)
2. Image-label pairing
3. Label format (YOLO format)
4. Image readability
"""

import argparse
from pathlib import Path
import yaml
from typing import Tuple, List
import cv2


def validate_yolo_label(label_path: Path) -> Tuple[bool, str]:
    """Validate YOLO format label file"""
    try:
        with open(label_path, 'r') as f:
            lines = f.readlines()
        
        if not lines:
            return True, "Empty label (no objects)"
        
        for line_num, line in enumerate(lines, 1):
            parts = line.strip().split()
            
            if len(parts) != 5:
                return False, f"Line {line_num}: Expected 5 values (class x y w h), got {len(parts)}"
            
            try:
                class_id = int(parts[0])
                x, y, w, h = map(float, parts[1:])
                
                # Validate ranges
                if not (0 <= x <= 1 and 0 <= y <= 1 and 0 <= w <= 1 and 0 <= h <= 1):
                    return False, f"Line {line_num}: Coordinates must be in [0, 1]"
                
            except ValueError as e:
                return False, f"Line {line_num}: Invalid number format - {e}"
        
        return True, "Valid"
    
    except Exception as e:
        return False, f"Error reading file: {e}"


def validate_image(image_path: Path) -> Tuple[bool, str]:
    """Validate image file"""
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            return False, "Cannot read image"
        
        h, w = img.shape[:2]
        if h == 0 or w == 0:
            return False, f"Invalid dimensions: {w}x{h}"
        
        return True, f"{w}x{h}"
    
    except Exception as e:
        return False, f"Error: {e}"


def validate_dataset(dataset_path: Path) -> None:
    """Main validation function"""
    
    print("=" * 60)
    print("YOLO Dataset Validation")
    print("=" * 60)
    print(f"Dataset: {dataset_path}")
    print()
    
    # Check data.yaml
    data_yaml = dataset_path / "data.yaml"
    if not data_yaml.exists():
        print("❌ data.yaml not found!")
        return
    
    print("✓ data.yaml found")
    
    with open(data_yaml, 'r') as f:
        data_config = yaml.safe_load(f)
    
    print(f"  - Classes: {data_config.get('names', [])}")
    print(f"  - NC: {data_config.get('nc', 'N/A')}")
    print()
    
    # Validate train and val sets
    for split in ['train', 'val']:
        print(f"[{split.upper()}]")
        
        images_dir = dataset_path / split / "images"
        labels_dir = dataset_path / split / "labels"
        
        if not images_dir.exists():
            print(f"  ❌ Images directory not found: {images_dir}")
            continue
        
        if not labels_dir.exists():
            print(f"  ❌ Labels directory not found: {labels_dir}")
            continue
        
        # Get all images
        image_files = sorted(list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png")))
        
        if not image_files:
            print(f"  ⚠ No images found in {images_dir}")
            continue
        
        print(f"  Found {len(image_files)} images")
        
        # Validate each image-label pair
        errors = []
        warnings = []
        
        for img_path in image_files:
            # Check corresponding label
            label_path = labels_dir / f"{img_path.stem}.txt"
            
            if not label_path.exists():
                warnings.append(f"Missing label: {img_path.name}")
                continue
            
            # Validate image
            img_valid, img_msg = validate_image(img_path)
            if not img_valid:
                errors.append(f"{img_path.name}: {img_msg}")
                continue
            
            # Validate label
            label_valid, label_msg = validate_yolo_label(label_path)
            if not label_valid:
                errors.append(f"{label_path.name}: {label_msg}")
        
        # Report results
        if errors:
            print(f"  ❌ {len(errors)} errors found:")
            for error in errors[:5]:  # Show first 5
                print(f"     - {error}")
            if len(errors) > 5:
                print(f"     ... and {len(errors) - 5} more")
        else:
            print(f"  ✓ All images and labels valid")
        
        if warnings:
            print(f"  ⚠ {len(warnings)} warnings:")
            for warning in warnings[:5]:
                print(f"     - {warning}")
            if len(warnings) > 5:
                print(f"     ... and {len(warnings) - 5} more")
        
        print()
    
    print("=" * 60)
    print("Validation Complete")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate YOLO dataset structure and format")
    parser.add_argument(
        '--dataset_path',
        type=str,
        default='/mnt/b/cd_p/bmt_demo/experiments/shuttlecock_detection/yolo/dataset',
        help='Path to dataset root directory'
    )
    
    args = parser.parse_args()
    dataset_path = Path(args.dataset_path)
    
    if not dataset_path.exists():
        print(f"❌ Dataset path does not exist: {dataset_path}")
        exit(1)
    
    validate_dataset(dataset_path)
