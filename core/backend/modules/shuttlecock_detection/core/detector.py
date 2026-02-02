"""
Shuttlecock Detector

메인 검출 로직을 담당하는 클래스입니다.
"""

from typing import List, Optional, Dict, Any
import numpy as np
from pathlib import Path

from ..models.base_detector import BaseDetector, Detection
from ..models.model_factory import create_detector
from ..config.default_config import DetectionConfig


class ShuttlecockDetector:
    """
    셔틀콕 검출기 메인 클래스
    
    다양한 검출 모델을 통합하여 사용할 수 있는 고수준 인터페이스를 제공합니다.
    """
    
    def __init__(
        self,
        config: Optional[DetectionConfig] = None,
        detector: Optional[BaseDetector] = None,
    ):
        """
        Args:
            config: 검출 설정 (None이면 기본값 사용)
            detector: 사용할 검출기 (None이면 config로부터 생성)
        """
        self.config = config or DetectionConfig()
        self.config.validate()
        
        # 검출기 초기화
        if detector is not None:
            self.detector = detector
        else:
            self.detector = create_detector(
                model_type=self.config.model_type,
                model_path=self.config.model_path,
                conf_threshold=self.config.conf_threshold,
                iou_threshold=self.config.iou_threshold,
                device=self.config.device,
                img_size=self.config.img_size,
                half=self.config.half_precision,
            )
        
        # 검출 히스토리
        self.detection_history: List[List[Detection]] = []
        self.frame_count = 0
        
    def detect(
        self,
        frame: np.ndarray,
        conf_threshold: Optional[float] = None,
    ) -> List[Detection]:
        """
        프레임에서 셔틀콕을 검출합니다.
        
        Args:
            frame: 입력 이미지 (numpy array, BGR)
            conf_threshold: 신뢰도 임계값 (None이면 기본값 사용)
            
        Returns:
            검출된 셔틀콕 리스트
        """
        # 검출 수행
        detections = self.detector.detect(frame, conf_threshold)
        
        # 최대 검출 개수 제한
        if len(detections) > self.config.max_detections:
            # 신뢰도 순으로 정렬하여 상위 N개만 선택
            detections = sorted(
                detections,
                key=lambda d: d.confidence,
                reverse=True
            )[:self.config.max_detections]
        
        # 히스토리 저장
        self.detection_history.append(detections)
        self.frame_count += 1
        
        return detections
    
    def detect_batch(
        self,
        frames: List[np.ndarray],
        conf_threshold: Optional[float] = None,
    ) -> List[List[Detection]]:
        """
        여러 프레임을 배치로 검출합니다.
        
        Args:
            frames: 입력 이미지 리스트
            conf_threshold: 신뢰도 임계값
            
        Returns:
            프레임별 검출 결과 리스트
        """
        results = []
        for frame in frames:
            detections = self.detect(frame, conf_threshold)
            results.append(detections)
        return results
    
    def reset(self) -> None:
        """검출 히스토리를 초기화합니다."""
        self.detection_history.clear()
        self.frame_count = 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        검출 통계를 반환합니다.
        
        Returns:
            통계 정보 딕셔너리
        """
        if not self.detection_history:
            return {
                'total_frames': 0,
                'total_detections': 0,
                'avg_detections_per_frame': 0.0,
                'detection_rate': 0.0,
            }
        
        total_detections = sum(len(dets) for dets in self.detection_history)
        frames_with_detection = sum(
            1 for dets in self.detection_history if len(dets) > 0
        )
        
        return {
            'total_frames': self.frame_count,
            'total_detections': total_detections,
            'avg_detections_per_frame': total_detections / self.frame_count,
            'detection_rate': frames_with_detection / self.frame_count,
            'frames_with_detection': frames_with_detection,
            'frames_without_detection': self.frame_count - frames_with_detection,
        }
    
    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보를 반환합니다."""
        return self.detector.get_model_info()
    
    def __repr__(self) -> str:
        return (
            f"ShuttlecockDetector("
            f"model={self.config.model_type}, "
            f"frames={self.frame_count})"
        )
