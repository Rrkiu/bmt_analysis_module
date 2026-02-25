# 신뢰도 점수 및 통합 파이프라인

## 자동 검출 신뢰도 (DetectionConfidence)

수동 캘리브레이션과 달리, 자동 검출 결과는 품질이 보장되지 않는다. 조명 조건, 코트 상태, 카메라 앵글에 따라 검출 품질이 달라지기 때문이다. `DetectionConfidence` 클래스는 검출 결과를 세 가지 측면에서 정량 평가하여 `0~1` 사이의 점수를 반환한다.

---

## 세 가지 품질 점수

### 1. Mask Quality (마스크 품질) — 가중치 20%

코트 라인 마스크가 얼마나 깨끗하게 생성되었는지를 평가한다.

```python
# 마스크 커버리지 비율 = 흰색 픽셀 수 / 전체 픽셀 수
coverage = metadata.get('mask_coverage_ratio', 0.0)

# 최적 범위: 5% ~ 15%
if coverage < 0.02:
    score = coverage / 0.02          # 라인이 너무 적음 → 선형 감점
elif coverage <= 0.15:
    score = 1.0                      # 정상 범위
else:
    score = max(0, 1.0 - (coverage - 0.15) / 0.15)  # 너무 많음 → 감점
```

코트 라인이 이미지에서 너무 적게 또는 너무 많이 검출된 경우 모두 점수가 낮아진다.

### 2. Geometry Quality (기하 품질) — 가중치 50%

검출된 4개 코너의 기하학적 위치가 실제 배드민턴 코트 형태에 얼마나 부합하는지를 평가한다. **가장 중요한 지표**로, 최종 점수의 절반을 차지한다.

**검사 항목:**

```python
# 검사 1: 모든 코너가 이미지 내에 존재하는가 (10픽셀 마진)
in_bounds = all([10 <= pt[0] <= W-10 and 10 <= pt[1] <= H-10 for pt in corners])

# 검사 2: 상단 두 코너(TL, TR)의 y좌표가 비슷한가
top_y_diff = abs(tl[1] - tr[1])
y_alignment_score = max(0, 1.0 - top_y_diff / (H * 0.15))  # 15% 이내

# 검사 3: 종횡비가 코트 비율에 맞는가
# 배드민턴 전체 코트: 6.1m / 13.4m ≈ 0.45 (복식 너비 / 전체 길이)
# 카메라 커버 코트(한쪽): 0.3 ~ 0.7 범위 허용
aspect_ratio = avg_width / avg_height

# 검사 4: 좌우 변과 상하 변이 대칭적인가
width_consistency  = 1 - |top_width - bottom_width| / max(top_width, bottom_width)
height_consistency = 1 - |left_height - right_height| / max(left_height, right_height)
```

네 검사 점수의 평균이 Geometry Quality 점수가 된다.

### 3. Calibration Quality (캘리브레이션 품질) — 가중치 30%

`pixels_per_meter` 값의 합리성을 검사한다.

```python
# 예상 범위: 15 ~ 100 pixels/meter
# (1080p 이미지, 풀 코트 촬영 기준 약 30-80)
if 15 <= pixels_per_meter <= 100:
    score = 1.0
elif pixels_per_meter < 15:
    score = pixels_per_meter / 15     # 너무 작은 스케일
else:
    score = max(0, 1.0 - (pixels_per_meter - 100) / 100)  # 너무 큰 스케일
```

### 최종 종합 점수

```python
overall = (mask_score * 0.2) + (geometry_score * 0.5) + (calibration_score * 0.3)
```

API 응답에서 반환되는 형식:
```json
{
  "mask_quality": 0.92,
  "geometry_quality": 0.87,
  "calibration_quality": 1.0,
  "overall": 0.906
}
```

---

## 통합 API 함수: detect_court_with_overlay()

API가 호출하는 최상위 함수. 검출, 신뢰도 계산, 코트 라인 생성, 오버레이 렌더링까지 4단계를 순차 실행한다.

```python
def detect_court_with_overlay(
    image: np.ndarray,
    ensemble_mode: str = 'conservative',
    use_extrapolation: bool = False,
    include_doubles: bool = True,
    overlay_alpha: float = 1.0,
    draw_corners: bool = True,
    return_separate_images: bool = False,
) -> Dict[str, Any]:
```

### 내부 4단계

**Step 1 — Auto-calibration (`integration.py`)**
```python
calibration_result = auto_calibrate_from_image(
    image=image,
    ensemble_mode=ensemble_mode,
    use_extrapolation=use_extrapolation,
)
# 반환: AutoCalibrationResult(corners_image, homography_matrix, pixels_per_meter, ...)
```
`CourtDetector`로 코너 검출 → `CalibrationService.calibrate_from_corners()`로 Homography 계산.

**Step 2 — 신뢰도 계산**
```python
confidence = DetectionConfidence.calculate_overall_confidence(
    calibration_result, image_shape
)
```

**Step 3 — 코트 라인 생성 (`line_generator.py`)**
```python
generator = CourtLineGenerator(court_type='singles')
world_lines = generator.generate_all_lines(include_net=True, include_doubles=include_doubles)
# 반환: {'singles_sideline_left': [[x1,y1],[x2,y2]], 'net': [...], ...}
```
실세계 미터 좌표로 표현된 코트 라인 딕셔너리를 생성한다.

**Step 4 — 오버레이 렌더링 (`overlay_renderer.py`)**
```python
renderer = CourtOverlayRenderer(calibration_result.homography_matrix)
overlay_image = renderer.render(
    image=image,
    world_lines=world_lines,
    styles=styles,
    alpha=overlay_alpha,
    draw_corners=draw_corners,
    detected_corners=calibration_result.corners_image
)
```
Homography 역행렬로 실세계 라인 좌표를 픽셀 좌표로 변환하여 이미지에 그린다.

---

## API 엔드포인트: POST /api/detect-court-auto

```python
# main.py → detect_court_auto()
```

### 요청 바디 (AutoDetectRequest)

```json
{
  "session_id": "c3f8a1e2-...",
  "include_doubles": true,
  "overlay_alpha": 1.0,
  "draw_corners": true,
  "save_overlay": true,
  "roi": {
    "x": 100, "y": 50,
    "width": 1720, "height": 980
  }
}
```

| 필드 | 설명 |
|------|------|
| `session_id` | 업로드된 이미지 세션 ID |
| `include_doubles` | 복식 사이드라인을 오버레이에 포함할지 여부 |
| `overlay_alpha` | 오버레이 투명도 (0.0 = 없음, 1.0 = 불투명) |
| `draw_corners` | 코너 마커(원+레이블) 표시 여부 |
| `save_overlay` | 오버레이 이미지를 파일로 저장 여부 |
| `roi` | 검출에 사용할 관심 영역 (선택, 미지정 시 전체 이미지) |

### ROI (Region of Interest) 처리

`roi`를 지정하면 이미지의 일부 영역만 잘라서 검출을 수행한 뒤, 결과 코너 좌표를 원본 이미지 좌표로 변환한다.

```python
# ROI 영역 추출
detection_image = image[y:y+h, x:x+w].copy()
roi_offset = (x, y)

# 검출 후 좌표 보정
result['corners']['TL'][0] += roi_offset[0]  # x 오프셋 추가
result['corners']['TL'][1] += roi_offset[1]  # y 오프셋 추가
```

ROI를 사용하면 코트 외의 배경(벽, 관중석 등)이 마스크 생성을 방해하는 경우에 검출 정확도를 높일 수 있다.

### 응답 (AutoDetectResponse)

```json
{
  "success": true,
  "session_id": "c3f8a1e2-...",
  "message": "자동 검출 성공",
  "confidence": {
    "mask_quality": 0.92,
    "geometry_quality": 0.87,
    "calibration_quality": 1.0,
    "overall": 0.906
  },
  "corners": {
    "TL": [342.1, 98.7],
    "TR": [1591.3, 94.2],
    "BR": [1618.4, 976.8],
    "BL": [283.6, 981.2]
  },
  "calibration": {
    "pixels_per_meter": 87.43,
    "homography_matrix": [[...], [...], [...]]
  },
  "overlay_url": "/storage/results/c3f8a1e2-..._overlay.jpg",
  "metadata": {
    "image_shape": [1080, 1920],
    "include_doubles": true,
    "detection_time": "2026-02-25T20:31:00"
  }
}
```

### 세션에 저장되는 데이터

자동 검출 성공 시, 세션에는 다음 데이터가 추가된다.

```python
session['calibrated'] = True
session['calibration_result'] = {
    'homography_matrix': ...,
    'pixels_per_meter': ...,
    'court_corners_world': ...,
    'court_corners_image': {...},  # dict 형식 {'TL': [x,y], ...}
    'image_shape': [H, W]
}
session['auto_detect_confidence'] = confidence
session['auto_detect_time'] = "2026-02-25T20:31:00"
```

이 구조는 수동 캘리브레이션 세션과 동일하므로 이후 비디오 분석 파이프라인에서 동일하게 사용된다.

---

## 검출 상태 조회

```
GET /api/detect-court-auto/status/{session_id}
```

검출 이전: `{"status": "not_detected"}`  
검출 이후: `{"status": "detected", "confidence": {...}, "calibration": {...}}`
