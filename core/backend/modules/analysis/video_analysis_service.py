"""
비디오 분석 서비스

실시간 비디오 스트림에 코트 영역 오버레이 및 분석
"""

import cv2
import numpy as np
from typing import Optional, Tuple, Dict
import time
import sys
from pathlib import Path
# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
from ..tracking import TrackNetService
from ..tracking.shuttlecock_tracker import ShuttlecockLandingDetector
from ..visualization import VisualizationService
from ..calibration.geometry import HomographyTransform, CourtGeometry
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
        corners_data = None
        if 'court_corners_image' in calibration_data:
            corners_data = calibration_data['court_corners_image']
        elif 'corners_image' in calibration_data:
            corners_data = calibration_data['corners_image']
        else:
            raise ValueError("calibration_data에 'court_corners_image' 또는 'corners_image' 키가 필요합니다")
        
        # 딕셔너리 형태인 경우 (자동 검출 결과) -> 배열로 변환
        if isinstance(corners_data, dict):
            # 순서: TL, TR, BR, BL
            corner_order = ['TL', 'TR', 'BR', 'BL']
            self.corners_image = np.array([corners_data[k] for k in corner_order], dtype=np.int32)
        else:
            # 이미 리스트/배열 형태인 경우
            self.corners_image = np.array(corners_data, dtype=np.int32)
        
        self.homography = np.array(calibration_data['homography_matrix'], dtype=np.float32)
        
        # 코너 색상 (TL, TR, BR, BL)
        self.corner_colors = [
            (0, 255, 0),    # TL: Green
            (255, 0, 0),    # TR: Blue
            (0, 0, 255),    # BR: Red
            (0, 255, 255)   # BL: Yellow
        ]
        self.corner_labels = ['TL', 'TR', 'BR', 'BL']
        
        # 낙하 감지기 초기화 (10fps 분석 주기에 최적화)
        self.landing_detector = ShuttlecockLandingDetector(stay_threshold=10.0, stay_frames=4)
        
        # Homography 변환기 초기화
        self.ht = HomographyTransform()
        self.ht.homography_matrix = self.homography
        
        # 마지막 낙하 정보 저장
        self.last_landing_info = None
        self.last_world_pos = None
        self.is_last_in_court = False
        self.frame_counter = 0
        self.last_video_time = 0.0 # 비디오 시간 추적
        self.last_landing_time = -10.0 # 마지막 낙하 발생 시간
        self.last_landing_frame = -100 # 마지막 낙하 발생 프레임 번호
    
    @time_logger("Analysis: Process Frame")
    def process_frame(
        self, 
        frame: np.ndarray,
        mode: str = 'normal',
        video_time: float = 0.0 # 현재 비디오 시간 추가
    ) -> Tuple[np.ndarray, Dict]:
        """
        프레임 처리 및 오버레이
        """
        # 비디오 탐색(Seek) 감지: 
        # 0.5초 이상 뒤로 가거나(반복 재생 포함), 5초 이상 앞으로 갑자기 뛰는 경우 리셋
        is_seek = (video_time < self.last_video_time - 0.5) or (video_time > self.last_video_time + 5.0)
        
        if is_seek:
            print(f"🔄 Video Seek Detected ({self.last_video_time:.2f}s -> {video_time:.2f}s). Resetting detector.")
            self.landing_detector.reset()
            self.last_landing_info = None
            self.last_landing_frame = -100  # 프레임 카운트 초기화 (오타 수정)
            self.last_landing_time = -10.0  # 낙하 시간도 초기화
            self.last_world_pos = None
            self.is_last_in_court = False
            self.frame_counter = 0  # 프레임 카운터도 리셋하여 완전한 상태 초기화
            
        self.last_video_time = video_time
        processed = frame.copy()
        self.frame_counter += 1
        
        # 1. TrackNet 분석 수행
        tracknet_info = {
            'x': 0, 'y': 0, 'visibility': 0, 
            'is_landed': self.landing_detector.is_landed,
            'landing_debug': self.landing_detector.get_debug_info()
        }
        
        if self.use_tracknet and self.tracknet_service:
            prediction = self.tracknet_service.get_prediction(frame)
            
            x, y, vis = (0, 0, 0)
            if prediction:
                # 궤적 그리기 (이전 예측값들)
                processed = self.tracknet_service.draw_prediction(processed, prediction)
                x, y, vis = prediction
            
            # 2. 낙하 감지 업데이트 (매 프레임 수행 - 공이 안 보여도 visibility=0으로 업데이트)
            new_landing = self.landing_detector.update(x, y, vis, self.frame_counter)
            
            if new_landing:
                self.last_landing_info = self.landing_detector.get_landing_info()
                self.last_landing_time = video_time
                self.last_landing_frame = self.frame_counter
                # 실세계 좌표 변환
                world_pos = self.ht.image_to_world((self.last_landing_info['x'], self.last_landing_info['y']))
                self.last_world_pos = world_pos
                
                # 코트 내/외 판별 (좌표 변환 실패 시 무조건 OUT으로 간주)
                if world_pos is not None:
                    self.is_last_in_court = CourtGeometry.is_point_in_court(world_pos)
                else:
                    self.is_last_in_court = False
                    print(f"   ⚠️ Warning: Could not transform image pos ({self.last_landing_info['x']}, {self.last_landing_info['y']}) to world coordinates.")
            
            tracknet_info = {
                'x': x,
                'y': y,
                'visibility': vis,
                'is_landed': self.landing_detector.is_landed,
                'landing_debug': self.landing_detector.get_debug_info()
            }
        
        # 3. 코트 오버레이
        if mode == 'debug':
            processed = self._draw_debug_overlay(processed)
        else:
            processed = self._draw_court_overlay(processed)
            
        # 4. 낙하 시각화 정보 계산 (마일스톤 4)
        show_result = False
        time_since_landing = video_time - self.last_landing_time
        frames_since_landing = self.frame_counter - self.last_landing_frame
        
        if self.last_landing_info is not None:
            # 현재 낙하 중이거나, 낙하한지 20초 이내(시간) 또는 500프레임 이내(프레임 카운트)인 경우 표시
            if self.landing_detector.is_landed or (0 <= time_since_landing < 20.0) or (0 <= frames_since_landing < 500):
                show_result = True

        if show_result:
            try:
                lx, ly = int(self.last_landing_info['x']), int(self.last_landing_info['y'])
                landing_color = (0, 255, 0) if self.is_last_in_court else (0, 0, 255)
                
                # 이미지 범위 내로 좌표 클리핑
                h, w = processed.shape[:2]
                lx = max(0, min(lx, w - 1))
                ly = max(0, min(ly, h - 1))
                
                # 2. 메인 화면 마킹 (백엔드 렌더링 유지 - 디버깅/백업용)
                cv2.circle(processed, (lx, ly), 20, landing_color, -1) 
                cv2.drawMarker(processed, (lx, ly), (255, 255, 255), cv2.MARKER_TILTED_CROSS, 60, 5) 
                
                # 3. 미니맵 그리기 (좌표가 있을 때만)
                if self.last_world_pos is not None:
                    # 사용자 요청 이미지 스타일 요약 카드 (우측 상단)
                    card_w, card_h = 240, 320
                    card_x = processed.shape[1] - card_w - 30
                    card_y = 30
                    
                    # 카드 배경
                    cv2.rectangle(processed, (card_x, card_y), (card_x + card_w, card_y + card_h), (210, 212, 210), -1)
                    cv2.rectangle(processed, (card_x, card_y), (card_x + card_w, card_y + card_h), (180, 180, 180), 2)
                    
                    # 미니맵 영역
                    m_pad = 15
                    m_size = (card_w - m_pad * 2, card_h - 100)
                    processed = VisualizationService.draw_minimap(
                        processed,
                        world_point=self.last_world_pos,
                        is_in_court=self.is_last_in_court,
                        position=(card_x + m_pad, card_y + m_pad),
                        size=m_size
                    )
                    
                    # 텍스트 정보 (POS, RESULT)
                    pos_str = f"POS: {self.last_world_pos[0]:.2f}, {self.last_world_pos[1]:.2f}"
                    res_str = f"RESULT: {'IN' if self.is_last_in_court else 'OUT'}"
                    res_color = (0, 150, 0) if self.is_last_in_court else (0, 0, 255)
                    
                    cv2.putText(processed, pos_str, (card_x + m_pad, card_y + card_h - 50), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 100), 2)
                    cv2.putText(processed, res_str, (card_x + m_pad, card_y + card_h - 15), 
                                cv2.FONT_HERSHEY_DUPLEX, 0.8, res_color, 2)
                else:
                    print("   [Drawing] Skipping minimap because world_pos is None.")
                
                # 4. 판정 텍스트 (화면 하단 중앙 - 기존 유지)
                status_text = "JUDGMENT: IN" if self.is_last_in_court else "JUDGMENT: OUT"
                text_size = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 2.0, 5)[0]
                tx = (processed.shape[1] - text_size[0]) // 2
                ty = processed.shape[0] - 80
                cv2.rectangle(processed, (tx - 10, ty - text_size[1] - 10), (tx + text_size[0] + 10, ty + 10), (0, 0, 0), -1)
                cv2.putText(processed, status_text, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 2.0, landing_color, 5)
                
            except Exception as e:
                print(f"   ⚠️ Visualization Internal Error: {str(e)}")

        # 최종 반환 정보 구성
        info = {
            'frame_width': frame.shape[1],
            'frame_height': frame.shape[0],
            'mode': mode,
            'tracknet': tracknet_info,
            'landing': {
                'is_landed': self.landing_detector.is_landed,
                'pos': self.last_world_pos.tolist() if hasattr(self.last_world_pos, 'tolist') else self.last_world_pos,
                'image_x': self.last_landing_info['x'],
                'image_y': self.last_landing_info['y'],
                'is_in_court': self.is_last_in_court,
                'time_since': time_since_landing
            } if self.last_landing_info is not None else None
        }
        
        # 5. 최종 이미지 필터링 (불필요한 로그 제거, 판정 시에만 출력)
        dbg = tracknet_info['landing_debug']
        if dbg['stay_counter'] > 0:
            print(f"   [Landing] Frame: {self.frame_counter:04d} | Stay: {dbg['stay_counter']} | Reason: {dbg['reason']}")
        
        # 여기서 반환되는 'processed'가 진짜 그려진 이미지인지 다시 확인
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