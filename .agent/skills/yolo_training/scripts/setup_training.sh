#!/bin/bash

# ==========================================
# YOLO Training Environment Setup Script
# ==========================================

set -e  # Exit on error

echo "=========================================="
echo "YOLO Training Environment Setup"
echo "=========================================="

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "Project Root: $PROJECT_ROOT"
echo ""

# Check Python version
echo "[1/5] Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION"

# Check CUDA availability
echo ""
echo "[2/5] Checking CUDA availability..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    echo "✓ CUDA available"
else
    echo "⚠ CUDA not found. Training will use CPU (slower)"
fi

# Install required packages
echo ""
echo "[3/5] Installing required packages..."
pip install -q ultralytics wandb pyyaml opencv-python numpy

echo "✓ Packages installed"

# Verify installations
echo ""
echo "[4/5] Verifying installations..."
python3 -c "import ultralytics; print(f'✓ ultralytics {ultralytics.__version__}')"
python3 -c "import wandb; print(f'✓ wandb {wandb.__version__}')"
python3 -c "import cv2; print(f'✓ opencv {cv2.__version__}')"

# Check dataset structure
echo ""
echo "[5/5] Checking dataset structure..."
DATASET_DIR="$PROJECT_ROOT/experiments/shuttlecock_detection/yolo/dataset"

if [ -d "$DATASET_DIR" ]; then
    echo "✓ Dataset directory exists: $DATASET_DIR"
    
    if [ -f "$DATASET_DIR/data.yaml" ]; then
        echo "✓ data.yaml found"
    else
        echo "⚠ data.yaml not found"
    fi
    
    if [ -d "$DATASET_DIR/train/images" ] && [ -d "$DATASET_DIR/train/labels" ]; then
        TRAIN_IMAGES=$(ls -1 "$DATASET_DIR/train/images" 2>/dev/null | wc -l)
        TRAIN_LABELS=$(ls -1 "$DATASET_DIR/train/labels" 2>/dev/null | wc -l)
        echo "✓ Training set: $TRAIN_IMAGES images, $TRAIN_LABELS labels"
    else
        echo "⚠ Training set not found"
    fi
    
    if [ -d "$DATASET_DIR/val/images" ] && [ -d "$DATASET_DIR/val/labels" ]; then
        VAL_IMAGES=$(ls -1 "$DATASET_DIR/val/images" 2>/dev/null | wc -l)
        VAL_LABELS=$(ls -1 "$DATASET_DIR/val/labels" 2>/dev/null | wc -l)
        echo "✓ Validation set: $VAL_IMAGES images, $VAL_LABELS labels"
    else
        echo "⚠ Validation set not found"
    fi
else
    echo "⚠ Dataset directory not found: $DATASET_DIR"
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Configure training: edit config/train_config.yaml"
echo "2. Validate dataset: python scripts/validate_dataset.py"
echo "3. Start training: sh scripts/run_with_wandb.sh"
