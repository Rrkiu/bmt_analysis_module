#!/usr/bin/env python3
"""
TrackNet 비디오 프레임 추출 스크립트
Visibility=1인 프레임만 추출하여 저장
"""

import cv2
import pandas as pd
from pathlib import Path
import json
from datetime import datetime
from tqdm import tqdm
import multiprocessing as mp
from functools import partial
import traceback

# ========================================
# 설정: 여기에 경로를 직접 입력하세요
# ========================================
TRACKNET_ROOT = "/mnt/d/dataset/TrackNetV2"  # TrackNet 데이터셋 루트 경로
OUTPUT_DIR = "/mnt/d/dataset/prepreocessed_tracknet"     # 추출된 프레임 저장 경로
# ========================================

# 전역 설정
SAVE_FORMAT = "jpg"  # jpg 또는 png
JPEG_QUALITY = 95    # JPEG 품질 (1-100)
NUM_WORKERS = 4      # 병렬 처리 워커 수 (CPU 코어 수에 맞게 조정)


class FrameExtractor:
    """TrackNet 비디오 프레임 추출 클래스"""
    
    def __init__(self, tracknet_root, output_dir):
        self.tracknet_root = Path(tracknet_root)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 통계 추적
        self.stats = {
            "total_videos_processed": 0,
            "total_frames_extracted": 0,
            "total_frames_skipped": 0,
            "errors": [],
            "processing_time": {},
            "category_stats": {}
        }
    
    def find_matching_video(self, csv_file, video_dir):
        """
        CSV 파일명에 해당하는 비디오 파일 찾기
        예: 1_00_01_ball.csv -> 1_00_01.mp4
        """
        # CSV 파일명에서 rally ID 추출 (예: 1_00_01_ball.csv -> 1_00_01)
        rally_id = csv_file.stem.replace("_ball", "")
        
        # 가능한 비디오 확장자들
        video_extensions = [".mp4", ".avi", ".mov"]
        
        for ext in video_extensions:
            video_path = video_dir / f"{rally_id}{ext}"
            if video_path.exists():
                return video_path
        
        return None
    
    def extract_frames_from_rally(self, csv_path, video_path, category, match_name):
        """
        단일 rally의 프레임 추출
        
        Args:
            csv_path: CSV 파일 경로
            video_path: 비디오 파일 경로
            category: 카테고리 이름 (Amateur/Professional/Test)
            match_name: 매치 이름 (match1, match2, ...)
        
        Returns:
            dict: 추출 통계
        """
        rally_id = csv_path.stem.replace("_ball", "")
        
        try:
            # CSV 파일 읽기
            df = pd.read_csv(csv_path)
            
            # Visibility=1인 프레임만 필터링
            visible_df = df[df['Visibility'] == 1].copy()
            
            if len(visible_df) == 0:
                return {
                    "rally_id": rally_id,
                    "status": "no_visible_frames",
                    "extracted": 0,
                    "skipped": len(df)
                }
            
            # 비디오 열기
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                return {
                    "rally_id": rally_id,
                    "status": "video_open_failed",
                    "error": f"Cannot open video: {video_path}",
                    "extracted": 0,
                    "skipped": len(df)
                }
            
            # 비디오 메타정보
            total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            
            extracted_count = 0
            skipped_count = 0
            
            # visible 프레임 추출
            for idx, row in visible_df.iterrows():
                frame_num = int(row['Frame'])
                
                # 프레임 번호가 비디오 범위를 벗어나는지 체크
                if frame_num >= total_video_frames:
                    skipped_count += 1
                    continue
                
                # 해당 프레임으로 이동
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                
                if not ret:
                    skipped_count += 1
                    continue
                
                # 파일명 생성: {category}_{match}_{rally}_{frame}.jpg
                filename = f"{category}_{match_name}_{rally_id}_{frame_num:06d}.{SAVE_FORMAT}"
                output_path = self.output_dir / filename
                
                # 이미지 저장
                if SAVE_FORMAT == "jpg":
                    cv2.imwrite(str(output_path), frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                else:
                    cv2.imwrite(str(output_path), frame)
                
                extracted_count += 1
            
            cap.release()
            
            return {
                "rally_id": rally_id,
                "status": "success",
                "extracted": extracted_count,
                "skipped": skipped_count,
                "total_visible": len(visible_df),
                "video_info": {
                    "total_frames": total_video_frames,
                    "fps": video_fps
                }
            }
            
        except Exception as e:
            return {
                "rally_id": rally_id,
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "extracted": 0,
                "skipped": 0
            }
    
    def process_match(self, category_dir, match_dir):
        """
        단일 매치 처리
        
        Args:
            category_dir: 카테고리 디렉토리 (Amateur/Professional/Test)
            match_dir: 매치 디렉토리 (match1, match2, ...)
        
        Returns:
            dict: 매치 처리 결과
        """
        category_name = category_dir.name
        match_name = match_dir.name
        
        csv_dir = match_dir / "csv"
        video_dir = match_dir / "video"
        
        if not csv_dir.exists() or not video_dir.exists():
            return {
                "category": category_name,
                "match": match_name,
                "status": "missing_directories",
                "extracted": 0,
                "skipped": 0
            }
        
        # CSV 파일 목록
        csv_files = sorted(csv_dir.glob("*_ball.csv"))
        
        match_results = {
            "category": category_name,
            "match": match_name,
            "rallies": [],
            "total_extracted": 0,
            "total_skipped": 0
        }
        
        # 각 rally 처리
        for csv_file in csv_files:
            # 매칭되는 비디오 파일 찾기
            video_path = self.find_matching_video(csv_file, video_dir)
            
            if video_path is None:
                match_results["rallies"].append({
                    "rally_id": csv_file.stem.replace("_ball", ""),
                    "status": "video_not_found",
                    "extracted": 0,
                    "skipped": 0
                })
                continue
            
            # 프레임 추출
            rally_result = self.extract_frames_from_rally(
                csv_file, video_path, category_name, match_name
            )
            
            match_results["rallies"].append(rally_result)
            match_results["total_extracted"] += rally_result.get("extracted", 0)
            match_results["total_skipped"] += rally_result.get("skipped", 0)
            
            # 에러 추적
            if rally_result.get("status") == "error":
                self.stats["errors"].append({
                    "category": category_name,
                    "match": match_name,
                    "rally": rally_result.get("rally_id"),
                    "error": rally_result.get("error"),
                    "traceback": rally_result.get("traceback")
                })
        
        return match_results
    
    def process_category(self, category_name):
        """
        카테고리 전체 처리 (Amateur/Professional/Test)
        
        Args:
            category_name: 카테고리 이름
        
        Returns:
            dict: 카테고리 처리 결과
        """
        category_dir = self.tracknet_root / category_name
        
        if not category_dir.exists():
            print(f"⚠️  Category not found: {category_name}")
            return None
        
        print(f"\n{'='*60}")
        print(f"Processing Category: {category_name}")
        print(f"{'='*60}")
        
        # 매치 디렉토리 찾기
        match_dirs = sorted([d for d in category_dir.iterdir() 
                           if d.is_dir() and d.name.startswith("match")])
        
        print(f"Found {len(match_dirs)} matches")
        
        category_results = {
            "category": category_name,
            "matches": [],
            "total_extracted": 0,
            "total_skipped": 0
        }
        
        # 각 매치 처리 (progress bar 포함)
        for match_dir in tqdm(match_dirs, desc=f"{category_name} matches"):
            match_result = self.process_match(category_dir, match_dir)
            category_results["matches"].append(match_result)
            category_results["total_extracted"] += match_result.get("total_extracted", 0)
            category_results["total_skipped"] += match_result.get("total_skipped", 0)
        
        # 카테고리 통계 저장
        self.stats["category_stats"][category_name] = {
            "matches": len(match_dirs),
            "extracted": category_results["total_extracted"],
            "skipped": category_results["total_skipped"]
        }
        
        print(f"\n✅ {category_name} Complete:")
        print(f"   Extracted: {category_results['total_extracted']} frames")
        print(f"   Skipped: {category_results['total_skipped']} frames")
        
        return category_results
    
    def run(self):
        """전체 프레임 추출 실행"""
        print("="*60)
        print("TrackNet Frame Extraction Started")
        print("="*60)
        print(f"TrackNet Root: {self.tracknet_root}")
        print(f"Output Directory: {self.output_dir}")
        print(f"Workers: {NUM_WORKERS}")
        print("="*60)
        
        start_time = datetime.now()
        
        # 카테고리 목록
        categories = ["Amateur", "Professional", "Test"]
        
        all_results = {
            "extraction_timestamp": start_time.isoformat(),
            "config": {
                "tracknet_root": str(self.tracknet_root),
                "output_dir": str(self.output_dir),
                "save_format": SAVE_FORMAT,
                "jpeg_quality": JPEG_QUALITY,
                "num_workers": NUM_WORKERS
            },
            "categories": []
        }
        
        # 각 카테고리 처리
        for category in categories:
            result = self.process_category(category)
            if result:
                all_results["categories"].append(result)
                self.stats["total_frames_extracted"] += result["total_extracted"]
                self.stats["total_frames_skipped"] += result["total_skipped"]
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        # 최종 통계
        self.stats["processing_time"] = {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "elapsed_seconds": elapsed,
            "elapsed_formatted": f"{elapsed/60:.2f} minutes"
        }
        
        all_results["statistics"] = self.stats
        
        # 결과 저장
        log_path = self.output_dir / "extraction_log.json"
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        
        # 최종 요약 출력
        print("\n" + "="*60)
        print("Extraction Complete!")
        print("="*60)
        print(f"Total Extracted: {self.stats['total_frames_extracted']} frames")
        print(f"Total Skipped: {self.stats['total_frames_skipped']} frames")
        print(f"Processing Time: {elapsed/60:.2f} minutes")
        print(f"Log saved: {log_path}")
        
        if self.stats["errors"]:
            print(f"\n⚠️  {len(self.stats['errors'])} errors occurred. Check log for details.")
        
        return all_results


def main():
    """메인 실행 함수"""
    
    # 경로 검증
    tracknet_root = Path(TRACKNET_ROOT)
    output_dir = Path(OUTPUT_DIR)
    
    if not tracknet_root.exists():
        print(f"❌ Error: TrackNet root path does not exist: {tracknet_root}")
        print("Please check TRACKNET_ROOT in the script configuration.")
        return
    
    if output_dir == Path("/path/to/output/directory"):
        print("❌ Error: Please set OUTPUT_DIR in the script configuration.")
        print("Current value is the default placeholder.")
        return
    
    # 확인 메시지
    print("\n" + "="*60)
    print("Configuration Check")
    print("="*60)
    print(f"TrackNet Root: {tracknet_root}")
    print(f"Output Directory: {output_dir}")
    print(f"Output will be created at: {output_dir}")
    print("="*60)
    
    response = input("\nProceed with extraction? (yes/no): ").strip().lower()
    
    if response != "yes":
        print("Extraction cancelled.")
        return
    
    # 프레임 추출 실행
    extractor = FrameExtractor(TRACKNET_ROOT, OUTPUT_DIR)
    results = extractor.run()
    
    print("\n✅ All done!")


if __name__ == "__main__":
    main()