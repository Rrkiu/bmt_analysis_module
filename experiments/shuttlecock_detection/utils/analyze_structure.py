# scripts/analyze_structure.py
from pathlib import Path
import pandas as pd
import json
from datetime import datetime
import cv2

def analyze_tracknet_structure(tracknet_root):
    """TrackNet 데이터셋 구조 분석 (비디오 + CSV 기반)"""
    tracknet_root = Path(tracknet_root)
    
    structure = {
        "root": str(tracknet_root),
        "exists": tracknet_root.exists(),
        "categories": {},
        "total_matches": 0,
        "total_videos": 0,
        "total_csv_files": 0,
        "total_frames": 0,
        "total_visible_frames": 0,
        "sample_csv_format": None,
        "video_info": {
            "resolutions": {},
            "fps_values": {},
            "durations": []
        }
    }
    
    if not tracknet_root.exists():
        print(f"❌ TrackNet root path does not exist: {tracknet_root}")
        return structure
    
    # Amateur, Professional, Test 카테고리 찾기
    categories = [d for d in tracknet_root.iterdir() if d.is_dir()]
    
    print(f"Found {len(categories)} categories: {[c.name for c in categories]}")
    
    for category_dir in categories:
        category_name = category_dir.name
        category_info = {
            "name": category_name,
            "matches": [],
            "match_count": 0,
            "video_count": 0,
            "csv_count": 0,
            "total_frames": 0,
            "visible_frames": 0
        }
        
        # match 디렉토리 찾기
        match_dirs = sorted([d for d in category_dir.iterdir() if d.is_dir() and d.name.startswith("match")])
        category_info["match_count"] = len(match_dirs)
        structure["total_matches"] += len(match_dirs)
        
        print(f"\n📁 {category_name}: {len(match_dirs)} matches")
        
        for match_dir in match_dirs:
            match_info = {
                "name": match_dir.name,
                "videos": [],
                "csv_files": [],
                "frames": 0,
                "visible_frames": 0
            }
            
            csv_dir = match_dir / "csv"
            video_dir = match_dir / "video"
            
            # CSV 파일 분석
            if csv_dir.exists():
                csv_files = list(csv_dir.glob("*.csv"))
                match_info["csv_files"] = [f.name for f in csv_files]
                match_info["csv_count"] = len(csv_files)
                category_info["csv_count"] += len(csv_files)
                structure["total_csv_files"] += len(csv_files)
                
                # 각 CSV 파일 분석
                for csv_file in csv_files:
                    try:
                        df = pd.read_csv(csv_file)
                        frame_count = len(df)
                        visible_count = df[df['Visibility'] == 1].shape[0] if 'Visibility' in df.columns else 0
                        
                        match_info["frames"] += frame_count
                        match_info["visible_frames"] += visible_count
                        
                        # 첫 번째 CSV 샘플 저장
                        if structure["sample_csv_format"] is None:
                            structure["sample_csv_format"] = {
                                "category": category_name,
                                "match": match_dir.name,
                                "file": csv_file.name,
                                "columns": list(df.columns),
                                "total_rows": len(df),
                                "visible_rows": visible_count,
                                "sample_rows": df.head(5).to_dict('records')
                            }
                    except Exception as e:
                        print(f"  ⚠️  Error reading {csv_file.name}: {e}")
                
                category_info["total_frames"] += match_info["frames"]
                category_info["visible_frames"] += match_info["visible_frames"]
                structure["total_frames"] += match_info["frames"]
                structure["total_visible_frames"] += match_info["visible_frames"]
            
            # 비디오 파일 분석
            if video_dir.exists():
                video_files = list(video_dir.glob("*.mp4")) + list(video_dir.glob("*.avi")) + list(video_dir.glob("*.mov"))
                match_info["videos"] = [v.name for v in video_files]
                match_info["video_count"] = len(video_files)
                category_info["video_count"] += len(video_files)
                structure["total_videos"] += len(video_files)
                
                # 비디오 메타정보 추출 (첫 번째 비디오만)
                if video_files and len(structure["video_info"]["resolutions"]) < 5:
                    for video_file in video_files[:1]:  # 각 매치에서 1개씩만
                        try:
                            cap = cv2.VideoCapture(str(video_file))
                            if cap.isOpened():
                                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                                fps = cap.get(cv2.CAP_PROP_FPS)
                                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                                duration = frame_count / fps if fps > 0 else 0
                                
                                resolution = f"{width}x{height}"
                                structure["video_info"]["resolutions"][resolution] = \
                                    structure["video_info"]["resolutions"].get(resolution, 0) + 1
                                structure["video_info"]["fps_values"][f"{fps:.1f}"] = \
                                    structure["video_info"]["fps_values"].get(f"{fps:.1f}", 0) + 1
                                structure["video_info"]["durations"].append(duration)
                                
                                cap.release()
                        except Exception as e:
                            print(f"  ⚠️  Error reading video {video_file.name}: {e}")
            
            category_info["matches"].append(match_info)
            
            print(f"  {match_dir.name}: {match_info['video_count']} videos, "
                  f"{match_info['csv_count']} CSVs, "
                  f"{match_info['frames']} frames ({match_info['visible_frames']} visible)")
        
        structure["categories"][category_name] = category_info
    
    # 비디오 duration 통계
    if structure["video_info"]["durations"]:
        import numpy as np
        durations = structure["video_info"]["durations"]
        structure["video_info"]["duration_stats"] = {
            "min_seconds": float(np.min(durations)),
            "max_seconds": float(np.max(durations)),
            "mean_seconds": float(np.mean(durations)),
            "total_seconds": float(np.sum(durations))
        }
        del structure["video_info"]["durations"]
    
    return structure

def analyze_roboflow_structure(roboflow_root):
    """Roboflow 데이터셋 구조 분석"""
    roboflow_root = Path(roboflow_root)
    
    structure = {
        "root": str(roboflow_root),
        "exists": roboflow_root.exists(),
        "splits": {},
        "total_images": 0,
        "total_labels": 0,
        "sample_label": None,
        "bbox_statistics": {
            "widths": [],
            "heights": [],
            "areas": []
        },
        "image_resolutions": {},
        "data_yaml_content": None
    }
    
    if not roboflow_root.exists():
        print(f"❌ Roboflow root path does not exist: {roboflow_root}")
        return structure
    
    # train/valid/test 폴더 확인
    for split in ["train", "valid", "test"]:
        split_dir = roboflow_root / split
        if split_dir.exists():
            img_dir = split_dir / "images"
            lbl_dir = split_dir / "labels"
            
            images = list(img_dir.glob("*.[jJ][pP][gG]")) + list(img_dir.glob("*.[pP][nN][gG]")) if img_dir.exists() else []
            labels = list(lbl_dir.glob("*.txt")) if lbl_dir.exists() else []
            
            structure["splits"][split] = {
                "images": len(images),
                "labels": len(labels),
                "match": len(images) == len(labels),
                "sample_images": [img.name for img in images[:3]]
            }
            structure["total_images"] += len(images)
            structure["total_labels"] += len(labels)
            
            # 첫 번째 이미지 해상도 확인
            if images and len(structure["image_resolutions"]) < 10:
                try:
                    for img_path in images[:5]:
                        img = cv2.imread(str(img_path))
                        if img is not None:
                            h, w = img.shape[:2]
                            resolution = f"{w}x{h}"
                            structure["image_resolutions"][resolution] = \
                                structure["image_resolutions"].get(resolution, 0) + 1
                except Exception as e:
                    print(f"  ⚠️  Error reading image resolution: {e}")
            
            # 라벨 파일 샘플링 및 bbox 통계
            if labels:
                for label_file in labels[:100]:  # 처음 100개 샘플
                    try:
                        with open(label_file, 'r') as f:
                            lines = f.read().strip().split('\n')
                            for line in lines:
                                if line:
                                    parts = line.split()
                                    if len(parts) >= 5:
                                        w, h = float(parts[3]), float(parts[4])
                                        structure["bbox_statistics"]["widths"].append(w)
                                        structure["bbox_statistics"]["heights"].append(h)
                                        structure["bbox_statistics"]["areas"].append(w * h)
                    except Exception as e:
                        pass
                
                # 첫 번째 라벨 샘플 저장
                if structure["sample_label"] is None:
                    try:
                        with open(labels[0], 'r') as f:
                            structure["sample_label"] = {
                                "file": labels[0].name,
                                "content": f.read().strip().split('\n')[:5]
                            }
                    except Exception as e:
                        print(f"  ⚠️  Error reading label file: {e}")
            
            print(f"  {split}: {len(images)} images, {len(labels)} labels")
    
    # bbox 통계 계산
    if structure["bbox_statistics"]["widths"]:
        import numpy as np
        structure["bbox_statistics"]["summary"] = {
            "width": {
                "min": float(np.min(structure["bbox_statistics"]["widths"])),
                "max": float(np.max(structure["bbox_statistics"]["widths"])),
                "mean": float(np.mean(structure["bbox_statistics"]["widths"])),
                "std": float(np.std(structure["bbox_statistics"]["widths"])),
                "pixel_1280x720": float(np.mean(structure["bbox_statistics"]["widths"]) * 1280)  # 참고용
            },
            "height": {
                "min": float(np.min(structure["bbox_statistics"]["heights"])),
                "max": float(np.max(structure["bbox_statistics"]["heights"])),
                "mean": float(np.mean(structure["bbox_statistics"]["heights"])),
                "std": float(np.std(structure["bbox_statistics"]["heights"])),
                "pixel_1280x720": float(np.mean(structure["bbox_statistics"]["heights"]) * 720)  # 참고용
            },
            "area": {
                "min": float(np.min(structure["bbox_statistics"]["areas"])),
                "max": float(np.max(structure["bbox_statistics"]["areas"])),
                "mean": float(np.mean(structure["bbox_statistics"]["areas"])),
                "std": float(np.std(structure["bbox_statistics"]["areas"]))
            }
        }
        # 원본 리스트는 삭제 (용량 절약)
        del structure["bbox_statistics"]["widths"]
        del structure["bbox_statistics"]["heights"]
        del structure["bbox_statistics"]["areas"]
    
    # data.yaml 확인
    yaml_path = roboflow_root / "data.yaml"
    if yaml_path.exists():
        try:
            with open(yaml_path, 'r') as f:
                structure["data_yaml_content"] = f.read()
        except Exception as e:
            print(f"  ⚠️  Error reading data.yaml: {e}")
    
    return structure

def save_structure_report(tracknet_info, roboflow_info, output_path):
    """분석 결과 저장"""
    report = {
        "analysis_timestamp": datetime.now().isoformat(),
        "tracknet": tracknet_info,
        "roboflow": roboflow_info,
        "summary": {
            "tracknet": {
                "data_format": "video + CSV labels",
                "categories": list(tracknet_info.get("categories", {}).keys()),
                "total_matches": tracknet_info.get("total_matches", 0),
                "total_videos": tracknet_info.get("total_videos", 0),
                "total_csv_files": tracknet_info.get("total_csv_files", 0),
                "total_frames": tracknet_info.get("total_frames", 0),
                "total_visible_frames": tracknet_info.get("total_visible_frames", 0),
                "visibility_ratio": tracknet_info.get("total_visible_frames", 0) / max(tracknet_info.get("total_frames", 1), 1)
            },
            "roboflow": {
                "data_format": "images + YOLO labels",
                "total_images": roboflow_info.get("total_images", 0),
                "total_labels": roboflow_info.get("total_labels", 0),
                "splits": list(roboflow_info.get("splits", {}).keys())
            },
            "estimated_combined_dataset": {
                "note": "TrackNet requires video frame extraction first",
                "total_images_after_extraction": tracknet_info.get("total_visible_frames", 0) + roboflow_info.get("total_images", 0),
                "tracknet_contribution_ratio": tracknet_info.get("total_visible_frames", 0) / max(
                    tracknet_info.get("total_visible_frames", 0) + roboflow_info.get("total_images", 0), 1
                ),
                "roboflow_contribution_ratio": roboflow_info.get("total_images", 0) / max(
                    tracknet_info.get("total_visible_frames", 0) + roboflow_info.get("total_images", 0), 1
                )
            },
            "preprocessing_notes": {
                "tracknet": [
                    "Need to extract frames from video files",
                    "Match CSV labels with video frames by frame number",
                    "Filter only frames where Visibility == 1",
                    "Convert center point (X, Y) to YOLO bbox format"
                ],
                "roboflow": [
                    "Already in YOLO format",
                    "Use bbox statistics to determine TrackNet bbox size"
                ]
            }
        }
    }
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Structure report saved to: {output_path}")
    
    return report

if __name__ == "__main__":
    # ========================================
    # 여기에 데이터셋 경로를 직접 입력하세요
    # ========================================
    tracknet_path = "/mnt/d/dataset/TrackNetV2"  # TrackNet 데이터셋 루트 경로
    roboflow_path = "/mnt/d/dataset/roboflow_stc_dataset"  # Roboflow 데이터셋 루트 경로
    
    print("="*60)
    print("Shuttlecock Dataset Structure Analysis")
    print("="*60)
    print(f"TrackNet Path: {tracknet_path}")
    print(f"Roboflow Path: {roboflow_path}")
    print("="*60)
    
    print("\n" + "="*60)
    print("Analyzing TrackNet Dataset Structure")
    print("="*60)
    tracknet_info = analyze_tracknet_structure(tracknet_path)
    
    print("\n" + "="*60)
    print("Analyzing Roboflow Dataset Structure")
    print("="*60)
    roboflow_info = analyze_roboflow_structure(roboflow_path)
    
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    print(f"TrackNet (Video + CSV):")
    print(f"  - Categories: {list(tracknet_info.get('categories', {}).keys())}")
    print(f"  - Total Matches: {tracknet_info.get('total_matches', 0)}")
    print(f"  - Total Videos: {tracknet_info.get('total_videos', 0)}")
    print(f"  - Total CSV Files: {tracknet_info.get('total_csv_files', 0)}")
    print(f"  - Total Frames (in CSV): {tracknet_info.get('total_frames', 0)}")
    print(f"  - Visible Frames: {tracknet_info.get('total_visible_frames', 0)}")
    if tracknet_info.get('total_frames', 0) > 0:
        visibility_ratio = tracknet_info.get('total_visible_frames', 0) / tracknet_info.get('total_frames', 1)
        print(f"  - Visibility Ratio: {visibility_ratio:.2%}")
    
    print(f"\nRoboflow (Images + Labels):")
    print(f"  - Total Images: {roboflow_info.get('total_images', 0)}")
    print(f"  - Total Labels: {roboflow_info.get('total_labels', 0)}")
    for split, info in roboflow_info.get('splits', {}).items():
        print(f"  - {split}: {info['images']} images")
    
    print(f"\nEstimated Combined Dataset (after frame extraction):")
    total_combined = tracknet_info.get('total_visible_frames', 0) + roboflow_info.get('total_images', 0)
    print(f"  - Total Images: {total_combined}")
    print(f"  - From TrackNet: {tracknet_info.get('total_visible_frames', 0)} ({tracknet_info.get('total_visible_frames', 0)/max(total_combined, 1)*100:.1f}%)")
    print(f"  - From Roboflow: {roboflow_info.get('total_images', 0)} ({roboflow_info.get('total_images', 0)/max(total_combined, 1)*100:.1f}%)")
    
    # 결과 저장
    output_json = "dataset_structure_report.json"
    report = save_structure_report(tracknet_info, roboflow_info, output_json)
    
    print("\n" + "="*60)
    print("Analysis Complete!")
    print("="*60)
    print(f"📄 Report saved: {output_json}")
    print("\n⚠️  Important Notes:")
    print("  - TrackNet requires VIDEO FRAME EXTRACTION before use")
    print("  - Each video needs to be processed frame-by-frame")
    print("  - CSV files contain frame-level labels (Visibility, X, Y)")
    print("\nNext steps:")
    print("1. Review the JSON report")
    print("2. Check Roboflow bbox statistics for TrackNet conversion")
    print("3. Prepare video frame extraction pipeline")
    print("4. Design CSV-to-YOLO label conversion")