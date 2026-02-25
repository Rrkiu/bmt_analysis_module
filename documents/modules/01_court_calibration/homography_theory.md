# Homography 이론 및 좌표 변환

## Homography란

Homography는 한 평면에서 다른 평면으로의 투영 변환(Projective Transformation)을 나타내는 3×3 행렬이다. 이 시스템에서는 **"카메라 이미지 평면(픽셀 좌표)"** 과 **"실제 바닥 코트 평면(미터 좌표)"** 사이의 변환에 사용된다.

평면-to-평면 대응이 성립하는 이유는 코트가 완전한 평면(바닥)이고, 카메라의 렌즈 센터, 코트의 한 점, 이미지 센서의 대응 픽셀이 하나의 직선 위에 있기 때문이다. 이 조건이 충족되면 4개의 대응점 쌍만으로 고유한 Homography 행렬이 결정된다.

---

## 행렬 형태

```
H (3×3) =  | h11  h12  h13 |
           | h21  h22  h23 |
           | h31  h32  h33 |
```

이미지 좌표 `(x_img, y_img)` → 실세계 좌표 `(X_world, Y_world)` 변환:

```
[X_world * w]       [h11  h12  h13]   [x_img]
[Y_world * w]  =  H × [h21  h22  h23] × [y_img]
[    w       ]       [h31  h32  h33]   [  1  ]

X_world = (X_world * w) / w
Y_world = (Y_world * w) / w
```

`w`는 동차 좌표(Homogeneous Coordinate)의 스케일 인수로, 마지막 원소로 나눠 실제 좌표를 얻는다.

---

## OpenCV 구현 (`geometry.py`)

### Homography 행렬 계산

```python
# calibration_service.py → calibrate_from_corners() 내부
src_points = np.array(court_corners_image, dtype=np.float32)   # 이미지 좌표 4점
dst_points = np.array(court_corners_world, dtype=np.float32)   # 실세계 좌표 4점

# 4점 정확 해: method=0 (RANSAC 없이 정확한 4점 풀이)
self.homography.compute_homography(src_points, dst_points, method=0)
```

4개의 점을 사용하기 때문에 `method=0` (정확한 대수적 해)를 쓴다. `cv2.RANSAC`은 아웃라이어가 포함된 다수 점 집합에서 강건한 해를 구할 때 사용하는데, 이 시스템에서는 사용자가 직접 지정한 4점만 사용하므로 정확한 해를 직접 구하는 것이 더 적합하다.

내부적으로는 `cv2.findHomography()` 가 DLT(Direct Linear Transform) 알고리즘으로 행렬을 계산한다.

### 역행렬 계산

```python
# geometry.py → HomographyTransform.compute_homography()
self.homography_matrix, mask = cv2.findHomography(src_points, dst_points, method)
self.inv_homography_matrix = np.linalg.inv(self.homography_matrix)
```

- `homography_matrix`: 이미지 좌표 → 실세계 좌표 (forward)
- `inv_homography_matrix`: 실세계 좌표 → 이미지 좌표 (inverse)

역행렬은 시각화 시 실세계 좌표를 픽셀로 되돌릴 때 사용한다.

---

## 이미지 ↔ 실세계 좌표 변환

### 이미지 → 실세계 (`image_to_world`)

```python
def image_to_world(self, image_point: Tuple[float, float]) -> Optional[Tuple[float, float]]:
    point = np.array([[image_point[0], image_point[1]]], dtype=np.float32)
    transformed = cv2.perspectiveTransform(
        point.reshape(-1, 1, 2),
        self.homography_matrix   # forward 행렬
    )
    return (float(transformed[0][0][0]), float(transformed[0][0][1]))
```

셔틀콕의 픽셀 좌표가 입력되면 실세계 미터 좌표로 변환된다.  
이 결과로 코트 내/외 판정, 미니맵 좌표 계산이 가능해진다.

### 실세계 → 이미지 (`world_to_image`)

```python
def world_to_image(self, world_point: Tuple[float, float]) -> Optional[Tuple[float, float]]:
    point = np.array([[world_point[0], world_point[1]]], dtype=np.float32)
    transformed = cv2.perspectiveTransform(
        point.reshape(-1, 1, 2),
        self.inv_homography_matrix  # inverse 행렬
    )
    return (float(transformed[0][0][0]), float(transformed[0][0][1]))
```

실세계 기준의 코트 라인 좌표들을 이미지 픽셀 위치로 변환하여 오버레이를 그릴 때 사용한다.

---

## pixels_per_meter (픽셀/미터 비율)

Homography 행렬과는 별개로, 이미지에서 1미터가 몇 픽셀에 해당하는지를 나타내는 근사 스케일 값도 계산한다. 이는 객체 크기 추정 등 단순 계산에 활용된다.

```python
# calibration_service.py → calibrate_from_corners()
w_pixels = np.linalg.norm(src_points[0] - src_points[1])   # TL-TR 거리 (픽셀)
w_meters = CourtDimensions.DOUBLES_WIDTH                    # 6.1m
h_pixels = np.linalg.norm(src_points[0] - src_points[3])   # TL-BL 거리 (픽셀)
h_meters = CourtDimensions.TOTAL_LENGTH                     # 13.4m

pixels_per_meter = (w_pixels/w_meters + h_pixels/h_meters) / 2  # 가로/세로 평균
```

카메라 앵글에 따라 이 비율은 위치마다 달라지지만, Homography를 사용하는 주요 좌표 변환에는 이 값을 사용하지 않는다. 거리 근사 계산 등 부수적 용도로만 사용된다.

---

## 재투영 오차 (Reprojection Error)

캘리브레이션 품질을 정량적으로 평가하는 지표다. 실세계 좌표를 다시 이미지 좌표로 역투영했을 때, 원래 이미지 좌표와의 유클리드 거리 평균으로 계산한다.

```python
# calibration_profile_service.py → _calculate_reprojection_error()
corners_world_array = np.array(corners_world, dtype=np.float32).reshape(-1, 1, 2)
projected = cv2.perspectiveTransform(corners_world_array, homography)
# homography는 여기서 world→image 방향 역행렬을 사용

errors = np.sqrt(np.sum((projected.reshape(-1, 2) - corners_image_array) ** 2, axis=1))
mean_error = np.mean(errors)  # 단위: 픽셀
```

재투영 오차가 낮을수록 캘리브레이션 정확도가 높다. 이 값은 프로파일 저장 시 `validation.reprojection_error` 필드에 기록된다.

---

## 코트 유효성 검증 (`CourtGeometry.is_valid_court_shape`)

사용자가 지정한 4점이 실제 코트 형태에 가까운지 간단히 검증한다. 4점 직접 선택 방식에서는 Homography가 원근 왜곡을 모두 처리하므로, 엄격한 비율 검증보다는 극단적인 오입력만 걸러내는 방식으로 구현되어 있다.

```python
# 코트 영역이 최소 1000 제곱픽셀 이상
area = CourtGeometry.compute_court_area(corners)
if area < 1000:
    return False, "코트 영역이 너무 작습니다"

# 비율이 10:1을 넘지 않는지 확인 (명백한 오입력 방지)
ratio = max(height / width, width / height)
if ratio > 10.0:
    return False, f"코트 비율이 극단적입니다 (ratio: {ratio:.2f})"
```
