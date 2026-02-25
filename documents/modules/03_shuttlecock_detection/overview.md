# 셔틀콕 검출 & 추적 — 모듈 개요

## 목적

캘리브레이션으로 좌표 변환 체계가 준비되면, 다음 단계는 **비디오의 매 프레임에서 셔틀콕을 검출하고, 그 위치 변화를 추적하여 낙하 지점을 판정**하는 것이다. Milestone 3는 이 검출·추적·판정 파이프라인 전체를 다룬다.

---

## 관련 모듈 구성

```
modules/
├── shuttlecock_detection/            # 검출 추상화 계층
│   ├── core/
│   │   └── detector.py               # ShuttlecockDetector — 고수준 공용 인터페이스
│   ├── models/
│   │   ├── base_detector.py          # BaseDetector 추상 클래스, Detection 데이터클래스
│   │   ├── yolo_detector.py          # YOLODetector — YOLO .pt/.engine 추론 구현
│   │   ├── tracknet_detector.py      # TrackNetDetector — 레거시 (미구현)
│   │   └── model_factory.py          # create_detector() 팩토리 함수
│   ├── adapters/
│   │   ├── base_adapter.py           # BaseDetectorAdapter, DetectionResult 데이터클래스
│   │   ├── yolo_adapter.py           # YOLODetectorAdapter — 분석 파이프라인 연결
│   │   └── tracknet_adapter.py       # TrackNetDetectorAdapter — ZMQ 기반 레거시
│   ├── config/
│   │   └── default_config.py         # DetectionConfig, TrackingConfig, VisualizationConfig
│   └── weights/                      # 모델 가중치 파일 저장 위치
│       └── yolov8m_shuttlecock_best.pt  (실제 사용 모델)
│
├── tracking/
│   └── shuttlecock_tracker.py        # ShuttlecockLandingDetector — 낙하 판정
│
└── analysis/
    └── video_analysis_service.py     # VideoAnalysisService — 프레임 처리 파이프라인 통합
```

---

## 클래스 계층 구조

```
BaseDetector (ABC)
  └── YOLODetector           ← 실제 사용 (YOLO .pt / TensorRT .engine)
  └── TrackNetDetector       ← 레거시 (미구현, stub)

BaseDetectorAdapter (ABC)
  └── YOLODetectorAdapter    ← VideoAnalysisService에서 사용
  └── TrackNetDetectorAdapter ← ZMQ 기반 레거시

ShuttlecockDetector          ← BaseDetector wrapping, 독립 사용 가능
ShuttlecockLandingDetector   ← 낙하 판정 상태 기계
VideoAnalysisService          ← 전체 파이프라인 통합 Entry Point
```

---

## 프레임 처리 전체 흐름

```
[비디오 프레임 입력 (BGR numpy array)]
         │
         ▼
[YOLODetectorAdapter.get_prediction(frame)]
   └── YOLO model.predict() 추론
   └── Detection(x, y, conf) 리스트 추출
   └── 가장 높은 신뢰도 선택 → (x, y, visibility=1) 반환
   └── 미검출 시 → (0, 0, visibility=0) 반환
         │
         ▼
[ShuttlecockLandingDetector.update(x, y, visibility, frame_idx)]
   └── stay_threshold = 10픽셀 이내에서 4프레임 연속 정지 → 낙하 판정
   └── 반환: True (낙하 감지) or False
         │
    (낙하 시)
         ▼
[HomographyTransform.image_to_world(x, y)]
   └── 픽셀 → 실세계 미터 좌표 변환
         │
         ▼
[CourtGeometry.is_point_in_court(world_pos)]
   └── 코트 내/외 판정
         │
         ▼
[VisualizationService.draw_minimap()]
   └── 우측 상단 미니맵에 낙하 위치 표시
   └── 화면 하단 "JUDGMENT: IN / OUT" 텍스트 렌더링
```

---

## 두 가지 검출 계층의 역할 분리

### 1. `models/` — 순수 추론 계층

- `BaseDetector` / `YOLODetector`: CUDA/CPU 상의 모델 로드 및 단일 추론 실행
- 독립적으로 사용 가능 (`ShuttlecockDetector`로 래핑)
- 상태를 최소화: 히스토리는 `ShuttlecockDetector`가 관리

### 2. `adapters/` — 파이프라인 연결 계층

- `YOLODetectorAdapter`: `VideoAnalysisService`와 검출기를 연결하는 중간 계층
- **출력 포맷을 TrackNet 호환 `(x, y, visibility)` 튜플로 통일**
- 프레임 버퍼 8개 유지 (시간적 정보 활용 확장 가능성 대비)
- 시각화 코드(`draw_prediction`) 포함

이 두 계층으로 분리한 이유는, 향후 TrackNet이나 다른 모델로 교체해도 `adapters/` 인터페이스만 맞추면 `VideoAnalysisService` 코드 변경 없이 전환할 수 있도록 하기 위해서다.

---

## 현재 사용 모델

| 항목 | 내용 |
|------|------|
| 기반 모델 | YOLOv8m (medium) |
| 가중치 파일 | `weights/yolov8m_shuttlecock_best.pt` |
| 추론 해상도 | 640 또는 1280 (학습 설정 따름) |
| TensorRT 지원 | `.engine` 파일 로드 지원 |
| 학습 데이터 | 실내 배드민턴 코트 영상 + 합성 데이터 |
| 클래스 | 단일 클래스 (`shuttlecock`, class_id=0) |

TrackNet은 `TrackNetDetector` 클래스 구조는 있지만, 실제 추론 로직은 `NotImplementedError`로 stub 상태다. 실제 프로덕션에서는 YOLO만 사용한다.
