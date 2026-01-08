#!/usr/bin/env python3
"""
YOLOv11-pose 추론 스크립트
배드민턴 코트 4개 코너 포인트 검출 및 시각화
"""
import argparse
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO


def draw_keypoints(image, keypoints, conf_threshold=0.5):
    """
    키포인트를 이미지에 그립니다.
    
    Args:
        image: 원본 이미지
        keypoints: 키포인트 배열 (N, K, 3) - N개 객체, K개 키포인트, (x, y, confidence)
        conf_threshold: 신뢰도 임계값
    
    Returns:
        시각화된 이미지
    """
    vis = image.copy()
    h, w = image.shape[:2]
    
    # 코너 포인트 색상 (좌상, 우상, 우하, 좌하)
    colors = [
        (255, 0, 0),    # 좌상: 파란색
        (0, 255, 0),    # 우상: 초록색
        (0, 0, 255),    # 우하: 빨간색
        (255, 255, 0),  # 좌하: 청록색
    ]
    
    labels = ['Top-Left', 'Top-Right', 'Bottom-Right', 'Bottom-Left']
    
    for obj_kpts in keypoints:
        # 각 객체의 키포인트
        points = []
        
        for idx, (x, y, conf) in enumerate(obj_kpts):
            if conf < conf_threshold:
                continue
            
            # 픽셀 좌표로 변환
            px, py = int(x), int(y)
            
            # 키포인트 그리기
            color = colors[idx % len(colors)]
            cv2.circle(vis, (px, py), 8, color, -1)
            cv2.circle(vis, (px, py), 10, (255, 255, 255), 2)
            
            # 라벨 표시
            label = f"{labels[idx]}: {conf:.2f}"
            cv2.putText(
                vis, label, (px + 15, py - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
            )
            
            points.append((px, py))
        
        # 코너 포인트를 선으로 연결 (사각형)
        if len(points) >= 4:
            # 폴리곤 그리기
            pts = np.array(points[:4], dtype=np.int32)
            cv2.polylines(vis, [pts], isClosed=True, color=(0, 255, 255), thickness=3)
            
            # 반투명 오버레이
            overlay = vis.copy()
            cv2.fillPoly(overlay, [pts], (0, 255, 255))
            vis = cv2.addWeighted(overlay, 0.2, vis, 0.8, 0)
    
    return vis


def visualize_result(image, result, conf_threshold=0.25, output_path=None):
    """
    추론 결과를 시각화합니다.
    
    Args:
        image: 원본 이미지
        result: YOLO 추론 결과
        conf_threshold: 신뢰도 임계값
        output_path: 저장 경로 (None이면 저장하지 않음)
    
    Returns:
        시각화된 이미지
    """
    vis = image.copy()
    
    # 키포인트가 없으면 원본 반환
    if result.keypoints is None or len(result.keypoints) == 0:
        print("  ⚠️  키포인트가 검출되지 않았습니다.")
        return vis
    
    # 키포인트 데이터 추출
    keypoints = result.keypoints.data.cpu().numpy()  # (N, K, 3)
    boxes = result.boxes.xyxy.cpu().numpy() if result.boxes is not None else None
    confs = result.boxes.conf.cpu().numpy() if result.boxes is not None else None
    
    print(f"  ✓ {len(keypoints)}개 객체 검출")
    
    # 바운딩 박스 그리기
    if boxes is not None and confs is not None:
        for box, conf in zip(boxes, confs):
            if conf < conf_threshold:
                continue
            
            x1, y1, x2, y2 = box.astype(int)
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            label = f"Court: {conf:.2f}"
            cv2.putText(
                vis, label, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
            )
    
    # 키포인트 그리기
    vis = draw_keypoints(vis, keypoints, conf_threshold)
    
    # 결과 저장
    if output_path:
        cv2.imwrite(str(output_path), vis)
        print(f"  💾 저장: {output_path}")
    
    return vis


def process_image(model, image_path, output_dir, conf_threshold=0.25, save_txt=False):
    """
    단일 이미지 처리
    
    Args:
        model: YOLO 모델
        image_path: 이미지 경로
        output_dir: 출력 디렉토리
        conf_threshold: 신뢰도 임계값
        save_txt: 텍스트 결과 저장 여부
    """
    print(f"\n📸 처리 중: {image_path.name}")
    
    # 이미지 로드
    image = cv2.imread(str(image_path))
    if image is None:
        print(f"  ❌ 이미지를 읽을 수 없습니다: {image_path}")
        return
    
    # 추론
    results = model.predict(
        source=str(image_path),
        conf=conf_threshold,
        verbose=False
    )
    
    if len(results) == 0:
        print("  ⚠️  검출 결과 없음")
        return
    
    result = results[0]
    
    # 시각화 및 저장
    output_path = output_dir / f"{image_path.stem}_result.jpg"
    visualize_result(image, result, conf_threshold, output_path)
    
    # 텍스트 결과 저장
    if save_txt and result.keypoints is not None:
        txt_path = output_dir / f"{image_path.stem}_result.txt"
        keypoints = result.keypoints.data.cpu().numpy()
        
        with open(txt_path, 'w') as f:
            for obj_idx, obj_kpts in enumerate(keypoints):
                f.write(f"Object {obj_idx}:\n")
                for kpt_idx, (x, y, conf) in enumerate(obj_kpts):
                    f.write(f"  Point {kpt_idx}: ({x:.2f}, {y:.2f}) conf={conf:.3f}\n")
                f.write("\n")
        
        print(f"  💾 텍스트 저장: {txt_path}")


def main():
    parser = argparse.ArgumentParser(
        description='YOLOv11 Pose Estimation 추론'
    )
    parser.add_argument(
        '--model',
        required=True,
        help='학습된 모델 경로 (.pt 파일)'
    )
    parser.add_argument(
        '--source',
        required=True,
        help='입력 이미지 파일 또는 디렉토리'
    )
    parser.add_argument(
        '--output',
        default='results',
        help='출력 디렉토리'
    )
    parser.add_argument(
        '--conf',
        type=float,
        default=0.25,
        help='신뢰도 임계값'
    )
    parser.add_argument(
        '--save-txt',
        action='store_true',
        help='텍스트 결과 저장'
    )
    
    args = parser.parse_args()
    
    print("="*70)
    print("🔍 YOLOv11 Pose Estimation 추론")
    print("="*70)
    print(f"모델: {args.model}")
    print(f"소스: {args.source}")
    print(f"출력: {args.output}")
    print(f"신뢰도 임계값: {args.conf}")
    print("="*70)
    
    # 모델 로드
    model = YOLO(args.model)
    
    # 경로 설정
    source = Path(args.source)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 이미지 파일 찾기
    if source.is_file():
        images = [source]
    elif source.is_dir():
        images = (
            list(source.glob('*.jpg')) +
            list(source.glob('*.jpeg')) +
            list(source.glob('*.png')) +
            list(source.glob('*.bmp'))
        )
    else:
        print(f"❌ 유효하지 않은 소스: {source}")
        return
    
    if len(images) == 0:
        print(f"❌ 이미지를 찾을 수 없습니다: {source}")
        return
    
    print(f"\n📁 총 {len(images)}개 이미지 처리 시작\n")
    
    # 각 이미지 처리
    for img_path in images:
        process_image(model, img_path, output_dir, args.conf, args.save_txt)
    
    print("\n" + "="*70)
    print("✅ 모든 처리 완료!")
    print("="*70)
    print(f"📁 결과 저장 위치: {output_dir.absolute()}")
    print("="*70)


if __name__ == "__main__":
    main()
