# 코너 좌표 검출 (PointDetector)

## 목적

`MaskGenerator`가 만든 코트 라인 이진 마스크에서 **4개의 코트 코너(TL, TR, BR, BL)** 픽셀 좌표를 자동으로 찾는다. 전체 자동 검출 파이프라인에서 핵심적이고 가장 복잡한 단계다.

---

## 알고리즘 개요

### 전체 흐름

```
[마스크 입력 (0/255)]
       │
[Step 1] 수평 라인 성분 제거
   - 모폴로지 연산으로 가로 선 제거
   - 서비스 라인, 단식 라인 등 수평 요소 제거
   - 목표: 세로 사이드라인만 남기기
       │
[Step 2] 포인트 추출
   - 마스크에서 255인 픽셀 좌표 전부 추출
   - 최대 120,000개까지만 샘플링
       │
[Step 3] Bottom-Up 사이드라인 추출
   - 하단 25% 구역에서 왼쪽·오른쪽 사이드라인 씨앗점(seed) 선별
   - 씨앗점에서 위쪽 방향으로 라인을 따라 점들을 수집
   - 연속성 조건으로 라인에서 벗어난 점 제거
       │
[Step 4] 선형성 필터링 (k-NN 기반)
   - 인근 12개 이웃점과의 직선 오차 계산
   - 잔차 4픽셀 이상 → 제거 (노이즈)
       │
[Step 5] RANSAC 직선 피팅
   - 각 사이드라인 후보 점들에 RANSAC 적용
   - 이상치에 강건한 직선 방정식 추정
   - 거리 임계값: 3.0픽셀
       │
[Step 6] 엔드포인트 계산
   - 직선 방정식으로 이미지 상단/하단 교점 계산
   - TL = 왼쪽 라인의 상단 엔드포인트
   - BL = 왼쪽 라인의 하단 엔드포인트
   - TR = 오른쪽 라인의 상단 엔드포인트
   - BR = 오른쪽 라인의 하단 엔드포인트
       │
[반환] {'TL': [x,y], 'TR': [x,y], 'BR': [x,y], 'BL': [x,y]}
```

---

## Step 1: 수평 라인 성분 제거

배드민턴 코트에는 사이드라인(세로) 외에도 서비스 라인, 네트 라인 등 수평선이 많이 존재한다. 이 수평 요소들이 마스크에 포함되면 RANSAC 직선 피팅을 방해하므로, 먼저 제거한다.

```python
# 이미지 너비의 25%에 해당하는 길이의 수평 커널로 형태학적 열기(opening) 연산
horizontal_kernel = cv2.getStructuringElement(
    cv2.MORPH_RECT, 
    ksize=(int(W * horiz_kernel_ratio), 1)  # horiz_kernel_ratio = 0.25
)
# 수평으로 긴 구조를 제거
mask_no_horizontal = mask - cv2.morphologyEx(mask, cv2.MORPH_OPEN, horizontal_kernel)
```

너비의 25%보다 긴 수평 구조가 제거된다. 사이드라인은 주로 세로 방향이므로 이 연산의 영향을 덜 받는다.

---

## Step 2 & 3: Bottom-Up 사이드라인 추출

배드민턴 코트를 측면에서 촬영하는 표준 카메라 배치에서, 사이드라인은 이미지 하단에서 가장 넓게, 상단에서 가장 좁게 보인다 (원근 수렴). 이 특성을 이용해 **하단에서 위쪽으로** 라인을 추적한다.

```python
# bottom_ratio = 0.25: 이미지 하단 25% 구역에서 씨앗점 선별
bottom_strip = mask[int(H * (1 - bottom_ratio)):H, :]

# 왼쪽/오른쪽으로 픽셀 분포를 분석하여 두 사이드라인의 씨앗 x 좌표 추정
# seed_tolerance = 10.0: 씨앗선 기준 ±10픽셀 범위 내의 점들만 수집

# Y축을 seed_y_bin = 10 픽셀 단위로 슬라이싱하면서
# 현재 슬라이스에서 이전 슬라이스의 중심 x에서 extend_x_tolerance = 15픽셀 이내의 점들을 수집
```

연속성 체크: 인접 Y 슬라이스 사이에서 x 좌표의 점프가 `continuity_th = 25.0픽셀`을 넘으면 라인이 끊어진 것으로 판단하고 추출을 중단한다.

---

## Step 4: 선형성 필터링

수집된 각 사이드라인 점 집합에서 이상치를 제거한다. 각 점마다 가장 가까운 12개 이웃(`k_neighbors=12`)을 찾고, 이 12점에 맞는 직선에서 해당 점까지의 거리를 계산한다. 거리가 `linearity_th=4.0픽셀`을 초과하면 이상치로 간주해 제거한다.

---

## Step 5: RANSAC 직선 피팅

선형성 필터링 후 남은 점들에 RANSAC(Random Sample Consensus) 알고리즘을 적용하여 최종 직선 방정식을 추정한다.

```python
# 500번 반복, 각 반복에서 2점을 무작위 샘플링하여 직선 가설 생성
# 거리 임계값 3.0픽셀 이내의 점들이 inlier
# inlier가 가장 많은 직선을 최종 선택
final_ransac_dist_th = 3.0
final_ransac_iter = 500
```

결과로 각 사이드라인의 직선 방정식 `(기준점 p0, 방향 벡터 d)` 가 얻어진다.

---

## Step 6: 엔드포인트 계산 (코너 좌표)

직선 방정식에 이미지 경계 y 좌표를 대입하여 4개의 코너 픽셀 좌표를 계산한다.

```
use_line_equation = True (기본값)
```

- **상단 엔드포인트**: 직선과 `y = top_margin * H` 수평선의 교점 (`top_margin = 0.02`, 2%)
- **하단 엔드포인트**: 직선과 `y = (1 - bot_margin) * H` 수평선의 교점 (`bot_margin = 0.02`)

```
TL = 왼쪽 사이드라인 직선 @ y = 0.02 * H
BL = 왼쪽 사이드라인 직선 @ y = 0.98 * H
TR = 오른쪽 사이드라인 직선 @ y = 0.02 * H
BR = 오른쪽 사이드라인 직선 @ y = 0.98 * H
```

### 상단 코너 제약 조건

```python
max_top_y_diff = 90.0  # TL.y - TR.y 최대 허용 차이 (픽셀)
```

TL과 TR의 y 좌표 차이가 90픽셀을 초과하면 (`enforce_paired_top_constraint_line_equation`), 두 상단 코너의 y 좌표를 평균으로 보정한다. 이는 카메라가 완전히 정면을 향하지 않은 경우에도 합리적인 코너를 생성하기 위한 로직이다.

---

## extrapolation 옵션

```python
use_extrapolation = False  # 기본값 (API에서도 False로 고정)
```

`True`로 설정하면 실제 검출된 점 범위 밖으로 직선을 연장하여 코너를 추정한다. 코트가 카메라 프레임 일부에만 보이는 경우 유용할 수 있으나, 오차가 크게 증가할 위험이 있다. 현재 API에서는 항상 `False`로 사용한다.

---

## 레거시 코드 래핑 구조

`PointDetector`는 레거시 파일 `pl_1_ransac_cld_bup_ll_v7.py`의 함수들을 직접 임포트해서 사용한다.

```python
# point_detector.py
from pl_1_ransac_cld_bup_ll_v7 import estimate_4pts_from_mask
```

레거시 코드를 재작성하지 않고 래퍼 클래스로 감싼 이유는 "레거시 알고리즘과 100% 동일한 결과"를 보장하면서 API를 표준화하기 위해서다. 레거시 코드에서 `argparse`로 받던 파라미터들을 `PointDetectorArgs` 클래스로 대체한다.

---

## PointDetectorArgs 파라미터 전체 목록

| 파라미터 | 기본값 | 의미 |
|---------|--------|------|
| `dilate_ks` | 3 | 마스크 팽창 커널 크기 |
| `horiz_kernel_ratio` | 0.25 | 수평 제거 커널 비율 (너비 대비) |
| `max_points` | 120,000 | 추출하는 최대 픽셀 수 |
| `bottom_ratio` | 0.25 | 씨앗점 추출 하단 구역 비율 |
| `seed_y_bin` | 10 | 씨앗 추출 시 Y 슬라이스 크기 |
| `seed_tolerance` | 10.0 | 씨앗 X 범위 (픽셀) |
| `extend_dist_th` | 8.0 | 씨앗 라인에서 최대 거리 |
| `extend_x_tolerance` | 15.0 | 연장 시 X 허용 범위 |
| `continuity_th` | 25.0 | 슬라이스 간 X 점프 최대값 |
| `k_neighbors` | 12 | 선형성 체크 이웃 수 |
| `linearity_th` | 4.0 | 선형성 최대 잔차 (픽셀) |
| `final_ransac_dist_th` | 3.0 | RANSAC 인라이어 거리 임계값 |
| `final_ransac_iter` | 500 | RANSAC 반복 횟수 |
| `max_top_y_diff` | 90.0 | TL-TR y 차이 최대 허용값 |
| `use_extrapolation` | False | 범위 밖 외삽 여부 |
