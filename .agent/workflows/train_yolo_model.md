---
description: Train YOLO model with validated configuration
---

# Train YOLO Model Workflow

This workflow guides you through training a YOLOv8/v11 model for shuttlecock detection with validated, production-ready settings.

## Prerequisites

- Dataset prepared in YOLO format
- GPU with CUDA support (recommended)
- WandB account for experiment tracking

## Steps

### 1. Navigate to Training Directory

```bash
cd /mnt/b/cd_p/bmt_demo/experiments/shuttlecock_detection/yolo
```

### 2. Validate Dataset Structure

Check that your dataset is properly formatted:

```bash
python scripts/validate_dataset.py --dataset_path ./dataset
```

**Expected Output**:
- ✓ data.yaml found
- ✓ Training set: N images, N labels
- ✓ Validation set: N images, N labels
- ✓ All images and labels valid

**If validation fails**: Fix dataset issues before proceeding.

### 3. Configure Training Parameters

Edit `config/train_config.yaml`:

```yaml
# Key settings to review:
model: yolov8m.pt        # yolov8n/s/m for different speed/accuracy tradeoffs
data: /path/to/dataset/data.yaml  # Update to your dataset path
epochs: 100              # Adjust based on dataset size
imgsz: 1280              # ✅ Keep at 1280 for shuttlecock detection
batch: 4                 # Reduce if OOM errors occur
amp: True                # ✅ Keep enabled for memory efficiency
```

**Recommended Settings** (from past experiments):
- **Best Accuracy**: `yolov8m.pt`, `imgsz: 1280`, `batch: 4`
- **Faster Training**: `yolov8s.pt`, `imgsz: 1280`, `batch: 8`
- **Memory Constrained**: `yolov8n.pt`, `imgsz: 1280`, `batch: 2`

### 4. Setup WandB (First Time Only)

If you haven't configured WandB yet:

```bash
# Login to WandB
wandb login

# Or set API key in run_with_wandb.sh
# Edit scripts/run_with_wandb.sh and add your key
```

### 5. Start Training

// turbo
```bash
sh scripts/run_with_wandb.sh
```

**What this does**:
1. Validates ultralytics and wandb installation
2. Sets WandB API key
3. Runs training with config from `config/train_config.yaml`
4. Auto-generates experiment name: `{model}_{timestamp}`

**Training will start**. Monitor progress in terminal and WandB dashboard.

### 6. Monitor Training

**Terminal Output**: Watch for:
- Epoch progress
- Loss values (should decrease)
- mAP metrics (should increase)

**WandB Dashboard**: https://wandb.ai/your-project/shuttlecock_detection
- Real-time metrics
- Training curves
- System resources

**Expected Training Time**:
- YOLOv8n: ~2-3 hours (100 epochs, RTX 3090)
- YOLOv8m: ~4-6 hours (100 epochs, RTX 3090)

### 7. Validate Results

After training completes, check the results:

```bash
# Navigate to experiment directory
cd experiments/{model}_{timestamp}

# Check training curves
ls results.png

# List saved weights
ls weights/
# Should see: best.pt, last.pt
```

**Key Files**:
- `weights/best.pt`: Best mAP model (use this for production)
- `weights/last.pt`: Last epoch (use if training interrupted)
- `args.yaml`: Training arguments (for reproducibility)
- `results.png`: Training curves

### 8. Test Inference

Test the trained model on a video:

```bash
python scripts/predict_video.py \
    --weights experiments/{exp_name}/weights/best.pt \
    --source /path/to/test/video.mp4 \
    --imgsz 1280 \
    --conf 0.25
```

**Check Output**:
- Visualization saved in `test_video_output/{exp_name}_{timestamp}/`
- Review detection quality

### 9. Evaluate Performance

**Good Performance Indicators**:
- ✅ mAP@0.5 > 0.8
- ✅ Detections visible in test video
- ✅ Low false positives
- ✅ Consistent detection across frames

**If Performance is Poor**:
- Check dataset quality (labels correct?)
- Try longer training (increase epochs)
- Adjust confidence threshold in inference
- Review augmentation settings

### 10. Deploy to Production (Optional)

If results are satisfactory:

```bash
# Copy best weights to production location
cp experiments/{exp_name}/weights/best.pt \
   /mnt/b/cd_p/bmt_demo/core/backend/modules/shuttlecock_detection/weights/yolo_production.pt

# Update backend configuration to use new weights
# Edit: core/backend/main.py or config file
```

## Troubleshooting

### Out of Memory (OOM)

**Symptoms**: CUDA OOM error during training

**Solutions**:
1. Reduce batch size in `config/train_config.yaml`: `batch: 2` or `batch: 1`
2. Ensure FP16 is enabled: `amp: True`
3. Use smaller model: `yolov8s.pt` instead of `yolov8m.pt`

### Low mAP (< 0.7)

**Symptoms**: Model performs poorly on validation

**Solutions**:
1. Verify `imgsz: 1280` (NOT 640)
2. Check dataset labels are correct
3. Increase training epochs: `epochs: 150`
4. Lower confidence during training: `conf: 0.001`

### Training Crashes

**Symptoms**: Script exits unexpectedly

**Solutions**:
1. Verify dataset paths in `data.yaml`
2. Run dataset validation: `python scripts/validate_dataset.py`
3. Check GPU memory: `nvidia-smi`
4. Review error logs

## Notes

- **Always use imgsz=1280** for shuttlecock detection (small object)
- **Enable FP16** (`amp: True`) for 40% memory savings
- **Save checkpoints** every 5 epochs for recovery
- **Document experiments** in SKILL.md for future reference

## Related Skills

- YOLO Training: `.agent/skills/yolo_training/SKILL.md`
- Video Processing: `.agent/skills/video_processing/SKILL.md`
