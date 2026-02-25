# 프레임 분석 API (`/api/analysis/frame-predict`)

## 개요

프론트엔드의 30fps 분석 루프가 매 33ms마다 호출하는 핵심 엔드포인트다. 단일 비디오 프레임 이미지를 받아 셔틀콕 검출, 낙하 판정, 좌표 변환을 수행하고 결과를 반환한다.

---

## 요청 (`multipart/form-data`)

```
POST /api/analysis/frame-predict
Content-Type: multipart/form-data
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `session_id` | string | 캘리브레이션이 완료된 세션 ID |
| `file` | blob (JPEG) | 비디오 프레임 이미지 (Canvas API로 캡처) |
| `video_time` | float | 현재 비디오 재생 위치 (초) |

`video_time`은 `ShuttlecockLandingDetector`의 Seek 감지에 사용된다.

---

## 처리 순서 (백엔드)

### Step 1: 세션 검증 및 `VideoAnalysisService` 초기화

```python
if session_id not in sessions:
    raise HTTPException(404, "세션을 찾을 수 없습니다")

session = sessions[session_id]

# 해당 세션에 서비스 인스턴스가 없으면 최초 1회 생성
if 'analysis_service' not in session:
    if not session.get('calibrated'):
        raise HTTPException(400, "캘리브레이션이 완료되지 않았습니다")

    session['analysis_service'] = VideoAnalysisService(
        session_id=session_id,
        calibration_data=session['calibration_result'],
        detector_type=app.state.detector_type,    # 'yolo' | 'tracknet'
        detector_config={
            'model_path': app.state.yolo_weights,
            'conf_threshold': 0.5,
            'img_size': app.state.yolo_img_size,
            'device': 'cuda'
        }
    )
```

`VideoAnalysisService`는 세션당 1개 인스턴스를 유지한다. 최초 생성 시 YOLO 모델을 로드하므로 약 1~3초 지연이 발생할 수 있다.

### Step 2: 이미지 디코딩

```python
contents = await file.read()
nparr = np.frombuffer(contents, np.uint8)
frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)  # BGR numpy array
```

### Step 3: 프레임 분석

```python
processed_frame, info = service.process_frame(
    frame=frame,
    video_time=video_time
)
```

내부적으로 YOLO 검출 → 낙하 판정 → 코트 오버레이 렌더링이 수행된다.

### Step 4: numpy 타입 직렬화

FastAPI의 `JSONResponse`는 numpy 타입(`np.float32`, `np.int64` 등)을 직렬화할 수 없으므로, 재귀적으로 Python 기본 타입으로 변환한다.

```python
def sanitize_info(obj):
    if isinstance(obj, np.ndarray): return obj.tolist()
    if isinstance(obj, (np.float32, np.float64)): return float(obj)
    if isinstance(obj, (np.int32, np.int64)): return int(obj)
    if isinstance(obj, dict): return {k: sanitize_info(v) for k, v in obj.items()}
    if isinstance(obj, list): return [sanitize_info(v) for v in obj]
    return obj
```

### Step 5: 응답 반환

```json
{
    "success": true,
    "tracknet": {
        "x": 842,
        "y": 514,
        "visibility": 1,
        "is_landed": false,
        "landing_debug": {
            "dist": 4.2,
            "stay_counter": 2,
            "visibility": 1,
            "is_landed": false,
            "reason": "Staying (dist=4.20 < 10.0)"
        }
    },
    "landing": {
        "is_landed": true,
        "pos": [1.24, -4.18],
        "image_x": 842,
        "image_y": 918,
        "is_in_court": true,
        "time_since": 2.4
    },
    "processed_image": "data:image/jpeg;base64,/9j/4AAQ..."
}
```

`processed_image`는 백엔드에서 렌더링된 오버레이 포함 JPEG 이미지(JPEG 품질 80)다. 현재 프론트엔드에서는 이 값을 무시하고 Canvas로 독립 렌더링하므로, 이 필드는 디버깅 용도로만 유지된다.

---

## 세션 구조 (분석 서비스 추가 후)

```python
sessions[session_id] = {
    # 기본 세션 (이미지 업로드 시 생성)
    'image_path': '/path/to/image.jpg',
    'image_url': '/api/image/session_id/original',

    # 캘리브레이션 완료 후 추가
    'calibrated': True,
    'calibration_result': {
        'court_corners_image': [[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
        'homography_matrix': [[...], [...], [...]],
        'pixels_per_meter': 87.43,
        'image_shape': [1080, 1920],
    },

    # 분석 시작 후 추가 (최초 frame-predict 호출 시 생성)
    'analysis_service': VideoAnalysisService(...)
}
```

---

## 앱 시작 시 모델 설정 (`app.state`)

`main.py` 시작 시 커맨드라인 인자로 검출기 설정을 지정한다.

```bash
# YOLO .pt 파일 사용
uvicorn main:app --port 8000 \
    --detector=yolo \
    --yolo_weights=modules/shuttlecock_detection/weights/yolov8m_best.pt \
    --yolo_img_size=640

# YOLO TensorRT .engine 사용
uvicorn main:app --port 8000 \
    --detector=yolo \
    --yolo_weights=modules/shuttlecock_detection/weights/yolov8m_best.engine \
    --yolo_img_size=640

# TrackNet 사용 (레거시)
uvicorn main:app --port 8000 \
    --detector=tracknet \
    --tracknet_url=tcp://localhost:8002
```

`app.state.detector_type`, `app.state.yolo_weights`, `app.state.yolo_img_size`로 접근한다.

---

## GET `/api/session/{session_id}/calibration` — 캘리브레이션 조회

프론트엔드 `useVideoAnalysis.loadCalibration()`이 초기화 시 호출하는 엔드포인트.

```json
// 응답
{
    "success": true,
    "session_id": "c3f8a1e2-...",
    "calibrated": true,
    "calibration_result": {
        "court_corners_image": [[342, 98], [1591, 94], [1618, 977], [284, 981]],
        "image_shape": [1080, 1920],
        "pixels_per_meter": 87.43,
        "homography_matrix": [[...], [...], [...]]
    }
}
```

`court_corners_image`를 Canvas에서 코트 오버레이를 그릴 때, `image_shape`를 기준으로 비디오 해상도로 스케일링하여 사용한다.

---

## 성능 고려사항

### 30fps 요청 한계

33ms 간격으로 HTTP POST 요청을 보내는 방식은 네트워크 왕복 시간(RTT)이 0에 가까운 로컬 환경에서만 실용적이다.

| 환경 | YOLO 추론 | 전체 왕복 | 실효 fps |
|------|-----------|-----------|---------|
| GPU 로컬 (cuda) | ~15ms | ~25ms | ~35fps |
| CPU 로컬 | ~100ms | ~115ms | ~8fps |
| 원격 서버 | ~15ms | 15ms + RTT | RTT에 따라 다름 |

CPU 환경에서는 33ms 인터벌을 맞출 수 없어 실제 분석 fps가 크게 낮아진다. 이 경우 `ANALYSIS_INTERVAL`을 100ms(약 10fps)로 늘리는 것이 효율적이다.

### 중복 요청 방지

```typescript
if (now - lastAnalysisTimeRef.current < ANALYSIS_INTERVAL) return;
```

인터벌이 33ms여도 이전 요청이 33ms 이상 걸리면 중복 발생. `lastAnalysisTimeRef`로 최소 간격을 강제한다.

### `canvas.toBlob()` 비동기 특성

`toBlob()`은 콜백 기반 비동기다. 콜백 내부에서 `fetch()`를 호출하므로, 이 fetch가 완료되기 전에 다음 analyzeFrame 호출이 시작될 수 있다. 즉, **요청이 실제로 겹칠 수 있다**. 현재 서버는 세션당 하나의 `VideoAnalysisService` 인스턴스를 공유하므로, 이론적으로 동시 요청 시 `ShuttlecockLandingDetector` 상태가 경합할 수 있다. 실제로는 33ms 내에 이전 요청이 완료되므로 문제가 없지만, 고부하 상황에서는 주의가 필요하다.
