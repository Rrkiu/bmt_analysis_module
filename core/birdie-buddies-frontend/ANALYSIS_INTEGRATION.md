# 배드민턴 분석 도구 통합 가이드

## 📋 개요

이 프로젝트는 **두 개의 독립적인 애플리케이션**을 포함합니다:

1. **Birdie Buddies 앱** (기존)
   - 배드민턴 세션 예약 및 관리
   - 인증 필요
   
2. **배드민턴 분석 도구** (신규 추가 - 2025-12-23)
   - 코트 캘리브레이션 및 비디오 분석
   - 인증 불필요 (공개 접근)

---

## 🏗️ 프로젝트 구조

```
birdie-buddies-frontend/
├── src/
│   ├── App.tsx                    # [수정됨] 메인 라우터 (두 앱 통합)
│   ├── AnalysisApp.tsx            # [추가됨] 분석 도구 앱
│   │
│   ├── pages/                     # [기존] Birdie Buddies 페이지
│   │   ├── SessionsPage.tsx
│   │   ├── LoginPage.tsx
│   │   └── ...
│   │
│   ├── pages/Analysis/            # [추가됨] 분석 도구 페이지
│   │   ├── CalibrationPage.tsx   # 코트 캘리브레이션
│   │   ├── CalibrationPage.css
│   │   └── (향후 추가 예정)
│   │
│   ├── services/
│   │   ├── api.ts                 # [기존] Birdie Buddies API
│   │   └── analysisAPI.ts         # [추가됨] 분석 엔진 API
│   │
│   ├── hooks/
│   │   └── useCalibration.ts      # [추가됨] 캘리브레이션 Hook
│   │
│   └── lib/
│       └── auth.tsx               # [기존] Birdie Buddies 인증
│
└── .env.local                     # [추가됨] 환경 변수
```

---

## 🔀 라우팅 구조

### **Birdie Buddies 앱 (인증 필요)**
```
/                    → /login으로 리다이렉트
/login               → 로그인 페이지
/sessions            → 세션 목록
/sessions/:id        → 세션 상세
/wallet              → 지갑
/my                  → 내 게임
/admin               → 관리자 페이지
```

### **분석 도구 (인증 불필요)** ⭐ 신규
```
/analysis                → /analysis/calibration으로 리다이렉트
/analysis/calibration    → 코트 캘리브레이션
/analysis/video          → 비디오 분석 (향후 구현)
/analysis/profiles       → 프로파일 관리 (향후 구현)
```

---

## 🚀 실행 방법

### **1. 의존성 설치**
```bash
npm install
```

### **2. 환경 변수 설정**
`.env.local` 파일 생성:
```bash
# Birdie Buddies API (기존 - 유지)
VITE_API_BASE_URL=http://localhost:8000

# 분석 엔진 API (신규 - 별도 환경 변수)
VITE_ANALYSIS_API_BASE_URL=http://localhost:8000
```

**중요**: 
- `VITE_API_BASE_URL`: Birdie Buddies 앱용 (기존 설정 유지)
- `VITE_ANALYSIS_API_BASE_URL`: 분석 도구용 (신규 추가)
- 현재는 두 API가 같은 백엔드(localhost:8000)를 사용하지만, 향후 분리 가능

### **3. 개발 서버 실행**

**Node.js 버전 요구사항: 20.19 이상**

```bash
# nvm 사용 시
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm use 20

# 개발 서버 실행
npm run dev
```

또는 편의 스크립트 사용:
```bash
./dev.sh
```

### **4. 브라우저 접속**
```
# Birdie Buddies 앱
http://localhost:5173/login

# 분석 도구 (인증 불필요)
http://localhost:5173/analysis/calibration
```

---

## 🔧 백엔드 연동

### **분석 도구 백엔드**

분석 도구는 별도의 FastAPI 백엔드와 통신합니다:

```bash
# 백엔드 실행 (별도 터미널)
cd ../backend
python3 main.py  # Port 8000
```

### **API 엔드포인트**

분석 도구가 사용하는 주요 API:

```typescript
POST /api/upload              // 이미지 업로드
POST /api/align-corners       // 캘리브레이션
POST /api/analysis/frame-predict  // 프레임 분석
GET  /api/videos/list         // 비디오 목록
```

자세한 API 명세: `src/services/analysisAPI.ts` 참조

---

## 📝 주요 변경 사항 (2025-12-23)

### **1. App.tsx**
- **변경**: 두 앱을 통합하는 라우팅 구조 추가
- **추가**: `/analysis/*` 경로 (인증 불필요)
- **유지**: 기존 Birdie Buddies 라우팅 (인증 필요)

### **2. AnalysisApp.tsx** (신규)
- 분석 도구 전용 앱 컴포넌트
- 자체 네비게이션 및 라우팅
- AuthProvider와 독립적

### **3. CalibrationPage.tsx** (신규)
- 코트 캘리브레이션 UI
- Canvas 기반 4점 코너 선택
- 백엔드 API 연동

### **4. analysisAPI.ts** (신규)
- 분석 엔진 백엔드 API 클라이언트
- TypeScript 타입 정의 포함

### **5. useCalibration.ts** (신규)
- 캘리브레이션 상태 관리 Hook
- 이미지 업로드, 코너 선택, API 호출 로직

---

## ⚠️ 머지 시 주의사항

### **충돌 가능성이 높은 파일**
1. `src/App.tsx` - 라우팅 구조 변경
2. `package.json` - 의존성 추가 가능성

### **머지 전 확인 사항**
- [ ] `/analysis/*` 라우트가 `RequireAuth`로 감싸지지 않았는지 확인
- [ ] `AnalysisApp.tsx` import가 정상적으로 추가되었는지 확인
- [ ] `.env.local` 파일이 `.gitignore`에 포함되어 있는지 확인
- [ ] 기존 Birdie Buddies 라우팅이 정상 동작하는지 테스트

### **머지 후 테스트**
```bash
# 1. Birdie Buddies 앱 테스트
http://localhost:5173/login

# 2. 분석 도구 테스트
http://localhost:5173/analysis/calibration

# 3. 인증 없이 분석 도구 접근 가능한지 확인
```

---

## 🎯 향후 개발 계획

### **Phase 1: 캘리브레이션** ✅ 완료
- [x] 이미지 업로드
- [x] 4점 코너 선택
- [x] Homography 계산
- [x] 결과 표시

### **Phase 2: 비디오 분석** (진행 예정)
- [ ] 비디오 파일 업로드
- [ ] 실시간 프레임 분석
- [ ] 셔틀콕 추적 시각화
- [ ] 낙하 지점 판정

### **Phase 3: 프로파일 관리** (진행 예정)
- [ ] 캘리브레이션 프로파일 저장
- [ ] 프로파일 목록 조회
- [ ] 프로파일 로드 및 재사용

---

## 📚 참고 자료

### **관련 문서**
- 백엔드 API 문서: `../backend/README.md`
- 프로젝트 전체 README: `../README.md`

### **주요 파일**
- 라우팅: `src/App.tsx`, `src/AnalysisApp.tsx`
- API 클라이언트: `src/services/analysisAPI.ts`
- 캘리브레이션: `src/pages/Analysis/CalibrationPage.tsx`
- 상태 관리: `src/hooks/useCalibration.ts`

---

## 🐛 문제 해결

### **Node.js 버전 오류**
```
Error: Unsupported engine
```
**해결**: Node.js 20.19 이상으로 업그레이드
```bash
nvm install 20
nvm use 20
```

### **백엔드 연결 실패**
```
Failed to fetch
```
**해결**: 백엔드 서버 실행 확인
```bash
cd ../backend
python3 main.py
```

### **CORS 오류**
**해결**: 백엔드 `main.py`에서 CORS 설정 확인
```python
allow_origins=["http://localhost:5173"]
```

---

## 👥 기여자

- 분석 도구 통합: 2025-12-23
- 기존 Birdie Buddies 앱: (기존 팀)

---

## 📞 문의

분석 도구 관련 문의: (담당자 정보)
Birdie Buddies 앱 관련 문의: (기존 팀 정보)
