# YOLO 기반 셔틀콕 검출 구조

## 검출 요청 흐름

```
VideoAnalysisService
    └── YOLODetectorAdapter.get_prediction(frame)
            └── YOLODetector.detect(frame)         ← YOLO 추론 실행
                    └── model.predict(...)           ← Ultralytics API
                    └── postprocess(results)         ← Detection 객체 변환
```

---

## `Detection` 데이터클래스

모든 검출 결과는 이 구조체로 표현된다.

```python
@dataclass
class Detection:
    x: float           # 바운딩 박스 중심 x (픽셀)
    y: float           # 바운딩 박스 중심 y (픽셀)
    width: float       # 바운딩 박스 너비 (픽셀)
    height: float      # 바운딩 박스 높이 (픽셀)
    confidence: float  # 신뢰도 (0.0 ~ 1.0)
    class_id: int = 0
    class_name: str = "shuttlecock"
```

`bbox` 프로퍼티: `(x1, y1, x2, y2)` — 중심점+크기에서 코너 좌표로 변환  
`center` 프로퍼티: `(x, y)` — 중심점 좌표만 추출

---

## `YOLODetector` — 추론 구현

### 모델 로드 (`load_model`)

`YOLODetector`는 `.pt` (PyTorch) 와 `.engine` (TensorRT) 두 가지 형식을 **동일한 Ultralytics YOLO API**로 로드한다.

```python
self.model = YOLO(str(model_path))  # .pt 또는 .engine 모두 동작
```

**분기 처리:**

| 파일 형식 | 처리 방식 |
|-----------|-----------|
| `.pt` | CUDA 없으면 CPU로 자동 전환 |
| `.engine` | CUDA 필수, 없으면 RuntimeError |
| `.onnx` | `auto_detect_model_type()`에서 `yolo` 타입으로 감지 |

TensorRT `.engine` 파일의 `imgsz`는 컴파일 시점에 고정되므로, `predict()` 호출 시 `imgsz` 파라미터를 전달하지 않는다.

### `detect()` 메서드

```python
# .pt 파일
results = model.predict(
    source=frame,
    conf=conf,
    iou=self.iou_threshold,
    device=self.device,
    imgsz=self.img_size,      # .pt만
    half=self.half,           # .pt만
    verbose=False,
)

# .engine 파일 (imgsz, half 제외)
results = model.predict(
    source=frame,
    conf=conf,
    iou=self.iou_threshold,
    device=self.device,
    verbose=False,
)
```

### `postprocess()` — Ultralytics 결과 → Detection 변환

```python
for result in outputs:
    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
        detection = Detection(
            x=(x1 + x2) / 2,      # 중심 x
            y=(y1 + y2) / 2,      # 중심 y
            width=x2 - x1,
            height=y2 - y1,
            confidence=float(box.conf[0].cpu()),
            class_id=int(box.cls[0].cpu()),
            class_name="shuttlecock"
        )
```

---

## `YOLODetectorAdapter` — 파이프라인 연결

`VideoAnalysisService`와 YOLO 검출기 사이에 위치하는 어댑터 계층이다. 주요 역할:

1. **출력 포맷 통일**: `(x, y, visibility)` 튜플 반환 (TrackNet과 동일한 인터페이스)
2. **최선 검출 선택**: 여러 검출 중 신뢰도 최고 1개를 메인으로 선택
3. **프레임 버퍼 유지**: 마지막 8개 프레임을 버퍼로 유지 (현재는 최신 프레임만 사용)
4. **시각화 제공**: 모든 검출 박스를 프레임에 그리는 `draw_prediction()` 포함

### `get_prediction()` 핵심 로직

```python
def get_prediction(self, frame) -> Optional[Tuple[int, int, int]]:
    # 1. 프레임 버퍼 업데이트 (8프레임 슬라이딩 윈도우)
    self.update_frame_buffer(frame)
    current_frame = self.frame_buffer[-1]   # 현재 프레임 사용

    # 2. YOLO 추론
    detections = self.detector.detect(current_frame, self.conf_threshold)

    if not detections:
        return DetectionResult.no_detection().to_tuple()  # (0, 0, 0)

    # 3. 최고 신뢰도 검출 선택
    best = max(detections, key=lambda d: d.confidence)

    return DetectionResult(
        x=int(best.x),
        y=int(best.y),
        visibility=1,
        confidence=best.confidence
    ).to_tuple()   # (x, y, 1)
```

**`visibility` 값의 의미:**
- `1`: 셔틀콕이 검출됨, `(x, y)` 좌표가 유효
- `0`: 검출 없음, `(x, y)`는 `(0, 0)`으로 무시됨

### 시각화: `draw_prediction()`

검출이 있을 때 프레임 위에 다음 요소를 그린다.

```
메인 검출 (최고 신뢰도):
  - 노란색 (0, 255, 255) 반투명 원 radius=10
  - 중심점 원 radius=2
  - 신뢰도 텍스트 (흰 배경)

기타 검출 (다중 검출 시):
  - 주황색 (0, 165, 255) 반투명 원 radius=8
  - 메인 검출에 별(*) 마크 추가
  - "Detected: N shuttlecocks" 카운트 텍스트
```

---

## `DetectionConfig` 파라미터

`VideoAnalysisService` 초기화 시 `detector_config` 딕셔너리로 주입된다.

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `model_path` | `weights/yolov8m_shuttlecock_best.pt` | 모델 가중치 경로 |
| `conf_threshold` | 0.5 | 신뢰도 임계값 (낮추면 검출률↑ 오탐↑) |
| `iou_threshold` | 0.4 | NMS IoU 임계값 |
| `device` | `cuda` | 추론 디바이스 |
| `img_size` | 640 | 추론 해상도 (1280도 가능) |
| `max_detections` | 10 | 프레임당 최대 검출 수 |
| `half_precision` | False | FP16 추론 (GPU만 가능) |

### 워밍업 (Warmup)

첫 번째 YOLO 추론은 모델 로드 후 GPU 메모리 준비로 인해 지연이 발생한다. `warmup()` 메서드로 더미 이미지를 미리 추론하여 첫 실제 프레임의 처리 지연을 제거할 수 있다.

```python
detector.warmup(input_shape=(640, 640, 3))
```

---

## `model_factory.py` — 팩토리 함수

```python
detector = create_detector(
    model_type='yolo',        # 'yolo' | 'tracknet'
    model_path='weights/best.pt',
    conf_threshold=0.5,
    iou_threshold=0.4,
    device='cuda',
    img_size=1280,            # 추가 kwargs
)
```

파일 확장자 자동 감지도 지원한다:

```python
model_type = auto_detect_model_type('weights/best.engine')
# → 'yolo'

model_type = auto_detect_model_type('weights/tracknet.pth')
# → 'tracknet'
```

확장자 매핑: `.pt` → yolo, `.engine` → yolo, `.onnx` → yolo, `.pth` → tracknet
