"""
실제 이미지를 사용한 캘리브레이션 테스트
"""

import cv2
import numpy as np
import sys
import os
from calibration_service import CalibrationService
from visualization_service import VisualizationService

# 현재 스크립트의 상위 디렉토리(backend)를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

def test_with_real_image(image_path, t_point_x, t_point_y):
    """
    실제 이미지로 캘리브레이션 테스트
    
    Args:
        image_path: 이미지 파일 경로
        t_point_x: T자 기준점 x 좌표 (픽셀)
        t_point_y: T자 기준점 y 좌표 (픽셀)
    """
    print("=" * 60)
    print("실제 이미지 캘리브레이션 테스트")
    print("=" * 60)
    
    # 1. 이미지 로드
    print(f"\n[1] 이미지 로드: {image_path}")
    
    if not os.path.exists(image_path):
        print(f"   ✗ 오류: 파일을 찾을 수 없습니다")
        return
    
    image = cv2.imread(image_path)
    if image is None:
        print(f"   ✗ 오류: 이미지를 읽을 수 없습니다")
        return
    
    height, width = image.shape[:2]
    print(f"   ✓ 이미지 크기: {width}x{height}")
    
    # 2. T자 기준점 확인
    print(f"\n[2] T자 기준점: ({t_point_x}, {t_point_y})")
    
    # T자 위치가 이미지 범위 내인지 확인
    if t_point_x < 0 or t_point_x >= width or t_point_y < 0 or t_point_y >= height:
        print(f"   ✗ 오류: T자 기준점이 이미지 범위를 벗어났습니다")
        return
    
    # 원본 이미지에 T자 위치 표시하여 저장
    preview = image.copy()
    cv2.circle(preview, (int(t_point_x), int(t_point_y)), 20, (0, 0, 255), -1)
    cv2.circle(preview, (int(t_point_x), int(t_point_y)), 25, (255, 255, 255), 3)
    cv2.putText(preview, "T-point", 
               (int(t_point_x) + 30, int(t_point_y)), 
               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
    cv2.imwrite('storage/test_preview.jpg', preview)
    print("   ✓ T자 미리보기 저장: storage/test_preview.jpg")
    
    # 3. 캘리브레이션 수행
    print("\n[3] 캘리브레이션 수행...")
    service = CalibrationService()
    
    result = service.calibrate_from_t_point(
        t_point_image=(t_point_x, t_point_y),
        image_shape=(height, width)
    )
    
    if not result['success']:
        print(f"   ✗ 실패: {result.get('error')}")
        return
    
    print("   ✓ 캘리브레이션 성공!")
    print(f"   - 픽셀/미터: {result['pixels_per_meter']:.2f}")
    print(f"   - T자 점 (이미지): {result['t_point_image']}")
    
    # 코너 출력
    print("\n   코트 4개 코너 (이미지 좌표):")
    for i, corner in enumerate(result['court_corners_image']):
        print(f"     {i+1}. ({corner[0]:.1f}, {corner[1]:.1f})")
    
    # 4. 코트 영역 생성
    print("\n[4] 코트 영역 생성...")
    court_region = service.generate_court_region(result)
    
    if court_region['success']:
        region = court_region['court_region']
        print("   ✓ 코트 영역 생성 완료")
        print(f"   - 면적: {region['area_pixels']:.0f} pixels²")
        print(f"   - 유효성: {region['is_valid']}")
        print(f"   - 메시지: {region['validation_message']}")
    
    # 5. T자 가이드 좌표
    print("\n[5] T자 가이드 좌표 계산...")
    t_guide = service.get_t_guide_image_coords(result)
    
    # 6. 시각화
    print("\n[6] 결과 시각화...")
    vis_service = VisualizationService()
    
    result_image = vis_service.draw_complete_visualization(
        image=image,
        calibration_result=result,
        t_guide_coords=t_guide,
        show_t_guide=True,
        show_court_region=True
    )
    
    cv2.imwrite('storage/test_result.jpg', result_image)
    print("   ✓ 저장: storage/test_result.jpg")
    
    # 7. 좌표 변환 예시
    print("\n[7] 좌표 변환 예시...")
    
    # 이미지의 몇 가지 포인트를 실세계 좌표로 변환
    test_points = [
        ("T자 기준점", (t_point_x, t_point_y)),
        ("좌상단 코너", tuple(result['court_corners_image'][0])),
        ("우하단 코너", tuple(result['court_corners_image'][2])),
    ]
    
    for name, img_pt in test_points:
        world_pt = service.image_to_world_point(img_pt)
        if world_pt:
            print(f"   {name}:")
            print(f"     - 이미지: ({img_pt[0]:.1f}, {img_pt[1]:.1f})")
            print(f"     - 실세계: ({world_pt[0]:.3f}m, {world_pt[1]:.3f}m)")
    
    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)
    print("\n생성된 파일:")
    print("  - storage/test_preview.jpg (T자 위치 미리보기)")
    print("  - storage/test_result.jpg (최종 결과)")


def interactive_test():
    """
    대화형 모드로 테스트
    """
    print("=" * 60)
    print("배드민턴 코트 캘리브레이션 - 대화형 테스트")
    print("=" * 60)
    
    # 이미지 경로 입력
    image_path = input("\n이미지 파일 경로를 입력하세요: ").strip()
    
    if not os.path.exists(image_path):
        print(f"오류: 파일을 찾을 수 없습니다 - {image_path}")
        return
    
    # 이미지 정보 표시
    image = cv2.imread(image_path)
    if image is None:
        print("오류: 이미지를 읽을 수 없습니다")
        return
    
    height, width = image.shape[:2]
    print(f"\n이미지 크기: {width} x {height}")
    print(f"이미지 중심: ({width//2}, {height//2})")
    
    # T자 기준점 입력
    print("\nT자 기준점 좌표를 입력하세요")
    print("(센터라인과 숏 서비스 라인이 만나는 점)")
    
    try:
        t_x = float(input("  X 좌표: ").strip())
        t_y = float(input("  Y 좌표: ").strip())
    except ValueError:
        print("오류: 숫자를 입력해주세요")
        return
    
    # 테스트 실행
    test_with_real_image(image_path, t_x, t_y)


def auto_find_t_point(image_path):
    """
    이미지에서 T자 기준점을 자동으로 찾기 (간단한 휴리스틱)
    
    Args:
        image_path: 이미지 경로
        
    Returns:
        (t_x, t_y) 또는 None
    """
    image = cv2.imread(image_path)
    if image is None:
        return None
    
    height, width = image.shape[:2]
    
    # 간단한 추정: 이미지 중앙 약간 위
    # (실제로는 라인 검출 알고리즘 필요)
    t_x = width // 2
    t_y = int(height * 0.4)
    
    return t_x, t_y


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 1:
        # 인자 없음 -> 대화형 모드
        interactive_test()
    
    elif len(sys.argv) == 2:
        # 이미지 경로만 -> 자동으로 T자 위치 추정
        image_path = sys.argv[1]
        t_point = auto_find_t_point(image_path)
        
        if t_point:
            print(f"T자 기준점 자동 추정: ({t_point[0]}, {t_point[1]})")
            print("(실제 위치가 다르면 좌표를 직접 지정하세요)\n")
            test_with_real_image(image_path, t_point[0], t_point[1])
        else:
            print("오류: 이미지를 로드할 수 없습니다")
    
    elif len(sys.argv) == 4:
        # 이미지 경로 + T자 좌표
        image_path = sys.argv[1]
        t_x = float(sys.argv[2])
        t_y = float(sys.argv[3])
        
        test_with_real_image(image_path, t_x, t_y)
    
    else:
        print("사용법:")
        print("  1. 대화형 모드:")
        print("     python test_real_image.py")
        print()
        print("  2. 이미지만 지정 (T자 위치 자동 추정):")
        print("     python test_real_image.py <이미지_경로>")
        print()
        print("  3. 이미지 + T자 좌표 직접 지정:")
        print("     python test_real_image.py <이미지_경로> <t_x> <t_y>")
        print()
        print("예시:")
        print("  python test_real_image.py court.jpg")
        print("  python test_real_image.py court.jpg 640 288")