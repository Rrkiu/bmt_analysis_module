"""
Base Detector Adapter

모든 검출기 어댑터가 구현해야 할 추상 베이스 클래스입니다.
TrackNet 형식의 출력을 제공하여 기존 파이프라인과 호환됩니다.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, List
from dataclasses import dataclass
import numpy as np


@dataclass
class DetectionResult:
    """
    검출 결과를 나타내는 데이터 클래스
    
    TrackNet 형식과 호환되도록 설계되었습니다:
    - (x, y, visibility) 튜플 형식 지원
    - visibility: 0 (검출 없음) 또는 1 (검출 있음)
    """
    x: int  # 중심점 x 좌표
    y: int  # 중심점 y 좌표
    visibility: int  # 0 or 1
    confidence: float = 0.0  # 신뢰도 (YOLO용, TrackNet은 사용 안함)
    
    def to_tuple(self) -> Tuple[int, int, int]:
        """TrackNet 형식 (x, y, visibility) 튜플로 변환"""
        return (self.x, self.y, self.visibility)
    
    @classmethod
    def from_tuple(cls, data: Tuple[int, int, int], confidence: float = 0.0):
        """TrackNet 형식 튜플에서 생성"""
        return cls(x=data[0], y=data[1], visibility=data[2], confidence=confidence)
    
    @classmethod
    def no_detection(cls):
        """검출 없음을 나타내는 결과"""
        return cls(x=0, y=0, visibility=0, confidence=0.0)


class BaseDetectorAdapter(ABC):
    """
    검출기 어댑터의 추상 베이스 클래스
    
    모든 어댑터는 이 클래스를 상속받아 구현해야 합니다.
    TrackNet과 동일한 인터페이스를 제공하여 기존 코드와 호환됩니다.
    """
    
    def __init__(self, session_id: str):
        """
        Args:
            session_id: 세션 ID (로깅 및 디버깅용)
        """
        self.session_id = session_id
        self.last_prediction: Optional[DetectionResult] = None
        self.frame_buffer: List[np.ndarray] = []  # 프레임 버퍼 (8개 프레임 저장)
        self.buffer_size = 8  # TrackNet과 동일
        
    @abstractmethod
    def get_prediction(self, frame: np.ndarray) -> Optional[Tuple[int, int, int]]:
        """
        프레임에서 셔틀콕을 검출합니다.
        
        Args:
            frame: 입력 프레임 (BGR, numpy array)
            
        Returns:
            (x, y, visibility) 튜플 또는 None
            - x, y: 중심점 좌표
            - visibility: 0 (검출 없음) 또는 1 (검출 있음)
        """
        pass
    
    def draw_prediction(
        self, 
        frame: np.ndarray, 
        prediction: Optional[Tuple[int, int, int]] = None
    ) -> np.ndarray:
        """
        검출 결과를 프레임에 그립니다.
        
        Args:
            frame: 입력 프레임
            prediction: 검출 결과 (None이면 마지막 결과 사용)
            
        Returns:
            시각화된 프레임
        """
        pred = prediction or (self.last_prediction.to_tuple() if self.last_prediction else None)
        
        if pred and pred[2] == 1:  # visibility == 1
            x, y, _ = pred
            
            # TrackNet 스타일: 반투명 노란색 원
            overlay = frame.copy()
            cv2.circle(overlay, (x, y), 15, (0, 255, 255), -1)
            cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)
            
            # 중심점
            cv2.circle(frame, (x, y), 3, (0, 255, 255), -1)
        
        return frame
    
    def update_frame_buffer(self, frame: np.ndarray) -> None:
        """
        프레임 버퍼를 업데이트합니다.
        
        Args:
            frame: 새로운 프레임
        """
        self.frame_buffer.append(frame)
        
        # 버퍼 크기 유지
        if len(self.frame_buffer) > self.buffer_size:
            self.frame_buffer.pop(0)
    
    def get_frame_stack(self) -> List[np.ndarray]:
        """
        현재 프레임 스택을 반환합니다.
        
        Returns:
            최근 N개 프레임 리스트
        """
        return self.frame_buffer.copy()
    
    def reset(self) -> None:
        """검출기 상태를 초기화합니다."""
        self.last_prediction = None
        self.frame_buffer.clear()
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(session_id='{self.session_id}')"


# cv2 import for draw_prediction
import cv2
