"""
캘리브레이션 서비스
T자 기준점 기반 코트 영역 생성
"""

import numpy as np
from typing import Dict, Tuple, List, Optional
import sys
from pathlib import Path
# Add backend directory to path for constants import
backend_dir = Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
from constants import CourtDimensions, COURT_TEMPLATE, T_GUIDE
from .geometry import HomographyTransform, CourtGeometry


class CalibrationService:
    """캘리브레이션 서비스"""
    
    def __init__(self):
        self.homography = HomographyTransform()
        self.court_template = COURT_TEMPLATE
    
    def calibrate_from_t_point(
        self,
        t_point_image: Tuple[float, float],
        image_shape: Tuple[int, int],
        rotation_angle: float = 0.0
    ) -> Dict:
        """
        T자 기준점으로부터 코트 캘리브레이션 수행 (추정 방식)
        """
        # ... (생략 또는 기존 코드 유지)
        # 이 방식보다는 직접 4개 코너를 지정하는 방식을 권장함
        
        user_court = self.court_template['user_court']
        t_point_world = self.court_template['t_reference']
        court_corners_world = [
            user_court['top_left'],
            user_court['top_right'],
            user_court['bottom_right'],
            user_court['bottom_left']
        ]
        
        image_height, image_width = image_shape
        estimated_court_height_pixels = image_height * 0.7
        actual_court_length = CourtDimensions.BACK_BOUNDARY_LINE
        pixels_per_meter = estimated_court_height_pixels / actual_court_length
        
        t_x_img, t_y_img = t_point_image
        
        court_corners_image = []
        for world_corner in court_corners_world:
            offset_x_world = world_corner[0] - t_point_world['x']
            offset_y_world = world_corner[1] - t_point_world['y']
            offset_x_pixels = offset_x_world * pixels_per_meter
            offset_y_pixels = offset_y_world * pixels_per_meter
            court_corners_image.append([t_x_img + offset_x_pixels, t_y_img + offset_y_pixels])
        
        return self.calibrate_from_corners(court_corners_image, image_shape)

    def calibrate_from_corners(
        self,
        court_corners_image: List[List[float]],
        image_shape: Tuple[int, int]
    ) -> Dict:
        """
        사용자가 지정한 4개 코너로부터 캘리브레이션 수행
        
        Args:
            court_corners_image: [TL, TR, BR, BL] 이미지 좌표 (풀코트 복식 기준)
            image_shape: (height, width)
            
        Returns:
            dict: 캘리브레이션 결과
        """
        # FULL COURT 기준 world coordinates (DOUBLES WIDTH)
        # 검출된 코너는 복식 코트의 외곽선
        # TL, TR = 상대방 베이스라인 (-6.7m)
        # BR, BL = 플레이어 베이스라인 (+6.7m)
        half_width = CourtDimensions.DOUBLES_WIDTH / 2  # 3.05m (복식)
        half_length = CourtDimensions.BACK_BOUNDARY_LINE  # 6.7m
        
        court_corners_world = [
            [-half_width, -half_length],  # TL: 상대방 베이스라인 왼쪽 (복식)
            [half_width, -half_length],   # TR: 상대방 베이스라인 오른쪽 (복식)
            [half_width, half_length],    # BR: 플레이어 베이스라인 오른쪽 (복식)
            [-half_width, half_length]    # BL: 플레이어 베이스라인 왼쪽 (복식)
        ]
        
        # Homography 계산
        src_points = np.array(court_corners_image, dtype=np.float32)
        dst_points = np.array(court_corners_world, dtype=np.float32)
        
        # 4개 점일 때는 method=0 (정확한 해) 사용
        success = self.homography.compute_homography(src_points, dst_points, method=0)
        
        if not success:
            return {
                'success': False,
                'error': 'Homography 계산 실패'
            }
            
        # 픽셀/미터 비율은 가로/세로 평균으로 추정
        # TL-TR 거리 (가로, 복식)
        w_pixels = np.linalg.norm(src_points[0] - src_points[1])
        w_meters = CourtDimensions.DOUBLES_WIDTH  # 6.1m
        # TL-BL 거리 (세로, 풀코트)
        h_pixels = np.linalg.norm(src_points[0] - src_points[3])
        h_meters = CourtDimensions.TOTAL_LENGTH  # 13.4m (풀코트)
        
        pixels_per_meter = float((w_pixels/w_meters + h_pixels/h_meters) / 2)
        
        return {
            'success': True,
            'court_corners_image': court_corners_image,
            'court_corners_world': court_corners_world,
            'homography_matrix': self.homography.homography_matrix.astype(float).tolist(),
            'pixels_per_meter': pixels_per_meter,
            'image_shape': image_shape,
        }
    
    def generate_court_region(
        self,
        calibration_result: Dict
    ) -> Dict:
        """
        캘리브레이션 결과로부터 코트 영역 정보 생성
        
        Args:
            calibration_result: calibrate_from_t_point 결과
            
        Returns:
            dict: 코트 영역 정보
        """
        if not calibration_result.get('success'):
            return {'success': False, 'error': 'Invalid calibration result'}
        
        corners_image = calibration_result['court_corners_image']
        corners_world = calibration_result['court_corners_world']
        
        # 코트 형태 검증
        is_valid, message = CourtGeometry.is_valid_court_shape(corners_image)
        
        # 넓이 계산
        area = CourtGeometry.compute_court_area(corners_image)
        
        return {
            'success': True,
            'court_region': {
                'corners_image': corners_image,
                'corners_world': corners_world,
                'area_pixels': area,
                'is_valid': is_valid,
                'validation_message': message,
            }
        }
    
    def get_t_guide_image_coords(
        self,
        calibration_result: Dict
    ) -> Dict:
        """
        T자 가이드 라인의 이미지 좌표 계산
        
        Args:
            calibration_result: 캘리브레이션 결과
            
        Returns:
            dict: T자 라인 정보
        """
        if not calibration_result.get('success'):
            return {'success': False}
        
        # 실세계 T자 가이드 좌표
        t_guide_world = T_GUIDE
        
        # 이미지 좌표로 변환
        vertical_start = self.homography.world_to_image(
            tuple(t_guide_world['vertical']['start'])
        )
        vertical_end = self.homography.world_to_image(
            tuple(t_guide_world['vertical']['end'])
        )
        horizontal_start = self.homography.world_to_image(
            tuple(t_guide_world['horizontal']['start'])
        )
        horizontal_end = self.homography.world_to_image(
            tuple(t_guide_world['horizontal']['end'])
        )
        
        return {
            'success': True,
            't_guide': {
                'vertical': {
                    'start': list(vertical_start) if vertical_start else None,
                    'end': list(vertical_end) if vertical_end else None,
                },
                'horizontal': {
                    'start': list(horizontal_start) if horizontal_start else None,
                    'end': list(horizontal_end) if horizontal_end else None,
                }
            }
        }
    
    def world_to_image_point(
        self,
        world_point: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """실세계 좌표를 이미지 좌표로 변환"""
        return self.homography.world_to_image(world_point)
    
    def image_to_world_point(
        self,
        image_point: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """이미지 좌표를 실세계 좌표로 변환"""
        return self.homography.image_to_world(image_point)