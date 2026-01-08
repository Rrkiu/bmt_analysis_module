"""
배드민턴 코트 검출 데이터셋 통합 스크립트

여러 개의 공개 데이터셋을 하나로 통합하여 pose_dataset을 생성합니다.
- 숫자_bmt_court~~ 형태의 폴더에서 이미지 수집
- 중복 방지를 위한 인덱스 기반 파일명 변경
- 640x640 크기로 이미지 리사이즈
"""

import os
import shutil
from pathlib import Path
from PIL import Image
from tqdm import tqdm
import re


class PoseDatasetMerger:
    def __init__(self, source_dir, target_dir):
        """
        Args:
            source_dir: 원본 데이터셋들이 있는 디렉토리 (dataset 폴더)
            target_dir: 통합 데이터셋을 생성할 디렉토리 (pose_dataset)
        """
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.target_images_dir = self.target_dir / "images"
        self.target_size = (640, 640)
        
        # 출력 디렉토리 생성
        self.target_images_dir.mkdir(parents=True, exist_ok=True)
        
        # 통계 정보
        self.stats = {
            'total_copied': 0,
            'resized': 0,
            'already_640': 0,
            'datasets_processed': 0,
            'dataset_counts': {}  # 각 데이터셋별 이미지 개수
        }
    
    def find_dataset_folders(self):
        """숫자_bmt_court~~ 형태의 폴더 찾기"""
        pattern = re.compile(r'^\d+_bmt_court.*')
        dataset_folders = []
        
        for item in self.source_dir.iterdir():
            if item.is_dir() and pattern.match(item.name):
                dataset_folders.append(item)
        
        # 숫자 순으로 정렬
        dataset_folders.sort(key=lambda x: int(re.match(r'^(\d+)_', x.name).group(1)))
        return dataset_folders
    
    def collect_images_from_dataset(self, dataset_folder):
        """하나의 데이터셋 폴더에서 모든 이미지 경로 수집"""
        image_paths = []
        
        # train, valid, test 폴더에서 이미지 수집
        for split in ['train', 'valid', 'test']:
            split_images_dir = dataset_folder / split / 'images'
            
            if split_images_dir.exists():
                # 이미지 파일 확장자
                image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
                
                for img_file in split_images_dir.iterdir():
                    if img_file.suffix.lower() in image_extensions:
                        image_paths.append(img_file)
        
        return image_paths
    
    def resize_image(self, image_path, output_path):
        """이미지를 640x640으로 리사이즈"""
        try:
            with Image.open(image_path) as img:
                original_size = img.size
                
                # 이미 640x640인 경우
                if original_size == self.target_size:
                    shutil.copy2(image_path, output_path)
                    self.stats['already_640'] += 1
                    return True
                
                # 리사이즈 필요
                # 비율 유지하면서 리사이즈 후 패딩 추가 (letterbox)
                img_resized = img.resize(self.target_size, Image.Resampling.LANCZOS)
                
                # RGB 모드로 변환 (RGBA 등의 경우)
                if img_resized.mode != 'RGB':
                    img_resized = img_resized.convert('RGB')
                
                img_resized.save(output_path, quality=95)
                self.stats['resized'] += 1
                return True
                
        except Exception as e:
            print(f"Error processing {image_path}: {e}")
            return False
    
    def merge_datasets(self):
        """모든 데이터셋 통합"""
        dataset_folders = self.find_dataset_folders()
        
        if not dataset_folders:
            print("No dataset folders found matching pattern: 숫자_bmt_court~~")
            return
        
        print(f"Found {len(dataset_folders)} dataset folders:")
        for folder in dataset_folders:
            print(f"  - {folder.name}")
        print()
        
        # 전역 인덱스 카운터
        global_index = 0
        
        # 각 데이터셋 처리
        for dataset_folder in dataset_folders:
            print(f"\nProcessing: {dataset_folder.name}")
            
            # 이미지 수집
            image_paths = self.collect_images_from_dataset(dataset_folder)
            print(f"  Found {len(image_paths)} images")
            
            if not image_paths:
                self.stats['dataset_counts'][dataset_folder.name] = 0
                continue
            
            # 데이터셋별 카운터 초기화
            dataset_copied = 0
            
            # 이미지 복사 및 리사이즈
            for img_path in tqdm(image_paths, desc=f"  Copying from {dataset_folder.name}"):
                # 새 파일명 생성 (인덱스 기반)
                new_filename = f"court_pose_{global_index:06d}{img_path.suffix}"
                output_path = self.target_images_dir / new_filename
                
                # 이미지 처리
                if self.resize_image(img_path, output_path):
                    global_index += 1
                    self.stats['total_copied'] += 1
                    dataset_copied += 1
            
            # 데이터셋별 통계 저장
            self.stats['dataset_counts'][dataset_folder.name] = dataset_copied
            print(f"  ✓ Copied {dataset_copied} images from {dataset_folder.name}")
            
            self.stats['datasets_processed'] += 1
        
        # 결과 출력
        self.print_summary()
    
    def print_summary(self):
        """처리 결과 요약 출력"""
        print("\n" + "="*60)
        print("Dataset Merge Summary")
        print("="*60)
        print(f"Datasets processed: {self.stats['datasets_processed']}")
        print(f"Total images copied: {self.stats['total_copied']}")
        print(f"Images already 640x640: {self.stats['already_640']}")
        print(f"Images resized: {self.stats['resized']}")
        
        # 각 데이터셋별 이미지 개수 출력
        if self.stats['dataset_counts']:
            print("\nImages per dataset:")
            for dataset_name, count in self.stats['dataset_counts'].items():
                print(f"  - {dataset_name}: {count} images")
        
        print(f"\nOutput directory: {self.target_images_dir}")
        print("="*60)


def main():
    # 경로 설정
    source_dir = "/mnt/b/cd_p/bmt_demo/test_yolo/dataset"
    target_dir = "/mnt/b/cd_p/bmt_demo/test_yolo/pose_dataset"
    
    print("Badminton Court Pose Dataset Merger")
    print("="*60)
    print(f"Source directory: {source_dir}")
    print(f"Target directory: {target_dir}")
    print("="*60)
    
    # 데이터셋 통합 실행
    merger = PoseDatasetMerger(source_dir, target_dir)
    merger.merge_datasets()


if __name__ == "__main__":
    main()
