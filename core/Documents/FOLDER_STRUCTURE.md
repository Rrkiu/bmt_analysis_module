# 폴더 구조 정리 가이드

## 📁 현재 상태 (2026-01-09)

### 핵심 프로덕션 코드 (Git 추적)
- `backend/` - FastAPI 백엔드
- `birdie-buddies-frontend/` - React 프론트엔드
- `trackernet/` - TrackNet 모델 서버
- `Documents/` - 프로젝트 문서

### 실험/개발 코드 (Git 무시)
- `test_yolo/` - YOLO 실험 (코트 검출)
- `cvat/` - CVAT 라벨링 도구
- `stage0_1_linepixel_mask/` - 디버그 출력
- `stage1_courtdetection/` - 디버그 출력
- `_adutils/` - 유틸리티

### 런타임 데이터 (Git 무시)
- `storage/` - 업로드, 결과, 비디오

---

## 🎯 정리 옵션

### Option 1: 최소 개입 (추천 ⭐)
**현재 상태 유지 + .gitignore 개선**

장점:
- 안전하고 빠름
- 기존 작업 방해 없음
- 실험 코드 보존

단점:
- 로컬 디렉토리는 여전히 복잡

실행:
```bash
# .gitignore 이미 업데이트됨
git status  # 추적 파일 확인
```

---

### Option 2: 실험 폴더 통합
**test_yolo, cvat 등을 experiments/ 폴더로 이동**

장점:
- 깔끔한 루트 디렉토리
- 명확한 구분

단점:
- 경로 변경 필요
- 스크립트 수정 필요

실행:
```bash
mkdir experiments
mv test_yolo experiments/
mv cvat experiments/
mv stage0_1_linepixel_mask experiments/
mv stage1_courtdetection experiments/
```

---

### Option 3: 브랜치 분리
**실험 코드를 별도 브랜치로 관리**

장점:
- main/dev 브랜치 깔끔
- 필요시 체크아웃

단점:
- 브랜치 관리 복잡도 증가

실행:
```bash
git checkout -b experiments
git add test_yolo/ cvat/
git commit -m "Move experiments to separate branch"
git checkout dev
```

---

## 📋 추천 전략

### 개발 중 (현재)
**Option 1 사용**
- .gitignore로 실험 코드 제외
- 로컬에서는 모든 폴더 유지
- Git에는 핵심 코드만 추적

### 프로젝트 완성 후
**Option 2 또는 별도 저장소**
- 실험 코드를 experiments/ 또는 별도 repo로 이동
- 프로덕션 코드만 메인 repo에 유지

---

## 🗂️ 이상적인 최종 구조

```
bmt_demo/
├── backend/
├── frontend/
├── trackernet/
├── docs/
├── scripts/
├── .github/
│   └── workflows/
├── docker-compose.yml
├── README.md
└── .gitignore
```

---

## 📝 체크리스트

- [x] .gitignore 업데이트
- [x] README.md 재작성
- [ ] 불필요한 파일 삭제 결정
- [ ] 실험 코드 정리 방법 선택
- [ ] Git 커밋 & 푸시

---

## 🔧 유지보수 팁

### 정기적으로 확인
```bash
# 추적되지 않는 대용량 파일 찾기
find . -type f -size +100M -not -path "./.git/*"

# Git 추적 파일 확인
git ls-files

# 디스크 사용량 확인
du -sh */ | sort -hr
```

### 데이터셋 관리
- 대용량 데이터는 Git LFS 사용
- 또는 외부 스토리지 (Google Drive, S3)
- README에 다운로드 링크 명시

### 모델 가중치
- GitHub Release에 업로드
- 또는 Hugging Face Model Hub
- 자동 다운로드 스크립트 제공
