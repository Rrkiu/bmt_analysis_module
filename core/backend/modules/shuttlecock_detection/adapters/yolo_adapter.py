"""
YOLO Detector Adapter

YOLO 검출기를 TrackNet 형식으로 변환하는 어댑터입니다.
"""

from typing import Optional, Tuple
import numpy as np
from pathlib import Path

from .base_adapter import BaseDetectorAdapter, DetectionResult
from ..models import create_detector, BaseDetector


class YOLODetectorAdapter(BaseDetectorAdapter):
    """
    YOLO 검출기 어댑터
    
    YOLO 검출 결과를 TrackNet 형식 (x, y, visibility)로 변환합니다.
    현재는 8개 프레임 중 마지막 프레임만 사용하지만, 향후 시간적 정보 활용 가능합니다.
    """
    
    def __init__(
        self,
        session_id: str,
        model_path: str,
        conf_threshold: float = 0.5,
        device: str = 'cuda',
        img_size: int = 640,
        **kwargs
    ):
        """
        Args:
            session_id: 세션 ID
            model_path: YOLO 모델 가중치 경로
            conf_threshold: 신뢰도 임계값
            device: 실행 디바이스 ('cuda' 또는 'cpu')
            img_size: 추론 입력 해상도 (학습 해상도와 일치 권장)
            **kwargs: 추가 YOLO 파라미터
        """
        super().__init__(session_id)
        
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.device = device
        self.img_size = img_size
        
        # 모든 검출 정보 저장 (시각화용)
        self.all_detections = []  # Detection 객체 리스트
        
        # YOLO 검출기 초기화
        print(f"🔄 Initializing YOLO detector for session {session_id}...")
        print(f"   Model : {model_path}")
        print(f"   imgsz : {img_size}")
        self.detector: BaseDetector = create_detector(
            model_type='yolo',
            model_path=model_path,
            conf_threshold=conf_threshold,
            device=device,
            img_size=img_size,
            **kwargs
        )
        print(f"✅ YOLO detector initialized")

        
    def get_prediction(self, frame: np.ndarray) -> Optional[Tuple[int, int, int]]:
        """
        프레임에서 셔틀콕을 검출합니다.
        
        현재 구현: 8개 프레임 버퍼를 유지하지만, 마지막 프레임만 사용
        향후: 시간적 정보를 활용한 필터링/추적 가능
        
        Args:
            frame: 입력 프레임
            
        Returns:
            (x, y, visibility) 튜플
        """
        import time
        start_time = time.time()
        
        # 프레임 버퍼 업데이트
        self.update_frame_buffer(frame)
        
        # 현재 프레임 (마지막 프레임) 사용
        current_frame = self.frame_buffer[-1] if self.frame_buffer else frame
        
        try:
            # YOLO 검출 수행
            detect_start = time.time()
            detections = self.detector.detect(current_frame, self.conf_threshold)
            detect_time = (time.time() - detect_start) * 1000
            
            # 모든 검출 정보 저장 (시각화용)
            self.all_detections = detections if detections else []
            
            if not detections or len(detections) == 0:
                # 검출 없음
                result = DetectionResult.no_detection()
                self.last_prediction = result
                total_time = (time.time() - start_time) * 1000
                # print(f"   [YOLO] No detection | Total: {total_time:.1f}ms")
                return result.to_tuple()
            
            # 가장 신뢰도 높은 검출 선택 (메인 검출)
            best_detection = max(detections, key=lambda d: d.confidence)
            
            # DetectionResult로 변환
            result = DetectionResult(
                x=int(best_detection.x),
                y=int(best_detection.y),
                visibility=1,  # 검출 있음
                confidence=best_detection.confidence
            )
            
            self.last_prediction = result
            total_time = (time.time() - start_time) * 1000
            # print(f"   [YOLO] Detected {len(detections)} shuttlecock(s) | Best @ ({result.x}, {result.y}) | Conf: {result.confidence:.2f} | Total: {total_time:.1f}ms")
            return result.to_tuple()

            
        except Exception as e:
            print(f"⚠️  YOLO detection error: {e}")
            result = DetectionResult.no_detection()
            self.last_prediction = result
            return result.to_tuple()

    
    def draw_prediction(
        self, 
        frame: np.ndarray, 
        prediction: Optional[Tuple[int, int, int]] = None
    ) -> np.ndarray:
        """
        검출 결과를 프레임에 그립니다.
        
        모든 검출된 셔틀콕을 표시:
        - 메인 검출 (신뢰도 최고): 노란색 (0, 255, 255)
        - 기타 검출: 주황색 (0, 165, 255)
        """
        # 모든 검출 표시
        if self.all_detections and len(self.all_detections) > 0:
            # 메인 검출 찾기 (신뢰도 최고)
            main_detection = max(self.all_detections, key=lambda d: d.confidence)
            
            for detection in self.all_detections:
                x, y = int(detection.x), int(detection.y)
                conf = detection.confidence
                
                # 메인 검출 여부에 따라 색상 결정
                is_main = (detection == main_detection)
                color = (0, 255, 255) if is_main else (0, 165, 255)  # 노란색 or 주황색
                alpha = 0.4 if is_main else 0.3
                radius = 10 if is_main else 8  # 크기 축소: 15→10, 12→8
                
                # 반투명 원
                overlay = frame.copy()
                cv2.circle(overlay, (x, y), radius, color, -1)
                cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
                
                # 중심점 (더 작게)
                cv2.circle(frame, (x, y), 2, color, -1)  # 3→2

                
                # 신뢰도 표시
                conf_text = f"{conf:.2f}"
                text_color = color if is_main else (0, 140, 255)
                
                # 텍스트 배경
                (text_w, text_h), _ = cv2.getTextSize(
                    conf_text, 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.5, 
                    1
                )
                cv2.rectangle(
                    frame,
                    (x + 18, y - text_h - 12),
                    (x + 18 + text_w + 4, y - 8),
                    (0, 0, 0),
                    -1
                )
                
                # 신뢰도 텍스트
                cv2.putText(
                    frame, 
                    conf_text, 
                    (x + 20, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    text_color,
                    1
                )
                
                # 메인 검출 표시 (별 마크)
                if is_main and len(self.all_detections) > 1:
                    cv2.putText(
                        frame,
                        "*",
                        (x - 8, y - 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (255, 255, 255),
                        2
                    )
            
            # 검출 개수 표시 (좌측 상단)
            if len(self.all_detections) > 1:
                count_text = f"Detected: {len(self.all_detections)} shuttlecocks"
                cv2.rectangle(frame, (10, 10), (350, 45), (0, 0, 0), -1)
                cv2.putText(
                    frame,
                    count_text,
                    (15, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2
                )
        
        return frame

    
    def get_model_info(self) -> dict:
        """모델 정보 반환"""
        info = self.detector.get_model_info()
        info['adapter_type'] = 'YOLO'
        info['session_id'] = self.session_id
        return info
    
    def reset(self) -> None:
        """검출기 상태 초기화"""
        super().reset()
        self.all_detections = []
        # YOLO 검출기는 상태가 없으므로 추가 초기화 불필요



# cv2 import
import cv2
