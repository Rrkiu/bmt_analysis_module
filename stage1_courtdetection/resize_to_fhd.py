#!/usr/bin/env python3
"""
JSON 파일에서 이미지를 읽어 FHD(1920x1080) 해상도로 리사이즈하고,
area 좌표도 비례하여 조정한 후 새로운 JSON 파일을 생성하는 스크립트
"""

import json
import cv2
import numpy as np
import os
import argparse
from pathlib import Path


# FHD 해상도 상수
FHD_WIDTH = 1920
FHD_HEIGHT = 1080


def load_json_config(json_path):
    """JSON 설정 파일 로드"""
    with open(json_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


def save_json_config(config, output_path):
    """JSON 설정 파일 저장"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def resize_image_to_fhd(image):
    """
    이미지를 FHD 해상도로 리사이즈
    aspect ratio를 유지하면서 FHD에 맞춤
    
    Args:
        image: 원본 이미지
    
    Returns:
        resized_image: 리사이즈된 이미지
        scale_x: x축 스케일 비율
        scale_y: y축 스케일 비율
    """
    original_height, original_width = image.shape[:2]
    
    # 스케일 비율 계산
    scale_x = FHD_WIDTH / original_width
    scale_y = FHD_HEIGHT / original_height
    
    # FHD 해상도로 리사이즈
    resized_image = cv2.resize(image, (FHD_WIDTH, FHD_HEIGHT), interpolation=cv2.INTER_AREA)
    
    return resized_image, scale_x, scale_y


def resize_area_points(area, scale_x, scale_y):
    """
    area 좌표를 스케일 비율에 따라 조정
    
    Args:
        area: 원본 area 좌표 리스트 [[x1, y1], [x2, y2], ...]
        scale_x: x축 스케일 비율
        scale_y: y축 스케일 비율
    
    Returns:
        resized_area: 조정된 area 좌표 리스트
    """
    resized_area = []
    for point in area:
        x, y = point
        new_x = int(round(x * scale_x))
        new_y = int(round(y * scale_y))
        resized_area.append([new_x, new_y])
    
    return resized_area


def process_test_case(test_case, output_image_dir, base_output_dir):
    """
    개별 테스트 케이스 처리
    
    Args:
        test_case: 테스트 케이스 딕셔너리
        output_image_dir: 리사이즈된 이미지 저장 디렉토리
        base_output_dir: 출력 기본 디렉토리
    
    Returns:
        updated_test_case: 업데이트된 테스트 케이스 딕셔너리 (성공 시)
        None: 실패 시
    """
    name = test_case.get('name', 'unknown')
    image_path = test_case.get('image_path')
    area = test_case.get('area')
    description = test_case.get('description', '')
    
    # 이미지 경로 확인
    if not os.path.exists(image_path):
        print(f"❌ 이미지 파일을 찾을 수 없습니다: {image_path}")
        return None
    
    # area 좌표 확인
    if not area or len(area) != 4:
        print(f"❌ area에 4개의 점이 필요합니다. 현재: {len(area) if area else 0}개")
        return None
    
    # 이미지 로드
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ 이미지를 읽을 수 없습니다: {image_path}")
        return None
    
    original_height, original_width = image.shape[:2]
    
    print(f"\n📷 처리 중: {name}")
    print(f"   설명: {description}")
    print(f"   원본 이미지 크기: {original_width}x{original_height}")
    print(f"   원본 Area 좌표:")
    for idx, point in enumerate(area):
        print(f"      Point {idx+1}: ({point[0]}, {point[1]})")
    
    # FHD로 리사이즈
    resized_image, scale_x, scale_y = resize_image_to_fhd(image)
    
    print(f"   리사이즈 후 크기: {FHD_WIDTH}x{FHD_HEIGHT}")
    print(f"   스케일 비율: x={scale_x:.4f}, y={scale_y:.4f}")
    
    # area 좌표 조정
    resized_area = resize_area_points(area, scale_x, scale_y)
    
    print(f"   리사이즈된 Area 좌표:")
    for idx, point in enumerate(resized_area):
        print(f"      Point {idx+1}: ({point[0]}, {point[1]})")
    
    # 리사이즈된 이미지 저장
    output_image_filename = f"{name}_fhd.jpg"
    output_image_path = os.path.join(output_image_dir, output_image_filename)
    cv2.imwrite(output_image_path, resized_image)
    print(f"✅ 이미지 저장 완료: {output_image_path}")
    
    # 업데이트된 테스트 케이스 생성
    updated_test_case = test_case.copy()
    updated_test_case['image_path'] = output_image_path
    updated_test_case['area'] = resized_area
    updated_test_case['original_size'] = [original_width, original_height]
    updated_test_case['resized_size'] = [FHD_WIDTH, FHD_HEIGHT]
    updated_test_case['scale_ratio'] = [scale_x, scale_y]
    
    # description 업데이트
    if description:
        updated_test_case['description'] = f"{description} (FHD 리사이즈)"
    else:
        updated_test_case['description'] = "FHD 리사이즈"
    
    return updated_test_case


def main():
    parser = argparse.ArgumentParser(
        description='JSON 파일에서 이미지를 FHD로 리사이즈하고 area 좌표를 조정하여 새 JSON 생성'
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
        help='출력 디렉토리 (기본값: JSON 파일과 동일한 디렉토리의 output_fhd 폴더)'
    )
    parser.add_argument(
        '--output-json',
        type=str,
        default=None,
        help='출력 JSON 파일명 (기본값: 원본파일명_fhd.json)'
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
        output_dir = os.path.join(json_dir, 'output_fhd')
    
    # 이미지 출력 디렉토리
    output_image_dir = os.path.join(output_dir, 'images')
    
    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(output_image_dir, exist_ok=True)
    
    print(f"📁 출력 디렉토리: {output_dir}")
    print(f"📁 이미지 저장 디렉토리: {output_image_dir}")
    
    # 출력 JSON 파일명 설정
    if args.output_json:
        output_json_filename = args.output_json
    else:
        json_basename = os.path.basename(json_path)
        json_name, json_ext = os.path.splitext(json_basename)
        output_json_filename = f"{json_name}_fhd{json_ext}"
    
    output_json_path = os.path.join(output_dir, output_json_filename)
    
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
    
    print(f"\n총 {len(test_cases)}개의 테스트 케이스를 처리합니다.")
    print(f"목표 해상도: {FHD_WIDTH}x{FHD_HEIGHT} (FHD)")
    print("=" * 60)
    
    # 각 테스트 케이스 처리
    updated_test_cases = []
    success_count = 0
    
    for idx, test_case in enumerate(test_cases, 1):
        print(f"\n[{idx}/{len(test_cases)}]")
        updated_case = process_test_case(test_case, output_image_dir, output_dir)
        if updated_case:
            updated_test_cases.append(updated_case)
            success_count += 1
    
    # 새로운 JSON 설정 생성
    if updated_test_cases:
        new_config = config.copy()
        new_config['test_cases'] = updated_test_cases
        new_config['resolution'] = {
            'width': FHD_WIDTH,
            'height': FHD_HEIGHT,
            'name': 'FHD'
        }
        
        # JSON 파일 저장
        save_json_config(new_config, output_json_path)
        print("\n" + "=" * 60)
        print(f"✅ 새로운 JSON 파일 저장 완료: {output_json_path}")
    
    # 결과 요약
    print("\n" + "=" * 60)
    print(f"\n✨ 처리 완료: {success_count}/{len(test_cases)} 성공")
    print(f"📁 결과 저장 위치: {output_dir}")
    print(f"📄 JSON 파일: {output_json_path}")
    print(f"🖼️  이미지 파일: {output_image_dir}")


if __name__ == "__main__":
    main()
