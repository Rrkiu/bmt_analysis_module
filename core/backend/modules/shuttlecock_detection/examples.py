"""
Shuttlecock Detection - Quick Start Example

셔틀콕 검출 모듈의 기본 사용법을 보여주는 예시 스크립트입니다.
"""

import cv2
import numpy as np
from pathlib import Path

# 모듈 import
from shuttlecock_detection import create_detector
from shuttlecock_detection.utils import draw_detections
from shuttlecock_detection.config import DetectionConfig


def example_basic_detection():
    """기본 검출 예시"""
    print("=" * 60)
    print("Example 1: Basic Detection")
    print("=" * 60)
    
    # 1. 검출기 생성
    detector = create_detector(
        model_type='yolo',
        model_path='weights/best.pt',  # 실제 모델 경로로 변경
        conf_threshold=0.5,
        device='cuda'  # 또는 'cpu'
    )
    
    # 2. 이미지 로드
    frame = cv2.imread('test_image.jpg')
    
    # 3. 검출 수행
    detections = detector.detect(frame)
    
    # 4. 결과 출력
    print(f"검출된 셔틀콕 개수: {len(detections)}")
    for i, det in enumerate(detections):
        print(f"  [{i}] 위치: ({det.x:.1f}, {det.y:.1f}), 신뢰도: {det.confidence:.3f}")
    
    # 5. 시각화
    vis_frame = draw_detections(frame, detections)
    cv2.imwrite('result_basic.jpg', vis_frame)
    print("✓ 결과 저장: result_basic.jpg\n")


def example_video_detection():
    """비디오 검출 예시"""
    print("=" * 60)
    print("Example 2: Video Detection")
    print("=" * 60)
    
    # 1. 검출기 생성
    detector = create_detector(
        model_type='yolo',
        model_path='weights/best.pt',
        conf_threshold=0.5,
        device='cuda'
    )
    
    # 2. 비디오 열기
    video_path = 'test_video.mp4'
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"⚠️  비디오를 열 수 없습니다: {video_path}")
        return
    
    # 3. 비디오 정보
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"비디오 정보: {width}x{height} @ {fps}fps, {total_frames} frames")
    
    # 4. 결과 비디오 writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter('result_video.mp4', fourcc, fps, (width, height))
    
    # 5. 프레임별 검출
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # 검출
        detections = detector.detect(frame)
        
        # 시각화
        vis_frame = draw_detections(frame, detections)
        
        # 저장
        out.write(vis_frame)
        
        # 진행 상황 출력
        if frame_idx % 30 == 0:
            print(f"  처리 중... {frame_idx}/{total_frames} frames")
        
        frame_idx += 1
    
    # 6. 정리
    cap.release()
    out.release()
    
    print(f"✓ 총 {frame_idx} 프레임 처리 완료")
    print("✓ 결과 저장: result_video.mp4\n")


def example_with_config():
    """설정 파일을 사용한 검출 예시"""
    print("=" * 60)
    print("Example 3: Detection with Config")
    print("=" * 60)
    
    # 1. 설정 생성
    config = DetectionConfig(
        model_type='yolo',
        model_path='weights/best.pt',
        device='cuda',
        conf_threshold=0.6,
        iou_threshold=0.4,
        img_size=640,
        max_detections=5,
    )
    
    # 2. 설정 검증
    config.validate()
    print("설정:")
    for key, value in config.to_dict().items():
        print(f"  {key}: {value}")
    
    # 3. 검출기 생성
    from shuttlecock_detection.core import ShuttlecockDetector
    detector = ShuttlecockDetector(config=config)
    
    # 4. 검출 수행
    frame = cv2.imread('test_image.jpg')
    detections = detector.detect(frame)
    
    # 5. 통계 확인
    stats = detector.get_statistics()
    print("\n통계:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print()


def example_model_comparison():
    """여러 모델 비교 예시"""
    print("=" * 60)
    print("Example 4: Model Comparison")
    print("=" * 60)
    
    models = [
        ('yolo11n', 'weights/yolo11n.pt'),
        ('yolo11s', 'weights/yolo11s.pt'),
        ('custom', 'weights/best.pt'),
    ]
    
    frame = cv2.imread('test_image.jpg')
    
    for model_name, model_path in models:
        if not Path(model_path).exists():
            print(f"⚠️  모델 파일 없음: {model_path}")
            continue
        
        print(f"\n[{model_name}]")
        
        # 검출기 생성
        detector = create_detector(
            model_type='yolo',
            model_path=model_path,
            device='cuda'
        )
        
        # 검출 수행 (시간 측정)
        import time
        start = time.time()
        detections = detector.detect(frame)
        elapsed = time.time() - start
        
        # 결과 출력
        print(f"  검출 개수: {len(detections)}")
        print(f"  처리 시간: {elapsed*1000:.2f}ms")
        print(f"  FPS: {1/elapsed:.1f}")


def main():
    """메인 함수"""
    print("\n" + "=" * 60)
    print("Shuttlecock Detection - Examples")
    print("=" * 60 + "\n")
    
    # 예시 실행
    # 주석을 해제하여 원하는 예시를 실행하세요
    
    # example_basic_detection()
    # example_video_detection()
    # example_with_config()
    # example_model_comparison()
    
    print("=" * 60)
    print("모든 예시를 실행하려면 각 함수의 주석을 해제하세요.")
    print("=" * 60)


if __name__ == '__main__':
    main()
