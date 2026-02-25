# 캘리브레이션 워크플로우

## 전체 흐름

```
[1] 이미지 업로드 (POST /api/upload)
        ↓
[2] 프론트엔드에서 코트 4코너 클릭
        ↓
[3] 4코너 좌표 전송 (POST /api/align-corners)
        ↓
[4] CalibrationService.calibrate_from_corners() 실행
    - 실세계 코너 좌표 정의
    - cv2.findHomography() 로 H 행렬 계산
    - pixels_per_meter 추정
        ↓
[5] 결과 이미지 생성 및 세션 저장
        ↓
[6] (선택) 프로파일 저장 (POST /api/calibration/profile)
        ↓
[7] 비디오 분석에서 이 calibration_data 사용
```

---

## Step 1: 이미지 업로드

```
POST /api/upload
Content-Type: multipart/form-data
Body: file=<이미지 파일>
```

서버는 UUID 기반 `session_id`를 생성하고 이미지를 `storage/uploads/{session_id}.jpg` 에 저장한다. 이미지 너비/높이 정보와 함께 세션이 인메모리에 등록된다.

```json
// 응답
{
  "success": true,
  "session_id": "c3f8a1e2-...",
  "data": {
    "width": 1920,
    "height": 1080,
    "filename": "court.jpg",
    "image_url": "/storage/uploads/c3f8a1e2-....jpg"
  }
}
```

---

## Step 2 & 3: 4코너 캘리브레이션 실행

```
POST /api/align-corners
Content-Type: application/json
```

```json
// 요청 바디 (CornersAlignment)
{
  "session_id": "c3f8a1e2-...",
  "corners": [
    [320, 95],    // TL: 상대방 베이스라인 왼쪽
    [1580, 90],   // TR: 상대방 베이스라인 오른쪽
    [1620, 980],  // BR: 플레이어 베이스라인 오른쪽
    [280, 975]    // BL: 플레이어 베이스라인 왼쪽
  ],
  "image_width": 1920,
  "image_height": 1080
}
```

코너 순서는 반드시 `[TL, TR, BR, BL]` 시계 방향이어야 한다.

---

## Step 4: `calibrate_from_corners()` 내부 동작

```python
# calibration_service.py

def calibrate_from_corners(self, court_corners_image, image_shape):
    # 실세계 좌표 정의 (복식 코트 외곽선 기준, 단위: 미터)
    half_width = CourtDimensions.DOUBLES_WIDTH / 2   # 3.05m
    half_length = CourtDimensions.BACK_BOUNDARY_LINE  # 6.7m

    court_corners_world = [
        [-half_width, -half_length],  # TL: 상대방 베이스라인 왼쪽
        [ half_width, -half_length],  # TR: 상대방 베이스라인 오른쪽
        [ half_width,  half_length],  # BR: 플레이어 베이스라인 오른쪽
        [-half_width,  half_length],  # BL: 플레이어 베이스라인 왼쪽
    ]

    src_points = np.array(court_corners_image, dtype=np.float32)
    dst_points = np.array(court_corners_world, dtype=np.float32)

    # 4점 정확 해 계산 (method=0 → DLT)
    success = self.homography.compute_homography(src_points, dst_points, method=0)

    # pixels_per_meter 계산 (가로·세로 평균)
    w_pixels = np.linalg.norm(src_points[0] - src_points[1])  # TL-TR 거리
    h_pixels = np.linalg.norm(src_points[0] - src_points[3])  # TL-BL 거리
    pixels_per_meter = (w_pixels / 6.1 + h_pixels / 13.4) / 2

    return {
        'success': True,
        'court_corners_image': court_corners_image,
        'court_corners_world': court_corners_world,
        'homography_matrix': self.homography.homography_matrix.tolist(),
        'pixels_per_meter': pixels_per_meter,
        'image_shape': image_shape,
    }
```

### 실세계 코너 좌표 매핑

| 코너 | 이미지 좌표 (예시) | 실세계 좌표 (미터) |
|------|-----------------|------------------|
| TL | `[320, 95]` | `[-3.05, -6.7]` |
| TR | `[1580, 90]` | `[+3.05, -6.7]` |
| BR | `[1620, 980]` | `[+3.05, +6.7]` |
| BL | `[280, 975]` | `[-3.05, +6.7]` |

실세계 좌표는 **코드에 하드코딩**되어 있으며, 항상 BWF 표준 복식 코트 규격을 기준으로 한다. `constants.py`의 `CourtDimensions` 클래스에서 수치를 가져온다.

---

## Step 5: 결과 이미지 생성 및 세션 저장

캘리브레이션 완료 후 서버는 다음 작업을 수행한다.

1. **결과 이미지 생성**: `VisualizationService.draw_complete_visualization()` 로 코트 영역이 오버레이된 이미지 생성 → `storage/results/{session_id}_result.jpg` 저장
2. **세션 업데이트**: 인메모리 `sessions[session_id]` 딕셔너리에 `calibration_result`, `court_region`, `calibration_time` 등 저장

4코너 방식에서는 `show_t_guide=False` 로 설정하여 T자 가이드 라인을 숨기고 코트 영역 오버레이만 표시한다.

### API 응답

```json
{
  "success": true,
  "session_id": "c3f8a1e2-...",
  "message": "캘리브레이션 완료",
  "data": {
    "court_corners": [[320,95],[1580,90],[1620,980],[280,975]],
    "pixels_per_meter": 87.4,
    "court_area": 1234567,
    "validation": {
      "is_valid": true,
      "message": "유효한 코트 형태입니다"
    }
  }
}
```

---

## Step 6: 프로파일 저장 (선택)

동일한 카메라 배치에서 반복 촬영할 경우, 캘리브레이션 결과를 프로파일로 저장해 재사용할 수 있다.

```
POST /api/calibration/profile
Content-Type: application/json
```

```json
{
  "session_id": "c3f8a1e2-...",
  "profile_name": "A코트 카메라1",
  "camera_info": {
    "model": "Sony A7",
    "focal_length": "24mm"
  },
  "metadata": {
    "location": "실내체육관 A코트"
  }
}
```

`profile_id`를 지정하지 않으면 서버에서 `profile_{timestamp}` 형식으로 자동 생성한다. 저장 시 참조 이미지 원본, 썸네일(200×150), 코트 오버레이 이미지가 파일 시스템에 함께 저장된다.

---

## Step 7: 비디오 분석에서 캘리브레이션 활용

비디오 분석 요청 시 `session_id`를 함께 전달하면 해당 세션의 `calibration_result`가 `VideoAnalysisService`로 주입된다.

```python
# main.py → process_video_analysis()
calibration_data = sessions[session_id]['calibration_result']

analysis_service = VideoAnalysisService(
    session_id=session_id,
    calibration_data=calibration_data,   # Homography 행렬 포함
    detector_type='yolo',
)
```

`VideoAnalysisService`는 내부적으로 `HomographyTransform`을 초기화하여 매 프레임마다 셔틀콕 픽셀 좌표를 실세계 좌표로 변환한다.

---

## 세션의 생명주기

```
업로드 시      → sessions[session_id] 생성 (calibrated: False)
캘리브레이션 후 → calibration_result 추가 (calibrated: True)
분석 완료 후   → result_filepath 추가
서버 재시작     → 전체 소멸 (인메모리이므로)
DELETE 요청     → sessions 딕셔너리에서 제거 + 파일 삭제
```

프로덕션 환경으로 전환할 경우 인메모리 `sessions` 딕셔너리는 Redis 또는 DB 기반으로 교체가 필요하다. 현재는 단일 서버 프로세스 내에서만 유효하다.
