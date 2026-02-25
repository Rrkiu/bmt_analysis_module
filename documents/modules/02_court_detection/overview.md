# Court Auto Detection — 모듈 개요

## 목적

수동으로 4개 코너를 클릭하는 캘리브레이션(Milestone 1)과 달리, 이 모듈은 **이미지에서 코트 라인을 자동으로 분석하여 4개의 코너 좌표를 컴퓨터 비전 알고리즘으로 검출**한다. 자동 검출이 완료되면 동일한 `CalibrationService.calibrate_from_corners()`를 호출해 Homography 행렬을 계산하므로, 이후의 분석 파이프라인은 수동 캘리브레이션과 동일하게 동작한다.

---

## 모듈 구성 파일

```
modules/court_detection/
├── core_detector.py          # I/O 독립적인 검출 핵심 로직 (CourtDetector 클래스)
├── integration.py            # 검출 + 캘리브레이션 통합 (auto_calibrate_from_image)
├── api_integration.py        # API용 완성 파이프라인 (detect_court_with_overlay)
├── pipeline.py               # CLI 파일 기반 파이프라인 (테스트·실험용)
├── line_generator.py         # 실세계 코트 라인 좌표 생성
├── overlay_renderer.py       # Homography 기반 코트 오버레이 렌더링
├── config.py                 # 검출 파라미터 및 프리셋 설정
├── modules/
│   ├── mask_generator.py     # 다중 색공간 앙상블로 코트 라인 마스크 생성
│   ├── point_detector.py     # 마스크에서 4코너 좌표 검출
│   └── utils.py              # 이미지 I/O, 시각화 유틸리티
└── legacy/
    └── pl_1_ransac_cld_bup_ll_v7.py  # 레거시 검출 알고리즘 (래핑하여 사용)
```

---

## 전체 검출 파이프라인

```
[BGR 이미지 입력]
       │
       ▼
[Step 1] MaskGenerator.generate()
   - HSV, YCbCr, LAB 3개 색공간 변환
   - 각 색공간에서 흰색 픽셀 마스크 생성
   - AND 앙상블 → 코트 라인 이진 마스크 (0/255)
       │
       ▼
[Step 2] PointDetector.detect()
   - 수평 라인 성분 제거 (모폴로지 연산)
   - Bottom-Up 사이드라인 추출 (하단 25% → 상단 방향)
   - RANSAC 직선 피팅
   - 교점 계산 → TL, TR, BR, BL 코너 좌표
       │
       ▼
[Step 3] CalibrationService.calibrate_from_corners()
   - 자동 검출된 4코너 → 수동 캘리브레이션과 동일한 로직
   - Homography 행렬 계산
       │
       ▼
[Step 4] 신뢰도 점수 계산 (DetectionConfidence)
   - Mask Quality: 마스크 커버리지 비율
   - Geometry Quality: 코너 위치 기하학적 적합성
   - Calibration Quality: pixels_per_meter 유효 범위
       │
       ▼
[Step 5] 코트 라인 오버레이 생성
   - CourtLineGenerator: 실세계 코트 라인 좌표 생성
   - CourtOverlayRenderer: Homography로 이미지 위에 렌더링
       │
       ▼
[API 응답]: corners, homography, confidence, overlay_image
```

---

## 핵심 클래스 요약

| 클래스/함수 | 역할 |
|------------|------|
| `CourtDetector` | 검출 파이프라인 통합 (I/O 독립적) |
| `MaskGenerator` | 다중 색공간 AND 앙상블로 코트 라인 마스크 생성 |
| `PointDetector` | 레거시 알고리즘 래퍼 — RANSAC 기반 4코너 검출 |
| `auto_calibrate_from_image()` | 검출 + 캘리브레이션 통합 함수 |
| `detect_court_with_overlay()` | API용 완성 파이프라인 (신뢰도 + 오버레이 포함) |
| `DetectionConfidence` | 검출 품질 정량 평가 (0~1 점수) |
| `CourtLineGenerator` | BWF 규격 기반 코트 라인 좌표 생성 |
| `CourtOverlayRenderer` | Homography 변환으로 이미지에 코트 라인 렌더링 |

---

## 수동 vs 자동 캘리브레이션 비교

| 항목 | 수동 (align-corners) | 자동 (detect-court-auto) |
|------|---------------------|--------------------------|
| 코너 입력 | 사용자 직접 클릭 | CV 알고리즘 자동 검출 |
| 정확도 | 높음 (사용자 판단) | 환경에 따라 가변 |
| 신뢰도 점수 | 없음 | 0~1 스코어 제공 |
| 코트 라인 오버레이 | 별도 시각화 서비스 사용 | 검출 즉시 생성 |
| 이후 파이프라인 | 동일 (`calibration_result` 구조) | 동일 (`calibration_result` 구조) |

자동 검출 결과는 세션에 수동 캘리브레이션과 동일한 구조로 저장되므로, 이후 비디오 분석 파이프라인은 두 방식을 구분하지 않는다.

---

## ensemble_mode 현재 지원 상태

`config.py`에는 `conservative`, `moderate`, `aggressive` 세 모드가 정의되어 있으나, `MaskGenerator` 현재 구현(`mask_generator.py`)에서는 **`conservative` 모드만 실제로 동작**한다. 다른 모드를 전달하면 `ValueError`가 발생한다. API(`detect_court_auto`)에서는 `conservative`를 하드코딩하여 사용한다.
