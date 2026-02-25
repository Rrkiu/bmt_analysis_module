/**
 * AnalysisCanvas.tsx
 * 비디오 위에 오버레이되는 Canvas 컴포넌트
 * 
 * [추가됨 - Step 3]
 * 코트 영역, 셔틀콕, 낙하 지점 시각화
 */

import { useEffect, useRef } from 'react';

interface CalibrationData {
    court_corners_image: number[][];
    image_shape: number[];
    pixels_per_meter: number;
}

interface ShuttlecockData {
    x: number;
    y: number;
    visibility: number;
}

interface LandingData {
    is_landed: boolean;
    pos: number[] | null;
    image_x: number;
    image_y: number;
    is_in_court: boolean;
    time_since: number;
}

interface AnalysisCanvasProps {
    videoRef: React.RefObject<HTMLVideoElement | null>;
    calibrationData: CalibrationData | null;
    shuttlecock: ShuttlecockData | null;
    landing: LandingData | null;
    showOverlay: boolean;
}

export function AnalysisCanvas({
    videoRef,
    calibrationData,
    shuttlecock,
    landing,
    showOverlay,
}: AnalysisCanvasProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    /**
     * 60fps로 렌더링
     */
    useEffect(() => {
        if (!canvasRef.current || !videoRef.current) return;

        const canvas = canvasRef.current;
        const video = videoRef.current;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        let animationId: number;

        const render = () => {
            // Canvas 크기 동기화
            if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
            }

            // 클리어
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // calibrationData가 없으면 로딩 중 텍스트 표시 (디버깅용)
            if (!calibrationData) {
                ctx.fillStyle = 'rgba(255, 200, 0, 0.8)';
                ctx.font = 'bold 16px Arial';
                ctx.fillText('⏳ 캘리브레이션 데이터 로딩 중...', 10, 30);
                animationId = requestAnimationFrame(render);
                return;
            }

            // 캘리브레이션 이미지 크기 (코너 좌표 기준)
            // image_shape: [height, width] 형식
            const imgH = calibrationData.image_shape?.[0] ?? canvas.height;
            const imgW = calibrationData.image_shape?.[1] ?? canvas.width;

            // 오버레이 그리기
            if (showOverlay) {
                drawCourtOverlay(ctx, canvas, calibrationData, imgW, imgH);
            }

            // 셔틀콕 그리기
            if (shuttlecock && shuttlecock.visibility === 1) {
                drawShuttlecock(ctx, canvas, shuttlecock, imgW, imgH);
            }

            // 낙하 지점 그리기
            if (landing) {
                drawLanding(ctx, canvas, landing, imgW, imgH);
            }

            animationId = requestAnimationFrame(render);
        };

        render();

        return () => {
            cancelAnimationFrame(animationId);
        };
    }, [videoRef, calibrationData, shuttlecock, landing, showOverlay]);

    return (
        <canvas
            ref={canvasRef}
            style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                pointerEvents: 'none',
            }}
        />
    );
}

/**
 * 코트 오버레이 그리기
 */
function drawCourtOverlay(
    ctx: CanvasRenderingContext2D,
    canvas: HTMLCanvasElement,
    calibrationData: CalibrationData,
    imageW: number,
    imageH: number
) {
    const corners = calibrationData.court_corners_image;
    if (!corners || corners.length !== 4) return;

    // 캘리브레이션 이미지 → 현재 캔버스(비디오) 비율 계산
    const scaleX = canvas.width / imageW;
    const scaleY = canvas.height / imageH;

    const scaledCorners = corners.map(([x, y]) => [x * scaleX, y * scaleY]);

    // 코트 영역 (반투명 녹색)
    ctx.fillStyle = 'rgba(0, 255, 0, 0.15)';
    ctx.beginPath();
    ctx.moveTo(scaledCorners[0][0], scaledCorners[0][1]);
    scaledCorners.forEach(([x, y]) => ctx.lineTo(x, y));
    ctx.closePath();
    ctx.fill();

    // 코트 외곽선
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.9)';
    ctx.lineWidth = 3;
    ctx.stroke();

    // 코너 마커
    const colors = ['#00ff00', '#ff0000', '#0000ff', '#ffff00'];
    const labels = ['TL', 'TR', 'BR', 'BL'];

    scaledCorners.forEach(([x, y], i) => {
        ctx.fillStyle = colors[i];
        ctx.beginPath();
        ctx.arc(x, y, 10, 0, 2 * Math.PI);
        ctx.fill();

        ctx.fillStyle = 'white';
        ctx.font = 'bold 14px Arial';
        ctx.fillText(labels[i], x + 15, y - 5);
    });
}

/**
 * 셔틀콕 그리기
 */
function drawShuttlecock(
    ctx: CanvasRenderingContext2D,
    canvas: HTMLCanvasElement,
    shuttlecock: ShuttlecockData,
    imageW: number,
    imageH: number
) {
    const scaleX = canvas.width / imageW;
    const scaleY = canvas.height / imageH;

    const x = shuttlecock.x * scaleX;
    const y = shuttlecock.y * scaleY;

    // 외부 강조 (노란색 반투명 원)
    ctx.fillStyle = 'rgba(255, 255, 0, 0.4)';
    ctx.beginPath();
    ctx.arc(x, y, 20, 0, Math.PI * 2);
    ctx.fill();

    // 중심 노란색 점
    ctx.fillStyle = '#ffff00';
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fill();

    // 흰색 외곽선
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.stroke();
}

/**
 * 낙하 지점 그리기
 * [수정됨] X 마크 제거, 크기 축소, 투명도 50%, 미니맵 카드 추가
 */
function drawLanding(
    ctx: CanvasRenderingContext2D,
    canvas: HTMLCanvasElement,
    landing: LandingData,
    imageW: number,
    imageH: number
) {
    const color = landing.is_in_court ? '#00ff00' : '#ff0000';
    const scaleX = canvas.width / imageW;
    const scaleY = canvas.height / imageH;

    const lx = landing.image_x * scaleX;
    const ly = landing.image_y * scaleY;

    // [수정됨] X 마크 제거, 원만 표시 (투명도 50%, 크기 축소)
    ctx.fillStyle = color.replace(')', ', 0.5)').replace('rgb', 'rgba');
    ctx.beginPath();
    ctx.arc(lx, ly, 6, 0, Math.PI * 2);  // 10 → 6으로 더 축소
    ctx.fill();
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';  // 흰색 외곽선도 투명도 적용
    ctx.lineWidth = 1.5;  // 2 → 1.5로 축소
    ctx.stroke();

    // [추가됨] 미니맵 카드 (우측 상단)
    if (landing.pos) {
        drawMinimapCard(ctx, canvas, landing, color);
    }

    // [수정됨] 하단 판정 배너 (크기 축소)
    const bannerText = `JUDGMENT: ${landing.is_in_court ? 'IN' : 'OUT'}`;
    ctx.font = 'bold 40px Arial Black';  // 60px → 40px로 축소
    const textMeasure = ctx.measureText(bannerText);
    const bW = textMeasure.width + 40;  // 60 → 40
    const bH = 60;  // 80 → 60
    const bX = (canvas.width - bW) / 2;
    const bY = canvas.height - 100;  // 120 → 100

    // 배경
    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
    ctx.fillRect(bX, bY, bW, bH);

    // 텍스트
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(bannerText, canvas.width / 2, bY + bH / 2 + 5);
}

/**
 * [추가됨] 미니맵 카드 그리기 (우측 상단)
 */
function drawMinimapCard(
    ctx: CanvasRenderingContext2D,
    canvas: HTMLCanvasElement,
    landing: LandingData,
    color: string
) {
    // [수정] 크기 축소 (160x280) 및 풀코트 비율
    const cardW = 160;
    const cardH = 280;
    const cardX = canvas.width - cardW - 30;
    const cardY = 30;

    // 카드 배경
    ctx.fillStyle = 'rgba(210, 212, 210, 0.95)';
    ctx.strokeStyle = 'rgba(180, 180, 180, 1)';
    ctx.lineWidth = 3;

    // 둥근 모서리 사각형
    ctx.beginPath();
    ctx.roundRect(cardX, cardY, cardW, cardH, 12);
    ctx.fill();
    ctx.stroke();

    // 미니맵 영역
    const mPad = 10;
    const mx = cardX + mPad;
    const my = cardY + mPad;
    const mw = cardW - mPad * 2;
    const mh = cardH - mPad * 2;

    // 미니맵 배경 (진한 회색)
    ctx.fillStyle = 'rgba(40, 40, 40, 1)';
    ctx.fillRect(mx, my, mw, mh);
    ctx.strokeStyle = 'rgba(200, 200, 200, 1)';
    ctx.lineWidth = 2;
    ctx.strokeRect(mx, my, mw, mh);

    // [수정] 실제 배드민턴 코트 규격 및 좌표계 적용
    // 좌표계(추정): 네트 중앙 (0,0), X축: 좌우(-3.05 ~ 3.05), Y축: 전후(-6.7 ~ 6.7)
    // 미니맵: 위쪽이 상대편(+Y), 아래쪽이 우리편(-Y) 가정

    const courtHalfWidth = 3.05;  // 6.1m / 2
    const courtHalfLength = 6.7;  // 13.4m / 2

    // Canvas 좌표 매핑 함수
    // X: (-3.05 ~ 3.05) -> (mx ~ mx+mw)
    const toMiniX = (wx: number) => mx + ((wx + courtHalfWidth) / (2 * courtHalfWidth)) * mw;

    // Y: (+6.7 ~ -6.7) -> (my ~ my+mh) 
    // Y가 양수(상대편)일 때 위쪽(my), Y가 음수(우리편)일 때 아래쪽(my+mh)
    // 식: my + mh/2 - (wy / courtHalfLength) * (mh/2)
    // wy = 6.7 -> my
    // wy = -6.7 -> my + mh
    const toMiniY = (wy: number) => my + (mh / 2) - (wy / courtHalfLength) * (mh / 2);

    // 코트 라인 그리기 (흰색)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.lineWidth = 1.5;

    // 1. 네트 (중앙 가로선, y=0) - 노란색 점선이나 실선
    ctx.beginPath();
    ctx.strokeStyle = '#FFFF00';
    ctx.lineWidth = 2;
    const netY = toMiniY(0);
    ctx.moveTo(mx, netY);
    ctx.lineTo(mx + mw, netY);
    ctx.stroke();

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)'; // 다시 흰색
    ctx.lineWidth = 1.5;

    // 2. 숏 서비스 라인 (양쪽, 네트에서 1.98m)
    // 상대편(위쪽, +1.98)
    let y = toMiniY(1.98);
    ctx.beginPath(); ctx.moveTo(mx, y); ctx.lineTo(mx + mw, y); ctx.stroke();
    // 우리편(아래쪽, -1.98)
    y = toMiniY(-1.98);
    ctx.beginPath(); ctx.moveTo(mx, y); ctx.lineTo(mx + mw, y); ctx.stroke();

    // 3. 롱 서비스 라인 (복식, 백바운더리에서 0.76m 안쪽 -> 네트에서 5.94m)
    // 상대편(위쪽, +5.94)
    y = toMiniY(5.94);
    ctx.beginPath(); ctx.moveTo(mx, y); ctx.lineTo(mx + mw, y); ctx.stroke();
    // 우리편(아래쪽, -5.94)
    y = toMiniY(-5.94);
    ctx.beginPath(); ctx.moveTo(mx, y); ctx.lineTo(mx + mw, y); ctx.stroke();

    // 4. 센터 라인 (양쪽, 숏 서비스 ~ 백바운더리)
    const centerX = toMiniX(0);
    // 상대편 (1.98 ~ 6.7)
    ctx.beginPath(); ctx.moveTo(centerX, toMiniY(1.98)); ctx.lineTo(centerX, toMiniY(6.7)); ctx.stroke();
    // 우리편 (-1.98 ~ -6.7)
    ctx.beginPath(); ctx.moveTo(centerX, toMiniY(-1.98)); ctx.lineTo(centerX, toMiniY(-6.7)); ctx.stroke();

    // 5. 단식 사이드 라인 (좌우 0.46m 안쪽 -> 3.05 - 0.46 = 2.59)
    const leftSingles = toMiniX(-2.59);
    const rightSingles = toMiniX(2.59);
    // 끝에서 끝까지
    ctx.beginPath(); ctx.moveTo(leftSingles, my); ctx.lineTo(leftSingles, my + mh); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(rightSingles, my); ctx.lineTo(rightSingles, my + mh); ctx.stroke();

    // 낙하 지점 표시
    if (landing.pos) {
        let [wx, wy] = landing.pos;

        // [자동 보정] 좌표축 스왑 감지
        // X축(폭)은 보통 -3.05 ~ 3.05, Y축(길이)는 -6.7 ~ 6.7 (또는 더 큼)
        // 만약 첫 번째 값이 코트 폭을 크게 벗어난다면 Y축 값일 확률이 높음 (X, Y가 바뀐 경우)
        if (Math.abs(wx) > 4.0 && Math.abs(wy) < 4.0) {
            // 값 스왑
            [wx, wy] = [wy, wx];
        }

        const px = toMiniX(wx);

        // [수정] Y축 방향 반전
        // 백엔드 좌표계와 프론트엔드 미니맵 Y축 방향이 반대일 경우를 대비해 부호 조정
        // 사용자 피드백: "가까운 영역(우리편)" -> "상대편"에 찍힘. 
        // 즉, 현재 로직( -wy )이 반대로 동작함. 따라서 ( +wy )로 변경.
        // 식: my + mh/2 + (wy / courtHalfLength) * (mh / 2)
        const py = my + (mh / 2) + (wy / courtHalfLength) * (mh / 2);

        if (px >= mx - 10 && px <= mx + mw + 10 && py >= my - 10 && py <= my + mh + 10) {
            ctx.shadowBlur = 10;
            ctx.shadowColor = color;
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(px, py, 6, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = 'white';
            ctx.lineWidth = 2;
            ctx.stroke();
            ctx.shadowBlur = 0;
        }
    }

    // 텍스트(POS, RESULT) 제거함
}

