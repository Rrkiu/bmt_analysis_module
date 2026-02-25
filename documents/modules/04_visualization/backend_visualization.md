# 백엔드 시각화 서비스 (`VisualizationService` + `draw_minimap`)

## `VisualizationService` 개요

주로 캘리브레이션 확인용 정적 이미지 시각화를 담당한다. 실시간 비디오 분석의 핵심 시각화(`draw_minimap`, 낙하 오버레이)는 `VideoAnalysisService.process_frame()`에 직접 구현되어 있다.

---

## 코트 영역 그리기 (`draw_court_region`)

```python
VisualizationService.draw_court_region(
    image=bgr_img,
    court_corners=[[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
    fill_color=(0, 255, 0),    # 녹색 채우기
    border_color=(0, 255, 255), # 시안색 외곽선
    alpha=0.3,                  # 30% 투명도
    border_thickness=3
)
```

**렌더링 순서:**
1. 반투명 폴리곤 채우기 (`cv2.fillPoly` + `cv2.addWeighted`)
2. 외곽선 (`cv2.polylines`)
3. 4개 코너 마커 (컬러 원 + 흰 외곽 원 + TL/TR/BR/BL 레이블)

코너 마커 색상: TL=Green, TR=Blue, BR=Red, BL=Cyan

---

## T자 가이드 그리기 (`draw_t_guide`)

배드민턴 T자(숏 서비스 라인 + 센터라인 교차점) 시각화. 현재는 수동 캘리브레이션 화면에서 가이드 용도로 사용된다.

```python
VisualizationService.draw_t_guide(
    image=img,
    t_guide_coords={
        'success': True,
        't_guide': {
            'vertical': {'start': (cx, cy), 'end': (cx, bottom)},
            'horizontal': {'start': (left, cy), 'end': (right, cy)}
        }
    },
    color=(0, 0, 255),   # 빨간색
    thickness=3
)
```

그려지는 요소:
- 세로선: T자 교차점 → 베이스라인 방향
- 가로선: 숏 서비스 라인 전체
- 교차점 원 (반지름 8, 흰 외곽 원 반지름 12)

---

## 미니맵 그리기 (`draw_minimap`)

실시간 분석 중 매 프레임마다 호출되는 핵심 시각화 함수. 우측 상단 카드 영역에 배드민턴 코트 평면도를 그리고 낙하 위치를 표시한다.

### 좌표 변환 함수 (`world_to_mini`)

```python
# 실세계 좌표 → 미니맵 픽셀 좌표 변환 (백엔드 버전)
def world_to_mini(wx, wy):
    # X: -3.05 ~ +3.05m → mx ~ mx+mw
    mini_x = int(mx + (wx + 3.05) / 6.1 * mw)
    # Y: 0 ~ 13.4m → my ~ my+mh
    # 백엔드 좌표계: Y=0이 한쪽 베이스라인, Y=13.4가 반대쪽 베이스라인
    mini_y = int(my + wy / 13.4 * mh)
    return (mini_x, mini_y)
```

> **주의**: 백엔드 미니맵은 `Y: 0 ~ 13.4m` 풀코트 전체를 매핑하는 반면, 프론트엔드 미니맵은 `Y: -6.7 ~ +6.7m` 네트 중심 기준으로 매핑한다. 두 시스템의 Y축 기준이 다르다.

### 그려지는 코트 라인 (백엔드)

```
풀코트 외곽선 (흰색, 두께 2)
네트 (Y=6.7m, 노란색)
숏 서비스 라인 - 아래쪽 (Y=1.98m, 회색)
숏 서비스 라인 - 위쪽 (Y=11.42m = 13.4-1.98, 회색)
센터 라인 - 아래쪽 (X=0, 1.98~6.7m, 회색)
센터 라인 - 위쪽 (X=0, 6.7~11.42m, 회색)
```

### 낙하 위치 표시

```python
if world_point:
    px, py = world_to_mini(world_point[0], world_point[1])
    color = (0, 255, 0) if is_in_court else (0, 0, 255)  # IN=녹색, OUT=빨간색
    cv2.circle(img, (px, py), 5, color, -1)      # 반지름 5
    cv2.circle(img, (px, py), 7, (255, 255, 255), 1)  # 흰 외곽
```

### 미니맵 카드 레이아웃

```python
# VideoAnalysisService.process_frame() 내부
card_w, card_h = 160, 310        # 카드 크기 (px)
card_x = frame_width - card_w - 30   # 우측에서 30px 안쪽
card_y = 30                          # 상단에서 30px 아래
m_pad = 10

# 카드 배경
cv2.rectangle(processed, (card_x, card_y), (card_x+card_w, card_y+card_h), (210, 212, 210), -1)
cv2.rectangle(processed, (card_x, card_y), (card_x+card_w, card_y+card_h), (180, 180, 180), 2)

# 미니맵 (카드 내부)
VisualizationService.draw_minimap(
    processed,
    world_point=self.last_world_pos,
    is_in_court=self.is_last_in_court,
    position=(card_x + m_pad, card_y + m_pad),
    size=(card_w - m_pad*2, card_h - m_pad*2)   # (140, 290)
)
```

---

## 메인 화면 낙하 마커

```python
# VideoAnalysisService.process_frame() — 낙하 시각화
lx, ly = landing_image_x, landing_image_y
landing_color = (0, 255, 0) if is_in_court else (0, 0, 255)

# 낙하 위치 원 (반지름 20, 채우기)
cv2.circle(processed, (lx, ly), 20, landing_color, -1)

# X자 마커 (흰색, 크기 60, 두께 5)
cv2.drawMarker(processed, (lx, ly), (255, 255, 255),
               cv2.MARKER_TILTED_CROSS, 60, 5)
```

---

## 판정 텍스트 배너 (백엔드)

```python
status_text = "JUDGMENT: IN" if is_in_court else "JUDGMENT: OUT"
text_size = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 2.0, 5)[0]
tx = (frame_width - text_size[0]) // 2
ty = frame_height - 80

# 검은 배경 박스
cv2.rectangle(processed, (tx-10, ty-text_size[1]-10), (tx+text_size[0]+10, ty+10), (0,0,0), -1)

# 판정 텍스트 (글씨 크기 2.0, 두께 5)
cv2.putText(processed, status_text, (tx, ty),
            cv2.FONT_HERSHEY_SIMPLEX, 2.0, landing_color, 5)
```

판정 결과는 낙하 감지 후 **20초 이내 또는 500프레임 이내**에 계속 표시된다.

---

## 이미지 변환 유틸리티

```python
# OpenCV 이미지 → base64 문자열
b64 = VisualizationService.image_to_base64(image, format='.jpg')
# → "data:image/jpg;base64,/9j/4AAQ..."

# base64 문자열 → OpenCV 이미지
img = VisualizationService.base64_to_image(b64_string)
```

API 응답에 `processed_image` 필드를 포함할 때 사용된다 (`predict_frame` 엔드포인트).

---

