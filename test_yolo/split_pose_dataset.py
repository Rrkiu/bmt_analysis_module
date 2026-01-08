#!/usr/bin/env python3
"""
YOLO Pose Dataset Splitter
레이블된 pose 데이터셋을 train/valid/test로 분할하는 스크립트

분할 비율: train 70%, valid 10%, test 20%
"""

import os
import shutil
import random
from pathlib import Path
from typing import List, Tuple
import json


class PoseDatasetSplitter:
    """YOLO Pose 데이터셋을 train/valid/test로 분할하는 클래스"""
    
    def __init__(
        self,
        source_dir: str,
        output_dir: str,
        train_ratio: float = 0.7,
        valid_ratio: float = 0.1,
        test_ratio: float = 0.2,
        random_seed: int = 42
    ):
        """
        Args:
            source_dir: 레이블된 데이터셋 경로 (images, labels 폴더 포함)
            output_dir: 출력 디렉토리 경로
            train_ratio: 학습 데이터 비율
            valid_ratio: 검증 데이터 비율
            test_ratio: 테스트 데이터 비율
            random_seed: 랜덤 시드 (재현성을 위해)
        """
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.train_ratio = train_ratio
        self.valid_ratio = valid_ratio
        self.test_ratio = test_ratio
        self.random_seed = random_seed
        
        # 비율 검증
        total_ratio = train_ratio + valid_ratio + test_ratio
        if abs(total_ratio - 1.0) > 1e-6:
            raise ValueError(f"비율의 합이 1.0이 아닙니다: {total_ratio}")
        
        # 소스 디렉토리 검증
        self.images_dir = self.source_dir / "images"
        self.labels_dir = self.source_dir / "labels"
        
        if not self.images_dir.exists():
            raise FileNotFoundError(f"이미지 디렉토리를 찾을 수 없습니다: {self.images_dir}")
        if not self.labels_dir.exists():
            raise FileNotFoundError(f"레이블 디렉토리를 찾을 수 없습니다: {self.labels_dir}")
        
        # 통계 정보
        self.stats = {
            'total': 0,
            'train': 0,
            'valid': 0,
            'test': 0,
            'skipped': 0
        }
    
    def get_paired_files(self) -> List[Tuple[Path, Path]]:
        """
        이미지와 레이블이 쌍으로 존재하는 파일들을 찾습니다.
        
        Returns:
            (image_path, label_path) 튜플의 리스트
        """
        paired_files = []
        skipped_files = []
        
        # 이미지 파일 목록 가져오기
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        image_files = [
            f for f in self.images_dir.iterdir()
            if f.suffix.lower() in image_extensions
        ]
        
        print(f"\n📁 이미지 파일 스캔 중...")
        print(f"   총 이미지 파일: {len(image_files)}개")
        
        for image_path in image_files:
            # 대응하는 레이블 파일 찾기
            label_path = self.labels_dir / f"{image_path.stem}.txt"
            
            if label_path.exists():
                paired_files.append((image_path, label_path))
            else:
                skipped_files.append(image_path.name)
                self.stats['skipped'] += 1
        
        if skipped_files:
            print(f"\n⚠️  레이블이 없는 이미지 파일: {len(skipped_files)}개")
            if len(skipped_files) <= 10:
                for fname in skipped_files:
                    print(f"   - {fname}")
            else:
                for fname in skipped_files[:5]:
                    print(f"   - {fname}")
                print(f"   ... 외 {len(skipped_files) - 5}개")
        
        self.stats['total'] = len(paired_files)
        return paired_files
    
    def create_directory_structure(self):
        """출력 디렉토리 구조를 생성합니다."""
        print(f"\n📂 디렉토리 구조 생성 중...")
        
        splits = ['train', 'valid', 'test']
        for split in splits:
            split_dir = self.output_dir / split
            images_dir = split_dir / 'images'
            labels_dir = split_dir / 'labels'
            
            images_dir.mkdir(parents=True, exist_ok=True)
            labels_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"   ✓ {split_dir}")
    
    def split_dataset(self, paired_files: List[Tuple[Path, Path]]):
        """
        데이터셋을 train/valid/test로 분할하고 파일을 복사합니다.
        
        Args:
            paired_files: (image_path, label_path) 튜플의 리스트
        """
        # 랜덤 시드 설정
        random.seed(self.random_seed)
        
        # 파일 목록 셔플
        shuffled_files = paired_files.copy()
        random.shuffle(shuffled_files)
        
        total = len(shuffled_files)
        train_count = int(total * self.train_ratio)
        valid_count = int(total * self.valid_ratio)
        
        # 데이터셋 분할
        train_files = shuffled_files[:train_count]
        valid_files = shuffled_files[train_count:train_count + valid_count]
        test_files = shuffled_files[train_count + valid_count:]
        
        print(f"\n🔀 데이터셋 분할 (랜덤 시드: {self.random_seed})")
        print(f"   Train: {len(train_files)}개 ({len(train_files)/total*100:.1f}%)")
        print(f"   Valid: {len(valid_files)}개 ({len(valid_files)/total*100:.1f}%)")
        print(f"   Test:  {len(test_files)}개 ({len(test_files)/total*100:.1f}%)")
        
        # 파일 복사
        splits_data = {
            'train': train_files,
            'valid': valid_files,
            'test': test_files
        }
        
        for split_name, files in splits_data.items():
            print(f"\n📋 {split_name.upper()} 데이터 복사 중...")
            self._copy_files(split_name, files)
            self.stats[split_name] = len(files)
    
    def _copy_files(self, split_name: str, files: List[Tuple[Path, Path]]):
        """
        파일들을 지정된 split 디렉토리로 복사합니다.
        
        Args:
            split_name: 'train', 'valid', 'test' 중 하나
            files: (image_path, label_path) 튜플의 리스트
        """
        split_dir = self.output_dir / split_name
        images_dir = split_dir / 'images'
        labels_dir = split_dir / 'labels'
        
        total = len(files)
        for idx, (image_path, label_path) in enumerate(files, 1):
            # 이미지 복사
            dest_image = images_dir / image_path.name
            shutil.copy2(image_path, dest_image)
            
            # 레이블 복사
            dest_label = labels_dir / label_path.name
            shutil.copy2(label_path, dest_label)
            
            # 진행상황 표시 (10% 단위)
            if idx % max(1, total // 10) == 0 or idx == total:
                progress = idx / total * 100
                print(f"   진행: {idx}/{total} ({progress:.1f}%)")
    
    def save_split_info(self):
        """분할 정보를 JSON 파일로 저장합니다."""
        info_file = self.output_dir / 'split_info.json'
        
        info = {
            'source_directory': str(self.source_dir),
            'output_directory': str(self.output_dir),
            'split_ratios': {
                'train': self.train_ratio,
                'valid': self.valid_ratio,
                'test': self.test_ratio
            },
            'random_seed': self.random_seed,
            'statistics': self.stats,
            'percentages': {
                'train': f"{self.stats['train']/self.stats['total']*100:.2f}%" if self.stats['total'] > 0 else "0%",
                'valid': f"{self.stats['valid']/self.stats['total']*100:.2f}%" if self.stats['total'] > 0 else "0%",
                'test': f"{self.stats['test']/self.stats['total']*100:.2f}%" if self.stats['total'] > 0 else "0%"
            }
        }
        
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 분할 정보 저장: {info_file}")
    
    def print_summary(self):
        """최종 결과 요약을 출력합니다."""
        print("\n" + "="*70)
        print("📊 데이터셋 분할 완료!")
        print("="*70)
        print(f"\n📁 출력 디렉토리: {self.output_dir}")
        print(f"\n📈 통계:")
        print(f"   총 데이터:     {self.stats['total']:>6}개")
        print(f"   건너뛴 파일:   {self.stats['skipped']:>6}개")
        print(f"\n   Train 데이터:  {self.stats['train']:>6}개 ({self.stats['train']/self.stats['total']*100:>5.1f}%)")
        print(f"   Valid 데이터:  {self.stats['valid']:>6}개 ({self.stats['valid']/self.stats['total']*100:>5.1f}%)")
        print(f"   Test 데이터:   {self.stats['test']:>6}개 ({self.stats['test']/self.stats['total']*100:>5.1f}%)")
        print(f"\n🎲 랜덤 시드: {self.random_seed}")
        print("="*70)
        
        # 디렉토리 구조 출력
        print(f"\n📂 생성된 디렉토리 구조:")
        print(f"{self.output_dir}/")
        for split in ['train', 'valid', 'test']:
            split_dir = self.output_dir / split
            images_count = len(list((split_dir / 'images').glob('*')))
            labels_count = len(list((split_dir / 'labels').glob('*.txt')))
            print(f"├── {split}/")
            print(f"│   ├── images/ ({images_count}개)")
            print(f"│   └── labels/ ({labels_count}개)")
        print(f"└── split_info.json")
        print()
    
    def run(self):
        """전체 분할 프로세스를 실행합니다."""
        print("="*70)
        print("🚀 YOLO Pose 데이터셋 분할 시작")
        print("="*70)
        print(f"\n소스 디렉토리: {self.source_dir}")
        print(f"출력 디렉토리: {self.output_dir}")
        print(f"분할 비율: Train {self.train_ratio*100:.0f}% | Valid {self.valid_ratio*100:.0f}% | Test {self.test_ratio*100:.0f}%")
        
        # 1. 쌍으로 된 파일 찾기
        paired_files = self.get_paired_files()
        
        if not paired_files:
            print("\n❌ 에러: 유효한 이미지-레이블 쌍을 찾을 수 없습니다.")
            return
        
        print(f"\n✓ 유효한 데이터: {len(paired_files)}개")
        
        # 2. 디렉토리 구조 생성
        self.create_directory_structure()
        
        # 3. 데이터셋 분할 및 복사
        self.split_dataset(paired_files)
        
        # 4. 분할 정보 저장
        self.save_split_info()
        
        # 5. 결과 요약 출력
        self.print_summary()


def main():
    """메인 함수"""
    # 경로 설정
    source_dir = "/mnt/b/cd_p/bmt_demo/test_yolo/labeled_pose_dataset"
    output_dir = "/mnt/b/cd_p/bmt_demo/test_yolo/260107"
    
    # 데이터셋 분할 실행
    splitter = PoseDatasetSplitter(
        source_dir=source_dir,
        output_dir=output_dir,
        train_ratio=0.7,
        valid_ratio=0.1,
        test_ratio=0.2,
        random_seed=42
    )
    
    splitter.run()


if __name__ == "__main__":
    main()
