"""
비디오 분석 서비스

실시간 비디오 스트림에 코트 영역 오버레이 및 분석
"""

import cv2
import numpy as np
from typing import Optional, Tuple, Dict
import time
from tracknet_service import TrackNetService
from decorators import time_logger


class VideoAnalysisService:
    """비디오 분석 서비스"""
    
    def __init__(self, session_id: str, calibration_data: Dict, use_tracknet: bool = True):
        """
        초기화
        
        Args:
            calibration_data: 캘리브레이션 데이터
                - court_corners_image: 이미지 좌표 4개 코너
                - homography_matrix: Homography 행렬
            use_tracknet: TrackNet 추적 활성화 여부
        """
        self.calibration_data = calibration_data
        
        # TrackNet 서비스 초기화
        self.use_tracknet = use_tracknet
        self.tracknet_service = TrackNetService(session_id) if use_tracknet else None
        
        # 키 이름 정규화 (court_corners_image 또는 corners_image 둘 다 지원)
        if 'court_corners_image' in calibration_data:
            self.corners_image = np.array(calibration_data['court_corners_image'], dtype=np.int32)
        elif 'corners_image' in calibration_data:
            self.corners_image = np.array(calibration_data['corners_image'], dtype=np.int32)
        else:
            raise ValueError("calibration_data에 'court_corners_image' 또는 'corners_image' 키가 필요합니다")
        
        self.homography = np.array(calibration_data['homography_matrix'], dtype=np.float32)
        
        # 코너 색상 (TL, TR, BR, BL)
        self.corner_colors = [
            (0, 255, 0),    # TL: Green
            (255, 0, 0),    # TR: Blue
            (0, 0, 255),    # BR: Red
            (0, 255, 255)   # BL: Yellow
        ]
        self.corner_labels = ['TL', 'TR', 'BR', 'BL']
    
    @time_logger("Analysis: Process Frame")
    def process_frame(
        self, 
        frame: np.ndarray,
        mode: str = 'normal'
    ) -> Tuple[np.ndarray, Dict]:
        """
        프레임 처리 및 오버레이
        
        Args:
            frame: 입력 프레임
            mode: 'normal' | 'debug'
                - 'normal': 코트 영역만 표시
                - 'debug': 코트 영역 + 코너 포인트 + 좌표 정보
        
        Returns:
            (processed_frame, info)
            - processed_frame: 처리된 프레임
            - info: 분석 정보 (FPS 등)
        """
        processed = frame.copy()
        
        # TrackNet 분석 수행
        tracknet_info = None
        if self.use_tracknet and self.tracknet_service:
            prediction = self.tracknet_service.get_prediction(frame)
            if prediction:
                processed = self.tracknet_service.draw_prediction(processed, prediction)
                tracknet_info = {
                    'x': prediction[0],
                    'y': prediction[1],
                    'visibility': prediction[2]
                }
        
        if mode == 'debug':
            # 디버그 모드: 상세 정보 표시
            processed = self._draw_debug_overlay(processed)
        else:
            # 일반 모드: 코트 영역만 표시
            processed = self._draw_court_overlay(processed)
        
        info = {
            'frame_width': frame.shape[1],
            'frame_height': frame.shape[0],
            'mode': mode,
            'tracknet': tracknet_info
        }
        
        return processed, info
    
    def _draw_court_overlay(self, frame: np.ndarray) -> np.ndarray:
        """
        일반 모드: 코트 영역만 표시
        
        Args:
            frame: 입력 프레임
            
        Returns:
            오버레이가 적용된 프레임
        """
        # 반투명 녹색 영역
        overlay = frame.copy()
        cv2.fillPoly(overlay, [self.corners_image], (0, 255, 0))
        frame = cv2.addWeighted(frame, 0.85, overlay, 0.15, 0)
        
        # 코트 경계선 (노란색)
        cv2.polylines(frame, [self.corners_image], True, (0, 255, 255), 3)
        
        return frame
    
    def _draw_debug_overlay(self, frame: np.ndarray) -> np.ndarray:
        """
        디버그 모드: 코트 영역 + 코너 포인트 + 좌표 정보
        
        Args:
            frame: 입력 프레임
            
        Returns:
            디버그 정보가 포함된 프레임
        """
        # 반투명 녹색 영역
        overlay = frame.copy()
        cv2.fillPoly(overlay, [self.corners_image], (0, 255, 0))
        frame = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)
        
        # 코트 경계선 (시안색)
        cv2.polylines(frame, [self.corners_image], True, (255, 255, 0), 3)
        
        # 코너 포인트
        for i, (corner, color, label) in enumerate(zip(
            self.corners_image, 
            self.corner_colors, 
            self.corner_labels
        )):
            x, y = int(corner[0]), int(corner[1])
            
            # 원 (컬러)
            cv2.circle(frame, (x, y), 12, color, -1)
            # 외곽선 (흰색)
            cv2.circle(frame, (x, y), 15, (255, 255, 255), 2)
            
            # 레이블
            cv2.putText(frame, label, (x + 20, y - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # 좌표 정보
            coord_text = f"({x}, {y})"
            cv2.putText(frame, coord_text, (x + 20, y + 15), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # 상단 정보 패널
        info_panel_height = 100
        info_panel = np.zeros((info_panel_height, frame.shape[1], 3), dtype=np.uint8)
        info_panel[:] = (50, 50, 50)  # 어두운 회색
        
        # 정보 텍스트
        cv2.putText(info_panel, "DEBUG MODE", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(info_panel, f"Resolution: {frame.shape[1]}x{frame.shape[0]}", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(info_panel, f"Court Area: {self._calculate_court_area()} px^2", (10, 85), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # 정보 패널을 프레임 상단에 합성
        frame = np.vstack([info_panel, frame])
        
        return frame
    
    def _calculate_court_area(self) -> int:
        """코트 영역 면적 계산"""
        return int(cv2.contourArea(self.corners_image))
    
    def process_video_file(
        self,
        video_path: str,
        mode: str = 'normal',
        output_path: Optional[str] = None,
        max_frames: Optional[int] = None
    ) -> Dict:
        """
        비디오 파일 처리
        
        Args:
            video_path: 비디오 파일 경로
            mode: 'normal' | 'debug'
            output_path: 출력 비디오 경로 (선택)
            max_frames: 최대 처리 프레임 수 (None이면 전체)
        
        Returns:
            처리 결과 정보
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"비디오 파일을 열 수 없습니다: {video_path}")
        
        # 비디오 정보
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"📹 비디오 정보:")
        print(f"   - 해상도: {width}x{height}")
        print(f"   - FPS: {fps}")
        print(f"   - 총 프레임: {total_frames}")
        print(f"   - 모드: {mode}")
        
        # 출력 비디오 설정
        writer = None
        if output_path:
            # 디버그 모드면 높이 증가
            out_height = height + 100 if mode == 'debug' else height
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(output_path, fourcc, fps, (width, out_height))
        
        # 프레임 처리
        frame_count = 0
        start_time = time.time()
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 최대 프레임 체크
            if max_frames and frame_count >= max_frames:
                break
            
            # 프레임 처리
            processed, info = self.process_frame(frame, mode=mode)
            
            # 저장
            if writer:
                writer.write(processed)
            
            frame_count += 1
            
            # 진행 상황 출력
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps_actual = frame_count / elapsed
                print(f"   처리: {frame_count}/{total_frames} ({fps_actual:.1f} FPS)")
        
        # 정리
        cap.release()
        if writer:
            writer.release()
        
        elapsed_total = time.time() - start_time
        
        result = {
            'success': True,
            'frames_processed': frame_count,
            'elapsed_time': elapsed_total,
            'avg_fps': frame_count / elapsed_total,
            'output_path': output_path
        }
        
        print(f"✅ 처리 완료: {frame_count} 프레임, {elapsed_total:.1f}초")
        
        return result
    
    def process_webcam(
        self,
        mode: str = 'normal',
        camera_index: int = 0
    ):
        """
        웹캠 실시간 처리
        
        Args:
            mode: 'normal' | 'debug'
            camera_index: 카메라 인덱스 (기본: 0)
        """
        cap = cv2.VideoCapture(camera_index)
        
        if not cap.isOpened():
            raise ValueError(f"카메라를 열 수 없습니다: {camera_index}")
        
        print(f"🎥 웹캠 시작 (모드: {mode})")
        print("   ESC 또는 'q' 키로 종료")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 프레임 처리
            processed, info = self.process_frame(frame, mode=mode)
            
            # 표시
            cv2.imshow('Badminton Court Analysis', processed)
            
            # 키 입력
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q'):  # ESC or 'q'
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        print("✅ 웹캠 종료")