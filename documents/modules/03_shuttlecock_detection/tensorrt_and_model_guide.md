# TensorRT 최적화 및 모델 교체 가이드

## TensorRT `.engine` 변환이 필요한 이유

| 항목 | PyTorch `.pt` | TensorRT `.engine` |
|------|--------------|-------------------|
| 추론 시간 (GPU) | 15~30ms/frame | 5~10ms/frame |
| 메모리 사용량 | 높음 | 낮음 (layer fusion) |
| CUDA 없이 실행 | CPU 폴백 가능 | 불가 (CUDA 필수) |
| `imgsz` 변경 | 언제든 가능 | 빌드 시 고정 |
| 배포 이식성 | 높음 | 동일 GPU 아키텍처만 |

---

## `.pt` → `.engine` 변환 절차

`export_tensorrt.py` 스크립트를 사용한다.

```bash
cd core/backend/modules/shuttlecock_detection
python export_tensorrt.py \
    --weights weights/yolov8m_shuttlecock_best.pt \
    --imgsz 640 \
    --device 0
```

내부 처리:
```python
from ultralytics import YOLO

model = YOLO('weights/yolov8m_shuttlecock_best.pt')
model.export(
    format='engine',        # TensorRT 엔진
    imgsz=640,              # 입력 해상도 (고정됨)
    device=0,               # GPU 인덱스
    half=True,              # FP16 (메모리/속도 최적화)
    simplify=True,          # ONNX 그래프 단순화
)
# → 출력: weights/yolov8m_shuttlecock_best.engine
```

> **주의**: 변환된 `.engine` 파일은 **변환한 GPU 아키텍처에서만** 동작한다. RTX 3080에서 변환한 엔진은 RTX 4090에서 그대로 사용할 수 없다.

---

## 백엔드에서 `.engine` 파일 사용

`detector_config`의 `model_path`만 변경한다. 나머지 코드는 동일하게 동작한다.

```python
# .pt 사용 (기본)
detector_config = {
    'model_path': 'modules/shuttlecock_detection/weights/yolov8m_shuttlecock_best.pt',
    'img_size': 640,
    'device': 'cuda',
}

# .engine 사용 (TensorRT 최적화)
detector_config = {
    'model_path': 'modules/shuttlecock_detection/weights/yolov8m_shuttlecock_best.engine',
    # img_size는 engine 내부에 고정됨, 설정해도 무시될 수 있음
    'device': 'cuda',   # CUDA 필수
}
```

`model_factory.py`의 `auto_detect_model_type()`이 `.engine` 확장자를 자동으로 `'yolo'` 타입으로 인식한다.

---

## 새 YOLO 모델 교체 방법

### 1. 가중치 파일 교체만 필요한 경우

같은 YOLOv8/v11 아키텍처의 새 가중치로 교체할 때:

1. 새 `.pt` 파일을 `weights/` 디렉토리에 복사
2. `main.py` 또는 `VideoAnalysisService` 초기화의 `model_path` 변경
3. `img_size`가 학습 해상도와 일치하는지 확인

```
weights/
├── yolov8m_shuttlecock_best.pt      # 현재 사용
├── yolov8m_fp16_1280_best.pt        # 새 모델 (1280 해상도)
└── yolov8s_shuttlecock_v2.pt        # 경량 모델 후보
```

```python
detector_config = {
    'model_path': 'modules/shuttlecock_detection/weights/yolov8m_fp16_1280_best.pt',
    'img_size': 1280,  # 학습 해상도에 맞게 변경
}
```

### 2. 완전히 다른 모델 아키텍처 추가

`BaseDetector`를 상속받아 새 클래스를 구현하고 팩토리에 등록한다.

```python
# 1. 새 파일 생성: models/my_custom_detector.py
class MyCustomDetector(BaseDetector):
    def load_model(self): ...
    def preprocess(self, frame): ...
    def detect(self, frame, conf_threshold=None): ...
    def postprocess(self, outputs): ...

# 2. model_factory.py에 등록
from .my_custom_detector import MyCustomDetector

SUPPORTED_MODELS = {
    'yolo': YOLODetector,
    'tracknet': TrackNetDetector,
    'custom': MyCustomDetector,    # 추가
}

# 3. adapters에 어댑터 구현 (필요 시)
class MyCustomAdapter(BaseDetectorAdapter):
    def get_prediction(self, frame): ...

# 4. VideoAnalysisService에서 사용
VideoAnalysisService(detector_type='custom', ...)
```

---

## 탐지 성능 튜닝 가이드

### 검출율이 낮을 때 (`많이 놓침`)

```python
# conf_threshold 낮추기
detector_config['conf_threshold'] = 0.3  # 기본값 0.5 → 0.3

# img_size 높이기 (고해상도 추론)
detector_config['img_size'] = 1280  # 기본값 640 → 1280
```

### 오탐이 많을 때 (`배경이 셔틀콕으로 잘못 검출됨`)

```python
# conf_threshold 높이기
detector_config['conf_threshold'] = 0.7

# iou_threshold 조정 (NMS 강도)
# iou가 낮으면 중복 박스 제거 강화
```

### 낙하 판정이 너무 민감할 때 (`정상 비행 중 낙하 판정`)

```python
# stay_frames 높이기 (더 오래 정지해야 판정)
ShuttlecockLandingDetector(stay_threshold=10.0, stay_frames=6)

# stay_threshold 낮추기 (더 좁은 범위에서만 정지로 판정)
ShuttlecockLandingDetector(stay_threshold=6.0, stay_frames=4)
```

### 낙하 판정이 너무 늦을 때

```python
# stay_frames 낮추기
ShuttlecockLandingDetector(stay_threshold=10.0, stay_frames=3)
```

---

## TrackNet 레거시 아키텍처 (참고용)

TrackNet은 ShuttlecockNet 계열 모델로, **연속된 N개 프레임을 입력받아 히트맵을 출력**하는 방식이다. 현재 코드에는 `TrackNetDetectorAdapter`와 ZMQ 기반 통신 코드(`tracknet_adapter.py`)가 남아 있으나, `TrackNetDetector` 추론 로직은 구현되지 않은 상태다.

```
TrackNet 입력:  [Frame_t-7, Frame_t-6, ..., Frame_t] → 8 채널 이미지
TrackNet 출력:  히트맵 (H, W, 1) → 셔틀콕 위치 Gaussian 분포
```

YOLO와의 차이점:
- YOLO: 단일 프레임 입력, 바운딩 박스 출력
- TrackNet: 8프레임 입력, 히트맵 출력 → 모션 블러 내성이 높음

`YOLODetectorAdapter`의 8프레임 버퍼 구조는 TrackNet과의 인터페이스 호환성을 위해 유지되었으나, 현재는 마지막 프레임만 사용한다.
