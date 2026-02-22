import argparse
from pathlib import Path
from ultralytics import YOLO
import datetime
import os
import sys

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
    # If user provided imgsz, use it.
    # If not, try to determine from model metadata (if available and reliable), or default to standard (640).
    # Since we can't be 100% sure of the trained resolution from just the .pt without loading it fully, 
    # we inspect model.args if possible.
    
    # Determine inference image size
    inference_imgsz = imgsz
    
    if inference_imgsz is None:
        # Attempt to auto-detect from args.yaml if it exists
        # Assumes structure: .../ExpName/weights/best.pt -> .../ExpName/args.yaml
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
    # Naming convention: {ExperimentsName}_{WeightsName}_{Date}
    # Example: yolov8s_20260202_130048_best_20260204_120000
    
    weights_path = Path(weights)
    
    # Try to extract experiment name from path (assumes standard structure .../ExpName/weights/best.pt)
    # parent = weights, parent.parent = exp_name
    try:
        if weights_path.parent.name == 'weights':
            exp_name = weights_path.parent.parent.name
        else:
            exp_name = "custom"
    except:
        exp_name = "custom"
        
    model_stem = weights_path.stem # e.g., 'best' or 'last'
    
    current_date = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Combined folder name
    output_folder_name = f"{exp_name}_{model_stem}_{current_date}"
    output_dir = Path(output_root) / output_folder_name
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Results will be saved to: {output_dir}")

    # Video Inference
    # we use stream=True for large videos to handle memory, but for saving we can just run standard predict.
    # save=True saves to project/name. 
    # visualizaton is automatic with save=True.
    
    print(f"Starting inference on {source}...")
    
    # Arguments for prediction
    predict_args = {
        'source': source,
        'save': True,
        'project': str(output_dir),
        'name': 'vis_results', # subfolder inside output_dir
        'conf': conf,
        'device': device,
        'exist_ok': True # allow overwriting in the subfolder
    }
    
    if inference_imgsz:
        predict_args['imgsz'] = inference_imgsz
        
    results = model.predict(**predict_args)
    
    print(f"Done! Visualization saved in {output_dir / 'vis_results'}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run YOLO inference on videos and save visualizations.")
    
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
# 테스트 동영상에 대한 추론 진행

python predict_video.py \
    --weights /mnt/b/cd_p/bmt_demo/experiments/shuttlecock_detection/yolo/experiments/yolov8s_20260202_130108/weights/best.pt \
    --source /mnt/b/cd_p/bmt_demo/experiments/_adutils/bmt_ad \
    --imgsz 1280

"""