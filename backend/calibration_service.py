"""
캘리브레이션 서비스
T자 기준점 기반 코트 영역 생성
"""

import numpy as np
from typing import Dict, Tuple, List, Optional
from constants import CourtDimensions, COURT_TEMPLATE, T_GUIDE
from geometry import HomographyTransform, CourtGeometry


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
        T자 기준점으로부터 코트 캘리브레이션 수행
        
        Args:
            t_point_image: 이미지 상의 T자 기준점 (x, y) 픽셀 좌표
            image_shape: (height, width) 이미지 크기
            rotation_angle: 회전 각도 (도, 현재는 미사용)
            
        Returns:
            dict: 캘리브레이션 결과
                - court_corners_image: 이미지 좌표계의 코트 4개 코너
                - court_corners_world: 실세계 좌표계의 코트 4개 코너
                - t_point_world: 실세계 좌표계의 T자 점
                - homography_matrix: 변환 행렬
                - success: 성공 여부
        """
        
        # 1. 실세계 코트 템플릿 가져오기
        user_court = self.court_template['user_court']
        
        # 2. 실세계 좌표계의 주요 포인트들
        # T자 기준점 (실세계)
        t_point_world = self.court_template['t_reference']
        
        # 코트 4개 코너 (실세계) - 시계방향
        court_corners_world = [
            user_court['top_left'],
            user_court['top_right'],
            user_court['bottom_right'],
            user_court['bottom_left']
        ]
        
        # 3. 픽셀 스케일 추정
        # 이미지 크기로부터 적절한 스케일 계산
        image_height, image_width = image_shape
        
        # 코트가 이미지의 약 60-80%를 차지한다고 가정
        estimated_court_height_pixels = image_height * 0.7
        actual_court_length = CourtDimensions.BACK_BOUNDARY_LINE  # 6.7m
        pixels_per_meter = estimated_court_height_pixels / actual_court_length
        
        # 4. T자 기준점을 기준으로 코트 코너들의 이미지 좌표 계산
        # T자 점 = (0, SHORT_SERVICE_LINE) in world coords
        # 각 코트 코너와 T자 점의 실세계 오프셋을 계산하고
        # 픽셀로 변환하여 이미지 좌표 생성
        
        t_x_img, t_y_img = t_point_image
        
        court_corners_image = []
        for world_corner in court_corners_world:
            # 실세계에서 T자 점으로부터의 오프셋
            offset_x_world = world_corner[0] - t_point_world['x']
            offset_y_world = world_corner[1] - t_point_world['y']
            
            # 픽셀로 변환
            offset_x_pixels = offset_x_world * pixels_per_meter
            offset_y_pixels = offset_y_world * pixels_per_meter
            
            # 이미지 좌표 계산
            corner_x_img = t_x_img + offset_x_pixels
            corner_y_img = t_y_img + offset_y_pixels
            
            court_corners_image.append([corner_x_img, corner_y_img])
        
        # 5. Homography 계산
        src_points = np.array(court_corners_image, dtype=np.float32)
        dst_points = np.array(court_corners_world, dtype=np.float32)
        
        success = self.homography.compute_homography(src_points, dst_points)
        
        if not success:
            return {
                'success': False,
                'error': 'Homography 계산 실패'
            }
        
        # 6. 결과 반환
        return {
            'success': True,
            'court_corners_image': court_corners_image,
            'court_corners_world': court_corners_world,
            't_point_image': list(t_point_image),
            't_point_world': t_point_world,
            'homography_matrix': self.homography.homography_matrix.tolist(),
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