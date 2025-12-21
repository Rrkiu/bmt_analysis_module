"""
캘리브레이션 시스템 테스트 스크립트
"""

import sys
import os

# 현재 스크립트의 상위 디렉토리(backend)를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import cv2
import numpy as np
from calibration_service import CalibrationService
from visualization_service import VisualizationService
from constants import CourtDimensions

def create_synthetic_court_image():
    """
    테스트용 합성 코트 이미지 생성
    """
    # 이미지 크기
    width, height = 1280, 720
    image = np.ones((height, width, 3), dtype=np.uint8) * 50  # 어두운 배경
    
    # 그린 코트 그리기
    court_color = (34, 139, 34)  # 그린
    cv2.rectangle(image, (100, 50), (1180, 670), court_color, -1)
    
    # 코트 라인 (흰색)
    line_color = (255, 255, 255)
    line_thickness = 3
    
    # 단식 코트 (5.18m × 13.4m) 비율로 그리기
    # 픽셀 스케일: 약 100 pixels/meter
    pixels_per_meter = 80
    
    court_width = int(5.18 * pixels_per_meter)
    court_length = int(6.7 * pixels_per_meter)  # 반쪽 코트
    
    # 코트 중심
    center_x = width // 2
    center_y = height // 2
    
    # 네트 (가로선, 최상단)
    net_y = center_y - court_length
    cv2.line(image, 
             (center_x - court_width // 2, net_y),
             (center_x + court_width // 2, net_y),
             line_color, line_thickness)
    
    # 숏 서비스 라인
    short_service_y = net_y + int(1.98 * pixels_per_meter)
    cv2.line(image,
             (center_x - court_width // 2, short_service_y),
             (center_x + court_width // 2, short_service_y),
             line_color, line_thickness)
    
    # 베이스라인 (최하단)
    baseline_y = center_y + court_length
    cv2.line(image,
             (center_x - court_width // 2, baseline_y),
             (center_x + court_width // 2, baseline_y),
             line_color, line_thickness)
    
    # 사이드라인 (양쪽)
    cv2.line(image,
             (center_x - court_width // 2, net_y),
             (center_x - court_width // 2, baseline_y),
             line_color, line_thickness)
    
    cv2.line(image,
             (center_x + court_width // 2, net_y),
             (center_x + court_width // 2, baseline_y),
             line_color, line_thickness)
    
    # 센터라인
    cv2.line(image,
             (center_x, net_y),
             (center_x, short_service_y),
             line_color, line_thickness)
    
    # T자 기준점 위치 (테스트용 마커)
    t_point = (center_x, short_service_y)
    
    return image, t_point


def test_calibration():
    """캘리브레이션 테스트"""
    print("=" * 60)
    print("배드민턴 코트 캘리브레이션 시스템 테스트")
    print("=" * 60)
    
    # 1. 합성 이미지 생성
    print("\n[1] 합성 코트 이미지 생성...")
    image, true_t_point = create_synthetic_court_image()
    print(f"   ✓ 이미지 크기: {image.shape[1]}x{image.shape[0]}")
    print(f"   ✓ 실제 T자 위치: {true_t_point}")
    
    # 이미지 저장
    cv2.imwrite('storage/test_synthetic_court.jpg', image)
    print("   ✓ 저장: storage/test_synthetic_court.jpg")
    
    # 2. 캘리브레이션 서비스 초기화
    print("\n[2] 캘리브레이션 서비스 초기화...")
    service = CalibrationService()
    print("   ✓ 서비스 준비 완료")
    
    # 3. T자 기준점으로 캘리브레이션
    print("\n[3] 캘리브레이션 수행...")
    image_shape = (image.shape[0], image.shape[1])
    
    result = service.calibrate_from_t_point(
        t_point_image=true_t_point,
        image_shape=image_shape
    )
    
    if result['success']:
        print("   ✓ 캘리브레이션 성공!")
        print(f"   - 픽셀/미터: {result['pixels_per_meter']:.2f}")
        print(f"   - T자 점 (이미지): {result['t_point_image']}")
        print(f"   - T자 점 (실세계): {result['t_point_world']}")
        print(f"   - 코트 코너 수: {len(result['court_corners_image'])}")
    else:
        print(f"   ✗ 실패: {result.get('error')}")
        return
    
    # 4. 코트 영역 생성
    print("\n[4] 코트 영역 생성...")
    court_region = service.generate_court_region(result)
    
    if court_region['success']:
        region = court_region['court_region']
        print("   ✓ 코트 영역 생성 완료")
        print(f"   - 면적: {region['area_pixels']:.0f} pixels²")
        print(f"   - 유효성: {region['is_valid']}")
        print(f"   - 메시지: {region['validation_message']}")
    else:
        print(f"   ✗ 실패: {court_region.get('error')}")
        return
    
    # 5. T자 가이드 좌표
    print("\n[5] T자 가이드 좌표 계산...")
    t_guide = service.get_t_guide_image_coords(result)
    
    if t_guide['success']:
        print("   ✓ T자 가이드 좌표 계산 완료")
    
    # 6. 시각화
    print("\n[6] 결과 시각화...")
    vis_service = VisualizationService()
    
    # 전체 시각화
    result_image = vis_service.draw_complete_visualization(
        image=image,
        calibration_result=result,
        t_guide_coords=t_guide,
        show_t_guide=True,
        show_court_region=True
    )
    
    # 저장
    cv2.imwrite('storage/test_result.jpg', result_image)
    print("   ✓ 저장: storage/test_result.jpg")
    
    # 7. 좌표 변환 테스트
    print("\n[7] 좌표 변환 테스트...")
    
    # 이미지 좌표 → 실세계 좌표
    test_point_img = true_t_point
    test_point_world = service.image_to_world_point(test_point_img)
    
    if test_point_world:
        print(f"   - 이미지: {test_point_img}")
        print(f"   - 실세계: ({test_point_world[0]:.3f}, {test_point_world[1]:.3f}) m")
        print(f"   - 예상: (0.000, 1.980) m")
        
        # 오차 계산
        error_x = abs(test_point_world[0] - 0.0)
        error_y = abs(test_point_world[1] - CourtDimensions.SHORT_SERVICE_LINE)
        print(f"   - 오차: x={error_x:.3f}m, y={error_y:.3f}m")
    
    # 실세계 좌표 → 이미지 좌표
    world_corner = result['court_corners_world'][0]  # 첫 번째 코너
    image_corner = service.world_to_image_point(tuple(world_corner))
    
    if image_corner:
        print(f"\n   - 실세계 코너: {world_corner}")
        print(f"   - 이미지 변환: ({image_corner[0]:.1f}, {image_corner[1]:.1f})")
        print(f"   - 원본: {result['court_corners_image'][0]}")
    
    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)
    print("\n결과 파일:")
    print("  - storage/test_synthetic_court.jpg (입력)")
    print("  - storage/test_result.jpg (출력)")


if __name__ == "__main__":
    test_calibration()