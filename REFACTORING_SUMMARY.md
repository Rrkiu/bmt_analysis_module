# 프로젝트 구조 리팩토링 완료 요약

## ✅ 완료된 작업 (2026-01-09)

### 📁 최종 구조

```
bmt_demo/
├── .gitignore              # Git 무시 설정
├── .gitattributes          # Git 속성
├── Readme.md               # 프로젝트 README
│
├── 📦 core/                # 프로덕션 코드 (Git 추적)
│   ├── backend/
│   ├── birdie-buddies-frontend/
│   ├── trackernet/
│   ├── storage/
│   └── Documents/
│
├── 🔬 experiments/         # 실험 코드 (Git 무시)
│   ├── test_yolo/
│   ├── cvat/
│   ├── stage0_1_linepixel_mask/
│   ├── stage1_courtdetection/
│   ├── _adutils/
│   └── frontend_old/
│
└── ⚙️ config/              # 설정 및 스크립트
    ├── migrate_structure.sh
    ├── migrate_structure_nobackup.sh
    ├── node_modules/
    ├── package.json
    └── package-lock.json
```

### 🎯 주요 변경사항

1. **Core 폴더 생성**: 프로덕션 코드 통합
2. **Experiments 폴더**: 실험 코드 분리
3. **Config 폴더**: 설정 파일 정리
4. **.gitignore 업데이트**: experiments/ 전체 무시

### ⚠️ WSL 이슈 해결

**문제**: `d????????? trackernet` 권한 오류
**해결**: `wsl --shutdown` 후 재시작

---

## 📋 다음 단계

### 1. Git 커밋

```bash
# 모든 변경사항 스테이징
git add -A

# 커밋
git commit -m "refactor: 프로젝트 구조를 Core/Experiments/Config로 재구성

- core/: 프로덕션 코드 (backend, frontend, trackernet, storage, Documents)
- experiments/: 실험 코드 (test_yolo, cvat, stage*, _adutils, frontend_old)
- config/: 설정 파일 및 스크립트
- .gitignore 업데이트: experiments/ 전체 무시
- README 최상단 유지"

# 푸시
git push origin dev
```

### 2. 경로 업데이트 (필요시)

#### 백엔드 실행
```bash
cd core/backend
python main.py
```

#### 프론트엔드 실행
```bash
cd core/birdie-buddies-frontend
npm run dev
```

#### TrackNet 실행
```bash
cd core/trackernet
sh tracknet.sh
```

### 3. 실험 코드 접근
```bash
cd experiments/test_yolo
# 기존과 동일하게 사용
```

---

## 🔍 검증 체크리스트

- [x] Core 폴더에 모든 프로덕션 코드 이동
- [x] Experiments 폴더에 실험 코드 이동
- [x] Config 폴더에 설정 파일 이동
- [x] .gitignore, .gitattributes, README 최상단 유지
- [x] trackernet 정상 복사 (WSL 재시작 후)
- [ ] Git 커밋 및 푸시
- [ ] 백엔드 정상 동작 확인
- [ ] 프론트엔드 정상 동작 확인
- [ ] TrackNet 정상 동작 확인

---

## 💡 장점

1. **깔끔한 Git 저장소**: Core 코드만 추적
2. **명확한 구분**: 프로덕션 vs 실험 vs 설정
3. **장기 유지보수 용이**: 구조화된 프로젝트
4. **실험 자유도**: experiments에서 자유롭게 작업

---

## 🛠️ 롤백 방법 (필요시)

```bash
# Git으로 복원
git reset --hard HEAD

# 또는 이전 커밋으로
git reset --hard <commit-hash>
```
