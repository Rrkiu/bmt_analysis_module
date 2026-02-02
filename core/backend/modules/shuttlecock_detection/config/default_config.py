"""
Default Configuration

셔틀콕 검출 모듈의 기본 설정입니다.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class DetectionConfig:
    """검출 설정"""
    
    # 모델 설정
    model_type: str = 'yolo'  # 'yolo' 또는 'tracknet'
    model_path: str = 'weights/best.pt'
    device: str = 'cuda'  # 'cuda' 또는 'cpu'
    
    # 검출 파라미터
    conf_threshold: float = 0.5  # 신뢰도 임계값 (0~1)
    iou_threshold: float = 0.4  # NMS IoU 임계값
    max_detections: int = 10  # 최대 검출 개수
    
    # 이미지 전처리
    img_size: int = 640  # 입력 이미지 크기
    normalize: bool = True  # 정규화 여부
    
    # 성능 최적화
    half_precision: bool = False  # FP16 사용 (GPU만 가능)
    batch_size: int = 1  # 배치 크기
    
    def validate(self) -> None:
        """설정 값의 유효성을 검증합니다."""
        assert self.model_type in ['yolo', 'tracknet'], \
            f"Invalid model_type: {self.model_type}"
        assert 0 <= self.conf_threshold <= 1, \
            f"conf_threshold must be in [0, 1], got {self.conf_threshold}"
        assert 0 <= self.iou_threshold <= 1, \
            f"iou_threshold must be in [0, 1], got {self.iou_threshold}"
        assert self.img_size > 0, \
            f"img_size must be positive, got {self.img_size}"
        assert self.device in ['cuda', 'cpu'], \
            f"Invalid device: {self.device}"
    
    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            'model_type': self.model_type,
            'model_path': self.model_path,
            'device': self.device,
            'conf_threshold': self.conf_threshold,
            'iou_threshold': self.iou_threshold,
            'max_detections': self.max_detections,
            'img_size': self.img_size,
            'normalize': self.normalize,
            'half_precision': self.half_precision,
            'batch_size': self.batch_size,
        }


@dataclass
class TrackingConfig:
    """추적 설정"""
    
    # 추적 파라미터
    max_age: int = 30  # 트랙이 사라지기까지의 최대 프레임 수
    min_hits: int = 3  # 트랙으로 인정되기 위한 최소 검출 횟수
    iou_threshold: float = 0.3  # 트랙 매칭 IoU 임계값
    
    # 궤적 예측
    enable_prediction: bool = True  # 궤적 예측 활성화
    prediction_frames: int = 5  # 예측할 미래 프레임 수
    
    # 스무딩
    enable_smoothing: bool = True  # 위치 스무딩 활성화
    smoothing_window: int = 5  # 스무딩 윈도우 크기


@dataclass
class VisualizationConfig:
    """시각화 설정"""
    
    # 바운딩 박스
    bbox_color: Tuple[int, int, int] = (0, 255, 0)  # BGR
    bbox_thickness: int = 2
    show_confidence: bool = True
    
    # 궤적
    trajectory_color: Tuple[int, int, int] = (255, 0, 0)  # BGR
    trajectory_thickness: int = 2
    trajectory_length: int = 30  # 표시할 궤적 길이
    
    # 텍스트
    font_scale: float = 0.5
    font_thickness: int = 1
    text_color: Tuple[int, int, int] = (255, 255, 255)  # BGR


@dataclass
class Config:
    """전체 설정"""
    
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)
    
    def validate(self) -> None:
        """모든 설정의 유효성을 검증합니다."""
        self.detection.validate()
