"""
Model Factory

검출 모델을 생성하는 팩토리 패턴 구현입니다.
"""

from typing import Optional
from pathlib import Path

from .base_detector import BaseDetector
from .yolo_detector import YOLODetector
from .tracknet_detector import TrackNetDetector


# 지원하는 모델 타입
SUPPORTED_MODELS = {
    'yolo': YOLODetector,
    'tracknet': TrackNetDetector,
}


def create_detector(
    model_type: str,
    model_path: str,
    conf_threshold: float = 0.5,
    iou_threshold: float = 0.4,
    device: str = 'cuda',
    **kwargs
) -> BaseDetector:
    """
    검출 모델을 생성합니다.
    
    Args:
        model_type: 모델 타입 ('yolo' 또는 'tracknet')
        model_path: 모델 가중치 파일 경로
        conf_threshold: 신뢰도 임계값
        iou_threshold: NMS IoU 임계값
        device: 실행 디바이스 ('cuda' 또는 'cpu')
        **kwargs: 모델별 추가 파라미터
        
    Returns:
        BaseDetector를 상속받은 검출기 인스턴스
        
    Raises:
        ValueError: 지원하지 않는 모델 타입인 경우
        FileNotFoundError: 모델 파일이 존재하지 않는 경우
        
    Examples:
        >>> # YOLO 검출기 생성
        >>> detector = create_detector('yolo', 'weights/best.pt')
        
        >>> # TrackNet 검출기 생성
        >>> detector = create_detector('tracknet', 'weights/tracknet.pth')
    """
    model_type = model_type.lower()
    
    # 지원하는 모델 타입 확인
    if model_type not in SUPPORTED_MODELS:
        raise ValueError(
            f"지원하지 않는 모델 타입입니다: {model_type}\n"
            f"지원 모델: {list(SUPPORTED_MODELS.keys())}"
        )
    
    # 모델 파일 존재 확인
    model_path_obj = Path(model_path)
    if not model_path_obj.exists():
        raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {model_path}")
    
    # 모델 클래스 가져오기
    detector_class = SUPPORTED_MODELS[model_type]
    
    # 검출기 인스턴스 생성
    detector = detector_class(
        model_path=str(model_path),
        conf_threshold=conf_threshold,
        iou_threshold=iou_threshold,
        device=device,
        **kwargs
    )
    
    return detector


def list_available_models() -> dict:
    """
    사용 가능한 모델 타입과 설명을 반환합니다.
    
    Returns:
        모델 타입별 설명 딕셔너리
    """
    return {
        'yolo': {
            'name': 'YOLO',
            'description': 'Ultralytics YOLO 기반 검출기 (권장)',
            'class': YOLODetector,
            'supported_versions': ['YOLOv8', 'YOLOv11'],
        },
        'tracknet': {
            'name': 'TrackNet',
            'description': 'TrackNet 기반 검출기 (레거시)',
            'class': TrackNetDetector,
            'status': 'legacy',
        },
    }


def auto_detect_model_type(model_path: str) -> Optional[str]:
    """
    모델 파일 확장자를 기반으로 모델 타입을 자동 감지합니다.
    
    Args:
        model_path: 모델 파일 경로
        
    Returns:
        감지된 모델 타입 또는 None
    """
    model_path_obj = Path(model_path)
    suffix = model_path_obj.suffix.lower()
    
    # 확장자 기반 모델 타입 매핑
    extension_map = {
        '.pt': 'yolo',
        '.pth': 'tracknet',
        '.onnx': 'yolo',   # YOLO ONNX 지원
        '.engine': 'yolo', # TensorRT Engine 지원
    }
    
    return extension_map.get(suffix)
