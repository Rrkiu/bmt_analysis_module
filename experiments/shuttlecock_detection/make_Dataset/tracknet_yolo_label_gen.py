#!/usr/bin/env python3
"""
TrackNet YOLO 라벨 생성 스크립트
추출된 프레임에 대해 CSV 좌표를 YOLO bbox로 변환
"""

import pandas as pd
from pathlib import Path
import json
from datetime import datetime
from tqdm import tqdm
import cv2
import numpy as np

# ========================================
# 설정: 여기에 경로를 직접 입력하세요
# ========================================
TRACKNET_ROOT = "/mnt/d/dataset/TrackNetV2"                    # TrackNet 데이터셋 루트 경로
FRAMES_DIR = "/mnt/d/dataset/prepreocessed_tracknet"           # Phase 1에서 추출한 프레임 디렉토리
OUTPUT_LABELS_DIR = "/mnt/d/dataset/prepreocessed_tracknet_label"         # 라벨 파일 저장 경로
# ========================================

# YOLO bbox 설정
BBOX_WIDTH_PIXELS = 13   # Roboflow 통계에서 가져온 평균 bbox 너비 (픽셀)
BBOX_HEIGHT_PIXELS = 13  # Roboflow 통계에서 가져온 평균 bbox 높이 (픽셀)
IMAGE_WIDTH = 1280       # TrackNet 비디오 해상도
IMAGE_HEIGHT = 720       # TrackNet 비디오 해상도

# 검증 설정
ENABLE_VISUALIZATION = True   # 샘플 시각화 생성 여부
NUM_VISUALIZATION_SAMPLES = 100  # 시각화할 샘플 개수


class YOLOLabelGenerator:
    """TrackNet YOLO 라벨 생성 클래스"""
    
    def __init__(self, tracknet_root, frames_dir, output_labels_dir):
        self.tracknet_root = Path(tracknet_root)
        self.frames_dir = Path(frames_dir)
        self.output_labels_dir = Path(output_labels_dir)
        self.output_labels_dir.mkdir(parents=True, exist_ok=True)
        
        # 시각화 디렉토리
        if ENABLE_VISUALIZATION:
            self.viz_dir = self.output_labels_dir.parent / "visualizations"
            self.viz_dir.mkdir(parents=True, exist_ok=True)
        
        # 통계 추적
        self.stats = {
            "total_labels_created": 0,
            "total_frames_processed": 0,
            "frames_without_csv": 0,
            "invalid_coordinates": 0,
            "out_of_bounds": 0,
            "errors": [],
            "bbox_statistics": {
                "normalized_widths": [],
                "normalized_heights": [],
                "center_x": [],
                "center_y": []
            }
        }
        
        # CSV 캐시 (성능 향상)
        self.csv_cache = {}
    
    def load_csv_for_rally(self, category, match, rally_id):
        """
        특정 rally의 CSV 파일 로드 (캐싱)
        
        Args:
            category: 카테고리 (Amateur/Professional/Test)
            match: 매치 이름 (match1, match2, ...)
            rally_id: rally ID (예: 1_00_01)
        
        Returns:
            DataFrame: CSV 데이터
        """
        cache_key = f"{category}_{match}_{rally_id}"
        
        if cache_key in self.csv_cache:
            return self.csv_cache[cache_key]
        
        # CSV 파일 경로
        csv_path = self.tracknet_root / category / match / "csv" / f"{rally_id}_ball.csv"
        
        if not csv_path.exists():
            return None
        
        try:
            df = pd.read_csv(csv_path)
            # Visibility=1인 것만 필터링
            df = df[df['Visibility'] == 1].copy()
            self.csv_cache[cache_key] = df
            return df
        except Exception as e:
            self.stats["errors"].append({
                "type": "csv_load_error",
                "rally": cache_key,
                "error": str(e)
            })
            return None
    
    def center_point_to_yolo_bbox(self, x, y, img_w, img_h, bbox_w_pixels, bbox_h_pixels):
        """
        중앙점 좌표를 YOLO bbox 포맷으로 변환
        
        Args:
            x: 중앙점 X 좌표 (픽셀)
            y: 중앙점 Y 좌표 (픽셀)
            img_w: 이미지 너비 (픽셀)
            img_h: 이미지 높이 (픽셀)
            bbox_w_pixels: bbox 너비 (픽셀)
            bbox_h_pixels: bbox 높이 (픽셀)
        
        Returns:
            tuple: (class_id, x_center_norm, y_center_norm, width_norm, height_norm)
                   또는 None (범위를 벗어난 경우)
        """
        # 좌표 검증
        if x < 0 or y < 0 or x >= img_w or y >= img_h:
            return None
        
        # 중앙점 정규화 (0~1 범위)
        x_center_norm = x / img_w
        y_center_norm = y / img_h
        
        # bbox 크기 정규화
        width_norm = bbox_w_pixels / img_w
        height_norm = bbox_h_pixels / img_h
        
        # 경계 체크 (bbox가 이미지 범위를 벗어나지 않도록)
        x_min = x_center_norm - width_norm / 2
        x_max = x_center_norm + width_norm / 2
        y_min = y_center_norm - height_norm / 2
        y_max = y_center_norm + height_norm / 2
        
        # 범위 클리핑
        if x_min < 0 or x_max > 1 or y_min < 0 or y_max > 1:
            # 클리핑 수행
            x_center_norm = max(width_norm / 2, min(1 - width_norm / 2, x_center_norm))
            y_center_norm = max(height_norm / 2, min(1 - height_norm / 2, y_center_norm))
        
        # 통계 수집
        self.stats["bbox_statistics"]["normalized_widths"].append(width_norm)
        self.stats["bbox_statistics"]["normalized_heights"].append(height_norm)
        self.stats["bbox_statistics"]["center_x"].append(x_center_norm)
        self.stats["bbox_statistics"]["center_y"].append(y_center_norm)
        
        # YOLO 포맷: class x_center y_center width height
        return (0, x_center_norm, y_center_norm, width_norm, height_norm)
    
    def parse_frame_filename(self, filename):
        """
        프레임 파일명에서 메타데이터 추출
        
        Args:
            filename: 프레임 파일명 (예: Professional_match10_1_03_01_000245.jpg)
        
        Returns:
            dict: {category, match, rally_id, frame_num}
        """
        stem = filename.stem
        parts = stem.split('_')
        
        # 파일명 형식: {category}_{match}_{rally_parts...}_{frame}
        # 예: Professional_match10_1_03_01_000245
        
        if len(parts) < 5:
            return None
        
        category = parts[0]
        match = parts[1]
        
        # frame 번호 (마지막 부분)
        frame_num = int(parts[-1])
        
        # rally_id (중간 부분들을 조합)
        # 예: 1_03_01
        rally_parts = parts[2:-1]
        rally_id = '_'.join(rally_parts)
        
        return {
            "category": category,
            "match": match,
            "rally_id": rally_id,
            "frame_num": frame_num
        }
    
    def create_label_for_frame(self, frame_path):
        """
        단일 프레임에 대한 라벨 생성
        
        Args:
            frame_path: 프레임 이미지 경로
        
        Returns:
            tuple: (success: bool, label_path: Path or None)
        """
        try:
            # 파일명에서 메타데이터 추출
            metadata = self.parse_frame_filename(frame_path)
            
            if metadata is None:
                self.stats["errors"].append({
                    "type": "filename_parse_error",
                    "file": frame_path.name
                })
                return False, None
            
            # CSV 로드
            df = self.load_csv_for_rally(
                metadata["category"],
                metadata["match"],
                metadata["rally_id"]
            )
            
            if df is None:
                self.stats["frames_without_csv"] += 1
                return False, None
            
            # 해당 프레임의 좌표 찾기
            frame_row = df[df['Frame'] == metadata['frame_num']]
            
            if len(frame_row) == 0:
                self.stats["frames_without_csv"] += 1
                return False, None
            
            # 좌표 추출
            x = frame_row.iloc[0]['X']
            y = frame_row.iloc[0]['Y']
            
            # YOLO bbox 변환
            yolo_bbox = self.center_point_to_yolo_bbox(
                x, y,
                IMAGE_WIDTH, IMAGE_HEIGHT,
                BBOX_WIDTH_PIXELS, BBOX_HEIGHT_PIXELS
            )
            
            if yolo_bbox is None:
                self.stats["out_of_bounds"] += 1
                return False, None
            
            # 라벨 파일 저장
            label_filename = frame_path.stem + ".txt"
            label_path = self.output_labels_dir / label_filename
            
            with open(label_path, 'w') as f:
                class_id, x_c, y_c, w, h = yolo_bbox
                f.write(f"{class_id} {x_c:.6f} {y_c:.6f} {w:.6f} {h:.6f}\n")
            
            self.stats["total_labels_created"] += 1
            
            return True, label_path
            
        except Exception as e:
            self.stats["errors"].append({
                "type": "label_creation_error",
                "file": frame_path.name,
                "error": str(e)
            })
            return False, None
    
    def visualize_sample(self, frame_path, label_path):
        """
        프레임과 bbox를 시각화
        
        Args:
            frame_path: 프레임 이미지 경로
            label_path: 라벨 파일 경로
        """
        try:
            # 이미지 로드
            img = cv2.imread(str(frame_path))
            if img is None:
                return
            
            h, w = img.shape[:2]
            
            # 라벨 읽기
            with open(label_path, 'r') as f:
                line = f.readline().strip()
                parts = line.split()
                
                if len(parts) >= 5:
                    class_id = int(parts[0])
                    x_c = float(parts[1])
                    y_c = float(parts[2])
                    bbox_w = float(parts[3])
                    bbox_h = float(parts[4])
                    
                    # 픽셀 좌표로 변환
                    x_center_px = int(x_c * w)
                    y_center_px = int(y_c * h)
                    bbox_w_px = int(bbox_w * w)
                    bbox_h_px = int(bbox_h * h)
                    
                    # bbox 좌측 상단, 우측 하단
                    x1 = x_center_px - bbox_w_px // 2
                    y1 = y_center_px - bbox_h_px // 2
                    x2 = x_center_px + bbox_w_px // 2
                    y2 = y_center_px + bbox_h_px // 2
                    
                    # bbox 그리기
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    # 중앙점 표시
                    cv2.circle(img, (x_center_px, y_center_px), 3, (0, 0, 255), -1)
                    
                    # 텍스트
                    cv2.putText(img, "Shuttlecock", (x1, y1 - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # 저장
            viz_filename = frame_path.name
            viz_path = self.viz_dir / viz_filename
            cv2.imwrite(str(viz_path), img)
            
        except Exception as e:
            pass  # 시각화 실패는 무시
    
    def calculate_statistics(self):
        """bbox 통계 계산"""
        if not self.stats["bbox_statistics"]["normalized_widths"]:
            return
        
        self.stats["bbox_summary"] = {
            "normalized_width": {
                "min": float(np.min(self.stats["bbox_statistics"]["normalized_widths"])),
                "max": float(np.max(self.stats["bbox_statistics"]["normalized_widths"])),
                "mean": float(np.mean(self.stats["bbox_statistics"]["normalized_widths"])),
                "std": float(np.std(self.stats["bbox_statistics"]["normalized_widths"]))
            },
            "normalized_height": {
                "min": float(np.min(self.stats["bbox_statistics"]["normalized_heights"])),
                "max": float(np.max(self.stats["bbox_statistics"]["normalized_heights"])),
                "mean": float(np.mean(self.stats["bbox_statistics"]["normalized_heights"])),
                "std": float(np.std(self.stats["bbox_statistics"]["normalized_heights"]))
            },
            "pixel_width": BBOX_WIDTH_PIXELS,
            "pixel_height": BBOX_HEIGHT_PIXELS
        }
        
        # 원본 리스트 삭제 (메모리 절약)
        del self.stats["bbox_statistics"]
    
    def run(self):
        """전체 라벨 생성 실행"""
        print("="*60)
        print("TrackNet YOLO Label Generation Started")
        print("="*60)
        print(f"TrackNet Root: {self.tracknet_root}")
        print(f"Frames Directory: {self.frames_dir}")
        print(f"Output Labels Directory: {self.output_labels_dir}")
        print(f"BBox Size: {BBOX_WIDTH_PIXELS}x{BBOX_HEIGHT_PIXELS} pixels")
        print("="*60)
        
        start_time = datetime.now()
        
        # 프레임 파일 목록
        frame_files = sorted(self.frames_dir.glob("*.jpg")) + \
                     sorted(self.frames_dir.glob("*.png"))
        
        total_frames = len(frame_files)
        print(f"\nFound {total_frames} frames to process")
        
        if total_frames == 0:
            print("❌ No frames found! Please check FRAMES_DIR path.")
            return
        
        # 각 프레임 처리
        successful_labels = []
        
        for frame_path in tqdm(frame_files, desc="Creating labels"):
            success, label_path = self.create_label_for_frame(frame_path)
            
            if success:
                successful_labels.append((frame_path, label_path))
            
            self.stats["total_frames_processed"] += 1
        
        # 시각화 샘플 생성
        if ENABLE_VISUALIZATION and successful_labels:
            print(f"\nGenerating {NUM_VISUALIZATION_SAMPLES} visualization samples...")
            
            # 랜덤 샘플링
            num_samples = min(NUM_VISUALIZATION_SAMPLES, len(successful_labels))
            sample_indices = np.random.choice(len(successful_labels), num_samples, replace=False)
            
            for idx in tqdm(sample_indices, desc="Visualizing"):
                frame_path, label_path = successful_labels[idx]
                self.visualize_sample(frame_path, label_path)
        
        # 통계 계산
        self.calculate_statistics()
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        # 최종 결과
        results = {
            "generation_timestamp": start_time.isoformat(),
            "config": {
                "tracknet_root": str(self.tracknet_root),
                "frames_dir": str(self.frames_dir),
                "output_labels_dir": str(self.output_labels_dir),
                "bbox_width_pixels": BBOX_WIDTH_PIXELS,
                "bbox_height_pixels": BBOX_HEIGHT_PIXELS,
                "image_width": IMAGE_WIDTH,
                "image_height": IMAGE_HEIGHT
            },
            "statistics": {
                **self.stats,
                "processing_time": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "elapsed_seconds": elapsed,
                    "elapsed_formatted": f"{elapsed/60:.2f} minutes"
                }
            }
        }
        
        # 결과 저장
        log_path = self.output_labels_dir / "label_generation_log.json"
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # 최종 요약 출력
        print("\n" + "="*60)
        print("Label Generation Complete!")
        print("="*60)
        print(f"Total Frames Processed: {self.stats['total_frames_processed']}")
        print(f"Labels Created: {self.stats['total_labels_created']}")
        print(f"Frames Without CSV: {self.stats['frames_without_csv']}")
        print(f"Out of Bounds: {self.stats['out_of_bounds']}")
        print(f"Processing Time: {elapsed/60:.2f} minutes")
        print(f"Log saved: {log_path}")
        
        if ENABLE_VISUALIZATION:
            print(f"Visualizations saved: {self.viz_dir}")
        
        if self.stats["errors"]:
            print(f"\n⚠️  {len(self.stats['errors'])} errors occurred. Check log for details.")
        
        return results


def main():
    """메인 실행 함수"""
    
    # 경로 검증
    tracknet_root = Path(TRACKNET_ROOT)
    frames_dir = Path(FRAMES_DIR)
    output_labels_dir = Path(OUTPUT_LABELS_DIR)
    
    if not tracknet_root.exists():
        print(f"❌ Error: TrackNet root path does not exist: {tracknet_root}")
        return
    
    if not frames_dir.exists():
        print(f"❌ Error: Frames directory does not exist: {frames_dir}")
        print("Please run Phase 1 (frame extraction) first.")
        return
    
    if output_labels_dir == Path("/path/to/output/labels/directory"):
        print("❌ Error: Please set OUTPUT_LABELS_DIR in the script configuration.")
        return
    
    # 확인 메시지
    print("\n" + "="*60)
    print("Configuration Check")
    print("="*60)
    print(f"TrackNet Root: {tracknet_root}")
    print(f"Frames Directory: {frames_dir}")
    print(f"Output Labels Directory: {output_labels_dir}")
    print(f"BBox Size: {BBOX_WIDTH_PIXELS}x{BBOX_HEIGHT_PIXELS} pixels")
    print("="*60)
    
    response = input("\nProceed with label generation? (yes/no): ").strip().lower()
    
    if response != "yes":
        print("Label generation cancelled.")
        return
    
    # 라벨 생성 실행
    generator = YOLOLabelGenerator(TRACKNET_ROOT, FRAMES_DIR, OUTPUT_LABELS_DIR)
    results = generator.run()
    
    print("\n✅ All done!")


if __name__ == "__main__":
    main()