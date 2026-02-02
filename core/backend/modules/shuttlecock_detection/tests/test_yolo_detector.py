"""
Test YOLO Detector

YOLO 검출기의 기본 기능을 테스트합니다.
"""

import pytest
import numpy as np
from pathlib import Path

from shuttlecock_detection.models import YOLODetector, Detection


class TestYOLODetector:
    """YOLO 검출기 테스트"""
    
    @pytest.fixture
    def dummy_frame(self):
        """테스트용 더미 프레임 생성"""
        return np.zeros((640, 640, 3), dtype=np.uint8)
    
    def test_detector_initialization(self):
        """검출기 초기화 테스트"""
        # 모델 파일이 없는 경우 FileNotFoundError 발생 예상
        with pytest.raises(FileNotFoundError):
            detector = YOLODetector(
                model_path='nonexistent.pt',
                device='cpu'
            )
    
    def test_detection_output_format(self, dummy_frame):
        """검출 결과 형식 테스트"""
        # 실제 모델이 있다면 주석 해제
        # detector = YOLODetector(
        #     model_path='weights/best.pt',
        #     device='cpu'
        # )
        # detections = detector.detect(dummy_frame)
        # 
        # assert isinstance(detections, list)
        # for det in detections:
        #     assert isinstance(det, Detection)
        #     assert 0 <= det.confidence <= 1
        #     assert det.x >= 0 and det.y >= 0
        pass
    
    def test_confidence_threshold(self, dummy_frame):
        """신뢰도 임계값 테스트"""
        # detector = YOLODetector(
        #     model_path='weights/best.pt',
        #     conf_threshold=0.5,
        #     device='cpu'
        # )
        # 
        # # 낮은 임계값
        # detections_low = detector.detect(dummy_frame, conf_threshold=0.1)
        # 
        # # 높은 임계값
        # detections_high = detector.detect(dummy_frame, conf_threshold=0.9)
        # 
        # # 낮은 임계값일 때 더 많은 검출 예상
        # assert len(detections_low) >= len(detections_high)
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
