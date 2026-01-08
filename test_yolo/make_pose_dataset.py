"""
YOLOv8 Pose Dataset Labeling Tool

배드민턴 코트의 네 모서리 점을 마우스 클릭으로 레이블링하는 도구
- 순서: TL (Top-Left), TR (Top-Right), BR (Bottom-Right), BL (Bottom-Left)
- 보이지 않는 코너 처리 가능
- 작업 중단 후 재개 기능 지원

키보드 단축키:
- 'r': 현재 이미지 레이블 초기화 (Reset)
- 'n': 다음 이미지로 이동 (Next) - 현재 레이블 저장
- 's': 보이지 않는 점 건너뛰기 (Skip point)
- 'd': 코너가 하나도 보이지 않는 이미지 제외 (Discard)
- 'q': 프로그램 종료 (Quit)
- ESC: 프로그램 종료
"""

import cv2
import numpy as np
from pathlib import Path
import json


class PoseDatasetLabeler:
    def __init__(self, images_dir, output_dir):
        """
        Args:
            images_dir: 이미지가 있는 디렉토리
            output_dir: 레이블을 저장할 디렉토리 (images, labels 폴더가 생성됨)
        """
        self.images_dir = Path(images_dir)
        self.output_dir = Path(output_dir)
        
        # 출력 디렉토리 구조 생성
        self.output_images_dir = self.output_dir / "images"
        self.output_labels_dir = self.output_dir / "labels"
        self.output_images_dir.mkdir(parents=True, exist_ok=True)
        self.output_labels_dir.mkdir(parents=True, exist_ok=True)
        
        # 진행 상황 저장 파일
        self.progress_file = self.output_dir / "labeling_progress.json"
        
        # 키포인트 순서 (TL, TR, BR, BL)
        self.keypoint_names = ['TL', 'TR', 'BR', 'BL']
        self.num_keypoints = 4
        
        # 현재 작업 상태
        self.current_image = None
        self.current_image_path = None
        self.current_keypoints = []  # [(x, y, visibility), ...]
        self.current_point_index = 0
        
        # 이미지 리스트
        self.image_files = self._get_image_files()
        self.current_image_index = 0
        
        # 완료된 이미지 추적
        self.completed_images = self._load_progress()
        
        # 제외된 이미지 추적 (코너가 하나도 보이지 않는 경우)
        self.discarded_images = self._load_discarded()
        
        # 윈도우 설정
        self.window_name = "YOLOv8 Pose Labeling Tool"
        
        # 색상 설정
        self.colors = {
            'TL': (0, 255, 0),    # Green
            'TR': (255, 0, 0),    # Blue
            'BR': (0, 0, 255),    # Red
            'BL': (255, 255, 0)   # Cyan
        }
    
    def _get_image_files(self):
        """이미지 파일 리스트 가져오기"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        image_files = []
        
        for ext in image_extensions:
            image_files.extend(self.images_dir.glob(f'*{ext}'))
            image_files.extend(self.images_dir.glob(f'*{ext.upper()}'))
        
        return sorted(image_files)
    
    def _load_discarded(self):
        """제외된 이미지 목록 로드"""
        discarded_file = self.output_dir / "discarded_images.json"
        if discarded_file.exists():
            try:
                with open(discarded_file, 'r') as f:
                    return set(json.load(f))
            except Exception as e:
                print(f"Warning: Could not load discarded images: {e}")
        return set()
    
    def _save_discarded(self):
        """제외된 이미지 목록 저장"""
        discarded_file = self.output_dir / "discarded_images.json"
        try:
            with open(discarded_file, 'w') as f:
                json.dump(list(self.discarded_images), f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save discarded images: {e}")
    
    def _load_progress(self):
        """이전 작업 진행 상황 로드"""
        completed = set()
        
        # labels 폴더에서 이미 완료된 파일 확인
        for label_file in self.output_labels_dir.glob('*.txt'):
            completed.add(label_file.stem)
        
        # 진행 상황 파일에서 로드
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    completed.update(data.get('completed', []))
            except Exception as e:
                print(f"Warning: Could not load progress file: {e}")
        
        return completed
    
    def _save_progress(self):
        """진행 상황 저장"""
        try:
            with open(self.progress_file, 'w') as f:
                json.dump({
                    'completed': list(self.completed_images),
                    'discarded': list(self.discarded_images),
                    'total': len(self.image_files),
                    'remaining': len(self.image_files) - len(self.completed_images) - len(self.discarded_images)
                }, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save progress: {e}")
    
    def _find_next_unlabeled_image(self):
        """레이블링되지 않은 다음 이미지 찾기"""
        for i in range(self.current_image_index, len(self.image_files)):
            stem = self.image_files[i].stem
            if stem not in self.completed_images and stem not in self.discarded_images:
                return i
        return None
    
    def _reset_current_label(self):
        """현재 이미지의 레이블 초기화"""
        self.current_keypoints = []
        self.current_point_index = 0
        print("\n[RESET] Current label reset.")
    
    def _discard_current_image(self):
        """현재 이미지를 제외 목록에 추가하고 다음 이미지로 이동"""
        self.discarded_images.add(self.current_image_path.stem)
        self._save_discarded()
        print(f"[DISCARD] Image {self.current_image_path.name} discarded (no visible corners)")
        return self._load_next_image()
    
    def _skip_current_point(self):
        """현재 점을 보이지 않는 것으로 처리"""
        if self.current_point_index < self.num_keypoints:
            # visibility = 0 (보이지 않음)
            self.current_keypoints.append((0, 0, 0))
            point_name = self.keypoint_names[self.current_point_index]
            print(f"[SKIP] {point_name} marked as not visible")
            self.current_point_index += 1
    
    def _save_label(self):
        """현재 레이블을 YOLO Pose 형식으로 저장"""
        if len(self.current_keypoints) != self.num_keypoints:
            print(f"[WARNING] Not all keypoints labeled ({len(self.current_keypoints)}/{self.num_keypoints})")
            return False
        
        # YOLO Pose 형식: class x_center y_center width height x1 y1 v1 x2 y2 v2 ...
        # class: 0 (court)
        # bbox: 키포인트들을 포함하는 바운딩 박스
        # keypoints: normalized coordinates + visibility
        
        img_h, img_w = self.current_image.shape[:2]
        
        # 보이는 키포인트만 사용하여 바운딩 박스 계산
        visible_points = [(x, y) for x, y, v in self.current_keypoints if v > 0]
        
        if len(visible_points) == 0:
            print("[ERROR] No visible keypoints!")
            return False
        
        # 바운딩 박스 계산
        xs = [p[0] for p in visible_points]
        ys = [p[1] for p in visible_points]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        
        # 정규화된 바운딩 박스 (YOLO 형식: center_x, center_y, width, height)
        x_center = ((x_min + x_max) / 2) / img_w
        y_center = ((y_min + y_max) / 2) / img_h
        width = (x_max - x_min) / img_w
        height = (y_max - y_min) / img_h
        
        # 레이블 파일 생성
        label_path = self.output_labels_dir / f"{self.current_image_path.stem}.txt"
        
        with open(label_path, 'w') as f:
            # class bbox keypoints
            line = f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
            
            # 키포인트 추가 (정규화된 좌표)
            for x, y, v in self.current_keypoints:
                norm_x = x / img_w if v > 0 else 0
                norm_y = y / img_h if v > 0 else 0
                line += f" {norm_x:.6f} {norm_y:.6f} {v}"
            
            f.write(line + "\n")
        
        print(f"[SAVED] Label saved to {label_path.name}")
        return True
    
    def _copy_image_to_output(self):
        """이미지를 출력 디렉토리로 복사"""
        import shutil
        output_image_path = self.output_images_dir / self.current_image_path.name
        if not output_image_path.exists():
            shutil.copy2(self.current_image_path, output_image_path)
    
    def _load_next_image(self):
        """다음 이미지 로드"""
        # 레이블링되지 않은 다음 이미지 찾기
        next_index = self._find_next_unlabeled_image()
        
        if next_index is None:
            print("\n[COMPLETE] All images have been labeled!")
            return False
        
        self.current_image_index = next_index
        self.current_image_path = self.image_files[self.current_image_index]
        
        # 이미지 로드
        self.current_image = cv2.imread(str(self.current_image_path))
        
        if self.current_image is None:
            print(f"[ERROR] Could not load image: {self.current_image_path}")
            self.current_image_index += 1
            return self._load_next_image()
        
        # 상태 초기화
        self._reset_current_label()
        
        # 진행 상황 출력
        completed = len(self.completed_images)
        discarded = len(self.discarded_images)
        total = len(self.image_files)
        processed = completed + discarded
        print(f"\n{'='*60}")
        print(f"Image {processed + 1}/{total}: {self.current_image_path.name}")
        print(f"Progress: {completed} labeled, {discarded} discarded / {total} ({100*processed/total:.1f}%)")
        print(f"{'='*60}")
        print(f"Click points in order: {' -> '.join(self.keypoint_names)}")
        print("Press 's' to skip point, 'r' to reset, 'd' to discard, 'n' for next")
        
        return True
    
    def _mouse_callback(self, event, x, y, flags, param):
        """마우스 클릭 이벤트 처리"""
        if event == cv2.EVENT_LBUTTONDOWN:
            if self.current_point_index < self.num_keypoints:
                # 키포인트 추가 (visibility = 2: labeled and visible)
                self.current_keypoints.append((x, y, 2))
                point_name = self.keypoint_names[self.current_point_index]
                print(f"[CLICK] {point_name}: ({x}, {y})")
                self.current_point_index += 1
    
    def _draw_visualization(self):
        """현재 상태를 시각화한 이미지 생성"""
        display_image = self.current_image.copy()
        
        # 이미 클릭한 점들 그리기
        for i, (x, y, v) in enumerate(self.current_keypoints):
            if v > 0:  # visible
                point_name = self.keypoint_names[i]
                color = self.colors[point_name]
                
                # 점 그리기
                cv2.circle(display_image, (int(x), int(y)), 8, color, -1)
                cv2.circle(display_image, (int(x), int(y)), 10, (255, 255, 255), 2)
                
                # 레이블 그리기
                cv2.putText(display_image, point_name, (int(x) + 15, int(y) - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        # 선 그리기 (이미 클릭한 점들 연결)
        visible_points = [(x, y) for x, y, v in self.current_keypoints if v > 0]
        if len(visible_points) >= 2:
            for i in range(len(visible_points) - 1):
                pt1 = (int(visible_points[i][0]), int(visible_points[i][1]))
                pt2 = (int(visible_points[i+1][0]), int(visible_points[i+1][1]))
                cv2.line(display_image, pt1, pt2, (0, 255, 255), 2)
        
        # 다음 클릭할 점 표시
        if self.current_point_index < self.num_keypoints:
            next_point = self.keypoint_names[self.current_point_index]
            text = f"Next: {next_point}"
            cv2.putText(display_image, text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        else:
            text = "All points labeled! Press 'n' to save and continue"
            cv2.putText(display_image, text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # 도움말 표시
        help_text = [
            "Keys: 'r'=Reset | 's'=Skip point | 'd'=Discard | 'n'=Next | 'q'=Quit"
        ]
        y_offset = display_image.shape[0] - 20
        for text in help_text:
            cv2.putText(display_image, text, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y_offset -= 25
        
        return display_image
    
    def run(self):
        """레이블링 도구 실행"""
        print("\n" + "="*60)
        print("YOLOv8 Pose Dataset Labeling Tool")
        print("="*60)
        print(f"Images directory: {self.images_dir}")
        print(f"Output directory: {self.output_dir}")
        print(f"Total images: {len(self.image_files)}")
        print(f"Already labeled: {len(self.completed_images)}")
        print(f"Discarded: {len(self.discarded_images)}")
        print(f"Remaining: {len(self.image_files) - len(self.completed_images) - len(self.discarded_images)}")
        print("="*60)
        
        if len(self.image_files) == 0:
            print("[ERROR] No images found in the directory!")
            return
        
        # 첫 이미지 로드
        if not self._load_next_image():
            return
        
        # 윈도우 생성 및 마우스 콜백 설정
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.window_name, self._mouse_callback)
        
        # 메인 루프
        while True:
            # 시각화
            display_image = self._draw_visualization()
            cv2.imshow(self.window_name, display_image)
            
            # 키 입력 대기
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q') or key == 27:  # 'q' or ESC
                print("\n[QUIT] Exiting...")
                break
            
            elif key == ord('r'):  # Reset
                self._reset_current_label()
            
            elif key == ord('s'):  # Skip point
                self._skip_current_point()
            
            elif key == ord('d'):  # Discard image
                if not self._discard_current_image():
                    break
            
            elif key == ord('n'):  # Next
                if len(self.current_keypoints) == self.num_keypoints:
                    # 레이블 저장
                    if self._save_label():
                        # 이미지 복사
                        self._copy_image_to_output()
                        
                        # 완료 목록에 추가
                        self.completed_images.add(self.current_image_path.stem)
                        self._save_progress()
                        
                        # 다음 이미지 로드
                        if not self._load_next_image():
                            break
                else:
                    print(f"[WARNING] Please label all {self.num_keypoints} points first!")
        
        # 정리
        cv2.destroyAllWindows()
        self._save_progress()
        
        print("\n" + "="*60)
        print("Labeling Session Complete")
        print(f"Total labeled: {len(self.completed_images)}")
        print(f"Total discarded: {len(self.discarded_images)}")
        print(f"Total processed: {len(self.completed_images) + len(self.discarded_images)}/{len(self.image_files)}")
        print("="*60)


def main():
    # 경로 설정
    images_dir = "/mnt/b/cd_p/bmt_demo/test_yolo/pose_dataset/images"
    output_dir = "/mnt/b/cd_p/bmt_demo/test_yolo/labeled_pose_dataset"
    
    # 레이블러 실행
    labeler = PoseDatasetLabeler(images_dir, output_dir)
    labeler.run()


if __name__ == "__main__":
    main()
