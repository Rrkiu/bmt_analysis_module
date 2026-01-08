#!/usr/bin/env python3
"""
YOLOv11-pose 학습 스크립트
배드민턴 코트 4개 코너 포인트 검출을 위한 pose estimation 모델 학습
"""
import argparse
from pathlib import Path
from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser(
        description='YOLOv11 Pose Estimation 모델 학습'
    )
    parser.add_argument(
        '--data',
        required=True,
        help='data.yaml 파일 경로'
    )
    parser.add_argument(
        '--model',
        default='yolo11n-pose.pt',
        help='사전학습 모델 (yolo11n-pose.pt, yolo11s-pose.pt, yolo11m-pose.pt 등)'
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=150,
        help='학습 에포크 수'
    )
    parser.add_argument(
        '--batch',
        type=int,
        default=16,
        help='배치 사이즈'
    )
    parser.add_argument(
        '--imgsz',
        type=int,
        default=640,
        help='입력 이미지 크기'
    )
    parser.add_argument(
        '--name',
        default='court_pose',
        help='실험 이름 (저장 폴더명)'
    )
    parser.add_argument(
        '--device',
        default='0',
        help='GPU 디바이스 (0, 1, 2... 또는 cpu)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=8,
        help='데이터 로더 워커 수'
    )
    parser.add_argument(
        '--patience',
        type=int,
        default=50,
        help='Early stopping patience'
    )
    parser.add_argument(
        '--save-period',
        type=int,
        default=10,
        help='모델 저장 주기 (에포크)'
    )
    parser.add_argument(
        '--optimizer',
        default='AdamW',
        choices=['SGD', 'Adam', 'AdamW', 'RMSProp'],
        help='옵티마이저'
    )
    parser.add_argument(
        '--lr0',
        type=float,
        default=0.001,
        help='초기 학습률'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='이전 학습 재개'
    )
    parser.add_argument(
        '--project',
        default='/workspace/runs/pose',
        help='프로젝트 저장 경로'
    )
    
    args = parser.parse_args()
    
    print("="*70)
    print("🚀 YOLOv11 Pose Estimation 학습 시작")
    print("="*70)
    print(f"모델: {args.model}")
    print(f"데이터: {args.data}")
    print(f"에포크: {args.epochs}")
    print(f"배치 사이즈: {args.batch}")
    print(f"이미지 크기: {args.imgsz}")
    print(f"디바이스: {args.device}")
    print(f"실험 이름: {args.name}")
    print("="*70)
    
    # 모델 로드
    model = YOLO(args.model)
    
    # 학습 시작
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        patience=args.patience,
        save_period=args.save_period,
        optimizer=args.optimizer,
        lr0=args.lr0,
        plots=True,
        name=args.name,
        project=args.project,
        resume=args.resume,
        # Augmentation
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=10.0,
        translate=0.1,
        scale=0.5,
        shear=0.0,
        perspective=0.0,
        flipud=0.0,
        fliplr=0.0,  # 좌우 플립 비활성화 (코트는 좌우 대칭)
        mosaic=1.0,
        mixup=0.0,
    )
    
    print("\n" + "="*70)
    print("✅ 학습 완료!")
    print("="*70)
    print(f"📁 결과 저장 경로: {args.project}/{args.name}")
    print(f"🏆 Best 모델: {args.project}/{args.name}/weights/best.pt")
    print(f"📊 Last 모델: {args.project}/{args.name}/weights/last.pt")
    print("="*70)
    
    # 검증 수행
    print("\n🔍 최종 검증 수행 중...")
    metrics = model.val()
    
    print("\n📊 최종 성능 지표:")
    if hasattr(metrics, 'box'):
        print(f"  Box mAP50: {metrics.box.map50:.4f}")
        print(f"  Box mAP50-95: {metrics.box.map:.4f}")
    if hasattr(metrics, 'pose'):
        print(f"  Pose mAP50: {metrics.pose.map50:.4f}")
        print(f"  Pose mAP50-95: {metrics.pose.map:.4f}")
    
    print("\n✨ 모든 작업이 완료되었습니다!")


if __name__ == "__main__":
    main()
