#!/usr/bin/env python3
"""
비디오 분석 테스트 스크립트

실제 비디오 파일로 분석 기능을 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from video_analysis_service import VideoAnalysisService
import numpy as np

def test_video_analysis(video_path: str, mode: str = 'debug'):
    """
    비디오 분석 테스트
    
    Args:
        video_path: 비디오 파일 경로
        mode: 'normal' | 'debug'
    """
    print("=" * 70)
    print("비디오 분석 테스트")
    print("=" * 70)
    print(f"입력: {video_path}")
    print(f"모드: {mode}")
    print()
    
    # 테스트용 캘리브레이션 데이터
    calibration_data = {
        'corners_image': [
            [320, 216],   # TL
            [960, 216],   # TR
            [960, 504],   # BR
            [320, 504]    # BL
        ],
        'homography_matrix': [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ]
    }
    
    # 서비스 초기화
    service = VideoAnalysisService(calibration_data)
    
    # 출력 경로
    output_dir = "storage/results"
    os.makedirs(output_dir, exist_ok=True)
    
    output_filename = f"analyzed_{mode}_{os.path.basename(video_path)}"
    output_path = os.path.join(output_dir, output_filename)
    
    # 처리
    result = service.process_video_file(
        video_path=video_path,
        mode=mode,
        output_path=output_path,
        max_frames=300  # 최대 300 프레임 (10초 @ 30fps)
    )
    
    print("\n" + "=" * 70)
    print("처리 완료!")
    print("=" * 70)
    print(f"출력 파일: {output_path}")
    print(f"처리 프레임: {result['frames_processed']}")
    print(f"처리 시간: {result['elapsed_time']:.2f}초")
    print(f"평균 FPS: {result['avg_fps']:.2f}")
    print()
    print("📹 비디오 플레이어로 결과를 확인하세요:")
    print(f"   vlc {output_path}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='비디오 분석 테스트')
    parser.add_argument('video_path', help='비디오 파일 경로')
    parser.add_argument('--mode', default='debug', choices=['normal', 'debug'],
                       help='표시 모드 (default: debug)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.video_path):
        print(f"❌ 비디오 파일을 찾을 수 없습니다: {args.video_path}")
        sys.exit(1)
    
    test_video_analysis(args.video_path, args.mode)