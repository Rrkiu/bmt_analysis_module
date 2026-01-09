# 배드민턴 분석 시스템 (Badminton Analysis System)

배드민턴 코트 캘리브레이션 및 셔틀콕 추적 분석 시스템

## 📋 프로젝트 개요

이 시스템은 배드민턴 경기 영상을 분석하여 다음 기능을 제공합니다:
- **코트 캘리브레이션**: 4점 코너 기반 호모그래피 변환
- **셔틀콕 추적**: TrackNet 기반 실시간 추적
- **라인콜 판정**: 낙하 지점 자동 판정 (IN/OUT)
- **비디오 분석**: 프레임 단위 분석 및 시각화

---

## 🏗️ 프로젝트 구조

```
bmt_demo/
├── backend/                    # FastAPI 백엔드 서버
│   ├── main.py                # API 엔드포인트
│   ├── calibration_service.py # 캘리브레이션 로직
│   ├── video_analysis_service.py # 비디오 분석
│   ├── tracknet_service.py    # TrackNet 통신
│   ├── shuttlecock_tracker.py # 낙하 감지
│   ├── visualization_service.py # 시각화
│   └── geometry.py            # 호모그래피 변환
│
├── birdie-buddies-frontend/   # React + TypeScript 프론트엔드
│   ├── src/
│   │   ├── pages/Analysis/    # 분석 도구 페이지
│   │   ├── services/          # API 클라이언트
│   │   └── hooks/             # React Hooks
│   └── dev.sh                 # 개발 서버 실행 스크립트
│
├── trackernet/                # TrackNet 모델 서버
│   ├── TrackNetV3/
│   │   ├── inference_server.py # ZeroMQ 추론 서버
│   │   ├── model.py           # 모델 정의
│   │   └── ckpts/             # 모델 가중치 (.pt)
│   └── tracknet.sh            # Docker 실행 스크립트
│
├── storage/                   # 런타임 데이터 저장소
│   ├── videos/                # 분석용 비디오
│   ├── uploads/               # 업로드 이미지
│   ├── results/               # 분석 결과
│   └── calibrations/          # 캘리브레이션 프로파일
│
├── test_yolo/                 # YOLO 실험 (코트 검출)
│   └── yolov11_pose/          # Pose estimation 실험
│
└── Documents/                 # 프로젝트 문서
```

---

## 🚀 빠른 시작

### **1. 의존성 설치**

#### 백엔드
```bash
cd backend
pip install -r requirements.txt
```

#### 프론트엔드
```bash
cd birdie-buddies-frontend
npm install
```

### **2. TrackNet 모델 서버 실행**

```bash
# Docker 이미지 빌드 (최초 1회)
cd trackernet/TrackNetV3
docker build -t tracknet_inference:2512 .

# 컨테이너 실행
cd ../
sh tracknet.sh
```

### **3. 백엔드 서버 실행**

```bash
cd backend
python main.py
# 서버: http://localhost:8000
```

### **4. 프론트엔드 실행**

```bash
cd birdie-buddies-frontend
sh dev.sh
# 또는: npm run dev
# 프론트엔드: http://localhost:5173
```

### **5. 분석 페이지 접속**

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
│  백엔드 (FastAPI)                                       │
│  Port: 8000                                             │
│  - 이미지 업로드 & 캘리브레이션                         │
│  - 비디오 분석 & 프레임 처리                            │
└────────────────┬────────────────────────────────────────┘
                 │ ZeroMQ (tcp://localhost:8002)
                 ▼
┌─────────────────────────────────────────────────────────┐
│  TrackNet API (Docker)                                  │
│  Port: 8002                                             │
│  - 셔틀콕 위치 추적 (딥러닝 추론)                      │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 주요 기능

### **1. 코트 캘리브레이션**
- 4개 코너 클릭으로 호모그래피 행렬 계산
- 이미지 좌표 ↔ 실세계 좌표 변환
- BWF 공식 배드민턴 코트 규격 기준 (5.18m × 6.7m)

### **2. 셔틀콕 추적**
- TrackNet V3 기반 실시간 추적
- 프레임 단위 위치 예측
- 궤적 시각화

### **3. 낙하 감지**
- 정지 상태 감지 (10px, 4프레임 기준)
- 자동 라인콜 판정 (IN/OUT)
- 미니맵 표시

### **4. 시각화**
- 메인 화면: 낙하 지점 마킹
- 미니맵: 실세계 좌표 평면도
- 판정 텍스트: IN/OUT 표시

---

## 📝 API 엔드포인트

### **캘리브레이션**
```
POST /api/upload              # 이미지 업로드
POST /api/align-corners       # 4점 코너 캘리브레이션
GET  /api/result/{session_id} # 결과 조회
```

### **비디오 분석**
```
POST /api/analysis/frame-predict  # 프레임 단위 분석
POST /api/analysis/process-video  # 비디오 일괄 처리
GET  /api/videos/list             # 비디오 목록
```

### **프로파일 관리**
```
POST   /api/calibration/profile        # 프로파일 저장
GET    /api/calibration/profiles       # 프로파일 목록
GET    /api/calibration/profile/{id}   # 프로파일 조회
DELETE /api/calibration/profile/{id}   # 프로파일 삭제
```

---

## 🔧 개발 환경

### **필수 요구사항**
- Python 3.8+
- Node.js 20+
- Docker (TrackNet용)
- CUDA (GPU 추론용, 권장)

### **주요 라이브러리**
- **백엔드**: FastAPI, OpenCV, NumPy, PyTorch
- **프론트엔드**: React 19, TypeScript, Vite
- **모델**: TrackNet V3

---

## 📂 데이터 관리

### **Git 추적 대상**
- ✅ 소스 코드 (`backend/`, `birdie-buddies-frontend/`)
- ✅ 설정 파일 (`*.json`, `*.sh`)
- ✅ 문서 (`README.md`, `Documents/`)

### **Git 무시 대상**
- ❌ 모델 가중치 (`*.pt`, `*.pth`)
- ❌ 데이터셋 (`test_yolo/dataset/`)
- ❌ 런타임 데이터 (`storage/`)
- ❌ 실험 결과 (`runs/`, `results/`)

---

## 🐛 문제 해결

### **TrackNet 연결 실패**
```bash
# 컨테이너 상태 확인
docker ps | grep tracknet_api

# 재시작
docker restart tracknet_api
```

### **포트 충돌**
- 8000: 백엔드 FastAPI
- 8002: TrackNet ZeroMQ
- 5173: 프론트엔드 Vite

### **모델 파일 없음**
TrackNet 모델 파일 필요:
- 경로: `trackernet/TrackNetV3/ckpts/TrackNet_best.pt`
- 별도 다운로드 필요 (Git LFS 또는 외부 링크)

---

## 📚 참고 문서

- [API 연동 가이드](Documents/)
- [프론트엔드 통합 가이드](birdie-buddies-frontend/ANALYSIS_INTEGRATION.md)
- [TrackNet 논문](https://arxiv.org/abs/2004.10569)

---

## 🔄 개발 상태

- ✅ **Phase 1**: 코트 캘리브레이션 (완료)
- ✅ **Phase 2**: 셔틀콕 추적 (완료)
- ✅ **Phase 3**: 낙하 감지 & 라인콜 (완료)
- 🔄 **Phase 4**: YOLO 기반 코트 자동 검출 (진행 중)
- 📋 **Phase 5**: 통계 분석 & 리포트 (예정)

---

## 📞 문의

프로젝트 관련 문의: [담당자 정보]

---

## 📄 라이선스

[라이선스 정보]
