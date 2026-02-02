"""
YOLO-based Shuttlecock Detector

YOLO 모델을 사용한 셔틀콕 검출기 구현입니다.
Ultralytics YOLO 라이브러리를 사용합니다.
"""

from typing import List, Optional
import numpy as np
from pathlib import Path

from .base_detector import BaseDetector, Detection


class YOLODetector(BaseDetector):
    """
    YOLO 기반 셔틀콕 검출기
    
    Ultralytics YOLO를 사용하여 셔틀콕을 검출합니다.
    YOLOv8, YOLOv11 등 다양한 버전을 지원합니다.
    """
    
    def __init__(
        self,
        model_path: str,
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.4,
        device: str = 'cuda',
        img_size: int = 640,
        half: bool = False,
        **kwargs
    ):
        """
        Args:
            model_path: YOLO 모델 가중치 파일 경로 (.pt)
            conf_threshold: 신뢰도 임계값
            iou_threshold: NMS IoU 임계값
            device: 실행 디바이스 ('cuda' 또는 'cpu')
            img_size: 입력 이미지 크기
            half: FP16 사용 여부 (GPU에서만 가능)
        """
        super().__init__(model_path, conf_threshold, iou_threshold, device, **kwargs)
        self.img_size = img_size
        self.half = half and device == 'cuda'
        
        # 모델 자동 로드
        self.load_model()
        
    def load_model(self) -> None:
        """YOLO 모델을 로드합니다."""
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError(
                "ultralytics 패키지가 설치되지 않았습니다. "
                "'pip install ultralytics'로 설치하세요."
            )
        
        model_path = Path(self.model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {self.model_path}")
        
        # YOLO 모델 로드
        self.model = YOLO(str(model_path))
        
        # 디바이스 설정
        if self.device == 'cuda':
            import torch
            if not torch.cuda.is_available():
                print("CUDA를 사용할 수 없습니다. CPU로 전환합니다.")
                self.device = 'cpu'
        
        self.is_loaded = True
        print(f"✓ YOLO 모델 로드 완료: {model_path.name}")
        
    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """
        입력 프레임을 전처리합니다.
        
        YOLO는 내부적으로 전처리를 수행하므로 여기서는 최소한의 처리만 합니다.
        
        Args:
            frame: 원본 이미지 (BGR)
            
        Returns:
            전처리된 이미지
        """
        # YOLO는 자체적으로 리사이징과 정규화를 수행
        return frame
    
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
        if not self.is_loaded:
            raise RuntimeError("모델이 로드되지 않았습니다.")
        
        conf = conf_threshold if conf_threshold is not None else self.conf_threshold
        
        # YOLO 추론
        results = self.model.predict(
            source=frame,
            conf=conf,
            iou=self.iou_threshold,
            imgsz=self.img_size,
            device=self.device,
            half=self.half,
            verbose=False,
        )
        
        # 결과 후처리
        detections = self.postprocess(results)
        
        return detections
    
    def postprocess(self, outputs: any) -> List[Detection]:
        """
        YOLO 출력을 Detection 객체로 변환합니다.
        
        Args:
            outputs: YOLO 모델의 Results 객체
            
        Returns:
            Detection 객체 리스트
        """
        detections = []
        
        # YOLO Results 객체에서 박스 정보 추출
        for result in outputs:
            boxes = result.boxes
            
            if boxes is None or len(boxes) == 0:
                continue
            
            for box in boxes:
                # 바운딩 박스 좌표 (xyxy 형식)
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                
                # 중심점 및 크기 계산
                x_center = (x1 + x2) / 2
                y_center = (y1 + y2) / 2
                width = x2 - x1
                height = y2 - y1
                
                # 신뢰도 및 클래스
                confidence = float(box.conf[0].cpu().numpy())
                class_id = int(box.cls[0].cpu().numpy())
                
                # Detection 객체 생성
                detection = Detection(
                    x=float(x_center),
                    y=float(y_center),
                    width=float(width),
                    height=float(height),
                    confidence=confidence,
                    class_id=class_id,
                    class_name="shuttlecock"
                )
                
                detections.append(detection)
        
        return detections
    
    def get_model_info(self) -> dict:
        """모델 정보를 반환합니다."""
        info = super().get_model_info()
        info.update({
            'model_type': 'YOLO',
            'img_size': self.img_size,
            'half_precision': self.half,
        })
        return info
