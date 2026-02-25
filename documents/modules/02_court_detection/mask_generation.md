# 코트 라인 마스크 생성 (MaskGenerator)

## 목적

자동 검출의 첫 번째 단계는 입력 이미지에서 **코트 경계선(흰색 라인)**만 분리해내는 이진 마스크를 생성하는 것이다. 이 마스크가 이후 코너 좌표 검출의 입력이 된다.

배드민턴 코트 라인은 일반적으로 흰색이며 주변 바닥과 선명하게 대비된다. 이 특성을 이용하여 세 가지 색공간에서의 "흰색 픽셀" 조건을 AND 연산으로 결합해 정밀도가 높은 마스크를 생성한다.

---

## 왜 하나의 색공간만 쓰지 않는가

단순히 RGB에서 "밝은 픽셀"을 임계값으로 잘라내면 코트 라인과 조명 반사, 흰색 광고판, 밝은 배경 등이 함께 포함된다. 반면에 세 가지 색공간에서 **동시에** 흰색 조건을 만족하는 픽셀만 선택하면 이런 노이즈를 효과적으로 제거할 수 있다.

---

## 색공간별 흰색 판별 기준

### 1. HSV (Hue, Saturation, Value)

```python
# Hue: 완전 흰색은 색조가 없으므로 체크 안 함
# Saturation < 90: 채도가 낮아야 함 (색이 없어야 = 흰색)
# Value > 150: 명도가 높아야 함 (밝아야 함)
mask_hsv = (s_ch < 90) & (v_ch > 150)
```

- **S (Saturation)**: 흰색은 무채색이므로 채도가 0에 가깝다. 채도 90 미만인 픽셀만 선택.
- **V (Value)**: 흰색은 밝다. 명도 150 이상인 픽셀만 선택.
- 이 조건은 노란색 바닥(체육관 마루 등)이나 색깔 있는 광고판을 효과적으로 제거한다.

### 2. YCbCr (Luma, Blue Chroma, Red Chroma)

```python
# Y > 200: 휘도(밝기) 성분이 높아야 함
mask_ycbcr = (y_ch > 200)
```

- **Y**: 색상과 무관한 밝기 성분. 200 이상은 매우 밝은 픽셀에 해당한다.
- 화이트 라인이 조명을 받아 반사할 때 Y 값이 급격히 높아지는 특성을 활용한다.

### 3. LAB (Lightness, A, B)

```python
# L > 200: 지각 균등 색공간에서 밝기가 높아야 함
mask_lab = (l_ch > 200)
```

- **L (Lightness)**: 인간의 시각 특성을 반영한 지각 균등 밝기. L=100이 완전 흰색에 해당한다.
- OpenCV에서 LAB의 L 채널은 `[0, 255]` 스케일로 저장되므로 L > 200은 매우 밝은 픽셀을 의미한다.

---

## AND 앙상블 (Conservative 모드)

```python
# 세 마스크를 AND 연산 → 모두 만족하는 픽셀만 흰색(255)으로 선택
mask_final = (mask_hsv & mask_ycbcr & mask_lab) * 255
```

세 조건을 모두 만족해야 최종 마스크에 포함된다. 이 방식은 **False Positive(노이즈)를 최소화**하는 대신, 일부 코트 라인이 누락될 수 있다 (False Negative 가능성). 코너 검출 알고리즘은 완벽한 마스크보다 **배경 노이즈가 없는 깨끗한 라인**에서 더 안정적이므로, 이 trade-off는 의도적인 설계 결정이다.

---

## 코드 흐름 요약

```python
# 1. 색공간 변환
hsv    = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
ycbcr  = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2YCrCb)
lab    = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2LAB)

# 2. 채널 분리
_, s_ch, v_ch = cv2.split(hsv)      # S, V 사용
y_ch, _, _    = cv2.split(ycbcr)    # Y만 사용
l_ch, _, _    = cv2.split(lab)      # L만 사용

# 3. 각 마스크 생성
mask_hsv   = (s_ch < 90) & (v_ch > 150)
mask_ycbcr = (y_ch > 200)
mask_lab   = (l_ch > 200)

# 4. AND 결합
mask_final = (mask_hsv & mask_ycbcr & mask_lab) * 255
# 결과: 0 또는 255인 이진 마스크 (H, W) uint8
```

---

## 임계값 설정 근거 (config.py에서)

```python
# conservative 모드 기준 (현재 구현된 유일한 모드)
HSV:   s_max=90,  v_min=150
YCbCr: y_min=200
LAB:   l_min=200
```

이 값들은 실내 배드민턴 코트의 LED 조명 환경에서 코트 라인을 검출하는 실험을 통해 결정된 값이다. 조명이 어둡거나 코트 상태가 나쁠 경우 임계값 조정이 필요할 수 있다.

---

## 중간 결과 저장 (디버깅용)

`save_intermediate=True`로 초기화하면 각 색공간별 마스크를 파일로 저장한다.

```
out_dir/
├── mask_hsv.png               # HSV 마스크단독 결과
├── mask_ycbcr.png             # YCbCr 마스크 단독 결과
├── mask_lab.png               # LAB 마스크 단독 결과
└── mask_ensemble_conservative.png  # AND 앙상블 최종 마스크
```

개별 마스크를 비교하여 어느 채널에서 라인 검출이 실패하는지 진단할 수 있다.

---

## 마스크 커버리지 비율 (Mask Quality 지표)

`DetectionConfidence.calculate_mask_quality()`에서 마스크 품질 점수를 계산할 때 커버리지 비율을 사용한다.

```
coverage_ratio = (흰색 픽셀 수) / (전체 픽셀 수)
```

최적 범위: **5% ~ 15%** (코트 라인이 이미지의 약 5~15% 면적을 차지)

- `< 2%`: 라인이 너무 적게 검출됨 (품질 저하)
- `2% ~ 15%`: 정상 범위 (품질 점수 1.0)
- `> 15%`: 너무 많은 픽셀이 흰색으로 검출됨 (노이즈 또는 흰 배경 포함 가능성)
