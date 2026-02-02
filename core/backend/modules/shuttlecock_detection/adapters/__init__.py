"""
Shuttlecock Detection Adapters

어댑터 패턴을 사용하여 다양한 검출 모델을 통일된 인터페이스로 제공합니다.
TrackNet과 YOLO 검출기를 동일한 방식으로 사용할 수 있습니다.
"""

from .base_adapter import BaseDetectorAdapter, DetectionResult
from .yolo_adapter import YOLODetectorAdapter
from .tracknet_adapter import TrackNetDetectorAdapter

__all__ = [
    'BaseDetectorAdapter',
    'DetectionResult',
    'YOLODetectorAdapter',
    'TrackNetDetectorAdapter',
]
