#!/usr/bin/env python3
"""
데이터셋 통합 및 정제 스크립트
TrackNet + Roboflow 통합, 중복 제거, 해상도 통일
"""

import cv2
import shutil
from pathlib import Path
import json
from datetime import datetime
from tqdm import tqdm
import imagehash
from PIL import Image
import numpy as np
from collections import defaultdict

# ========================================
# 설정: 여기에 경로를 직접 입력하세요
# ========================================
# TrackNet 데이터 (Phase 1, 2 결과물)
TRACKNET_FRAMES_DIR = "/mnt/d/dataset/prepreocessed_tracknet"
TRACKNET_LABELS_DIR = "/mnt/d/dataset/prepreocessed_tracknet_label"

# Roboflow 데이터
ROBOFLOW_ROOT = "/mnt/d/dataset/roboflow_stc_dataset"

# 출력 (통합 데이터셋)
OUTPUT_DIR = "/mnt/d/dataset/total_stc_dataset"
# ========================================

# 통합 설정
TARGET_RESOLUTION = (1280, 720)  # 통일할 해상도 (None이면 원본 유지)
# 또는 (640, 640)으로 설정하면 모두 640x640으로 리사이즈

DUPLICATE_THRESHOLD = 5  # perceptual hash 차이 임계값 (5 이하면 중복으로 간주)
USE_HARD_LINK = False    # True: hard link 사용 (디스크 절약), False: 파일 복사


class DatasetMerger:
    """데이터셋 통합 클래스"""
    
    def __init__(self, tracknet_frames_dir, tracknet_labels_dir, roboflow_root, output_dir):
        self.tracknet_frames_dir = Path(tracknet_frames_dir)
        self.tracknet_labels_dir = Path(tracknet_labels_dir)
        self.roboflow_root = Path(roboflow_root)
        self.output_dir = Path(output_dir)
        
        # 출력 디렉토리 생성
        self.images_dir = self.output_dir / "images"
        self.labels_dir = self.output_dir / "labels"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.labels_dir.mkdir(parents=True, exist_ok=True)
        
        # 통계
        self.stats = {
            "tracknet": {
                "total_images": 0,
                "total_labels": 0,
                "copied": 0,
                "resized": 0,
                "duplicates_removed": 0,
                "errors": []
            },
            "roboflow": {
                "total_images": 0,
                "total_labels": 0,
                "copied": 0,
                "resized": 0,
                "duplicates_removed": 0,
                "errors": []
            },
            "combined": {
                "total_images": 0,
                "total_labels": 0,
                "total_duplicates_removed": 0
            }
        }
        
        # 해시 테이블 (중복 검사용) - 데이터셋별로 분리
        self.image_hashes = {
            "tracknet": {},
            "roboflow": {}
        }
        
        # 메타데이터 (데이터 출처 기록)
        self.metadata = {
            "files": {}  # filename -> source info
        }
    
    def compute_image_hash(self, image_path):
        """
        이미지의 perceptual hash 계산
        
        Args:
            image_path: 이미지 파일 경로
        
        Returns:
            ImageHash: perceptual hash 값
        """
        try:
            img = Image.open(image_path)
            return imagehash.phash(img)
        except Exception as e:
            return None
    
    def is_duplicate(self, image_path, source, threshold=DUPLICATE_THRESHOLD):
        """
        중복 이미지 체크 (다른 데이터셋과만 비교)
        
        Args:
            image_path: 체크할 이미지 경로
            source: 데이터 출처 ("tracknet" or "roboflow")
            threshold: hash 차이 임계값
        
        Returns:
            tuple: (is_duplicate: bool, duplicate_file: str or None)
        """
        img_hash = self.compute_image_hash(image_path)
        
        if img_hash is None:
            return False, None
        
        # 반대편 데이터셋의 해시들과만 비교 (TrackNet vs Roboflow)
        other_source = "roboflow" if source == "tracknet" else "tracknet"
        
        for existing_file, existing_hash in self.image_hashes[other_source].items():
            hash_diff = img_hash - existing_hash
            
            if hash_diff <= threshold:
                return True, existing_file
        
        # 중복 아니면 현재 데이터셋의 해시 테이블에 추가
        self.image_hashes[source][image_path.name] = img_hash
        return False, None
    
    def resize_image_and_update_label(self, image_path, label_path, target_size):
        """
        이미지 리사이즈 및 라벨 좌표 업데이트
        
        Args:
            image_path: 이미지 파일 경로
            label_path: 라벨 파일 경로
            target_size: 목표 해상도 (width, height)
        
        Returns:
            tuple: (resized_image: np.array, updated_label_lines: list)
        """
        # 이미지 로드
        img = cv2.imread(str(image_path))
        if img is None:
            return None, None
        
        original_h, original_w = img.shape[:2]
        target_w, target_h = target_size
        
        # 이미 목표 해상도면 리사이즈 불필요
        if original_w == target_w and original_h == target_h:
            # 라벨 그대로 읽기
            if label_path.exists():
                with open(label_path, 'r') as f:
                    label_lines = f.readlines()
            else:
                label_lines = []
            return img, label_lines
        
        # 이미지 리사이즈
        resized_img = cv2.resize(img, (target_w, target_h))
        
        # 라벨 좌표는 이미 정규화되어 있으므로 그대로 사용 가능
        # YOLO 포맷은 정규화 좌표 (0~1)이므로 해상도 변경해도 좌표 변경 불필요
        if label_path.exists():
            with open(label_path, 'r') as f:
                label_lines = f.readlines()
        else:
            label_lines = []
        
        return resized_img, label_lines
    
    def copy_or_link_file(self, src, dst):
        """
        파일 복사 또는 hard link 생성
        
        Args:
            src: 원본 파일 경로
            dst: 목적지 파일 경로
        """
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        if USE_HARD_LINK:
            try:
                # hard link 생성 (같은 파일시스템 내에서만 가능)
                dst.hardlink_to(src)
            except Exception as e:
                # hard link 실패 시 복사
                shutil.copy2(src, dst)
        else:
            shutil.copy2(src, dst)
    
    def process_tracknet_data(self):
        """TrackNet 데이터 처리"""
        print("\n" + "="*60)
        print("Processing TrackNet Data")
        print("="*60)
        
        # 이미지 파일 목록
        image_files = list(self.tracknet_frames_dir.glob("*.jpg")) + \
                     list(self.tracknet_frames_dir.glob("*.png"))
        
        self.stats["tracknet"]["total_images"] = len(image_files)
        
        # 라벨 파일 확인
        label_files = list(self.tracknet_labels_dir.glob("*.txt"))
        self.stats["tracknet"]["total_labels"] = len(label_files)
        
        print(f"Found {len(image_files)} images")
        print(f"Found {len(label_files)} labels")
        
        for image_path in tqdm(image_files, desc="Processing TrackNet"):
            try:
                # 대응하는 라벨 파일
                label_path = self.tracknet_labels_dir / (image_path.stem + ".txt")
                
                # 라벨이 없으면 스킵
                if not label_path.exists():
                    self.stats["tracknet"]["errors"].append({
                        "file": image_path.name,
                        "error": "label_not_found"
                    })
                    continue
                
                # 중복 체크 (Roboflow와만 비교)
                is_dup, dup_file = self.is_duplicate(image_path, "tracknet")
                
                if is_dup:
                    self.stats["tracknet"]["duplicates_removed"] += 1
                    continue
                
                # 새 파일명 (prefix 추가: tn_)
                new_filename = f"tn_{image_path.name}"
                new_image_path = self.images_dir / new_filename
                new_label_path = self.labels_dir / (Path(new_filename).stem + ".txt")
                
                # 해상도 처리
                if TARGET_RESOLUTION:
                    resized_img, label_lines = self.resize_image_and_update_label(
                        image_path, label_path, TARGET_RESOLUTION
                    )
                    
                    if resized_img is not None:
                        cv2.imwrite(str(new_image_path), resized_img)
                        
                        with open(new_label_path, 'w') as f:
                            f.writelines(label_lines)
                        
                        self.stats["tracknet"]["resized"] += 1
                        self.stats["tracknet"]["copied"] += 1
                    else:
                        self.stats["tracknet"]["errors"].append({
                            "file": image_path.name,
                            "error": "resize_failed"
                        })
                else:
                    # 원본 그대로 복사
                    self.copy_or_link_file(image_path, new_image_path)
                    self.copy_or_link_file(label_path, new_label_path)
                    self.stats["tracknet"]["copied"] += 1
                
                # 메타데이터 기록
                self.metadata["files"][new_filename] = {
                    "source": "tracknet",
                    "original_file": image_path.name,
                    "category": image_path.stem.split('_')[0]
                }
                
            except Exception as e:
                self.stats["tracknet"]["errors"].append({
                    "file": image_path.name,
                    "error": str(e)
                })
        
        print(f"✅ TrackNet: {self.stats['tracknet']['copied']} images copied")
        print(f"   Duplicates removed: {self.stats['tracknet']['duplicates_removed']}")
    
    def process_roboflow_data(self):
        """Roboflow 데이터 처리"""
        print("\n" + "="*60)
        print("Processing Roboflow Data")
        print("="*60)
        
        # Roboflow는 train/valid/test로 나뉘어 있음
        # 일단 모두 통합 (Phase 4에서 다시 분할 예정)
        splits = ["train", "valid", "test"]
        
        for split in splits:
            split_dir = self.roboflow_root / split
            
            if not split_dir.exists():
                continue
            
            images_dir = split_dir / "images"
            labels_dir = split_dir / "labels"
            
            if not images_dir.exists():
                continue
            
            image_files = list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png"))
            
            print(f"\nProcessing {split}: {len(image_files)} images")
            
            for image_path in tqdm(image_files, desc=f"Roboflow {split}"):
                try:
                    # 대응하는 라벨 파일
                    label_path = labels_dir / (image_path.stem + ".txt")
                    
                    if not label_path.exists():
                        self.stats["roboflow"]["errors"].append({
                            "file": image_path.name,
                            "error": "label_not_found"
                        })
                        continue
                    
                    # 중복 체크 (TrackNet과만 비교)
                    is_dup, dup_file = self.is_duplicate(image_path, "roboflow")
                    
                    if is_dup:
                        self.stats["roboflow"]["duplicates_removed"] += 1
                        continue
                    
                    # 새 파일명 (prefix 추가: rf_)
                    new_filename = f"rf_{image_path.name}"
                    new_image_path = self.images_dir / new_filename
                    new_label_path = self.labels_dir / (Path(new_filename).stem + ".txt")
                    
                    # 해상도 처리
                    if TARGET_RESOLUTION:
                        resized_img, label_lines = self.resize_image_and_update_label(
                            image_path, label_path, TARGET_RESOLUTION
                        )
                        
                        if resized_img is not None:
                            cv2.imwrite(str(new_image_path), resized_img)
                            
                            with open(new_label_path, 'w') as f:
                                f.writelines(label_lines)
                            
                            self.stats["roboflow"]["resized"] += 1
                            self.stats["roboflow"]["copied"] += 1
                        else:
                            self.stats["roboflow"]["errors"].append({
                                "file": image_path.name,
                                "error": "resize_failed"
                            })
                    else:
                        # 원본 그대로 복사
                        self.copy_or_link_file(image_path, new_image_path)
                        self.copy_or_link_file(label_path, new_label_path)
                        self.stats["roboflow"]["copied"] += 1
                    
                    # 메타데이터 기록
                    self.metadata["files"][new_filename] = {
                        "source": "roboflow",
                        "original_file": image_path.name,
                        "original_split": split
                    }
                    
                except Exception as e:
                    self.stats["roboflow"]["errors"].append({
                        "file": image_path.name,
                        "error": str(e)
                    })
            
            self.stats["roboflow"]["total_images"] += len(image_files)
        
        print(f"\n✅ Roboflow: {self.stats['roboflow']['copied']} images copied")
        print(f"   Duplicates removed: {self.stats['roboflow']['duplicates_removed']}")
    
    def verify_dataset(self):
        """통합 데이터셋 검증"""
        print("\n" + "="*60)
        print("Verifying Unified Dataset")
        print("="*60)
        
        # 이미지-라벨 쌍 확인
        image_files = list(self.images_dir.glob("*.jpg")) + list(self.images_dir.glob("*.png"))
        label_files = list(self.labels_dir.glob("*.txt"))
        
        self.stats["combined"]["total_images"] = len(image_files)
        self.stats["combined"]["total_labels"] = len(label_files)
        
        # 매칭 확인
        unmatched_images = []
        unmatched_labels = []
        
        for img_path in image_files:
            label_path = self.labels_dir / (img_path.stem + ".txt")
            if not label_path.exists():
                unmatched_images.append(img_path.name)
        
        for label_path in label_files:
            img_jpg = self.images_dir / (label_path.stem + ".jpg")
            img_png = self.images_dir / (label_path.stem + ".png")
            if not img_jpg.exists() and not img_png.exists():
                unmatched_labels.append(label_path.name)
        
        print(f"Total Images: {len(image_files)}")
        print(f"Total Labels: {len(label_files)}")
        print(f"Unmatched Images: {len(unmatched_images)}")
        print(f"Unmatched Labels: {len(unmatched_labels)}")
        
        if unmatched_images:
            print(f"⚠️  Warning: {len(unmatched_images)} images without labels")
        
        if unmatched_labels:
            print(f"⚠️  Warning: {len(unmatched_labels)} labels without images")
    
    def run(self):
        """전체 통합 프로세스 실행"""
        print("="*60)
        print("Dataset Merging Started")
        print("="*60)
        print(f"TrackNet Frames: {self.tracknet_frames_dir}")
        print(f"TrackNet Labels: {self.tracknet_labels_dir}")
        print(f"Roboflow Root: {self.roboflow_root}")
        print(f"Output Directory: {self.output_dir}")
        print(f"Target Resolution: {TARGET_RESOLUTION}")
        print(f"Duplicate Threshold: {DUPLICATE_THRESHOLD}")
        print("="*60)
        
        start_time = datetime.now()
        
        # Phase 3.1: TrackNet 처리
        self.process_tracknet_data()
        
        # Phase 3.2: Roboflow 처리
        self.process_roboflow_data()
        
        # Phase 3.3: 검증
        self.verify_dataset()
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        # 통계 계산
        self.stats["combined"]["total_duplicates_removed"] = \
            self.stats["tracknet"]["duplicates_removed"] + \
            self.stats["roboflow"]["duplicates_removed"]
        
        # 결과 저장
        results = {
            "merge_timestamp": start_time.isoformat(),
            "config": {
                "tracknet_frames_dir": str(self.tracknet_frames_dir),
                "tracknet_labels_dir": str(self.tracknet_labels_dir),
                "roboflow_root": str(self.roboflow_root),
                "output_dir": str(self.output_dir),
                "target_resolution": TARGET_RESOLUTION,
                "duplicate_threshold": DUPLICATE_THRESHOLD
            },
            "statistics": {
                **self.stats,
                "processing_time": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "elapsed_seconds": elapsed,
                    "elapsed_formatted": f"{elapsed/60:.2f} minutes"
                }
            },
            "metadata": self.metadata
        }
        
        # 로그 저장
        log_path = self.output_dir / "merge_log.json"
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # 최종 요약
        print("\n" + "="*60)
        print("Dataset Merging Complete!")
        print("="*60)
        print(f"TrackNet: {self.stats['tracknet']['copied']} images")
        print(f"Roboflow: {self.stats['roboflow']['copied']} images")
        print(f"Total: {self.stats['combined']['total_images']} images")
        print(f"Total Duplicates Removed: {self.stats['combined']['total_duplicates_removed']}")
        print(f"Processing Time: {elapsed/60:.2f} minutes")
        print(f"Log saved: {log_path}")
        
        return results


def main():
    """메인 실행 함수"""
    
    # 경로 검증
    tracknet_frames_dir = Path(TRACKNET_FRAMES_DIR)
    tracknet_labels_dir = Path(TRACKNET_LABELS_DIR)
    roboflow_root = Path(ROBOFLOW_ROOT)
    output_dir = Path(OUTPUT_DIR)
    
    if not tracknet_frames_dir.exists():
        print(f"❌ Error: TrackNet frames directory does not exist: {tracknet_frames_dir}")
        return
    
    if not tracknet_labels_dir.exists():
        print(f"❌ Error: TrackNet labels directory does not exist: {tracknet_labels_dir}")
        return
    
    if not roboflow_root.exists():
        print(f"❌ Error: Roboflow root does not exist: {roboflow_root}")
        return
    
    if output_dir == Path("/path/to/unified/dataset"):
        print("❌ Error: Please set OUTPUT_DIR in the script configuration.")
        return
    
    # 확인 메시지
    print("\n" + "="*60)
    print("Configuration Check")
    print("="*60)
    print(f"TrackNet Frames: {tracknet_frames_dir}")
    print(f"TrackNet Labels: {tracknet_labels_dir}")
    print(f"Roboflow Root: {roboflow_root}")
    print(f"Output Directory: {output_dir}")
    print(f"Target Resolution: {TARGET_RESOLUTION}")
    print("="*60)
    
    response = input("\nProceed with merging? (yes/no): ").strip().lower()
    
    if response != "yes":
        print("Merging cancelled.")
        return
    
    # 통합 실행
    merger = DatasetMerger(TRACKNET_FRAMES_DIR, TRACKNET_LABELS_DIR, 
                          ROBOFLOW_ROOT, OUTPUT_DIR)
    results = merger.run()
    
    print("\n✅ All done!")


if __name__ == "__main__":
    main()