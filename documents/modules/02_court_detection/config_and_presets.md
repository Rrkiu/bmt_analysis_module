# 설정 파라미터 및 프리셋 (config.py)

## 개요

`config.py`에는 두 가지 핵심 요소가 포함되어 있다:
1. **`DEFAULT_CONFIG`**: 마스크 생성 및 코너 검출의 기본 파라미터 딕셔너리
2. **`PRESETS`**: 코트 환경별로 최적화된 파라미터 묶음

---

## 파라미터 전체 구조

```python
DEFAULT_CONFIG = {
    'mask': { ... },       # 마스크 생성 파라미터
    'detection': { ... },  # 코너 검출 파라미터
    'endpoint': { ... },   # 코너 엔드포인트 계산 파라미터
    'visualization': {...} # 시각화 옵션
}
```

---

## 마스크 파라미터 (mask)

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `ensemble_mode` | `conservative` | 마스크 앙상블 모드 |

### 색공간별 임계값

```python
# HSV: 채도(S)와 명도(V)로 흰색 픽셀 선택
'hsv': {
    'conservative': {'s_max': 50, 'v_min': 180},   # 더 엄격 (MaskGenerator 구현과 다름)
    'moderate':     {'s_max': 70, 'v_min': 170},
    'aggressive':   {'s_max': 90, 'v_min': 150},   # MaskGenerator 구현값과 일치
}

# YCbCr: 휘도(Y)로 선택
'ycbcr': {
    'conservative': {'y_min': 200},
    'moderate':     {'y_min': 190},
    'aggressive':   {'y_min': 180},
}

# LAB: 밝기(L)로 선택
'lab': {
    'conservative': {'l_min': 200},
    'moderate':     {'l_min': 190},
    'aggressive':   {'l_min': 180},
}
```

> **주의**: `config.py`의 임계값과 `MaskGenerator` 내부 하드코딩 값이 일부 차이가 있다. 현재 `MaskGenerator`는 파라미터를 `config.py`에서 읽지 않고 내부에 고정된 값(`s_max=90, v_min=150`)을 사용한다. `config.py`는 향후 파라미터 외부화를 위한 준비 구조다.

### 형태학적 파라미터

| 파라미터 | 값 | 설명 |
|---------|----|------|
| `open_kernel_size` | 3 | 열기 연산 커널 크기 (노이즈 제거) |
| `close_kernel_size` | 7 | 닫기 연산 커널 크기 (라인 연결) |
| `min_component_area` | 80 | 최소 연결 성분 면적 (너무 작은 노이즈 제거) |

---

## 검출 파라미터 (detection)

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `bottom_ratio` | 0.25 | 씨앗점 추출 하단 구역 비율 |
| `seed_y_bin` | 10 | 씨앗 추출 Y 슬라이스 크기 (픽셀) |
| `seed_tolerance` | 10.0 | 씨앗 기준선 X 범위 (픽셀) |
| `extend_dist_th` | 8.0 | 씨앗 라인 기준 최대 거리 |
| `extend_x_tolerance` | 15.0 | 연장 시 X 허용 범위 (픽셀) |
| `continuity_th` | 25.0 | 슬라이스 간 최대 X 점프 |
| `extend_y_bin` | 15 | 연장 시 Y 슬라이스 크기 |
| `k_neighbors` | 12 | 선형성 체크 이웃 수 |
| `linearity_th` | 4.0 | 선형성 최대 잔차 (픽셀) |
| `final_ransac_dist_th` | 3.0 | RANSAC 인라이어 거리 임계값 |
| `final_ransac_iter` | 500 | RANSAC 반복 횟수 |
| `horiz_kernel_ratio` | 0.25 | 수평 제거 커널 너비 비율 |
| `horiz_iter` | 1 | 수평 제거 형태학 반복 횟수 |

---

## 엔드포인트 파라미터 (endpoint)

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `use_extrapolation` | False | 라인 범위 밖 외삽 여부 |
| `top_margin` | 0.02 | 상단 코너 y = `top_margin * H` |
| `bot_margin` | 0.02 | 하단 코너 y = `(1 - bot_margin) * H` |
| `max_top_y_diff` | 90.0 | TL.y - TR.y 최대 허용 차이 (픽셀) |

---

## 환경별 프리셋 (PRESETS)

다양한 코트 환경에 맞게 미리 정의된 파라미터 조합이다.

```python
PRESETS = {
    'pro_indoor': {            # 전문 실내 코트 (균일 조명, 선명한 라인)
        'mask': {'ensemble_mode': 'conservative'},
        'endpoint': {'use_extrapolation': False},
    },
    'amateur': {               # 아마추어 코트 (조명 불균일, 라인 마모)
        'mask': {'ensemble_mode': 'moderate'},
        'endpoint': {'use_extrapolation': True},
    },
    'high_angle': {            # 고각도 카메라 (이미지 내 코트 비율 작음)
        'mask': {'ensemble_mode': 'aggressive'},
        'detection': {'bottom_ratio': 0.30},
        'endpoint': {'use_extrapolation': True},
    },
    'top_view': {              # 탑뷰 카메라
        'mask': {'ensemble_mode': 'moderate'},
        'detection': {'bottom_ratio': 0.20},
        'endpoint': {'use_extrapolation': False},
    },
}
```

### 프리셋 사용법

```python
from modules.court_detection.config import get_config

config = get_config(preset='pro_indoor')
# 변경된 파라미터만 오버라이드되고 나머지는 DEFAULT_CONFIG 값 유지
```

---

## 파라미터 튜닝 가이드

자동 검출 품질이 낮을 때 상황별 권장 조정 방향:

| 상황 | 조정 방향 |
|------|-----------|
| 마스크에 노이즈가 많음 | `s_max` 낮추기, `v_min` 높이기 |
| 코트 라인이 마스크에 잘 안 잡힘 | `s_max` 높이기, `v_min` 낮추기 → `moderate` 또는 `aggressive` 모드 시도 |
| 상단 코너가 엉뚱한 위치에 검출됨 | `max_top_y_diff` 낮추기 |
| 코너까지 라인이 추적 안 됨 | `continuity_th` 높이기, `extend_x_tolerance` 높이기 |
| 코트 일부만 촬영됨 | `use_extrapolation=True` 시도 |
| 코트 상단이 프레임 밖에 있음 | `top_margin` 조정 또는 `use_extrapolation=True` |
