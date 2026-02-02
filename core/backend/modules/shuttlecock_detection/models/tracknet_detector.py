"""
TrackNet Detector (Legacy Support)

기존 TrackNet 모델을 위한 래퍼 클래스입니다.
호환성 유지를 위해 제공되며, 향후 YOLO로 완전히 대체될 예정입니다.
"""

from typing import List, Optional
import numpy as np

from .base_detector import BaseDetector, Detection


class TrackNetDetector(BaseDetector):
    """
    TrackNet 기반 셔틀콕 검출기 (레거시)
    
    기존 TrackNet 모델과의 호환성을 유지하기 위한 래퍼 클래스입니다.
    새로운 프로젝트에서는 YOLODetector 사용을 권장합니다.
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
            model_path: TrackNet 모델 가중치 파일 경로
            conf_threshold: 신뢰도 임계값
            iou_threshold: NMS IoU 임계값
            device: 실행 디바이스
        """
        super().__init__(model_path, conf_threshold, iou_threshold, device, **kwargs)
        
        # TODO: 기존 TrackNet 모델 통합
        print("⚠️  TrackNet은 레거시 모델입니다. YOLO 사용을 권장합니다.")
        
    def load_model(self) -> None:
        """TrackNet 모델을 로드합니다."""
        # TODO: 기존 TrackNet 로딩 로직 구현
        raise NotImplementedError(
            "TrackNet 모델 로딩은 아직 구현되지 않았습니다. "
            "기존 TrackNet 코드를 이 메서드에 통합해야 합니다."
        )
    
    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """입력 프레임을 전처리합니다."""
        # TODO: TrackNet 전처리 로직
        return frame
    
    def detect(
        self,
        frame: np.ndarray,
        conf_threshold: Optional[float] = None
    ) -> List[Detection]:
        """프레임에서 셔틀콕을 검출합니다."""
        # TODO: TrackNet 추론 로직
        raise NotImplementedError("TrackNet 검출 로직은 아직 구현되지 않았습니다.")
    
    def postprocess(self, outputs: any) -> List[Detection]:
        """TrackNet 출력을 Detection 객체로 변환합니다."""
        # TODO: TrackNet 후처리 로직
        return []
    
    def get_model_info(self) -> dict:
        """모델 정보를 반환합니다."""
        info = super().get_model_info()
        info.update({
            'model_type': 'TrackNet',
            'status': 'legacy',
        })
        return info
