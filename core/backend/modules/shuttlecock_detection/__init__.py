"""
Shuttlecock Detection Module

이 모듈은 배드민턴 셔틀콕 검출을 위한 다양한 알고리즘을 제공합니다.
현재 TrackNet과 YOLO 기반 검출을 지원하며, 쉽게 확장 가능한 구조로 설계되었습니다.

주요 컴포넌트:
- models: 다양한 검출 모델 (YOLO, TrackNet 등)
- core: 핵심 검출 및 추적 로직
- utils: 시각화, 메트릭, 전처리 등 유틸리티
- api: FastAPI 기반 REST API 인터페이스

사용 예시:
    from shuttlecock_detection import create_detector
    
    detector = create_detector('yolo', model_path='weights/best.pt')
    results = detector.detect(frame)
"""

from .models.model_factory import create_detector
from .core.detector import ShuttlecockDetector
from .config.default_config import DetectionConfig

__version__ = "0.1.0"
__all__ = [
    "create_detector",
    "ShuttlecockDetector",
    "DetectionConfig",
]
