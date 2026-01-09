# 프로젝트 구조 리팩토링 가이드

## 📅 리팩토링 일자: 2026-01-09

---

## 🎯 목표 구조

```
bmt_demo/
├── 📦 Core (프로덕션 코드 - Git 추적)
│   ├── backend/
│   ├── birdie-buddies-frontend/
│   ├── trackernet/
│   ├── storage/
│   └── Documents/
│
├── 🔬 experiments/ (실험 코드 - Git 무시)
│   ├── test_yolo/
│   ├── cvat/
│   ├── stage0_1_linepixel_mask/
│   ├── stage1_courtdetection/
│   ├── _adutils/
│   └── frontend_old/
│
└── 📝 Config
    ├── .gitignore
    ├── .gitattributes
    ├── README.md
    └── migrate_structure.sh
```

---

## ✅ 실행 방법

### **자동 마이그레이션 (추천)**

```bash
cd /mnt/b/cd_p/bmt_demo

# 스크립트 실행 권한 부여
chmod +x migrate_structure.sh

# 실행
bash migrate_structure.sh
```

### **수동 마이그레이션**

```bash
# 1. 백업
tar -czf ../bmt_demo_backup_$(date +%Y%m%d).tar.gz .

# 2. experiments 폴더 생성
mkdir -p experiments

# 3. 실험 코드 이동
mv test_yolo experiments/
mv cvat experiments/
mv stage0_1_linepixel_mask experiments/
mv stage1_courtdetection experiments/
mv _adutils experiments/
mv frontend experiments/frontend_old/  # 구버전

# 4. .gitignore 업데이트 (이미 완료)

# 5. Git 커밋
git add -A
git commit -m "refactor: 프로젝트 구조를 Core/Experiments로 재구성"
git push origin dev
```

---

## 🔍 영향도 분석

### **Import 경로 영향**

✅ **영향 없음** - Core와 Experiments 간 의존성 없음

- `backend/` ← `test_yolo/` **의존성 없음**
- `birdie-buddies-frontend/` ← `test_yolo/` **의존성 없음**
- `trackernet/` **독립적**

### **Docker 볼륨 마운트**

⚠️ **확인 필요** - 일부 스크립트 수정 필요

```bash
# 기존
-v $(pwd)/test_yolo:/workspace/test_yolo

# 변경 후
-v $(pwd)/experiments/test_yolo:/workspace/test_yolo
```

**영향받는 파일**:
- `experiments/test_yolo/run_docker.sh`
- `experiments/test_yolo/yolov11_pose/run_docker.sh`

---

## 📋 리팩토링 후 체크리스트

### **1. 백엔드 테스트**
```bash
cd backend
python main.py
# 서버 정상 시작 확인
```

### **2. 프론트엔드 테스트**
```bash
cd birdie-buddies-frontend
npm run dev
# http://localhost:5173 접속 확인
```

### **3. TrackNet 테스트**
```bash
cd trackernet
sh tracknet.sh
# Docker 컨테이너 정상 시작 확인
```

### **4. Git 상태 확인**
```bash
git status
# experiments/ 폴더가 무시되는지 확인
```

### **5. 실험 코드 접근**
```bash
# 실험 코드는 여전히 로컬에서 사용 가능
cd experiments/test_yolo
python split_pose_dataset.py
```

---

## 🔄 롤백 방법

### **문제 발생 시**

```bash
# 백업에서 복원
cd /mnt/b/cd_p
tar -xzf bmt_demo_backup_YYYYMMDD_HHMMSS.tar.gz -C bmt_demo/

# Git 변경사항 취소
cd bmt_demo
git reset --hard HEAD
```

---

## 📊 변경 사항 요약

### **이동된 폴더**
- ✅ `test_yolo/` → `experiments/test_yolo/`
- ✅ `cvat/` → `experiments/cvat/`
- ✅ `stage0_1_linepixel_mask/` → `experiments/`
- ✅ `stage1_courtdetection/` → `experiments/`
- ✅ `_adutils/` → `experiments/`
- ✅ `frontend/` → `experiments/frontend_old/`

### **Git 추적 변경**
- ✅ `experiments/` 전체 무시
- ✅ Core 코드만 추적
- ✅ 실험 코드는 로컬에서만 유지

### **장점**
- 🎯 깔끔한 Git 저장소
- 🔬 실험 코드 분리
- 📦 프로덕션 코드 명확화
- 🚀 장기 유지보수 용이

---

## 🛠️ 추가 작업 (선택)

### **experiments/ 내부 정리**

```bash
cd experiments

# README 추가
cat > README.md << 'EOF'
# Experiments

이 폴더는 실험 및 개발 코드를 포함합니다.
Git에 추적되지 않으며, 로컬에서만 유지됩니다.

## 폴더 구조
- test_yolo/ - YOLO 기반 코트 검출 실험
- cvat/ - CVAT 라벨링 도구
- stage*/ - 디버그 출력
- _adutils/ - 유틸리티
- frontend_old/ - 구버전 프론트엔드
EOF
```

### **Docker 스크립트 업데이트**

```bash
# experiments/test_yolo/run_docker.sh 수정
# 경로를 상대 경로로 변경
```

---

## 📝 커밋 메시지 템플릿

```
refactor: 프로젝트 구조를 Core/Experiments로 재구성

- experiments/ 폴더 생성 및 실험 코드 이동
- test_yolo, cvat, stage*, _adutils 이동
- 구버전 frontend를 frontend_old로 보관
- .gitignore 업데이트 (experiments/ 전체 무시)
- 프로덕션 코드와 실험 코드 명확히 분리

장점:
- Git 저장소 깔끔하게 유지
- 장기 프로젝트 유지보수 용이
- Core와 Experiments 명확한 구분
```

---

## 🎯 다음 단계

1. ✅ 리팩토링 실행
2. ✅ 테스트 수행
3. ✅ Git 커밋 & 푸시
4. 📋 팀원에게 구조 변경 공지
5. 📚 문서 업데이트
