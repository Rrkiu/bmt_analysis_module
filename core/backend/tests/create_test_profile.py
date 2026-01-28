#!/usr/bin/env python3
"""
테스트 프로파일 생성 스크립트
실제 이미지 없이 프로파일을 생성하여 UI 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from calibration_profile_service import CalibrationProfileService
import numpy as np
import cv2

def create_test_image():
    """테스트용 합성 이미지 생성"""
    # 1280x720 빈 이미지 (회색 배경)
    image = np.ones((720, 1280, 3), dtype=np.uint8) * 200
    
    # 코트 영역 그리기
    corners = np.array([
        [320, 216],   # TL
        [960, 216],   # TR
        [960, 504],   # BR
        [320, 504]    # BL
    ], dtype=np.int32)
    
    # 녹색 코트 영역
    cv2.fillPoly(image, [corners], (100, 200, 100))
    
    # 흰색 라인
    cv2.polylines(image, [corners], True, (255, 255, 255), 3)
    
    # 중앙선
    cv2.line(image, (640, 216), (640, 504), (255, 255, 255), 2)
    
    # 텍스트
    cv2.putText(image, "Test Court", (500, 360), 
                cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
    
    return image

def create_test_profiles():
    """테스트 프로파일 3개 생성"""
    
    print("=" * 60)
    print("테스트 프로파일 생성 시작")
    print("=" * 60)
    
    service = CalibrationProfileService()
    
    # 테스트 이미지 생성
    test_image = create_test_image()
    
    # Homography 행렬 (예시)
    homography = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0]
    ], dtype=np.float32)
    
    # 프로파일 1: A코트 카메라1
    print("\n1️⃣  A코트 카메라1 생성 중...")
    result1 = service.save_profile(
        profile_id="test_court_a_cam1",
        profile_name="A코트 카메라1",
        corners_image=[
            [320, 216],
            [960, 216],
            [960, 504],
            [320, 504]
        ],
        corners_world=[
            [-2.59, 1.98],
            [2.59, 1.98],
            [2.59, 6.7],
            [-2.59, 6.7]
        ],
        homography=homography,
        pixels_per_meter=75.2,
        image_width=1280,
        image_height=720,
        reference_image=test_image,
        metadata={
            "court_name": "A코트",
            "venue": "테스트 체육관",
            "notes": "테스트용 프로파일입니다"
        }
    )
    print(f"   ✅ 생성 완료: {result1['profile_id']}")
    
    # 프로파일 2: B코트 카메라1
    print("\n2️⃣  B코트 카메라1 생성 중...")
    result2 = service.save_profile(
        profile_id="test_court_b_cam1",
        profile_name="B코트 카메라1",
        corners_image=[
            [300, 200],
            [980, 200],
            [980, 520],
            [300, 520]
        ],
        corners_world=[
            [-2.59, 1.98],
            [2.59, 1.98],
            [2.59, 6.7],
            [-2.59, 6.7]
        ],
        homography=homography,
        pixels_per_meter=78.5,
        image_width=1280,
        image_height=720,
        reference_image=test_image,
        metadata={
            "court_name": "B코트",
            "venue": "테스트 체육관",
            "notes": "두 번째 테스트 프로파일"
        }
    )
    print(f"   ✅ 생성 완료: {result2['profile_id']}")
    
    # 프로파일 3: 실외 코트
    print("\n3️⃣  실외 코트 생성 중...")
    result3 = service.save_profile(
        profile_id="test_outdoor_court",
        profile_name="실외 코트",
        corners_image=[
            [280, 180],
            [1000, 180],
            [1000, 540],
            [280, 540]
        ],
        corners_world=[
            [-2.59, 1.98],
            [2.59, 1.98],
            [2.59, 6.7],
            [-2.59, 6.7]
        ],
        homography=homography,
        pixels_per_meter=72.0,
        image_width=1280,
        image_height=720,
        reference_image=test_image,
        metadata={
            "court_name": "야외 코트",
            "venue": "공원",
            "notes": "실외 테스트용"
        }
    )
    print(f"   ✅ 생성 완료: {result3['profile_id']}")
    
    # 검증
    print("\n" + "=" * 60)
    print("프로파일 목록 확인")
    print("=" * 60)
    
    profiles = service.list_profiles()
    print(f"\n총 {len(profiles)}개 프로파일:")
    for i, p in enumerate(profiles, 1):
        print(f"{i}. {p['profile_name']} (ID: {p['profile_id']})")
        print(f"   - 코트: {p['metadata'].get('court_name', 'N/A')}")
        print(f"   - 장소: {p['metadata'].get('venue', 'N/A')}")
        print(f"   - 생성: {p['created_at']}")
        print()
    
    print("✅ 테스트 프로파일 생성 완료!")
    print("\n📋 다음 단계:")
    print("   1. 백엔드 서버 실행: python main.py")
    print("   2. 프론트엔드 실행: python3 -m http.server 8080")
    print("   3. 브라우저에서 확인: http://localhost:8080/profile-manager.html")

if __name__ == '__main__':
    create_test_profiles()