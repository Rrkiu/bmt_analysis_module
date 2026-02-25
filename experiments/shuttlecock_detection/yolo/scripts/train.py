#!/usr/bin/env python3
"""
YOLO Training Script
Loads configuration from yaml and starts training.
"""

import argparse
import yaml
import shutil
from pathlib import Path
from ultralytics import YOLO
import os
import sys

# update wandb settings
from ultralytics import settings
settings.update({"wandb": True})

def setup_wandb(config):
    """
    Setup WandB using environment variables (Docker-friendly).
    """
    try:
        import wandb
        from ultralytics import settings

        # 1. API Key check (Docker env)
        if "WANDB_API_KEY" not in os.environ:
            print("⚠️ WANDB_API_KEY not found in environment. WandB disabled.")
            return False

        # 2. Set WandB environment variables
        os.environ["WANDB_PROJECT"] = config.get("wandb_project", "shuttlecock_detection")
        os.environ["WANDB_NAME"] = config.get("name", "train")
        os.environ["WANDB_MODE"] = config.get("wandb_mode", "online")  # online / offline / disabled

        # Optional (팀 계정 사용 시)
        if "wandb_entity" in config:
            os.environ["WANDB_ENTITY"] = config["wandb_entity"]

        # 3. Explicitly enable WandB in Ultralytics
        settings.update({"wandb": True})

        print("✅ WandB enabled (env-based login).")
        print(f"   Project: {os.environ['WANDB_PROJECT']}")
        print(f"   Run name: {os.environ['WANDB_NAME']}")

        return True

    except ImportError:
        print("⚠️ wandb not installed. WandB logging skipped.")
        return False
    except Exception as e:
        print(f"⚠️ WandB setup failed: {e}")
        return False


def train(config_path):
    # 1. Load Configuration
    config_path = Path(config_path)
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        return

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    print("=" * 60)
    print(f"Starting Training with config: {config_path}")
    print("=" * 60)
    for k, v in config.items():
        print(f"{k}: {v}")
    print("=" * 60)

    # 3. Setup Paths
    project_dir = Path(config.get("project", "runs/detect"))
    
    # Auto-generate experiment name to prevent overwriting
    # Format: {model_basename}_{timestamp}
    # e.g., yolo11n_20260202_183045
    experiment_name = config.get("name")
    if not experiment_name or experiment_name == "null":
        from datetime import datetime
        model_name = config.get("model", "yolov8n.pt")
        model_basename = Path(model_name).stem  # yolo11n.pt -> yolo11n
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        experiment_name = f"{model_basename}_{timestamp}"
        print(f"📝 Auto-generated experiment name: {experiment_name}")
    
    # 4. Setup WandB (after experiment name is generated)
    config_with_name = config.copy()
    config_with_name["name"] = experiment_name
    setup_wandb(config_with_name)
    
    project_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 4. Initialize Model
        model_name = config.get("model", "yolov8n.pt")
        print(f"\nInitializing model: {model_name}")
        model = YOLO(model_name)

        # 5. Train
        print("\nStarting training process...")
        
        # Build training arguments
        train_args = {
            'data': config["data"],
            'epochs': config.get("epochs", 100),
            'imgsz': config.get("imgsz", 640),
            'batch': config.get("batch", 16),
            'device': config.get("device", 0),
            'project': str(project_dir),
            'name': experiment_name,
            'patience': config.get("patience", 50),
            'save': config.get("save", True),
            'save_period': config.get("save_period", -1),
            'workers': config.get("workers", 8),
            'optimizer': config.get("optimizer", "auto"),
            'lr0': config.get("lr0", 0.01),
            'amp': config.get("amp", True),
            'exist_ok': True,
        }
        
        # Add loss function weights (for small object detection)
        if 'box' in config:
            train_args['box'] = config['box']
        if 'cls' in config:
            train_args['cls'] = config['cls']
        if 'dfl' in config:
            train_args['dfl'] = config['dfl']
        
        # Add confidence and IoU thresholds
        if 'conf' in config:
            train_args['conf'] = config['conf']
        if 'iou' in config:
            train_args['iou'] = config['iou']
        
        # Add small object detection parameters
        if 'close_mosaic' in config:
            train_args['close_mosaic'] = config['close_mosaic']
        
        # Add augmentation parameters
        aug_params = ['hsv_h', 'hsv_s', 'hsv_v', 'degrees', 'translate', 'scale', 
                      'shear', 'perspective', 'flipud', 'fliplr', 'mosaic', 'mixup',
                      'copy_paste']
        
        for param in aug_params:
            if param in config:
                train_args[param] = config[param]
        
        results = model.train(**train_args)

        # 6. Post-training: Copy best model
        print("\nTraining completed.")

        run_dir = project_dir / experiment_name
        best_weights = run_dir / "weights" / "best.pt"

        checkpoints_dir = Path(__file__).resolve().parent.parent / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)

        if best_weights.exists():
            # Use experiment name directly (already includes model name and timestamp)
            target_path = checkpoints_dir / f"{experiment_name}_best.pt"
            print(f"✅ Copying best model to checkpoints: {target_path}")
            shutil.copy2(best_weights, target_path)
            
            # Also copy last.pt for resume training
            last_weights = run_dir / "weights" / "last.pt"
            if last_weights.exists():
                last_target = checkpoints_dir / f"{experiment_name}_last.pt"
                print(f"✅ Copying last model to checkpoints: {last_target}")
                shutil.copy2(last_weights, last_target)
        else:
            print(f"⚠️  Warning: best.pt not found at {best_weights}")

    except Exception as e:
        print(f"Error during training: {e}")
    finally:
        print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train YOLO model")

    default_config = Path(__file__).resolve().parent.parent / "config" / "train_config.yaml"
    parser.add_argument("--config", type=str, default=str(default_config))

    args = parser.parse_args()
    train(args.config)
