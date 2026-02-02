# 배드민턴 분석 시스템 (Badminton Analysis System)

배드민턴 코트 캘리브레이션 및 셔틀콕 추적 분석 시스템

## 📋 프로젝트 개요

이 시스템은 배드민턴 경기 영상을 분석하여 다음 기능을 제공합니다:
- **코트 캘리브레이션**: 4점 코너 기반 호모그래피 변환 및 자동 코트 검출
- **셔틀콕 추적**: YOLOv11 / TrackNet 기반 실시간 추적 (30fps 지원)
- **라인콜 판정**: 낙하 지점 자동 판정 (IN/OUT)
- **비디오 분석**: 프레임 단위 분석 및 시각화

---

## 🏗️ 프로젝트 구조

```
bmt_demo/
├── core/
│   ├── backend/                    # FastAPI 백엔드 서버
│   │   ├── main.py                # API 엔드포인트
│   │   ├── modules/
│   │   │   ├── analysis/          # 통합 분석 서비스
│   │   │   ├── calibration/       # 캘리브레이션 모듈
│   │   │   ├── court_detection/   # 코트 검출 모듈
│   │   │   └── shuttlecock_detection/ # 셔틀콕 검출 모듈 (New!)
│   │   │       ├── adapters/      # YOLO/TrackNet 어댑터
│   │   │       ├── models/        # 모델 구현체
│   │   │       └── weights/       # 모델 가중치
│   │   └── performance_profiler.py # 성능 벤치마킹 도구
│   │
│   ├── birdie-buddies-frontend/   # React + TypeScript 프론트엔드
│   │   ├── src/
│   │   │   ├── pages/Analysis/    # 분석 도구 페이지
│   │   │   ├── services/          # API 클라이언트
│   │   │   └── hooks/             # React Hooks (useVideoAnalysis)
│   │   └── dev.sh                 # 개발 서버 실행 스크립트
│   │
│   └── trackernet/                # TrackNet 모델 서버 (Legacy)
│       └── TrackNetV3/            # TrackNet 구현체
│
├── storage/                   # 런타임 데이터 저장소
│   ├── videos/                # 분석용 비디오
│   ├── uploads/               # 업로드 이미지
│   ├── results/               # 분석 결과
│   └── calibrations/          # 캘리브레이션 프로파일
│
├── experiments/               # 실험 및 연구
│   └── shuttlecock_detection/ # YOLO 학습 실험
│
└── Documents/                 # 프로젝트 문서
```

---

## 🚀 빠른 시작

### **1. 의존성 설치**

#### 백엔드
```bash
cd core/backend
pip install -r requirements.txt
pip install ultralytics  # YOLO 실행을 위해 필요
```

#### 프론트엔드
```bash
cd core/birdie-buddies-frontend
npm install
```

### **2. 백엔드 서버 실행**

YOLO 모델을 사용하여 서버를 실행합니다 (권장).

```bash
cd core/backend
python main.py --detector yolo
# 서버: http://localhost:8000
```
> **Tip**: `--detector tracknet` 옵션을 사용하면 기존 TrackNet 모델을 사용할 수 있습니다.

### **3. 프론트엔드 실행**

```bash
cd core/birdie-buddies-frontend
sh dev.sh
# 또는: npm run dev
# 프론트엔드: http://localhost:5173
```

### **4. 분석 페이지 접속**

```
http://localhost:5173/analysis
```

---

## 📊 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│  프론트엔드 (React)                                     │
│  Port: 5173                                             │
└────────────────┬────────────────────────────────────────┘
                 │ HTTP REST API
                 ▼
┌─────────────────────────────────────────────────────────┐
│  백엔드 (FastAPI) [Port: 8000]                          │
│                                                         │
│  [VideoAnalysisService]                                 │
│         │                                               │
│         ▼                                               │
│  [ShuttlecockDetectorAdapter]                           │
│     │              │                                    │
│     ▼              ▼                                    │
│  [YOLOv11]      [TrackNet]                              │
│  (Internal)     (External)                              │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 주요 기능

### **1. 코트 캘리브레이션 & 자동 검출**
- 4개 코너 클릭으로 호모그래피 행렬 계산
- 이미지 기반 코트 자동 검출 기능
- BWF 공식 배드민턴 코트 규격 기준 (5.18m × 6.7m)

### **2. 셔틀콕 추적 (YOLOv11 통합)**
- **YOLOv11n** 기반의 고속/고성능 셔틀콕 검출
- **30fps 실시간 분석** 지원 (기존 15fps에서 향상)
- 다중 셔틀콕 검출 및 시각화 (메인/보조 구분)
- 낮은 Confidence Threshold(0.3)로 작은 물체 검출 강화

### **3. 낙하 감지**
- 정지 상태 감지 및 낙하 지점 좌표 계산
- 자동 라인콜 판정 (IN/OUT)
- 미니맵을 통한 실시간 위치 표시

### **4. 향상된 시각화**
- 검출된 모든 객체 표시 (주황색) 및 메인 객체 강조 (노란색)
- 신뢰도(Confidence) 점수 표시
- 직관적인 오버레이 UI

---

## 📝 API 엔드포인트

### **캘리브레이션**
```
POST /api/upload              # 이미지 업로드
POST /api/detect-court-auto   # 코트 자동 검출
POST /api/align-corners       # 4점 코너 캘리브레이션
GET  /api/result/{session_id} # 결과 조회
```

### **비디오 분석**
```
POST /api/analysis/frame-predict  # 프레임 단위 분석 (YOLO/TrackNet)
POST /api/analysis/process-video  # 비디오 일괄 처리
GET  /api/videos/list             # 비디오 목록
```

---

## 🔧 개발 환경

### **필수 요구사항**
- Python 3.10+
- Node.js 20+
- CUDA (GPU 가속 권장, YOLO 실행 시 성능 향상)
- Docker (TrackNet 사용 시에만 필요)

### **주요 라이브러리**
- **백엔드**: FastAPI, OpenCV, NumPy, PyTorch, Ultralytics (YOLO)
- **프론트엔드**: React 19, TypeScript, Vite
- **모델**: YOLOv11n (Custom Trained), TrackNet V3

---

## 📂 데이터 관리

### **Git 추적 대상**
- ✅ 소스 코드 (`core/`)
- ✅ 설정 파일 (`*.json`, `*.sh`)
- ✅ 문서 (`README.md`, `Documents/`)

### **Git 무시 대상**
- ❌ 모델 가중치 (`*.pt`, `*.pth`)
- ❌ 데이터셋 (`test_yolo/dataset/`)
- ❌ 런타임 데이터 (`storage/`)
- ❌ 실험 결과 (`runs/`, `results/`)

---

## 🐛 문제 해결

### **YOLO 모델 로드 실패**
```bash
# ultralytics 설치 확인
pip install ultralytics

# 가중치 파일 확인
ls core/backend/modules/shuttlecock_detection/weights/
```

### **TrackNet 연결 실패**
TrackNet을 사용하는 경우에만 Docker 컨테이너가 필요합니다.
```bash
cd core/trackernet/TrackNetV3
docker build -t tracknet_inference:2512 .
sh ../tracknet.sh
```

---

## 📚 참고 문서

- [셔틀콕 검출 모듈 문서](core/backend/modules/shuttlecock_detection/README.md)
- [다중 검출 시각화 가이드](core/backend/modules/shuttlecock_detection/MULTI_DETECTION_VISUALIZATION.md)
- [API 연동 가이드](Documents/)