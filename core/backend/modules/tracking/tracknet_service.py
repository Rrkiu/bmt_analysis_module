import cv2
import zmq
import numpy as np
from typing import Optional, Tuple
import sys
from pathlib import Path
# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
from decorators import time_logger

class TrackNetService:
    def __init__(self, session_id: str, zmq_url: str = "tcp://localhost:8002"):
        self.session_id = session_id
        self.zmq_url = zmq_url
        self.last_prediction = None # (x, y, visibility)
        
        # ZeroMQ Client setup
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(self.zmq_url)
        print(f"📡 Connected to TrackNet ZeroMQ at {zmq_url}")
        
    @time_logger("TrackNet: ZMQ Call & Scaling")
    def get_prediction(self, frame: np.ndarray) -> Optional[Tuple[int, int, int]]:
        """
        Strategy B: Sends frame bytes via ZeroMQ for ultra-fast communication.
        """
        try:
            # Encode single frame
            _, img_encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            
            # Send multipart: [session_id, frame_bytes]
            self.socket.send_multipart([
                self.session_id.encode('utf-8'),
                img_encoded.tobytes()
            ])
            
            # Recv JSON reply
            result = self.socket.recv_json()
            
            if "error" in result:
                print(f"ZMQ Server Error: {result['error']}")
                return None

            if result['visibility'] == 0:
                self.last_prediction = (0, 0, 0)
                return self.last_prediction

            # Get scale factor
            h, w = frame.shape[:2]
            scale_x = w / 512.0
            scale_y = h / 288.0
            
            real_x = int(result['x'] * scale_x)
            real_y = int(result['y'] * scale_y)
            
            self.last_prediction = (real_x, real_y, 1)
            return self.last_prediction

        except Exception as e:
            print(f"ZeroMQ Communication Error: {e}")
            # Recreate socket on error
            try:
                self.socket.close()
                self.socket = self.context.socket(zmq.REQ)
                self.socket.connect(self.zmq_url)
            except:
                pass
            return None

    def draw_prediction(self, frame: np.ndarray, prediction: Optional[Tuple[int, int, int]] = None):
        """
        Draws the prediction on the frame.
        """
        pred = prediction or self.last_prediction
        if pred and pred[2] == 1: # visibility == 1
            x, y, _ = pred
            # Draw a faint yellow circle as requested
            overlay = frame.copy()
            cv2.circle(overlay, (x, y), 15, (0, 255, 255), -1)
            cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)
            # Draw a center point
            cv2.circle(frame, (x, y), 3, (0, 255, 255), -1)
        return frame
