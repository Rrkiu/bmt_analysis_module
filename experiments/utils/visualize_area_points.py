#!/usr/bin/env python3
"""
JSON 파일에서 이미지 경로와 area 좌표를 읽어서
4점을 표시한 이미지를 생성하는 스크립트
"""

import json
import cv2
import numpy as np
import os
import argparse
from pathlib import Path


def load_json_config(json_path):
    """JSON 설정 파일 로드"""
    with open(json_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


def draw_area_points(image, points, color=(0, 255, 0), radius=10, thickness=3):
    """
    이미지에 4개의 점을 표시
    
    Args:
        image: 원본 이미지
        points: 4개의 좌표 리스트 [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
        color: 점의 색상 (BGR)
        radius: 점의 반지름
        thickness: 선의 두께
    
    Returns:
        점이 그려진 이미지
    """
    result_img = image.copy()
    
    # 4개의 점을 각각 다른 색상으로 표시
    colors = [
        (0, 0, 255),    # 빨강 - Point 1
        (0, 255, 0),    # 초록 - Point 2
        (255, 0, 0),    # 파랑 - Point 3
        (0, 255, 255)   # 노랑 - Point 4
    ]
    
    # 점 그리기
    for idx, (point, point_color) in enumerate(zip(points, colors)):
        x, y = int(point[0]), int(point[1])
        
        # 원으로 점 표시
        cv2.circle(result_img, (x, y), radius, point_color, thickness)
        
        # 점 번호 텍스트 추가
        cv2.putText(
            result_img, 
            f"P{idx+1}", 
            (x + 15, y - 15), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            1.5, 
            point_color, 
            3
        )
    
    # 점들을 연결하는 선 그리기 (폴리곤)
    pts = np.array(points, dtype=np.int32)
    cv2.polylines(result_img, [pts], isClosed=True, color=(255, 255, 0), thickness=2)
    
    return result_img


def process_test_case(test_case, output_dir):
    """
    개별 테스트 케이스 처리
    
    Args:
        test_case: 테스트 케이스 딕셔너리
        output_dir: 출력 디렉토리
    
    Returns:
        처리 성공 여부
    """
    name = test_case.get('name', 'unknown')
    image_path = test_case.get('image_path')
    area = test_case.get('area')
    description = test_case.get('description', '')
    
    # 이미지 경로 확인
    if not os.path.exists(image_path):
        print(f"❌ 이미지 파일을 찾을 수 없습니다: {image_path}")
        return False
    
    # area 좌표 확인
    if not area or len(area) != 4:
        print(f"❌ area에 4개의 점이 필요합니다. 현재: {len(area) if area else 0}개")
        return False
    
    # 이미지 로드
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ 이미지를 읽을 수 없습니다: {image_path}")
        return False
    
    print(f"\n📷 처리 중: {name}")
    print(f"   설명: {description}")
    print(f"   이미지 크기: {image.shape[1]}x{image.shape[0]}")
    print(f"   Area 좌표:")
    for idx, point in enumerate(area):
        print(f"      Point {idx+1}: ({point[0]}, {point[1]})")
    
    # 점 그리기
    result_img = draw_area_points(image, area)
    
    # 출력 파일명 생성
    output_filename = f"{name}_area_points.jpg"
    output_path = os.path.join(output_dir, output_filename)
    
    # 이미지 저장
    cv2.imwrite(output_path, result_img)
    print(f"✅ 저장 완료: {output_path}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='JSON 파일에서 이미지 경로와 area 좌표를 읽어 4점을 표시한 이미지 생성'
    )
    parser.add_argument(
        'json_path',
        type=str,
        help='JSON 설정 파일 경로'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='출력 디렉토리 (기본값: JSON 파일과 동일한 디렉토리의 output 폴더)'
    )
    
    args = parser.parse_args()
    
    # JSON 파일 경로 확인
    json_path = args.json_path
    if not os.path.exists(json_path):
        print(f"❌ JSON 파일을 찾을 수 없습니다: {json_path}")
        return
    
    # 출력 디렉토리 설정
    if args.output:
        output_dir = args.output
    else:
        json_dir = os.path.dirname(os.path.abspath(json_path))
        output_dir = os.path.join(json_dir, 'output_area_points')
    
    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    print(f"📁 출력 디렉토리: {output_dir}")
    
    # JSON 파일 로드
    try:
        config = load_json_config(json_path)
    except Exception as e:
        print(f"❌ JSON 파일 로드 실패: {e}")
        return
    
    # test_cases 처리
    test_cases = config.get('test_cases', [])
    if not test_cases:
        print("❌ JSON 파일에 test_cases가 없습니다.")
        return
    
    print(f"\n총 {len(test_cases)}개의 테스트 케이스를 처리합니다.\n")
    print("=" * 60)
    
    # 각 테스트 케이스 처리
    success_count = 0
    for idx, test_case in enumerate(test_cases, 1):
        print(f"\n[{idx}/{len(test_cases)}]")
        if process_test_case(test_case, output_dir):
            success_count += 1
    
    # 결과 요약
    print("\n" + "=" * 60)
    print(f"\n✨ 처리 완료: {success_count}/{len(test_cases)} 성공")
    print(f"📁 결과 저장 위치: {output_dir}")


if __name__ == "__main__":
    main()
