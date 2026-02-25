# 프론트엔드 비디오 분석 UI

## 전체 구조

```
VideoAnalysisPage (페이지 컨테이너)
  ├── <video ref={videoRef}>           HTML5 Video Player
  └── <AnalysisCanvas>                 Canvas 오버레이 (position: absolute)
        ├── drawCourtOverlay()          코트 영역 + 코너 마커
        ├── drawShuttlecock()           셔틀콕 위치 마커
        └── drawLanding()
              └── drawMinimapCard()     우측 상단 미니맵 카드

useVideoAnalysis (Custom Hook)
  ├── loadCalibration()     세션 캘리브레이션 데이터 로드
  ├── startAnalysis()       33ms 인터벌로 analyzeFrame() 시작
  ├── stopAnalysis()        인터벌 정지, 상태 리셋
  └── analyzeFrame()        프레임 캡처 → API 호출 → 상태 업데이트

analysisAPI.ts
  └── predictFrame()        POST /api/analysis/frame-predict
```

---

## `useVideoAnalysis` Hook

비디오 분석의 상태 관리와 API 폴링 루프를 담당하는 Custom Hook.

### 상태 구조

```typescript
interface AnalysisState {
    calibrationData: CalibrationData | null;  // 코트 코너, 이미지 크기, pixels_per_meter
    shuttlecock: ShuttlecockData | null;       // {x, y, visibility}
    landing: LandingData | null;               // 낙하 정보
    isAnalyzing: boolean;                      // 분석 중 여부
    error: string | null;
}
```

### 30fps 분석 루프

```typescript
const ANALYSIS_INTERVAL = 33;  // ms (≈ 30fps)

startAnalysis() {
    analysisIntervalRef.current = setInterval(() => {
        analyzeFrame();
    }, ANALYSIS_INTERVAL);
}
```

### `analyzeFrame()` — 프레임 캡처 → API

```typescript
async function analyzeFrame() {
    // 1. 중복 요청 방지 (33ms 미만이면 스킵)
    if (now - lastAnalysisTime < ANALYSIS_INTERVAL) return;
    // 2. 일시정지 시 분석 중단
    if (video.paused) return;

    // 3. 현재 비디오 프레임을 임시 Canvas에 캡처
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);

    // 4. JPEG Blob 변환 (품질 0.7 = 70%, 파일 크기 절약)
    canvas.toBlob(async (blob) => {
        const result = await analysisAPI.predictFrame(
            sessionId, blob, video.currentTime
        );
        // 5. 상태 업데이트
        setState(prev => ({
            ...prev,
            shuttlecock: result.tracknet,    // {x, y, visibility}
            landing: result.landing,          // 낙하 판정 결과
        }));
    }, 'image/jpeg', 0.7);
}
```

**JPEG 품질 0.7 선택 이유**: 원본 무압축 대비 파일 크기를 약 80% 줄이면서 YOLO 검출 정확도를 유지할 수 있는 실험적 최소 품질값.

### 캘리브레이션 데이터 로드

```typescript
// 세션 ID로 캘리브레이션 결과 조회
const response = await fetch(`/api/session/${sessionId}/calibration`);
const result = await response.json();
// result.calibration_result = {
//   court_corners_image: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
//   image_shape: [height, width],
//   pixels_per_meter: 87.43
// }
setState(prev => ({ ...prev, calibrationData: result.calibration_result }));
```

`court_corners_image`는 캘리브레이션 시점의 이미지 크기를 기준으로 한 코너 픽셀 좌표다. 비디오 해상도가 다를 경우 스케일 변환이 필요하다 (→ `AnalysisCanvas`에서 처리).

---

## `AnalysisCanvas` 컴포넌트

비디오 엘리먼트 위에 `position: absolute`로 겹쳐지는 투명 Canvas. 60fps `requestAnimationFrame` 루프로 계속 재렌더링한다.

### Canvas 배치

```tsx
<div style={{ position: 'relative' }}>
    <video ref={videoRef} style={{ width: '100%' }} />
    <AnalysisCanvas
        videoRef={videoRef}
        calibrationData={calibrationData}
        shuttlecock={shuttlecock}
        landing={landing}
        showOverlay={showOverlay}
        style={{
            position: 'absolute',
            top: 0, left: 0,
            width: '100%', height: '100%',
            pointerEvents: 'none'   // ← 클릭 이벤트가 Canvas에 흡수되지 않음
        }}
    />
</div>
```

`pointerEvents: 'none`으로 설정하여 Canvas 위의 마우스 클릭이 비디오 플레이어로 통과된다.

### 해상도 스케일링

캘리브레이션 이미지 크기와 비디오 재생 크기가 다를 수 있으므로, 모든 드로잉 함수에서 스케일 변환을 수행한다.

```typescript
// 캘리브레이션 이미지 크기 (코너 좌표의 기준이 된 해상도)
const imgH = calibrationData.image_shape?.[0] ?? canvas.height;
const imgW = calibrationData.image_shape?.[1] ?? canvas.width;

// 현재 Canvas (비디오) 크기 대비 스케일
const scaleX = canvas.width / imgW;
const scaleY = canvas.height / imgH;

// 모든 좌표에 스케일 적용
const scaledCorners = corners.map(([x, y]) => [x * scaleX, y * scaleY]);
```

---

## 드로잉 함수 상세

### `drawCourtOverlay(ctx, canvas, calibrationData, imgW, imgH)`

```typescript
// 1. 코트 영역 반투명 녹색 채우기 (alpha 15%)
ctx.fillStyle = 'rgba(0, 255, 0, 0.15)';
ctx.beginPath();
scaledCorners.forEach(([x,y]) => ctx.lineTo(x, y));
ctx.closePath();
ctx.fill();

// 2. 시안색 외곽선 (두께 3)
ctx.strokeStyle = 'rgba(0, 255, 255, 0.9)';
ctx.lineWidth = 3;
ctx.stroke();

// 3. 코너 마커 (반지름 10 컬러 원 + 흰색 레이블)
const colors = ['#00ff00', '#ff0000', '#0000ff', '#ffff00'];
// TL=Green, TR=Red, BR=Blue, BL=Yellow
```

> 백엔드의 코너 색상 순서(TL=Green, TR=Blue, BR=Red, BL=Yellow)와 프론트엔드의 순서(TL=Green, TR=Red, BR=Blue, BL=Yellow)가 TR, BR에서 다르다.

### `drawShuttlecock(ctx, canvas, shuttlecock, imgW, imgH)`

검출된 셔틀콕 위치에 마커를 그린다.

```typescript
const x = shuttlecock.x * scaleX;
const y = shuttlecock.y * scaleY;

// 노란색 반투명 원 (반지름 20, alpha 40%)
ctx.fillStyle = 'rgba(255, 255, 0, 0.4)';
ctx.arc(x, y, 20, 0, Math.PI * 2);
ctx.fill();

// 노란색 중심점 (반지름 5)
ctx.fillStyle = '#ffff00';
ctx.arc(x, y, 5, 0, Math.PI * 2);
ctx.fill();

// 흰색 외곽선 (두께 2)
ctx.strokeStyle = '#ffffff';
```

`shuttlecock.visibility === 1`일 때만 그려진다.

### `drawLanding(ctx, canvas, landing, imgW, imgH)`

낙하 지점 마커와 판정 배너를 그린다.

```typescript
const color = landing.is_in_court ? '#00ff00' : '#ff0000';
const lx = landing.image_x * scaleX;
const ly = landing.image_y * scaleY;

// 낙하 위치 원 (반지름 6, 투명도 50%)
ctx.fillStyle = color + '80';   // hex에 80 = 50% alpha
ctx.arc(lx, ly, 6, 0, Math.PI * 2);
ctx.fill();

// 흰 외곽선 (두께 1.5, 투명도 70%)
ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
ctx.lineWidth = 1.5;
```

```typescript
// 판정 배너 (하단 중앙)
const bannerText = `JUDGMENT: ${landing.is_in_court ? 'IN' : 'OUT'}`;
ctx.font = 'bold 40px Arial Black';
const bW = ctx.measureText(bannerText).width + 40;
const bH = 60;
const bX = (canvas.width - bW) / 2;
const bY = canvas.height - 100;

ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';   // 검은 배경
ctx.fillRect(bX, bY, bW, bH);
ctx.fillStyle = color;
ctx.textAlign = 'center';
ctx.fillText(bannerText, canvas.width/2, bY + bH/2 + 5);
```

---

## `drawMinimapCard()` — 프론트엔드 미니맵

### 좌표 변환 (프론트엔드 버전)

```typescript
const courtHalfWidth = 3.05;   // 6.1m / 2
const courtHalfLength = 6.7;   // 13.4m / 2

// X: -3.05 ~ +3.05m → mx ~ mx+mw
const toMiniX = (wx) => mx + ((wx + courtHalfWidth) / (2 * courtHalfWidth)) * mw;

// Y: 최종 수정된 방향 (양수 = 위쪽)
// wy = +6.7 → 미니맵 위쪽, wy = -6.7 → 미니맵 아래쪽
const py = my + (mh / 2) + (wy / courtHalfLength) * (mh / 2);
// (* +wy로 수정: 사용자 피드백으로 상하 반전 보정)
```

### 그려지는 코트 라인 (프론트엔드)

```
네트 (Y=0, 노란색)
숏 서비스 라인 (Y=±1.98, 흰색)
롱 서비스 라인/복식 (Y=±5.94 = ±6.7-0.76, 흰색)
센터 라인 (X=0, 숏서비스~베이스라인 구간)
단식 사이드라인 (X=±2.59 = ±3.05-0.46, 흰색)
```

### X/Y 축 스왑 자동 보정

```typescript
if (Math.abs(wx) > 4.0 && Math.abs(wy) < 4.0) {
    // wx가 코트 너비(3.05m)를 크게 벗어나고 wy가 너비 범위 안이면
    // 좌표가 바뀐 것으로 판단 → 스왑
    [wx, wy] = [wy, wx];
}
```

백엔드 좌표 변환에서 X/Y 값이 의도와 다르게 반전되는 경우를 자동으로 감지하여 보정한다.

---

## API 통신 (`analysisAPI.ts`)

### `predictFrame()` — 핵심 분석 API

```typescript
export async function predictFrame(
    sessionId: string,
    frameBlob: Blob,    // JPEG Blob
    videoTime: number   // 현재 비디오 재생 시간 (초)
): Promise<FramePredictionResponse> {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('file', frameBlob);
    formData.append('video_time', videoTime.toString());

    const response = await fetch('/api/analysis/frame-predict', {
        method: 'POST',
        body: formData,
    });
    return response.json();
}
```

### 응답 타입

```typescript
interface FramePredictionResponse {
    success: boolean;
    tracknet: {
        x: number;
        y: number;
        visibility: number;         // 0 or 1
        is_landed: boolean;
        landing_debug: { ... };
    };
    landing: {
        is_landed: boolean;
        pos: number[] | null;       // [X_m, Y_m] 실세계 좌표
        image_x: number;             // 낙하 픽셀 x
        image_y: number;             // 낙하 픽셀 y
        is_in_court: boolean;
        time_since: number;          // 낙하 후 경과 초
    } | null;
    processed_image?: string;        // base64 JPEG (백엔드 렌더링 이미지, 현재 미사용)
}
```

`tracknet` 키 이름은 TrackNet 레거시에서 유래하며, 실제로는 YOLO 검출 결과다.

---

## API 프록시 설정 (Vite)

WSL 환경에서 Windows 브라우저가 `localhost:8000`으로 직접 접근하면 WSL 포트포워딩 불안정 문제가 있어, Vite 프록시를 통해 우회한다.

```typescript
// analysisAPI.ts
const API_BASE_URL = import.meta.env.VITE_ANALYSIS_API_BASE_URL || '';
// VITE_ANALYSIS_API_BASE_URL이 없으면 빈 문자열 → 상대경로 → Vite 프록시가 처리

// → fetch('/api/analysis/frame-predict')
// → Vite 개발 서버가 WSL 내부 127.0.0.1:8000으로 프록시

// vite.config.ts에서:
// proxy: { '/api': { target: 'http://127.0.0.1:8000' } }
```
