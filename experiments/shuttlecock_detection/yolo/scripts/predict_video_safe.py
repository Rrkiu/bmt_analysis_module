import argparse
from pathlib import Path
from ultralytics import YOLO
import datetime
import os
import sys
import gc
import torch

def run_inference_single_video(model, video_path, output_dir, inference_imgsz, conf, device):
    """Run inference on a single video file"""
    print(f"\n{'='*60}")
    print(f"Processing: {video_path.name}")
    print(f"{'='*60}")
    
    # Arguments for prediction
    predict_args = {
        'source': str(video_path),
        'save': True,
        'project': str(output_dir),
        'name': f'vis_{video_path.stem}',  # separate folder for each video
        'conf': conf,
        'device': device,
        'exist_ok': True,
        'stream': True,  # Use streaming to reduce memory usage
        'verbose': True
    }
    
    if inference_imgsz:
        predict_args['imgsz'] = inference_imgsz
    
    try:
        results = model.predict(**predict_args)
        
        # Process results in streaming mode
        for r in results:
            pass  # Results are automatically saved with save=True
        
        print(f"✓ Successfully processed: {video_path.name}")
        
        # Clear memory after each video
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        
        return True
        
    except Exception as e:
        print(f"✗ Error processing {video_path.name}: {str(e)}")
        return False

def run_inference(weights, source, output_root, imgsz=None, device='0', conf=0.25):
    # Check weights
    if not os.path.exists(weights):
        print(f"Error: Weights file not found at {weights}")
        sys.exit(1)
        
    # Check source
    if not os.path.exists(source):
        print(f"Error: Source not found at {source}")
        sys.exit(1)

    # Load model
    print(f"Loading model from {weights}...")
    model = YOLO(weights)
    
    # Determine inference image size
    inference_imgsz = imgsz
    
    if inference_imgsz is None:
        # Attempt to auto-detect from args.yaml if it exists
        try:
            weights_path = Path(weights)
            args_yaml_path = weights_path.parent.parent / 'args.yaml'
            if args_yaml_path.exists():
                import yaml
                with open(args_yaml_path, 'r') as f:
                    args_data = yaml.safe_load(f)
                    if 'imgsz' in args_data:
                        detected_sz = args_data['imgsz']
                        print(f"Auto-detected training imgsz: {detected_sz} from {args_yaml_path}")
                        inference_imgsz = detected_sz
        except Exception as e:
            print(f"Could not auto-detect imgsz from args.yaml: {e}")

    if inference_imgsz is None:
        print("No --imgsz specified and auto-detection failed. Using model default (usually 640).")
    else:
        print(f"Using inference image size: {inference_imgsz}")

    # Construct Output Directory Name
    weights_path = Path(weights)
    
    try:
        if weights_path.parent.name == 'weights':
            exp_name = weights_path.parent.parent.name
        else:
            exp_name = "custom"
    except:
        exp_name = "custom"
        
    model_stem = weights_path.stem
    current_date = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    output_folder_name = f"{exp_name}_{model_stem}_{current_date}"
    output_dir = Path(output_root) / output_folder_name
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Results will be saved to: {output_dir}")

    # Get list of video files
    source_path = Path(source)
    
    if source_path.is_file():
        # Single video file
        video_files = [source_path]
    elif source_path.is_dir():
        # Directory containing videos
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.MP4', '.AVI', '.MOV', '.MKV']
        video_files = [f for f in source_path.iterdir() if f.suffix in video_extensions]
        video_files.sort()  # Process in alphabetical order
    else:
        print(f"Error: Source is neither a file nor a directory")
        sys.exit(1)
    
    if not video_files:
        print(f"Error: No video files found in {source}")
        sys.exit(1)
    
    print(f"\nFound {len(video_files)} video file(s) to process")
    print(f"Video files: {[v.name for v in video_files]}")
    
    # Process each video separately
    success_count = 0
    fail_count = 0
    
    for idx, video_file in enumerate(video_files, 1):
        print(f"\n[{idx}/{len(video_files)}] Processing video...")
        
        success = run_inference_single_video(
            model=model,
            video_path=video_file,
            output_dir=output_dir,
            inference_imgsz=inference_imgsz,
            conf=conf,
            device=device
        )
        
        if success:
            success_count += 1
        else:
            fail_count += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"Total videos: {len(video_files)}")
    print(f"Successfully processed: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"\nResults saved to: {output_dir}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run YOLO inference on videos and save visualizations (Memory-safe version).")
    
    parser.add_argument('--weights', type=str, required=True, help='Path to the trained model weights (.pt file)')
    parser.add_argument('--source', type=str, required=True, help='Path to video file or directory containing videos')
    parser.add_argument('--output_root', type=str, 
                        default='/mnt/b/cd_p/bmt_demo/experiments/shuttlecock_detection/yolo/test_video_output', 
                        help='Root directory to create output folders')
    
    parser.add_argument('--imgsz', type=int, default=None, help='Inference image size (e.g. 640 or 1280). If not set, uses model default.')
    parser.add_argument('--conf', type=float, default=0.25, help='Confidence threshold')
    parser.add_argument('--device', type=str, default='0', help='Device to run on (0, cpu, etc.)')
    
    args = parser.parse_args()
    
    run_inference(
        weights=args.weights,
        source=args.source,
        output_root=args.output_root,
        imgsz=args.imgsz,
        device=args.device,
        conf=args.conf
    )


"""
# 테스트 동영상에 대한 추론 진행 (메모리 안전 버전)

python predict_video_safe.py \
    --weights /mnt/b/cd_p/bmt_demo/experiments/shuttlecock_detection/yolo/experiments/yolov8s_20260202_130108/weights/best.pt \
    --source /mnt/b/cd_p/bmt_demo/experiments/_adutils/bmt_ad \
    --imgsz 1280

# 단일 비디오 테스트
python predict_video_safe.py \
    --weights /mnt/b/cd_p/bmt_demo/experiments/shuttlecock_detection/yolo/experiments/yolov8s_20260202_130108/weights/best.pt \
    --source /mnt/b/cd_p/bmt_demo/experiments/_adutils/bmt_ad/base3.mp4 \
    --imgsz 1280
"""
