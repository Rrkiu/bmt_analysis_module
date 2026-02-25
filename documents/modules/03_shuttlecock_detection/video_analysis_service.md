# 비디오 분석 파이프라인 (`VideoAnalysisService`)

## 목적

`VideoAnalysisService`는 검출(`YOLODetectorAdapter`), 추적(`ShuttlecockLandingDetector`), 좌표 변환(`HomographyTransform`), 시각화(`VisualizationService`)를 하나로 통합하는 **최상위 분석 파이프라인 클래스**다.

---

## 초기화

```python
service = VideoAnalysisService(
    session_id='c3f8a1e2-...',
    calibration_data={
        'court_corners_image': [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
        'homography_matrix': [[...], [...], [...]]
    },
    detector_type='yolo',      # 'yolo' | 'tracknet'
    detector_config={
        'model_path': 'modules/shuttlecock_detection/weights/yolov8m_shuttlecock_best.pt',
        'conf_threshold': 0.5,
        'device': 'cuda',
        'img_size': 640,
    }
)
```

### 코너 데이터 정규화

`calibration_data`의 코너는 두 가지 형식을 모두 지원한다:

| 형식 | 출처 | 예시 |
|------|------|------|
| `court_corners_image` (리스트) | 수동 캘리브레이션 | `[[342, 98], [1591, 94], ...]` |
| `corners_image` (딕셔너리) | 자동 검출 | `{'TL': [342, 98], 'TR': [1591, 94], ...}` |

딕셔너리 형식이면 `TL, TR, BR, BL` 순서로 `numpy array`로 변환하여 동일하게 처리한다.

---

## `process_frame()` — 핵심 메서드

프레임 단위로 호출되는 메인 처리 함수. 최종적으로 `(processed_frame, info_dict)`를 반환한다.

```python
processed_frame, info = service.process_frame(
    frame=bgr_numpy_array,
    mode='normal',   # 'normal' | 'debug'
    video_time=12.4  # 현재 비디오 재생 위치 (초)
)
```

### 처리 순서 (5단계)

**① Seek 감지**
```python
is_seek = (
    video_time < self.last_video_time - 0.5 or
    video_time > self.last_video_time + 5.0
)
if is_seek:
    self.landing_detector.reset()  # 모든 상태 초기화
```

**② 셔틀콕 검출**
```python
prediction = self.detector_adapter.get_prediction(frame)
x, y, vis = prediction if prediction else (0, 0, 0)

# 시각화 (검출 마커를 처리 프레임에 오버레이)
processed = self.detector_adapter.draw_prediction(processed, prediction)
```

**③ 낙하 감지 업데이트**
```python
new_landing = self.landing_detector.update(x, y, vis, self.frame_counter)

if new_landing:
    # 픽셀 → 실세계 좌표
    world_pos = self.ht.image_to_world((landing_x, landing_y))
    # 코트 내/외 판정
    is_in_court = CourtGeometry.is_point_in_court(world_pos)
```

**④ 코트 오버레이 렌더링**
```python
if mode == 'debug':
    processed = self._draw_debug_overlay(processed)
else:
    processed = self._draw_court_overlay(processed)
```

**⑤ 낙하 결과 시각화**

낙하 감지 후 **20초 이내** 또는 **500프레임 이내**에 표시가 유지된다.

```python
# 낙하 위치 마커 (메인 화면)
cv2.circle(processed, (lx, ly), 20, landing_color, -1)   # IN=녹색, OUT=빨간색
cv2.drawMarker(processed, (lx, ly), (255, 255, 255),
               cv2.MARKER_TILTED_CROSS, 60, 5)

# 미니맵 (우상단 160x310px 카드)
VisualizationService.draw_minimap(
    processed, world_point=self.last_world_pos, is_in_court=self.is_last_in_court,
    position=(card_x + pad, card_y + pad), size=(140, 290)
)

# 판정 텍스트 (화면 하단 중앙)
cv2.putText(processed, "JUDGMENT: IN" or "JUDGMENT: OUT", ...)
```

---

## 반환 `info` 딕셔너리 구조

```python
info = {
    'frame_width': 1920,
    'frame_height': 1080,
    'mode': 'normal',
    'tracknet': {
        'x': 842,
        'y': 514,
        'visibility': 1,
        'is_landed': False,
        'landing_debug': {
            'dist': 4.2,
            'stay_counter': 2,
            'visibility': 1,
            'is_landed': False,
            'reason': 'Staying (dist=4.20 < 10.0)'
        }
    },
    'landing': {              # None if no landing detected yet
        'is_landed': True,
        'pos': [1.24, -4.18], # 실세계 좌표 [X_m, Y_m]
        'image_x': 842,       # 픽셀 좌표
        'image_y': 918,
        'is_in_court': True,
        'time_since': 2.4     # 낙하 후 경과 초
    }
}
```

`tracknet` 키 이름은 레거시 TrackNet 코드에서 유래한 이름이며, 실제로는 YOLO 검출 결과를 담는다.

---

## 렌더링 모드

### Normal 모드 (`_draw_court_overlay`)

```python
# 반투명 녹색 코트 영역 (alpha=0.15)
cv2.fillPoly(overlay, [self.corners_image], (0, 255, 0))
frame = cv2.addWeighted(frame, 0.85, overlay, 0.15, 0)

# 노란색 코트 경계선 (두께 3)
cv2.polylines(frame, [self.corners_image], True, (0, 255, 255), 3)
```

### Debug 모드 (`_draw_debug_overlay`)

```python
# 진한 반투명 녹색 (alpha=0.30)
cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)

# 각 코너: 컬러 원 + 레이블 + 픽셀 좌표 표시
# TL=Green, TR=Blue, BR=Red, BL=Yellow

# 상단 100px 정보 패널 추가
# "DEBUG MODE" + 해상도 + 코트 면적(px²)
```

Debug 모드에서는 상단에 100픽셀 정보 패널이 추가되므로, 출력 프레임 높이가 `원본 + 100`이 된다.

---

## `process_video_file()` — 파일 전체 처리

개발/테스트 용도로 비디오 파일 전체를 처리한다.

```python
result = service.process_video_file(
    video_path='input.mp4',
    mode='normal',
    output_path='output.mp4',  # None이면 저장 안 함
    max_frames=300              # None이면 전체 처리
)
# result: {'success': True, 'frames_processed': 300, 'elapsed_time': 12.4, 'avg_fps': 24.2}
```

30프레임마다 진행률과 실제 처리 FPS를 로그로 출력한다.

---

## API와의 연결

`main.py`에서는 비디오 스트리밍 WebSocket 연결 시 세션별로 `VideoAnalysisService` 인스턴스를 생성하여 프레임 스트림을 처리한다.

```python
# main.py (WebSocket endpoint)
@app.websocket("/ws/video/{session_id}")
async def video_stream(websocket: WebSocket, session_id: str):
    session = sessions[session_id]
    service = VideoAnalysisService(
        session_id=session_id,
        calibration_data=session['calibration_result'],
        detector_type='yolo',
        detector_config={'model_path': MODEL_PATH, 'device': 'cuda'}
    )
    while True:
        frame_bytes = await websocket.receive_bytes()
        frame = decode_frame(frame_bytes)
        processed, info = service.process_frame(frame, video_time=...)
        await websocket.send_bytes(encode_frame(processed))
```

세션 당 하나의 `VideoAnalysisService` 인스턴스를 유지하므로, `ShuttlecockLandingDetector`의 상태(position_history, stay_counter 등)가 프레임 간에 연속적으로 유지된다.

---

## 15fps 실시간 처리 성능 목표

| 단계 | 예상 처리 시간 |
|------|--------------|
| YOLO 추론 (GPU) | 15~30ms |
| 낙하 감지 계산 | < 1ms |
| 코트 오버레이 렌더링 | 3~8ms |
| WebSocket 전송 overhead | 5~15ms |
| **합계** | **24~54ms (≈ 20~40fps 가능)** |

CPU 환경에서는 YOLO 추론이 100ms 이상 소요되므로 실시간 처리에 한계가 있다. TensorRT `.engine` 파일 사용 시 GPU 추론을 5~10ms로 단축할 수 있다.
