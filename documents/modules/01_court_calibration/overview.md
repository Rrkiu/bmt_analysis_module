# Court Calibration — 모듈 개요

## 목적

배드민턴 코트 분석의 모든 기능은 **"이미지 픽셀 좌표"와 "실세계 미터 좌표" 사이의 변환** 위에서 동작한다. 코트 캘리브레이션 모듈은 이 변환 관계를 계산하고 관리하는 역할을 담당한다.

사용자가 촬영된 코트 이미지에서 4개의 코너 좌표를 직접 지정하면, 이 모듈이 두 좌표계 사이의 Homography 행렬을 계산한다. 이후 모든 분석 과정(셔틀콕 낙하 위치 판정, 코트 영역 오버레이 등)은 이 행렬을 통해 이미지 픽셀 → 실세계 미터 좌표 변환을 수행한다.

---

## 모듈 구성 파일

```
modules/calibration/
├── __init__.py                   # CalibrationService, CalibrationProfileService export
├── calibration_service.py        # 캘리브레이션 계산 핵심 로직
├── calibration_profile_service.py # 프로파일 영속 저장 (SQLite + 파일 시스템)
└── geometry.py                   # HomographyTransform, CourtGeometry 유틸리티
```

---

## 핵심 클래스

| 클래스 | 파일 | 역할 |
|--------|------|------|
| `CalibrationService` | `calibration_service.py` | 4코너 → Homography 계산, 코트 영역 생성 |
| `CalibrationProfileService` | `calibration_profile_service.py` | 캘리브레이션 결과를 SQLite에 영속 저장/조회/삭제 |
| `HomographyTransform` | `geometry.py` | Homography 행렬 계산 및 양방향 좌표 변환 |
| `CourtGeometry` | `geometry.py` | 코트 넓이 계산, 유효성 검증, 좌표 스케일링 |

---

## 캘리브레이션 입력/출력

**입력**: 이미지에서 사용자가 직접 클릭하여 지정한 4개의 코너 픽셀 좌표  
```
[TL, TR, BR, BL]  =  [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
```
- **TL (Top-Left)**: 상대방 베이스라인 왼쪽 코너
- **TR (Top-Right)**: 상대방 베이스라인 오른쪽 코너
- **BR (Bottom-Right)**: 플레이어 베이스라인 오른쪽 코너
- **BL (Bottom-Left)**: 플레이어 베이스라인 왼쪽 코너

> 복식 코트 외곽선 기준. 네트 라인은 포함하지 않는다.

**출력**: `calibrate_from_corners()` 반환값
```json
{
  "success": true,
  "court_corners_image": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
  "court_corners_world": [[-3.05,-6.7], [3.05,-6.7], [3.05,6.7], [-3.05,6.7]],
  "homography_matrix": [[...], [...], [...]],
  "pixels_per_meter": 87.4,
  "image_shape": [1080, 1920]
}
```

---

## 실세계 좌표계 정의

코트 중심(네트 중앙)을 원점 `(0, 0)` 으로 설정한다.

```
                     상대방 코트
         TL (-3.05, -6.7) ─────── TR (3.05, -6.7)
          │                               │
          │          네트 (y=0)           │
         ─┼───────────────────────────────┼─
          │                               │
          │          플레이어 코트         │
         BL (-3.05, 6.7)  ─────── BR (3.05, 6.7)
```

- **X축**: 코트 너비 방향 (`-3.05m` ~ `+3.05m`, 복식 기준 `±3.05m`)
- **Y축**: 코트 길이 방향 (네트=0, 베이스라인=±6.7m)
- 이 시스템은 카메라가 **플레이어 코트 쪽(y > 0 영역)**을 촬영하는 배치를 기준으로 설계됨

---

## 캘리브레이션 사용 흐름 요약

```
[사용자 이미지 업로드]  →  POST /api/upload  →  session_id 반환
         ↓
[프론트엔드에서 4코너 클릭]  →  POST /api/align-corners
         ↓
CalibrationService.calibrate_from_corners()
  1. 이미지 4코너 → 실세계 4코너 매핑
  2. cv2.findHomography() 로 3×3 Homography 행렬 계산
  3. pixels_per_meter 추정 (가로/세로 평균)
         ↓
[세션에 calibration_result 저장]
         ↓
(선택)  POST /api/calibration/profile  →  SQLite 프로파일 저장
```

---

## 다른 모듈과의 연계

캘리브레이션 모듈이 생성하는 `homography_matrix`는 다음 두 곳에서 핵심적으로 사용된다.

1. **`VideoAnalysisService`**: 프레임 분석 시 셔틀콕의 픽셀 좌표를 실세계 좌표로 변환하여 코트 내/외 판정 및 미니맵 좌표 계산에 사용한다.
2. **`VisualizationService`**: 실세계 좌표 기준의 코트 라인 좌표들을 이미지 픽셀 좌표로 역변환하여 코트 오버레이를 렌더링한다.
