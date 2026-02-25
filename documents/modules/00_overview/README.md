# Backend Architecture Overview

## 시스템 개요

이 백엔드는 배드민턴 영상 분석 시스템의 서버 파트로, **FastAPI** 기반의 REST API 서버다. 코트 캘리브레이션, 셔틀콕 검출, 비디오 분석, 시각화 등의 핵심 기능을 모듈 단위로 제공한다. 프론트엔드(React/Vite)와 통신하며, 실시간 프레임 분석 및 영상 파일 분석을 지원한다.

---

## 디렉토리 구조

```
core/backend/
├── main.py                        # FastAPI 앱 진입점, 전체 API 라우터 정의
├── constants.py                   # 배드민턴 코트 규격 상수 (BWF 기준)
├── decorators.py                  # 공통 데코레이터 (time_logger 등)
├── benchmark_performance.py       # 성능 벤치마크 스크립트
├── performance_profiler.py        # 처리 시간 프로파일링 유틸리티
├── requirements.txt               # Python 의존성 목록
├── storage/                       # 런타임 파일 저장소 (업로드, 결과, 캘리브레이션)
│   ├── uploads/                   # 업로드된 원본 이미지
│   ├── results/                   # 캘리브레이션 결과 이미지
│   ├── calibrations/              # 프로파일 디렉토리 (profile_id별)
│   │   └── {profile_id}/
│   │       ├── reference.jpg      # 참조 이미지 원본
│   │       ├── thumbnail.jpg      # 썸네일 (200x150)
│   │       └── overlay.png        # 코트 오버레이 시각화 이미지
│   ├── videos/                    # 분석 대상 비디오 파일
│   └── calibrations.db            # SQLite DB (프로파일, 세션, 낙하 기록)
├── modules/
│   ├── calibration/               # 코트 캘리브레이션 (Homography 기반)
│   ├── court_detection/           # 자동 코트 코너 검출 (CV 알고리즘)
│   ├── shuttlecock_detection/     # 셔틀콕 검출 (YOLO / TensorRT)
│   ├── tracking/                  # 셔틀콕 궤적 추적 및 낙하 감지
│   ├── analysis/                  # 비디오 분석 서비스 (프레임 단위 처리)
│   └── visualization/             # 코트 오버레이, 미니맵 렌더링
└── tests/                         # 통합 테스트
```

---

## 모듈 의존 관계

```
main.py (FastAPI)
  │
  ├── modules/calibration        ← CalibrationService, CalibrationProfileService
  │       └── geometry.py        ← HomographyTransform, CourtGeometry
  │
  ├── modules/court_detection    ← CourtDetector (자동 코트 코너 검출)
  │       └── modules/           ← MaskGenerator, PointDetector
  │
  ├── modules/analysis           ← VideoAnalysisService
  │       ├── modules/shuttlecock_detection  ← YOLODetector / TrackNetDetector
  │       ├── modules/tracking              ← ShuttlecockLandingDetector
  │       ├── modules/calibration           ← HomographyTransform, CourtGeometry
  │       └── modules/visualization         ← VisualizationService
  │
  └── modules/visualization      ← VisualizationService (court overlay, minimap)
```

---

## 핵심 모듈 요약

| 모듈 | 위치 | 주요 역할 |
|------|------|-----------|
| **calibration** | `modules/calibration/` | 이미지 4코너 좌표로 Homography 행렬 계산, 이미지↔실세계 좌표 변환, 프로파일 영속 저장 |
| **court_detection** | `modules/court_detection/` | CV 알고리즘으로 코트 라인 마스크 생성 후 코너 4점 자동 검출 |
| **shuttlecock_detection** | `modules/shuttlecock_detection/` | YOLOv8/v11 또는 TensorRT Engine으로 셔틀콕 위치 bbox 검출 |
| **tracking** | `modules/tracking/` | 검출된 셔틀콕 위치 이력 기반으로 낙하 지점 판정 |
| **analysis** | `modules/analysis/` | 비디오/웹캠 프레임을 순차 처리하며 검출·추적·시각화 파이프라인 실행 |
| **visualization** | `modules/visualization/` | 코트 오버레이, 미니맵, 코너 포인트 등 이미지 위에 렌더링 |

---

## API 구조 요약

```
GET  /                                          # 루트 (API 정보)
GET  /health                                    # 헬스체크

# 캘리브레이션 (세션 기반)
POST /api/upload                                # 이미지 업로드 → session_id 반환
POST /api/align-corners                         # 4코너 좌표로 캘리브레이션 수행
GET  /api/result/{session_id}                   # 캘리브레이션 결과 조회
GET  /api/image/{session_id}/{image_type}       # 결과 이미지 파일 반환
DELETE /api/session/{session_id}                # 세션 삭제

# 캘리브레이션 프로파일 (영속 저장)
POST   /api/calibration/profile                 # 현재 세션 → 프로파일로 저장
GET    /api/calibration/profiles                # 전체 프로파일 목록
GET    /api/calibration/profile/{profile_id}    # 단일 프로파일 데이터
PUT    /api/calibration/profile/{profile_id}    # 프로파일 이름/메타데이터 수정
DELETE /api/calibration/profile/{profile_id}    # 프로파일 삭제
GET    /api/calibration/profile/{profile_id}/image  # 참조/썸네일/오버레이 이미지

# 자동 코트 검출
POST /api/calibration/auto-detect               # 업로드 이미지에서 코트 코너 자동 검출

# 비디오 분석
GET  /api/videos                                # 분석 가능한 비디오 목록
POST /api/analyze                               # 비디오 파일 분석 실행
POST /api/predict-frame                         # 단일 프레임 실시간 분석
GET  /api/session/{session_id}/calibration      # 분석 세션의 캘리브레이션 조회

# 정적 파일
GET  /storage/{path}                            # 업로드/결과 파일 직접 접근 (StaticFiles)
```

---

## 세션 vs 프로파일 구분

**세션(Session)**: 인메모리 임시 저장. 이미지 업로드 후 캘리브레이션을 수행하는 동안만 유지된다. 서버 재시작 시 소멸한다.

**프로파일(Profile)**: SQLite DB + 파일 시스템에 영속 저장. 특정 카메라/코트 배치의 캘리브레이션 설정을 재사용하기 위해 저장한다. 프로파일 ID는 `profile_{timestamp}` 형식으로 자동 생성되거나 클라이언트가 지정할 수 있다.

---

## 코트 좌표계 정의

이 시스템에서 사용하는 실세계 좌표계는 **코트 중심(네트 중앙)을 원점(0, 0)** 으로 설정한다.

- **X축**: 코트 너비 방향 (복식 기준: -3.05m ~ +3.05m)
- **Y축**: 코트 길이 방향 (네트에서 베이스라인: 0 ~ 6.7m)
- 분석 대상은 카메라가 촬영하는 **한쪽 절반 코트(플레이어 코트)** 기준이며, 코트 4개 코너는 복식 외곽선(`DOUBLES_WIDTH = 6.1m`)을 기준으로 정의된다.

---

## 기술 스택

| 항목 | 내용 |
|------|------|
| 웹 프레임워크 | FastAPI 0.x, Uvicorn |
| 컴퓨터 비전 | OpenCV, NumPy |
| 객체 검출 | Ultralytics YOLO (YOLOv8 / YOLOv11), TensorRT |
| 영속 저장 | SQLite (calibrations.db), 로컬 파일 시스템 |
| 런타임 | Python 3.10+, CUDA (GPU 추론 시) |

---

## 환경 설정

```bash
# 백엔드 실행
cd core/backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Storage 구조는 서버 시작 시 자동 생성됨
# PROJECT_ROOT/storage/ → uploads/, results/, calibrations/, videos/
```

CORS 설정은 `main.py` 상단에 명시적으로 허용 Origin 목록이 정의되어 있다.  
개발 환경에서 Vite 서버(`localhost:5173`, `localhost:5174`)와 WSL 네트워크 주소가 포함되어 있다.
