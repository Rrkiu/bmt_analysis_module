"""
영상에서 프레임을 추출하여 기존 Pose 데이터셋에 추가하는 도구

기능:
- 지정된 폴더의 영상 파일들을 읽어서 프레임 추출
- 추출된 프레임을 640x640 크기로 리사이즈
- 기존 데이터셋의 이미지 인덱스를 이어서 파일명 생성
- 중복 방지를 위한 자동 인덱싱
- 프레임 추출 간격 설정 가능 (매 N 프레임마다 추출)
"""

import cv2
import numpy as np
from pathlib import Path
from tqdm import tqdm
import json


class VideoFrameExtractor:
    def __init__(self, video_dir, output_images_dir, frame_interval=30):
        """
        Args:
            video_dir: 영상 파일들이 있는 디렉토리
            output_images_dir: 추출된 프레임을 저장할 디렉토리 (pose_dataset/images)
            frame_interval: 프레임 추출 간격 (기본값: 30프레임마다 1장)
        """
        self.video_dir = Path(video_dir)
        self.output_images_dir = Path(output_images_dir)
        self.frame_interval = frame_interval
        self.target_size = (640, 640)
        
        # 출력 디렉토리 생성
        self.output_images_dir.mkdir(parents=True, exist_ok=True)
        
        # 진행 상황 파일
        self.progress_file = self.video_dir / "extraction_progress.json"
        
        # 통계
        self.stats = {
            'videos_processed': 0,
            'frames_extracted': 0,
            'videos': {}
        }
        
        # 기존 이미지의 최대 인덱스 찾기
        self.start_index = self._find_max_index() + 1
        self.current_index = self.start_index
        
        # 처리된 영상 목록
        self.processed_videos = self._load_progress()
    
    def _find_max_index(self):
        """기존 이미지 파일들의 최대 인덱스 찾기"""
        max_index = -1
        
        # court_pose_XXXXXX.jpg 형식의 파일들 찾기
        for img_file in self.output_images_dir.glob('court_pose_*.jpg'):
            try:
                # 파일명에서 인덱스 추출
                index_str = img_file.stem.replace('court_pose_', '')
                index = int(index_str)
                max_index = max(max_index, index)
            except ValueError:
                continue
        
        return max_index
    
    def _load_progress(self):
        """이전 처리 기록 로드"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('processed_videos', []))
            except Exception as e:
                print(f"Warning: Could not load progress: {e}")
        return set()
    
    def _save_progress(self):
        """처리 진행 상황 저장"""
        try:
            with open(self.progress_file, 'w') as f:
                json.dump({
                    'processed_videos': list(self.processed_videos),
                    'stats': self.stats,
                    'last_index': self.current_index - 1
                }, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save progress: {e}")
    
    def _get_video_files(self):
        """영상 파일 리스트 가져오기"""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
        video_files = []
        
        for ext in video_extensions:
            video_files.extend(self.video_dir.glob(f'*{ext}'))
            video_files.extend(self.video_dir.glob(f'*{ext.upper()}'))
        
        # 이미 처리된 영상 제외
        video_files = [v for v in video_files if v.name not in self.processed_videos]
        
        return sorted(video_files)
    
    def _resize_frame(self, frame):
        """프레임을 640x640으로 리사이즈"""
        if frame.shape[:2] == self.target_size[::-1]:  # (height, width)
            return frame
        
        # 리사이즈
        resized = cv2.resize(frame, self.target_size, interpolation=cv2.INTER_LANCZOS4)
        return resized
    
    def extract_frames_from_video(self, video_path):
        """하나의 영상에서 프레임 추출"""
        print(f"\nProcessing: {video_path.name}")
        
        # 비디오 열기
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            print(f"[ERROR] Could not open video: {video_path}")
            return 0
        
        # 비디오 정보
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0
        
        print(f"  Total frames: {total_frames}")
        print(f"  FPS: {fps:.2f}")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Extracting every {self.frame_interval} frames...")
        
        frame_count = 0
        extracted_count = 0
        
        # 프레임 추출
        with tqdm(total=total_frames, desc=f"  Extracting frames") as pbar:
            while True:
                ret, frame = cap.read()
                
                if not ret:
                    break
                
                # 지정된 간격마다 프레임 저장
                if frame_count % self.frame_interval == 0:
                    # 리사이즈
                    resized_frame = self._resize_frame(frame)
                    
                    # 파일명 생성
                    output_filename = f"court_pose_{self.current_index:06d}.jpg"
                    output_path = self.output_images_dir / output_filename
                    
                    # 저장
                    cv2.imwrite(str(output_path), resized_frame, 
                               [cv2.IMWRITE_JPEG_QUALITY, 95])
                    
                    self.current_index += 1
                    extracted_count += 1
                
                frame_count += 1
                pbar.update(1)
        
        cap.release()
        
        print(f"  ✓ Extracted {extracted_count} frames from {video_path.name}")
        
        return extracted_count
    
    def process_all_videos(self):
        """모든 영상 처리"""
        video_files = self._get_video_files()
        
        if not video_files:
            print("No new videos to process!")
            return
        
        print("="*60)
        print("Video Frame Extraction Tool")
        print("="*60)
        print(f"Video directory: {self.video_dir}")
        print(f"Output directory: {self.output_images_dir}")
        print(f"Frame interval: Every {self.frame_interval} frames")
        print(f"Starting index: {self.start_index}")
        print(f"Videos to process: {len(video_files)}")
        print("="*60)
        
        # 각 영상 처리
        for video_path in video_files:
            extracted = self.extract_frames_from_video(video_path)
            
            # 통계 업데이트
            self.stats['videos_processed'] += 1
            self.stats['frames_extracted'] += extracted
            self.stats['videos'][video_path.name] = {
                'frames_extracted': extracted,
                'index_range': f"{self.current_index - extracted:06d} ~ {self.current_index - 1:06d}"
            }
            
            # 처리 완료 목록에 추가
            self.processed_videos.add(video_path.name)
            
            # 진행 상황 저장
            self._save_progress()
        
        # 최종 결과 출력
        self.print_summary()
    
    def print_summary(self):
        """처리 결과 요약"""
        print("\n" + "="*60)
        print("Extraction Summary")
        print("="*60)
        print(f"Videos processed: {self.stats['videos_processed']}")
        print(f"Total frames extracted: {self.stats['frames_extracted']}")
        print(f"Index range: {self.start_index:06d} ~ {self.current_index - 1:06d}")
        
        if self.stats['videos']:
            print("\nFrames per video:")
            for video_name, info in self.stats['videos'].items():
                print(f"  - {video_name}: {info['frames_extracted']} frames ({info['index_range']})")
        
        print(f"\nOutput directory: {self.output_images_dir}")
        print("="*60)
        print("\n💡 Next steps:")
        print("1. Run 'make_pose_dataset.py' to label the newly extracted frames")
        print("2. The labeling tool will automatically start from unlabeled images")
        print("="*60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract frames from videos for pose dataset')
    parser.add_argument('--video_dir', type=str, 
                       default='/mnt/b/cd_p/bmt_demo/test_yolo/extra_videos',
                       help='Directory containing video files')
    parser.add_argument('--output_dir', type=str,
                       default='/mnt/b/cd_p/bmt_demo/test_yolo/pose_dataset/images',
                       help='Output directory for extracted frames')
    parser.add_argument('--interval', type=int, default=30,
                       help='Frame extraction interval (extract every N frames)')
    
    args = parser.parse_args()
    
    # 프레임 추출 실행
    extractor = VideoFrameExtractor(
        video_dir=args.video_dir,
        output_images_dir=args.output_dir,
        frame_interval=args.interval
    )
    
    extractor.process_all_videos()


if __name__ == "__main__":
    main()
