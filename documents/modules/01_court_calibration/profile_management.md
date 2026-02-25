# 캘리브레이션 프로파일 관리

## 개요

캘리브레이션 결과는 기본적으로 인메모리 세션에만 저장되므로 서버 재시작 시 소멸한다. `CalibrationProfileService`는 이 결과를 **SQLite DB + 파일 시스템**에 영속적으로 저장하여, 동일한 카메라 배치에서 다시 캘리브레이션 없이 분석을 재개할 수 있도록 한다.

---

## 저장 구조

```
storage/
├── calibrations.db                  # SQLite DB (프로파일 메타데이터)
└── calibrations/
    └── {profile_id}/                # 예: profile_1740000000
        ├── reference.jpg            # 캘리브레이션 시 사용한 원본 이미지
        ├── thumbnail.jpg            # 썸네일 (200×150, 목록 화면용)
        └── overlay.png              # 코트 오버레이가 적용된 시각화 이미지
```

`profile_id`는 클라이언트가 지정하거나, 지정하지 않으면 서버에서 `profile_{Unix timestamp}` 형식으로 자동 생성한다.

---

## SQLite 스키마

### `calibration_profiles` 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `profile_id` | TEXT (PK) | 고유 식별자 (`profile_{timestamp}`) |
| `profile_name` | TEXT | 사용자 정의 이름 (예: "A코트 카메라1") |
| `created_at` | TIMESTAMP | 최초 생성 시각 |
| `updated_at` | TIMESTAMP | 최근 수정 시각 |
| `camera_info` | TEXT (JSON) | 카메라 정보 (선택, 자유 형식 dict) |
| `calibration_data` | TEXT (JSON) | 핵심 캘리브레이션 데이터 (아래 참조) |
| `validation` | TEXT (JSON) | 재투영 오차, 유효성 여부 |
| `reference_image_path` | TEXT | 참조 이미지 파일 절대 경로 |
| `thumbnail_path` | TEXT | 썸네일 파일 절대 경로 |
| `metadata` | TEXT (JSON) | 기타 메타데이터 (선택, 자유 형식 dict) |

### `calibration_data` JSON 구조 (상세)

```json
{
  "corners_image":  [[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
  "corners_world":  [[-3.05,-6.7],[3.05,-6.7],[3.05,6.7],[-3.05,6.7]],
  "homography_matrix": [[h11,h12,h13],[h21,h22,h23],[h31,h32,h33]],
  "inverse_homography": [[...],...],
  "pixels_per_meter": 87.4,
  "image_width": 1920,
  "image_height": 1080
}
```

`inverse_homography` (역행렬)도 함께 저장하는 이유는 프로파일 로드 후 즉시 `world_to_image` 변환이 가능하도록 역행렬 재계산 비용을 없애기 위함이다.

### `validation` JSON 구조

```json
{
  "is_valid": true,
  "reprojection_error": 1.23,
  "validation_time": "2026-02-25T20:31:00"
}
```

`reprojection_error`는 픽셀 단위의 평균 재투영 오차다. 4점 정확 해를 사용하므로 이론적으로 0에 가깝지만, 부동소수점 오차로 인해 0이 아닌 매우 작은 값이 나타난다.

### 기타 테이블

`analysis_sessions`와 `landing_detections` 테이블도 DDL에 정의되어 있으나, 현재 코드에서는 아직 사용하지 않는다. 향후 분석 세션 및 낙하 기록을 DB에 영속 저장할 때를 위한 Phase 3 준비 구조다.

---

## 주요 메서드

### `save_profile()` — 프로파일 저장

```python
profile_service.save_profile(
    profile_id="profile_1740000000",
    profile_name="A코트 카메라1",
    corners_image=[[320,95],[1580,90],[1620,980],[280,975]],
    corners_world=[[-3.05,-6.7],[3.05,-6.7],[3.05,6.7],[-3.05,6.7]],
    homography=np.array([[...]]),   # 3×3 numpy array
    pixels_per_meter=87.4,
    image_width=1920,
    image_height=1080,
    reference_image=cv2_image_array,  # 선택
    camera_info={"model": "Sony A7"},  # 선택
    metadata={"location": "A코트"}    # 선택
)
```

내부 처리 순서:
1. `storage/calibrations/{profile_id}/` 디렉토리 생성
2. 참조 이미지 저장 (`reference.jpg`)
3. 썸네일 생성(200×150) 및 저장 (`thumbnail.jpg`)
4. 코트 오버레이 이미지 생성 및 저장 (`overlay.png`)
5. Base64 인코딩 썸네일 생성 (API 응답용)
6. 역행렬 계산 후 `calibration_data` dict 구성
7. 재투영 오차 계산
8. SQLite `INSERT OR REPLACE` 실행

`INSERT OR REPLACE` 를 사용하므로 동일 `profile_id`로 재호출하면 덮어쓰기된다.

### `get_profile(profile_id)` — 단일 프로파일 조회

```python
profile = profile_service.get_profile("profile_1740000000")
# 반환: profile['calibration_data']['homography_matrix'] 형태로 접근
```

반환 딕셔너리에는 `thumbnail_base64` 필드가 자동으로 포함된다. 파일 경로에서 실시간으로 읽어 Base64 인코딩하므로, 썸네일 파일이 존재하지 않으면 이 필드는 포함되지 않는다.

### `list_profiles()` — 전체 목록 조회

`updated_at DESC` 기준 정렬. 각 항목에 요약 정보(profile_id, profile_name, created_at, updated_at)와 썸네일 Base64가 포함된다. `calibration_data` 등 대용량 JSON 필드는 목록 조회에서 제외한다.

### `update_profile(profile_id, profile_name, metadata)` — 이름/메타데이터 수정

캘리브레이션 행렬 자체는 수정할 수 없다. 이름과 메타데이터만 변경 가능하며, `updated_at`이 갱신된다.

### `delete_profile(profile_id)` — 프로파일 삭제

파일 시스템의 `{profile_id}/` 디렉토리를 `shutil.rmtree()`로 삭제한 후 SQLite 레코드도 삭제한다. 두 작업 중 하나가 실패해도 예외가 전파된다.

---

## 오버레이 이미지 생성 (`_create_overlay_image`)

프로파일 저장 시 참조 이미지에 코트 영역을 시각화한 `overlay.png`가 생성된다.

```python
# 반투명 녹색 채우기 (alpha=0.3)
cv2.fillPoly(mask, [corners_array], (0, 255, 0))
overlay = cv2.addWeighted(overlay, 0.7, mask, 0.3, 0)

# 경계선 (청록색)
cv2.polylines(overlay, [corners_array], True, (0, 255, 255), 3)

# 코너 포인트 (TL=녹, TR=파, BR=빨, BL=청록)
labels = ['TL', 'TR', 'BR', 'BL']
```

---

## API를 통한 프로파일 접근

프로파일에서 비디오 분석을 이어서 진행할 때는 프로파일 조회 API로 `calibration_data`를 가져와 `VideoAnalysisService`에 직접 주입한다.

```python
# main.py 에서 profile 기반 분석 세션을 시작할 경우 (예시)
profile = profile_service.get_profile(profile_id)
calibration_data = profile['calibration_data']
# calibration_data['homography_matrix'] 로 HomographyTransform 재구성
```

즉, 프로파일은 "한번 캘리브레이션 → 여러 번 분석" 패턴을 지원하기 위한 영속 저장 계층이다.
