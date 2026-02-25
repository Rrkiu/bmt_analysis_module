# 결과 시각화 시스템 — 모듈 개요

## 목적

Milestone 4는 셔틀콕 검출 및 낙하 판정 결과를 사용자에게 **시각적으로 전달**하는 시스템이다. 순수 분석 결과(픽셀 좌표, 실세계 좌표, IN/OUT 판정)를 세 가지 레이어로 표현한다.

1. **메인 화면 오버레이** — 코트 경계, 셔틀콕 위치 마커, 낙하 위치 마커
2. **미니맵 카드** — 우측 상단에 배드민턴 코트 평면도와 낙하 위치 표시
3. **판정 배너** — 화면 하단 중앙에 `JUDGMENT: IN / OUT` 텍스트

시각화는 **백엔드(Python/OpenCV)**와 **프론트엔드(React Canvas API)** 두 곳에서 이중으로 구현되어 있다.

---

## 관련 코드 위치

```
core/
├── backend/
│   ├── modules/visualization/
│   │   └── visualization_service.py   # VisualizationService — 정적 이미지용 시각화
│   ├── modules/analysis/
│   │   └── video_analysis_service.py  # process_frame() — 실시간 프레임 렌더링
│   └── constants.py                   # CourtDimensions — BWF 규격 상수
│
└── birdie-buddies-frontend/src/
    ├── components/Analysis/
    │   └── AnalysisCanvas.tsx          # Canvas API 기반 오버레이 컴포넌트
    ├── pages/Analysis/
    │   └── VideoAnalysisPage.tsx       # 비디오 플레이어 + Canvas 통합 페이지
    ├── hooks/
    │   └── useVideoAnalysis.ts         # 30fps 분석 루프, 상태 관리 Hook
    └── services/
        └── analysisAPI.ts              # 백엔드 API 클라이언트
```

---

## 백엔드 vs 프론트엔드 시각화 역할 분리

| 시각화 요소 | 백엔드 (OpenCV) | 프론트엔드 (Canvas API) |
|------------|----------------|----------------------|
| 코트 영역 반투명 채우기 | ✅ | ✅ |
| 코트 경계선 | ✅ | ✅ |
| 셔틀콕 검출 마커 | ✅ (`draw_prediction`) | ✅ (`drawShuttlecock`) |
| 낙하 위치 마커 | ✅ | ✅ (`drawLanding`) |
| 미니맵 카드 (코트 평면도) | ✅ (`draw_minimap`) | ✅ (`drawMinimapCard`) |
| 판정 배너 (JUDGMENT: IN/OUT) | ✅ | ✅ |
| 코너 마커 (TL/TR/BR/BL) | ✅ (debug mode) | ✅ (`drawCourtOverlay`) |

> **이중 구현 이유**: 백엔드는 `processed_image`(base64 JPEG)를 생성하여 API 응답에 포함할 수 있고, 프론트엔드는 이 이미지를 표시하거나 독립적으로 Canvas로 재렌더링한다. 현재 실제 UI는 **프론트엔드 Canvas**가 주된 시각화를 담당하며, 백엔드 렌더링 이미지는 디버깅·백업 용도로 유지된다.

---

## 배드민턴 코트 규격 (`constants.py`)

시각화의 기준이 되는 BWF 공식 규격이다.

```python
class CourtDimensions:
    TOTAL_LENGTH = 13.4        # m, 풀코트 전체 길이
    DOUBLES_WIDTH = 6.1        # m, 복식 코트 너비
    SINGLES_WIDTH = 5.18       # m, 단식 코트 너비
    SHORT_SERVICE_LINE = 1.98  # m, 숏 서비스 라인 (네트에서)
    LONG_SERVICE_LINE_DOUBLES = 0.76  # m, 롱 서비스 라인 (베이스라인에서 안쪽)
    BACK_BOUNDARY_LINE = 6.7   # m = TOTAL_LENGTH / 2, 한쪽 코트 길이
```

---

## 실세계 좌표계 (시각화 좌표 기준)

미니맵과 코트 내/외 판정에서 사용하는 실세계 좌표계:

```
        상대편 코트
         ____________________
        |         |          |  Y = +6.7m (상대 베이스라인)
        |         |          |
        |    Y = +1.98m      |  (상대편 숏 서비스 라인)
        |___________________|
    ====|    네트 (Y = 0)    |====
        |___________________| 
        |    Y = -1.98m      |  (우리편 숏 서비스 라인)
        |         |          |
        |_________|__________|  Y = -6.7m (우리편 베이스라인)
         우리편 코트

    X: -3.05m ~ +3.05m (복식 너비 기준)
    원점: 네트 중앙
```

**미니맵 Y축 주의사항**: 최종 구현에서는 Y 부호가 `+wy` (양수 방향이 위쪽)로 수정되었다. 초기 구현에서 사용자 피드백으로 미니맵의 상하 방향이 역전되는 문제가 발견되어 수정된 결과다.
