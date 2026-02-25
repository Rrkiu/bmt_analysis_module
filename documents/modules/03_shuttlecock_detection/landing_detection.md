# 셔틀콕 위치 추적 및 낙하 판정

## 목적

YOLO가 각 프레임에서 셔틀콕의 픽셀 좌표 `(x, y)`를 검출하면, 다음 단계는 이 좌표들의 **시간적 변화 패턴**을 분석하여 셔틀콕이 코트 바닥에 착지했는지 판정하는 것이다. `ShuttlecockLandingDetector`가 이 역할을 담당한다.

---

## 낙하 판정 알고리즘 (`ShuttlecockLandingDetector`)

### 핵심 아이디어

셔틀콕이 바닥에 떨어지면 **짧은 시간 동안 거의 같은 위치에 머문다**. 이 "정지 상태"를 감지하면 낙하로 판정한다.

```python
ShuttlecockLandingDetector(
    stay_threshold=10.0,   # 이전 좌표와의 거리 임계값 (픽셀)
    stay_frames=4,         # 연속 정지 프레임 수 임계값
    velocity_drop_threshold=0.5  # 현재 미사용
)
```

### 파라미터 설정 근거

- `stay_threshold=10픽셀`: 1080p 기준 코트 길이 ≈ 900픽셀, 13.4m 대비 약 0.15m 해상도. 바닥 착지 후 남은 떨림 정도를 허용하는 값.
- `stay_frames=4`: 10fps 분석 주기 기준 약 0.4초. 타구 후 다음 스윙 전에 정지 상태가 충분히 감지될 시간.

---

## `update()` 메서드 상세 동작

매 프레임마다 `update(x, y, visibility, frame_idx)`가 호출된다.

### 분기 1: visibility=0 (셔틀콕 미검출)

```python
if visibility == 0:
    if self.stay_counter > 0:
        # 이전까지 정지 중이었다면 정지 카운터를 계속 증가
        self.stay_counter += 1
        if self.stay_counter >= self.stay_frames and not self.is_landed:
            # 정지 카운터가 임계값 도달 → 마지막 알려진 위치에서 낙하 판정
            self.landing_pos = self.position_history[-1]
            self.is_landed = True
            return True  # 낙하 감지
    # stay_counter == 0이면 그냥 스킵
    return False
```

**이 분기가 존재하는 이유:** 셔틀콕이 바닥에 닿는 순간 YOLO가 놓치는 경우(모션 블러, 가림 등)가 있다. 착지 직전까지 정지 카운터가 증가했고, 그 직후 미검출이 이어지면 "착지 후 사라진 것"으로 해석해 낙하를 감지한다.

### 분기 2: visibility=1 (셔틀콕 검출됨)

```python
if self.position_history:
    prev_x, prev_y = self.position_history[-1]
    dist = math.sqrt((x - prev_x)**2 + (y - prev_y)**2)

    if dist < self.stay_threshold:  # 10픽셀 이내
        self.stay_counter += 1
    else:
        self.stay_counter = 0   # 움직이고 있으면 카운터 리셋
        self.is_landed = False  # 낙하 상태도 해제 (다시 날아감)

# 정지 프레임 수 임계값 도달
if self.stay_counter >= self.stay_frames and not self.is_landed:
    self.is_landed = True
    self.landing_pos = (x, y)
    self.landing_frame = frame_idx
    return True
```

### 상태 전이 다이어그램

```
초기 상태 (Moving)
    │
    │  연속 N프레임 dist < 10px
    ▼
정지 감지 (stay_counter >= stay_frames)
    │
    │  is_landed = True, landing_pos 기록
    ▼
낙하 판정 → True 반환
    │
    │  dist > stay_threshold (다시 움직임)
    ▼
낙하 해제 (is_landed = False, Counter 리셋)
    │
    └── 다음 랠리에서 재검출 가능
```

---

## Seek(탐색) 감지 및 리셋

비디오 탐색(앞뒤로 이동) 시 검출기 상태를 초기화하지 않으면 이전 랠리의 낙하 정보가 그대로 남는다. `VideoAnalysisService.process_frame()`에서 비디오 시간 변화로 Seek을 감지한다.

```python
is_seek = (
    video_time < self.last_video_time - 0.5 or  # 0.5초 이상 뒤로 감
    video_time > self.last_video_time + 5.0      # 5초 이상 앞으로 점프
)

if is_seek:
    self.landing_detector.reset()
    self.last_landing_info = None
    self.last_landing_frame = -100
    self.last_landing_time = -10.0
    self.last_world_pos = None
    self.is_last_in_court = False
    self.frame_counter = 0
```

일반적인 정상 재생에서는 프레임 간 시간 변화가 ≤ `1/fps` 초이므로 이 조건은 발동되지 않는다.

---

## 낙하 위치 → 실세계 좌표 변환

낙하 판정 직후 이미지 픽셀 좌표를 실세계 미터 좌표로 변환한다.

```python
# VideoAnalysisService.process_frame() 내부
world_pos = self.ht.image_to_world(
    (self.last_landing_info['x'], self.last_landing_info['y'])
)
```

`self.ht`는 `HomographyTransform` 인스턴스로, 캘리브레이션 시 계산된 Homography 행렬이 주입되어 있다.

---

## 코트 내/외 판정 (`CourtGeometry.is_point_in_court`)

실세계 좌표가 복식 코트 영역 내에 있는지를 판정한다.

```python
is_in_court = CourtGeometry.is_point_in_court(world_pos)
# world_pos: (X_meters, Y_meters) → 코트 절반 기준 실세계 좌표
```

내부 구현은 실세계 좌표의 X, Y 범위를 복식 코트 경계값과 비교한다.

```
복식 코트 경계:
  |X| <= 3.05m (복식 너비 절반)
  |Y| <= 6.7m  (베이스라인까지 거리)
```

판정 결과:
- `True` (IN): 코트 경계 내
- `False` (OUT): 코트 경계 밖

---

## `position_history` 버퍼

```python
self.position_history = deque(maxlen=20)  # 최근 20개 좌표 이력
```

`deque(maxlen=20)`으로 구현되어 오래된 좌표 자동 삭제. 현재는 직전 프레임(`[-1]`) 좌표와의 거리 계산에만 사용되며, 향후 궤적 스무딩이나 속도 계산 등에 활용할 수 있다.

---

## `position_history` 초기화 시점

`reset()` 메서드는 다음 상황에서 호출된다:

1. **비디오 Seek 감지 시** (자동): `landing_detector.reset()`
2. **새 세션 시작 시** (자동): `VideoAnalysisService` 초기화 시 새 인스턴스 생성
3. **ExternalAPI / 테스트** (수동): `detector.reset()` 직접 호출

```python
def reset(self):
    self.position_history.clear()
    self.is_landed = False
    self.landing_pos = None
    self.landing_frame = -1
    self.stay_counter = 0
```

---

## 낙하 정보 조회

```python
info = detector.get_landing_info()
# 낙하 감지됨:
# {'x': 423.1, 'y': 712.8, 'frame': 142}

# 낙하 미감지:
# None
```

디버그 정보도 제공된다.

```python
debug = detector.get_debug_info()
# {
#   'dist': 4.2,           # 이전 프레임과의 거리 (픽셀)
#   'stay_counter': 3,     # 현재 정지 카운터
#   'visibility': 1,       # 현재 가시성
#   'is_landed': False,    # 낙하 판정 여부
#   'reason': 'Staying (dist=4.20 < 10.0)'  # 판정 근거 문자열
# }
```

`VideoAnalysisService`에서는 `stay_counter > 0`일 때만 디버그 정보를 로그로 출력하여 로그가 과도하게 쌓이는 것을 방지한다.
