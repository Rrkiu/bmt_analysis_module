# 코트 라인 검출 테스트

## 📁 디렉토리 구조

```
courtdetect/
├── test_config.json          # 테스트 설정 파일
├── test_court_detection.py   # 메인 테스트 스크립트
├── input/                     # 입력 이미지 (사용자가 추가)
├── output/                    # 시각화 결과 이미지
└── results/                   # 최종 결과 JSON
```

## 🎯 워크플로우 (Option 1)

```
1. 사용자가 대략적인 4개 코너 지정
   ↓
2. 해당 영역 내에서 정밀 라인 검출
   ↓
3. 검출된 라인으로 코너 재계산
   ↓
4. 사용자 확인 및 수정
   ↓
5. 최종 캘리브레이션
```

## 🔬 테스트 알고리즘

### 1. Color Filter (색상 필터링)
- HSV 색공간에서 흰색 라인 검출
- Morphology 연산으로 노이즈 제거
- Hough Transform으로 직선 검출

### 2. Canny + Hough Transform
- Gaussian Blur로 노이즈 제거
- Canny Edge Detection
- Hough Line Transform

### 3. Adaptive Threshold
- Adaptive Thresholding
- Binary 이미지 생성
- Hough Line Transform

### 4. Combined (하이브리드)
- 모든 방법의 결과 결합
- 중복 라인 제거
- 최적 라인 선택

## 📝 테스트 설정 (test_config.json)

```json
{
  "test_cases": [
    {
      "name": "sample_court_1",
      "image_path": "/absolute/path/to/image.jpg",
      "area": [
        [x1, y1],  // TL (Top-Left)
        [x2, y2],  // TR (Top-Right)
        [x3, y3],  // BR (Bottom-Right)
        [x4, y4]   // BL (Bottom-Left)
      ],
      "description": "테스트 케이스 설명"
    }
  ]
}
```

## 🚀 실행 방법

```bash
cd /mnt/b/cd_p/bmt_demo/backend/test_code/courtdetect
python test_court_detection.py
```

## 📊 출력 파일 명명 규칙

```
{test_name}_{algorithm}_{scope}_{step}_{description}.jpg

scope: full (전체 이미지) 또는 roi (ROI 영역)

예시:
- session_a95000f0_roi_roi.jpg                                    # ROI 영역 표시
- session_a95000f0_color_filter_full_step1_white_mask.jpg        # 전체 - 색상 필터
- session_a95000f0_color_filter_full_step2_detected_lines.jpg
- session_a95000f0_color_filter_roi_step1_white_mask.jpg         # ROI - 색상 필터
- session_a95000f0_color_filter_roi_step2_detected_lines.jpg
- session_a95000f0_canny_hough_full_step1_edges.jpg              # 전체 - Canny
- session_a95000f0_canny_hough_full_step2_detected_lines.jpg
- session_a95000f0_canny_hough_roi_step1_edges.jpg               # ROI - Canny
- session_a95000f0_canny_hough_roi_step2_detected_lines.jpg
- session_a95000f0_adaptive_threshold_full_step1_binary.jpg      # 전체 - Adaptive
- session_a95000f0_adaptive_threshold_full_step2_detected_lines.jpg
- session_a95000f0_adaptive_threshold_roi_step1_binary.jpg       # ROI - Adaptive
- session_a95000f0_adaptive_threshold_roi_step2_detected_lines.jpg
- session_a95000f0_combined_all_lines.jpg                        # Combined (ROI 기반)
- session_a95000f0_corner_refinement.jpg                         # 코너 정밀화
```

## 🎨 시각화 내용

각 알고리즘별로 **전체 이미지**와 **ROI 영역** 모두에 대해 다음 단계를 시각화:

### 전체 이미지 (FULL)
- 인접 코트 라인 포함
- 전체 영역에 대한 라인 검출
- 비교 및 분석용

### ROI 영역 (ROI)
- 사용자 지정 영역만
- 정밀한 코트 라인 검출
- 실제 캘리브레이션에 사용

1. **ROI 영역**: 사용자 지정 4개 코너
2. **전처리 결과**: 필터링/엣지 검출 결과 (full + roi)
3. **라인 검출**: Hough Transform 결과 (full + roi)
4. **코너 정밀화**: 검색 영역 및 최종 코너 (roi 기반)

## 📈 다음 단계

1. ✅ 기본 테스트 스크립트 완성
2. 🔄 실제 이미지로 테스트
3. 🎯 코너 정밀화 알고리즘 구현
4. 🔧 파라미터 튜닝
5. 🚀 파이프라인 통합

## 💡 사용 팁

1. **테스트 이미지 준비**: `input/` 폴더에 배드민턴 코트 이미지 저장
2. **ROI 지정**: 이미지 뷰어로 대략적인 코너 좌표 확인
3. **설정 파일 수정**: `test_config.json`에 이미지 경로와 코너 좌표 입력
4. **테스트 실행**: 스크립트 실행 후 `output/` 폴더 확인
5. **결과 비교**: 각 알고리즘의 시각화 결과 비교

## 🐛 트러블슈팅

- **이미지 로드 실패**: 절대 경로 확인
- **라인 검출 안 됨**: 파라미터 조정 (threshold, minLineLength 등)
- **노이즈 많음**: 전처리 강화 (blur, morphology)
