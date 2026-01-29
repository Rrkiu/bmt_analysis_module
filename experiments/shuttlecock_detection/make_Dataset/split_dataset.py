#!/usr/bin/env python3
"""
데이터셋 분할 스크립트
통합 데이터셋을 Train/Val/Test로 전략적 분할
"""

from pathlib import Path
import json
from datetime import datetime
import shutil
import random
from collections import defaultdict
from tqdm import tqdm

# ========================================
# 설정: 여기에 경로를 직접 입력하세요
# ========================================
UNIFIED_DATASET_DIR = "/mnt/d/dataset/total_stc_dataset"  # Phase 3 결과물
OUTPUT_DIR = "/mnt/d/dataset/stc_yolo_0129"             # 최종 데이터셋 출력 경로
# ========================================

# 분할 비율 설정
TRAIN_RATIO = 0.70   # 70%
VAL_RATIO = 0.15     # 15%
TEST_RATIO = 0.15    # 15%

# 분할 전략
STRATIFIED_BY_SOURCE = True   # 데이터 출처별 균등 분할
RANDOM_SEED = 42              # 재현성을 위한 시드

# 파일 이동 방식
USE_HARD_LINK = False  # True: hard link (디스크 절약), False: 파일 복사


class DatasetSplitter:
    """데이터셋 분할 클래스"""
    
    def __init__(self, unified_dir, output_dir):
        self.unified_dir = Path(unified_dir)
        self.output_dir = Path(output_dir)
        
        # 입력 경로
        self.images_dir = self.unified_dir / "images"
        self.labels_dir = self.unified_dir / "labels"
        
        # 출력 경로
        self.splits = {
            "train": {
                "images": self.output_dir / "train" / "images",
                "labels": self.output_dir / "train" / "labels"
            },
            "val": {
                "images": self.output_dir / "val" / "images",
                "labels": self.output_dir / "val" / "labels"
            },
            "test": {
                "images": self.output_dir / "test" / "images",
                "labels": self.output_dir / "test" / "labels"
            }
        }
        
        # 출력 디렉토리 생성
        for split_data in self.splits.values():
            split_data["images"].mkdir(parents=True, exist_ok=True)
            split_data["labels"].mkdir(parents=True, exist_ok=True)
        
        # 통계
        self.stats = {
            "total_images": 0,
            "total_labels": 0,
            "splits": {
                "train": {"images": 0, "labels": 0, "tracknet": 0, "roboflow": 0},
                "val": {"images": 0, "labels": 0, "tracknet": 0, "roboflow": 0},
                "test": {"images": 0, "labels": 0, "tracknet": 0, "roboflow": 0}
            },
            "source_distribution": {
                "tracknet": {"total": 0, "train": 0, "val": 0, "test": 0},
                "roboflow": {"total": 0, "train": 0, "val": 0, "test": 0}
            },
            "errors": []
        }
    
    def get_image_files(self):
        """이미지 파일 목록 가져오기"""
        image_files = list(self.images_dir.glob("*.jpg")) + \
                     list(self.images_dir.glob("*.png"))
        return image_files
    
    def categorize_by_source(self, image_files):
        """
        데이터 출처별로 분류
        
        Returns:
            dict: {"tracknet": [...], "roboflow": [...]}
        """
        categorized = {
            "tracknet": [],
            "roboflow": []
        }
        
        for img_path in image_files:
            # 라벨 파일 확인
            label_path = self.labels_dir / (img_path.stem + ".txt")
            
            if not label_path.exists():
                self.stats["errors"].append({
                    "type": "missing_label",
                    "file": img_path.name
                })
                continue
            
            # 파일명 prefix로 출처 판단
            if img_path.name.startswith("tn_"):
                categorized["tracknet"].append((img_path, label_path))
            elif img_path.name.startswith("rf_"):
                categorized["roboflow"].append((img_path, label_path))
            else:
                self.stats["errors"].append({
                    "type": "unknown_source",
                    "file": img_path.name
                })
        
        return categorized
    
    def stratified_split(self, categorized_data):
        """
        계층적 샘플링으로 분할
        각 데이터 출처에서 동일한 비율로 분할
        
        Args:
            categorized_data: {"tracknet": [...], "roboflow": [...]}
        
        Returns:
            dict: {"train": [...], "val": [...], "test": [...]}
        """
        random.seed(RANDOM_SEED)
        
        split_data = {
            "train": [],
            "val": [],
            "test": []
        }
        
        for source, data_list in categorized_data.items():
            # 셔플
            random.shuffle(data_list)
            
            total = len(data_list)
            train_end = int(total * TRAIN_RATIO)
            val_end = train_end + int(total * VAL_RATIO)
            
            # 분할
            train_data = data_list[:train_end]
            val_data = data_list[train_end:val_end]
            test_data = data_list[val_end:]
            
            split_data["train"].extend(train_data)
            split_data["val"].extend(val_data)
            split_data["test"].extend(test_data)
            
            # 통계 기록
            self.stats["source_distribution"][source]["total"] = total
            self.stats["source_distribution"][source]["train"] = len(train_data)
            self.stats["source_distribution"][source]["val"] = len(val_data)
            self.stats["source_distribution"][source]["test"] = len(test_data)
            
            print(f"\n{source.upper()}:")
            print(f"  Total: {total}")
            print(f"  Train: {len(train_data)} ({len(train_data)/total*100:.1f}%)")
            print(f"  Val: {len(val_data)} ({len(val_data)/total*100:.1f}%)")
            print(f"  Test: {len(test_data)} ({len(test_data)/total*100:.1f}%)")
        
        return split_data
    
    def simple_split(self, image_files):
        """
        단순 랜덤 분할 (출처 구분 없이)
        
        Args:
            image_files: 이미지 파일 리스트
        
        Returns:
            dict: {"train": [...], "val": [...], "test": [...]}
        """
        random.seed(RANDOM_SEED)
        
        # 이미지-라벨 쌍 생성
        data_pairs = []
        for img_path in image_files:
            label_path = self.labels_dir / (img_path.stem + ".txt")
            if label_path.exists():
                data_pairs.append((img_path, label_path))
        
        # 셔플
        random.shuffle(data_pairs)
        
        total = len(data_pairs)
        train_end = int(total * TRAIN_RATIO)
        val_end = train_end + int(total * VAL_RATIO)
        
        split_data = {
            "train": data_pairs[:train_end],
            "val": data_pairs[train_end:val_end],
            "test": data_pairs[val_end:]
        }
        
        return split_data
    
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
                dst.hardlink_to(src)
            except Exception as e:
                shutil.copy2(src, dst)
        else:
            shutil.copy2(src, dst)
    
    def move_files_to_split(self, split_name, data_pairs):
        """
        파일들을 해당 split 디렉토리로 이동
        
        Args:
            split_name: "train", "val", "test"
            data_pairs: [(img_path, label_path), ...]
        """
        print(f"\nMoving files to {split_name}...")
        
        for img_path, label_path in tqdm(data_pairs, desc=f"{split_name}"):
            try:
                # 이미지 복사
                dst_img = self.splits[split_name]["images"] / img_path.name
                self.copy_or_link_file(img_path, dst_img)
                
                # 라벨 복사
                dst_label = self.splits[split_name]["labels"] / label_path.name
                self.copy_or_link_file(label_path, dst_label)
                
                # 통계 업데이트
                self.stats["splits"][split_name]["images"] += 1
                self.stats["splits"][split_name]["labels"] += 1
                
                # 출처별 카운트
                if img_path.name.startswith("tn_"):
                    self.stats["splits"][split_name]["tracknet"] += 1
                elif img_path.name.startswith("rf_"):
                    self.stats["splits"][split_name]["roboflow"] += 1
                
            except Exception as e:
                self.stats["errors"].append({
                    "type": "file_move_error",
                    "file": img_path.name,
                    "split": split_name,
                    "error": str(e)
                })
    
    def verify_split(self):
        """분할 결과 검증"""
        print("\n" + "="*60)
        print("Verifying Split Results")
        print("="*60)
        
        for split_name, paths in self.splits.items():
            images = list(paths["images"].glob("*.jpg")) + list(paths["images"].glob("*.png"))
            labels = list(paths["labels"].glob("*.txt"))
            
            print(f"\n{split_name.upper()}:")
            print(f"  Images: {len(images)}")
            print(f"  Labels: {len(labels)}")
            print(f"  Match: {'✅' if len(images) == len(labels) else '❌'}")
            
            # 이미지-라벨 매칭 확인
            unmatched = 0
            for img in images:
                label = paths["labels"] / (img.stem + ".txt")
                if not label.exists():
                    unmatched += 1
            
            if unmatched > 0:
                print(f"  ⚠️  Unmatched: {unmatched}")
    
    def create_data_yaml(self):
        """
        YOLO 학습용 data.yaml 파일 생성
        """
        yaml_content = f"""# Shuttlecock Detection Dataset
# Generated: {datetime.now().isoformat()}

path: {self.output_dir.absolute()}
train: train/images
val: val/images
test: test/images

# Classes
nc: 1
names: ['shuttlecock']

# Dataset Statistics
# Total Images: {self.stats['total_images']}
# Train: {self.stats['splits']['train']['images']} ({self.stats['splits']['train']['images']/self.stats['total_images']*100:.1f}%)
# Val: {self.stats['splits']['val']['images']} ({self.stats['splits']['val']['images']/self.stats['total_images']*100:.1f}%)
# Test: {self.stats['splits']['test']['images']} ({self.stats['splits']['test']['images']/self.stats['total_images']*100:.1f}%)

# Data Sources
# TrackNet: {self.stats['source_distribution']['tracknet']['total']} images
# Roboflow: {self.stats['source_distribution']['roboflow']['total']} images
"""
        
        yaml_path = self.output_dir / "data.yaml"
        with open(yaml_path, 'w') as f:
            f.write(yaml_content)
        
        print(f"\n✅ data.yaml created: {yaml_path}")
        
        return yaml_path
    
    def run(self):
        """전체 분할 프로세스 실행"""
        print("="*60)
        print("Dataset Splitting Started")
        print("="*60)
        print(f"Unified Dataset: {self.unified_dir}")
        print(f"Output Directory: {self.output_dir}")
        print(f"Split Ratio: Train {TRAIN_RATIO*100:.0f}% / Val {VAL_RATIO*100:.0f}% / Test {TEST_RATIO*100:.0f}%")
        print(f"Stratified by Source: {STRATIFIED_BY_SOURCE}")
        print(f"Random Seed: {RANDOM_SEED}")
        print("="*60)
        
        start_time = datetime.now()
        
        # 이미지 파일 목록
        print("\nLoading image files...")
        image_files = self.get_image_files()
        self.stats["total_images"] = len(image_files)
        
        print(f"Found {len(image_files)} images")
        
        if len(image_files) == 0:
            print("❌ No images found!")
            return
        
        # 분할 전략
        if STRATIFIED_BY_SOURCE:
            print("\nCategorizing by source...")
            categorized_data = self.categorize_by_source(image_files)
            
            print(f"TrackNet: {len(categorized_data['tracknet'])} images")
            print(f"Roboflow: {len(categorized_data['roboflow'])} images")
            
            print("\nPerforming stratified split...")
            split_data = self.stratified_split(categorized_data)
        else:
            print("\nPerforming simple random split...")
            split_data = self.simple_split(image_files)
        
        # 파일 이동
        for split_name, data_pairs in split_data.items():
            self.move_files_to_split(split_name, data_pairs)
        
        # 검증
        self.verify_split()
        
        # data.yaml 생성
        yaml_path = self.create_data_yaml()
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        # 결과 저장
        results = {
            "split_timestamp": start_time.isoformat(),
            "config": {
                "unified_dir": str(self.unified_dir),
                "output_dir": str(self.output_dir),
                "train_ratio": TRAIN_RATIO,
                "val_ratio": VAL_RATIO,
                "test_ratio": TEST_RATIO,
                "stratified_by_source": STRATIFIED_BY_SOURCE,
                "random_seed": RANDOM_SEED
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
        
        # 로그 저장
        log_path = self.output_dir / "split_log.json"
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # 최종 요약
        print("\n" + "="*60)
        print("Dataset Splitting Complete!")
        print("="*60)
        print(f"Train: {self.stats['splits']['train']['images']} images")
        print(f"Val: {self.stats['splits']['val']['images']} images")
        print(f"Test: {self.stats['splits']['test']['images']} images")
        print(f"Total: {self.stats['total_images']} images")
        print(f"\nProcessing Time: {elapsed/60:.2f} minutes")
        print(f"Log saved: {log_path}")
        print(f"Data config: {yaml_path}")
        
        if self.stats["errors"]:
            print(f"\n⚠️  {len(self.stats['errors'])} errors occurred. Check log for details.")
        
        print("\n🎉 Dataset is ready for training!")
        print(f"\nTo start training:")
        print(f"  from ultralytics import YOLO")
        print(f"  model = YOLO('yolov8n.pt')")
        print(f"  model.train(data='{yaml_path}', epochs=100, imgsz=640)")
        
        return results


def main():
    """메인 실행 함수"""
    
    # 경로 검증
    unified_dir = Path(UNIFIED_DATASET_DIR)
    output_dir = Path(OUTPUT_DIR)
    
    if not unified_dir.exists():
        print(f"❌ Error: Unified dataset directory does not exist: {unified_dir}")
        return
    
    if output_dir == Path("/path/to/final/dataset"):
        print("❌ Error: Please set OUTPUT_DIR in the script configuration.")
        return
    
    # 확인 메시지
    print("\n" + "="*60)
    print("Configuration Check")
    print("="*60)
    print(f"Unified Dataset: {unified_dir}")
    print(f"Output Directory: {output_dir}")
    print(f"Split Ratio: {TRAIN_RATIO*100:.0f}% / {VAL_RATIO*100:.0f}% / {TEST_RATIO*100:.0f}%")
    print(f"Stratified: {STRATIFIED_BY_SOURCE}")
    print("="*60)
    
    response = input("\nProceed with splitting? (yes/no): ").strip().lower()
    
    if response != "yes":
        print("Splitting cancelled.")
        return
    
    # 분할 실행
    splitter = DatasetSplitter(UNIFIED_DATASET_DIR, OUTPUT_DIR)
    results = splitter.run()
    
    print("\n✅ All done!")


if __name__ == "__main__":
    main()