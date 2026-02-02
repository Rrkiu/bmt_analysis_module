"""
TrackNet Detector Adapter

기존 TrackNet 서비스를 어댑터 인터페이스로 래핑합니다.
"""

from typing import Optional, Tuple
import numpy as np

from .base_adapter import BaseDetectorAdapter, DetectionResult


class TrackNetDetectorAdapter(BaseDetectorAdapter):
    """
    TrackNet 검출기 어댑터
    
    기존 TrackNetService를 래핑하여 통일된 인터페이스를 제공합니다.
    """
    
    def __init__(
        self,
        session_id: str,
        zmq_url: str = "tcp://localhost:8002"
    ):
        """
        Args:
            session_id: 세션 ID
            zmq_url: TrackNet ZeroMQ 서버 URL
        """
        super().__init__(session_id)
        
        self.zmq_url = zmq_url
        
        # TrackNetService 초기화
        print(f"🔄 Initializing TrackNet service for session {session_id}...")
        from ...tracking.tracknet_service import TrackNetService
        self.tracknet_service = TrackNetService(session_id, zmq_url)
        print(f"✅ TrackNet service initialized")
        
    def get_prediction(self, frame: np.ndarray) -> Optional[Tuple[int, int, int]]:
        """
        프레임에서 셔틀콕을 검출합니다.
        
        TrackNet은 8개 프레임 스택을 사용하므로 버퍼를 유지합니다.
        
        Args:
            frame: 입력 프레임
            
        Returns:
            (x, y, visibility) 튜플
        """
        # 프레임 버퍼 업데이트
        self.update_frame_buffer(frame)
        
        try:
            # TrackNet 서비스 호출
            prediction = self.tracknet_service.get_prediction(frame)
            
            if prediction is None:
                result = DetectionResult.no_detection()
                self.last_prediction = result
                return result.to_tuple()
            
            # DetectionResult로 변환
            result = DetectionResult.from_tuple(prediction)
            self.last_prediction = result
            return result.to_tuple()
            
        except Exception as e:
            print(f"⚠️  TrackNet detection error: {e}")
            result = DetectionResult.no_detection()
            self.last_prediction = result
            return result.to_tuple()
    
    def draw_prediction(
        self, 
        frame: np.ndarray, 
        prediction: Optional[Tuple[int, int, int]] = None
    ) -> np.ndarray:
        """
        검출 결과를 프레임에 그립니다.
        
        TrackNetService의 기존 draw_prediction을 사용합니다.
        """
        return self.tracknet_service.draw_prediction(frame, prediction)
    
    def reset(self) -> None:
        """검출기 상태 초기화"""
        super().reset()
        # TrackNetService는 상태를 유지하므로 추가 초기화 불필요
        # 필요 시 소켓 재연결 등 수행 가능
    
    def __del__(self):
        """소멸자: ZeroMQ 소켓 정리"""
        try:
            if hasattr(self, 'tracknet_service'):
                self.tracknet_service.socket.close()
                self.tracknet_service.context.term()
        except:
            pass
