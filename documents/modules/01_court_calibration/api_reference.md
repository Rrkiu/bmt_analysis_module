# 캘리브레이션 API 레퍼런스

## 공통 사항

- **Base URL**: `http://localhost:8000`
- **Content-Type**: 파일 업로드는 `multipart/form-data`, 나머지는 `application/json`
- **에러 응답**: FastAPI 표준 HTTPException 형식 (`{"detail": "메시지"}`)
- **세션**: 인메모리 저장, 서버 재시작 시 소멸

---

## 1. 이미지 업로드

```
POST /api/upload
```

캘리브레이션의 첫 단계. 이미지를 업로드하여 `session_id`를 발급받는다.

**요청**
```
Content-Type: multipart/form-data
file: <이미지 파일 (JPEG, PNG 등)>
```

**응답 (200 OK)**
```json
{
  "success": true,
  "session_id": "c3f8a1e2-4b7f-11ef-ab12-0242ac130002",
  "message": "이미지 업로드 완료",
  "data": {
    "width": 1920,
    "height": 1080,
    "filename": "court.jpg",
    "image_url": "/storage/uploads/c3f8a1e2-....jpg"
  }
}
```

`image_url`은 `/storage/` 마운트 경로로 직접 이미지에 접근 가능하다. 프론트엔드는 이 URL을 `<img>` 태그나 Canvas에 직접 사용하여 사용자가 4코너를 클릭할 이미지를 표시한다.

**오류**
- `400`: 이미지 파일이 아닌 경우, 이미지 읽기 실패
- `500`: 서버 내부 오류

---

## 2. 4코너 캘리브레이션

```
POST /api/align-corners
```

현재 사용 중인 유일한 캘리브레이션 방식. 사용자가 이미지에서 클릭한 코트 4코너 좌표로 Homography를 계산한다.

**요청 바디**
```json
{
  "session_id": "c3f8a1e2-...",
  "corners": [
    [320.5, 95.2],    // TL: 상대방 베이스라인 왼쪽
    [1580.1, 90.8],   // TR: 상대방 베이스라인 오른쪽
    [1620.3, 980.4],  // BR: 플레이어 베이스라인 오른쪽
    [280.7, 975.1]    // BL: 플레이어 베이스라인 왼쪽
  ],
  "image_width": 1920,
  "image_height": 1080
}
```

코너 순서는 **[TL, TR, BR, BL] 시계 방향** 을 지켜야 한다. 순서가 틀리면 Homography 행렬이 잘못 계산된다.

**응답 (200 OK)**
```json
{
  "success": true,
  "session_id": "c3f8a1e2-...",
  "message": "캘리브레이션 완료",
  "data": {
    "court_corners": [[320.5,95.2],[1580.1,90.8],[1620.3,980.4],[280.7,975.1]],
    "pixels_per_meter": 87.43,
    "court_area": 1192345.0,
    "validation": {
      "is_valid": true,
      "message": "유효한 코트 형태입니다"
    }
  }
}
```

캘리브레이션 완료 후 결과 오버레이 이미지가 `storage/results/{session_id}_result.jpg`에 저장된다.

**오류**
- `404`: session_id 없음
- `400`: 이미지 읽기 실패, Homography 계산 실패

---

## 3. 캘리브레이션 결과 조회

```
GET /api/result/{session_id}
```

캘리브레이션이 완료된 세션의 결과 요약을 반환한다.

**응답 (200 OK)**
```json
{
  "success": true,
  "session_id": "c3f8a1e2-...",
  "data": {
    "original_image": "/api/image/c3f8a1e2-.../original",
    "result_image": "/api/image/c3f8a1e2-.../result",
    "calibration_time": "2026-02-25T20:31:00",
    "court_corners": [[320.5,95.2],[1580.1,90.8],[1620.3,980.4],[280.7,975.1]],
    "validation": {
      "is_valid": true,
      "message": "유효한 코트 형태입니다"
    }
  }
}
```

Homography 행렬 자체는 이 응답에 포함되지 않는다. 행렬은 세션 내부에만 저장되며, 프로파일로 저장하거나 비디오 분석 요청 시 `session_id`를 통해 간접적으로 사용된다.

---

## 4. 이미지 파일 반환

```
GET /api/image/{session_id}/{image_type}
```

| `image_type` | 반환 이미지 |
|-------------|------------|
| `original` | 업로드된 원본 이미지 |
| `result` | 코트 오버레이가 적용된 결과 이미지 |
| `guide` | T자 가이드 오버레이 (레거시 용도) |

**응답**: 이미지 파일 (`FileResponse`)

---

## 5. 세션 삭제

```
DELETE /api/session/{session_id}
```

인메모리 세션과 관련 파일(업로드 이미지, 결과 이미지)을 삭제한다.

**응답 (200 OK)**
```json
{
  "success": true,
  "message": "세션이 삭제되었습니다"
}
```

---

## 6. 프로파일 저장

```
POST /api/calibration/profile
```

현재 세션의 캘리브레이션 결과를 SQLite DB + 파일 시스템에 영속 저장한다.

**요청 바디**
```json
{
  "session_id": "c3f8a1e2-...",
  "profile_name": "A코트 카메라1",
  "profile_id": null,
  "camera_info": {
    "model": "Sony A7",
    "focal_length": "28mm"
  },
  "metadata": {
    "location": "실내체육관 A코트",
    "notes": "정면 고정 카메라 촬영"
  }
}
```

`profile_id`가 `null`이면 서버에서 `profile_{timestamp}` 형식으로 자동 생성한다. 동일 `profile_id`로 재호출하면 덮어쓰기된다.

**응답 (200 OK)**
```json
{
  "success": true,
  "message": "프로파일이 저장되었습니다",
  "profile": {
    "profile_id": "profile_1740000000",
    "profile_name": "A코트 카메라1",
    "thumbnail_base64": "data:image/jpeg;base64,/9j/...",
    "created_at": "2026-02-25T20:31:00",
    "reprojection_error": 0.0003
  }
}
```

`reprojection_error`는 캘리브레이션 품질 지표다. 4점 정확 해를 사용하므로 정상적인 경우 매우 작은 값(< 1.0 픽셀)이 반환된다.

---

## 7. 프로파일 목록 조회

```
GET /api/calibration/profiles
```

저장된 모든 프로파일의 요약 정보와 썸네일을 반환한다.

**응답 (200 OK)**
```json
{
  "success": true,
  "count": 2,
  "profiles": [
    {
      "profile_id": "profile_1740000000",
      "profile_name": "A코트 카메라1",
      "created_at": "2026-02-25T20:31:00",
      "updated_at": "2026-02-25T20:31:00",
      "thumbnail_base64": "data:image/jpeg;base64,...",
      "metadata": null
    }
  ]
}
```

`updated_at` 내림차순 정렬. `calibration_data` (Homography 등 대용량 데이터)는 목록에 포함되지 않는다.

---

## 8. 단일 프로파일 조회

```
GET /api/calibration/profile/{profile_id}
```

Homography 행렬을 포함한 전체 캘리브레이션 데이터를 반환한다.

**응답 (200 OK)**
```json
{
  "success": true,
  "profile": {
    "profile_id": "profile_1740000000",
    "profile_name": "A코트 카메라1",
    "created_at": "...",
    "updated_at": "...",
    "camera_info": {"model": "Sony A7"},
    "calibration_data": {
      "corners_image": [[320,95],[1580,90],[1620,980],[280,975]],
      "corners_world": [[-3.05,-6.7],[3.05,-6.7],[3.05,6.7],[-3.05,6.7]],
      "homography_matrix": [[h11,h12,h13],[h21,h22,h23],[h31,h32,h33]],
      "inverse_homography": [[...],...],
      "pixels_per_meter": 87.43,
      "image_width": 1920,
      "image_height": 1080
    },
    "validation": {
      "is_valid": true,
      "reprojection_error": 0.0003
    },
    "reference_image_path": "/path/to/storage/calibrations/profile_.../reference.jpg",
    "thumbnail_base64": "data:image/jpeg;base64,...",
    "metadata": null
  }
}
```

---

## 9. 프로파일 수정

```
PUT /api/calibration/profile/{profile_id}
```

이름과 메타데이터만 수정 가능하다. Homography 행렬 등 캘리브레이션 데이터 자체는 수정할 수 없다.

**요청 바디**
```json
{
  "profile_name": "A코트 카메라1 (업데이트)",
  "metadata": {"notes": "조명 환경 변경 후 재촬영 필요"}
}
```

---

## 10. 프로파일 삭제

```
DELETE /api/calibration/profile/{profile_id}
```

SQLite 레코드와 `storage/calibrations/{profile_id}/` 디렉토리 전체를 삭제한다.

---

## 11. 프로파일 이미지 조회

```
GET /api/calibration/profile/{profile_id}/image?type=reference
```

| `type` 파라미터 | 반환 이미지 |
|----------------|------------|
| `reference` (기본) | 원본 참조 이미지 |
| `thumbnail` | 200×150 썸네일 |
| `overlay` | 코트 오버레이 시각화 이미지 |

**응답**: 이미지 파일 (`FileResponse`)
