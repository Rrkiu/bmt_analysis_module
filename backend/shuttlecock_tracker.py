"""
셔틀콕 상태 추적 및 낙하 감지 모듈
"""

import numpy as np
import math
from typing import List, Tuple, Optional, Dict
from collections import deque

class ShuttlecockLandingDetector:
    """
    셔틀콕의 궤적을 분석하여 낙하 지점을 감지하는 클래스
    """
    
    def __init__(
        self, 
        stay_threshold: float = 10.0, # 좀 더 넉넉하게 10픽셀 허용
        stay_frames: int = 3,          # 10fps 기준 약 0.3초면 충분
        velocity_drop_threshold: float = 0.5
    ):
        self.stay_threshold = stay_threshold
        self.stay_frames = stay_frames
        self.velocity_drop_threshold = velocity_drop_threshold
        
        # 상태 관리
        self.position_history = deque(maxlen=20)  # 최근 좌표 이력 (x, y)
        self.stay_counter = 0
        self.is_landed = False
        self.landing_pos = None
        self.landing_frame = None
        
        # 디버그 정보
        self.debug_info = {
            'dist': 0.0,
            'stay_counter': 0,
            'visibility': 0,
            'is_landed': False,
            'reason': 'Initializing'
        }

    def update(self, x: float, y: float, visibility: int, frame_idx: int) -> bool:
        """
        궤적 데이터를 업데이트하고 낙하 여부를 반환
        """
        # 1. 셔틀콕이 보이지 않는 경우 (Visibility 0)
        if visibility == 0:
            # 보이지 않더라도 이전까지 정지 중이었다면 카운터를 유지함 (낙하 후 사라지는 경우 대비)
            if self.stay_counter > 0:
                self.stay_counter += 1
                # 보이지 않는 상태에서 정지 카운터가 채워지면 마지막 알려진 위치에서 낙하한 것으로 판정
                if self.stay_counter >= self.stay_frames and not self.is_landed:
                    self.is_landed = True
                    if self.position_history:
                        px, py = self.position_history[-1]
                        self.landing_pos = (px, py)
                        self.landing_frame = frame_idx
                    self.debug_info.update({'is_landed': True, 'reason': f'Stayed {self.stay_counter} frames then disappeared'})
                    return True
                self.debug_info.update({'visibility': 0, 'stay_counter': self.stay_counter, 'reason': 'Invisible but tracking stay'})
            else:
                self.debug_info.update({'visibility': 0, 'stay_counter': 0, 'reason': 'Invisible'})
            return False
            
        # 2. 셔틀콕이 보이는 경우
        # 이전 좌표와의 거리 계산
        if self.position_history:
            prev_x, prev_y = self.position_history[-1]
            dist = math.sqrt((x - prev_x)**2 + (y - prev_y)**2)
            
            if dist < self.stay_threshold:
                self.stay_counter += 1
                if self.is_landed:
                    reason = f'Landed & Staying (dist={dist:.2f} < {self.stay_threshold})'
                else:
                    reason = f'Staying (dist={dist:.2f} < {self.stay_threshold})'
            else:
                self.stay_counter = 0
                self.is_landed = False
                reason = f'Moving (dist={dist:.2f} > {self.stay_threshold})'
            self.debug_info.update({'dist': dist, 'stay_counter': self.stay_counter, 'reason': reason})
        else:
            self.stay_counter = 0
            self.debug_info.update({'dist': 0.0, 'stay_counter': 0, 'reason': 'First point'})
        
        self.debug_info.update({'visibility': visibility})

        self.position_history.append((x, y))

        # 3. 낙하 판정
        if self.stay_counter >= self.stay_frames and not self.is_landed:
            self.is_landed = True
            self.landing_pos = (x, y)
            self.landing_frame = frame_idx
            self.debug_info.update({'is_landed': True, 'reason': f'Stayed for {self.stay_counter} frames'})
            return True
            
        return False

    def get_debug_info(self) -> Dict:
        """현재 판단 근거 반환"""
        return self.debug_info

    def reset(self):
        """상태 초기화"""
        self.position_history.clear()
        self.is_landed = False
        self.landing_pos = None
        self.landing_frame = -1
        self.stay_counter = 0

    def get_landing_info(self) -> Optional[Dict]:
        """낙하 정보 반환"""
        if self.is_landed:
            return {
                'x': self.landing_pos[0],
                'y': self.landing_pos[1],
                'frame': self.landing_frame
            }
        return None
