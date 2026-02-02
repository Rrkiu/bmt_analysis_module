"""
Base Detector Abstract Class

모든 셔틀콕 검출 모델이 상속받아야 하는 추상 베이스 클래스입니다.
새로운 검출 모델을 추가할 때는 이 클래스를 상속받아 구현하세요.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from dataclasses import dataclass
import numpy as np


@dataclass
class Detection:
    """검출 결과를 나타내는 데이터 클래스"""
    x: float  # 중심점 x 좌표
    y: float  # 중심점 y 좌표
    width: float  # 바운딩 박스 너비
    height: float  # 바운딩 박스 높이
    confidence: float  # 신뢰도 (0~1)
    class_id: int = 0  # 클래스 ID (셔틀콕은 보통 0)
    class_name: str = "shuttlecock"
    
    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """바운딩 박스 좌표 (x1, y1, x2, y2) 반환"""
        x1 = self.x - self.width / 2
        y1 = self.y - self.height / 2
        x2 = self.x + self.width / 2
        y2 = self.y + self.height / 2
        return (x1, y1, x2, y2)
    
    @property
    def center(self) -> Tuple[float, float]:
        """중심점 좌표 (x, y) 반환"""
        return (self.x, self.y)
    
    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'confidence': self.confidence,
            'class_id': self.class_id,
            'class_name': self.class_name,
            'bbox': self.bbox,
        }


class BaseDetector(ABC):
    """
    셔틀콕 검출기의 추상 베이스 클래스
    
    모든 검출 모델은 이 클래스를 상속받아 구현해야 합니다.
    """
    
    def __init__(
        self,
        model_path: str,
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.4,
        device: str = 'cuda',
        **kwargs
    ):
        """
        Args:
            model_path: 모델 가중치 파일 경로
            conf_threshold: 신뢰도 임계값
            iou_threshold: NMS IoU 임계값
            device: 실행 디바이스 ('cuda' 또는 'cpu')
            **kwargs: 추가 모델별 파라미터
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.device = device
        self.model = None
        self.is_loaded = False
        
    @abstractmethod
    def load_model(self) -> None:
        """
        모델을 로드합니다.
        
        각 검출기는 이 메서드를 구현하여 모델을 초기화해야 합니다.
        """
        pass
    
    @abstractmethod
    def detect(
        self,
        frame: np.ndarray,
        conf_threshold: Optional[float] = None
    ) -> List[Detection]:
        """
        프레임에서 셔틀콕을 검출합니다.
        
        Args:
            frame: 입력 이미지 (numpy array, BGR 형식)
            conf_threshold: 신뢰도 임계값 (None이면 기본값 사용)
            
        Returns:
            검출된 셔틀콕 리스트
        """
        pass
    
    @abstractmethod
    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """
        입력 프레임을 전처리합니다.
        
        Args:
            frame: 원본 이미지
            
        Returns:
            전처리된 이미지
        """
        pass
    
    @abstractmethod
    def postprocess(self, outputs: any) -> List[Detection]:
        """
        모델 출력을 후처리하여 Detection 객체로 변환합니다.
        
        Args:
            outputs: 모델의 원시 출력
            
        Returns:
            Detection 객체 리스트
        """
        pass
    
    def warmup(self, input_shape: Tuple[int, int, int] = (640, 640, 3)) -> None:
        """
        모델을 워밍업합니다 (첫 추론 속도 개선).
        
        Args:
            input_shape: 입력 이미지 크기 (height, width, channels)
        """
        dummy_input = np.zeros(input_shape, dtype=np.uint8)
        _ = self.detect(dummy_input)
        
    def get_model_info(self) -> dict:
        """
        모델 정보를 반환합니다.
        
        Returns:
            모델 메타데이터 딕셔너리
        """
        return {
            'model_path': self.model_path,
            'conf_threshold': self.conf_threshold,
            'iou_threshold': self.iou_threshold,
            'device': self.device,
            'is_loaded': self.is_loaded,
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model_path='{self.model_path}', device='{self.device}')"
