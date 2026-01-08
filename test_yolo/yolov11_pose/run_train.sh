#!/bin/bash
# YOLOv11 Pose 학습 실행 스크립트 (Docker 환경)

echo "======================================================================"
echo "🚀 YOLOv11 Pose Estimation 학습 시작"
echo "======================================================================"

# 기본 설정
DATA_YAML="/workspace/260107/data.yaml"
MODEL="yolo11n-pose.pt"
EPOCHS=150
BATCH=16
IMGSZ=640
NAME="court_pose"
DEVICE=0

# 인자 파싱
while [[ $# -gt 0 ]]; do
    case $1 in
        --model)
            MODEL="$2"
            shift 2
            ;;
        --epochs)
            EPOCHS="$2"
            shift 2
            ;;
        --batch)
            BATCH="$2"
            shift 2
            ;;
        --name)
            NAME="$2"
            shift 2
            ;;
        *)
            echo "알 수 없는 옵션: $1"
            exit 1
            ;;
    esac
done

echo "설정:"
echo "  데이터: $DATA_YAML"
echo "  모델: $MODEL"
echo "  에포크: $EPOCHS"
echo "  배치: $BATCH"
echo "  이미지 크기: $IMGSZ"
echo "  실험 이름: $NAME"
echo "======================================================================"

# 학습 실행
python train.py \
    --data "$DATA_YAML" \
    --model "$MODEL" \
    --epochs "$EPOCHS" \
    --batch "$BATCH" \
    --imgsz "$IMGSZ" \
    --name "$NAME" \
    --device "$DEVICE"

echo ""
echo "======================================================================"
echo "✅ 학습 완료!"
echo "======================================================================"
echo "결과 확인: /workspace/runs/pose/$NAME"
echo "======================================================================"
