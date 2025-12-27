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

            // 오버레이 그리기
            if (showOverlay && calibrationData) {
                drawCourtOverlay(ctx, canvas, calibrationData);
            }

            // 셔틀콕 그리기
            if (shuttlecock && shuttlecock.visibility === 1 && calibrationData) {
                drawShuttlecock(ctx, canvas, shuttlecock, calibrationData);
            }

            // 낙하 지점 그리기
            if (landing && calibrationData) {
                drawLanding(ctx, canvas, landing, calibrationData);
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
    calibrationData: CalibrationData
) {
    const corners = calibrationData.court_corners_image;
    if (!corners || corners.length !== 4) return;

    const scaleX = canvas.width / calibrationData.image_shape[1];
    const scaleY = canvas.height / calibrationData.image_shape[0];

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
    calibrationData: CalibrationData
) {
    const scaleX = canvas.width / calibrationData.image_shape[1];
    const scaleY = canvas.height / calibrationData.image_shape[0];

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
    calibrationData: CalibrationData
) {
    const color = landing.is_in_court ? '#00ff00' : '#ff0000';
    const scaleX = canvas.width / calibrationData.image_shape[1];
    const scaleY = canvas.height / calibrationData.image_shape[0];

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
    const cardW = 260;
    const cardH = 340;
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
    const mPad = 15;
    const mSizeH = cardH - 120;
    const mx = cardX + mPad;
    const my = cardY + mPad;
    const mw = cardW - mPad * 2;
    const mh = mSizeH;

    // 미니맵 배경 (진한 회색)
    ctx.fillStyle = 'rgba(160, 162, 160, 1)';
    ctx.fillRect(mx, my, mw, mh);
    ctx.strokeStyle = 'white';
    ctx.lineWidth = 2;
    ctx.strokeRect(mx, my, mw, mh);

    // [수정됨] 실제 배드민턴 복식 코트 라인 그리기
    if (landing.pos) {
        const [wx, wy] = landing.pos;

        // 좌표 매핑
        // 복식 코트 전체 폭: 6.1m → -3.05 ~ 3.05
        // 네트부터 후방까지 길이: 6.7m
        const courtWidth = 6.1;
        const courtLength = 6.7;

        const px = mx + ((wx + courtWidth / 2) / courtWidth) * mw;
        const py = my + (wy / courtLength) * mh;

        // 코트 라인 그리기 (흰색)
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
        ctx.lineWidth = 1.5;

        // 1. 중앙선 (세로)
        ctx.beginPath();
        ctx.moveTo(mx + mw / 2, my);
        ctx.lineTo(mx + mw / 2, my + mh);
        ctx.stroke();

        // 2. 숏 서비스 라인 (네트로부터 1.98m)
        const shortServiceY = my + (1.98 / courtLength) * mh;
        ctx.beginPath();
        ctx.moveTo(mx, shortServiceY);
        ctx.lineTo(mx + mw, shortServiceY);
        ctx.stroke();

        // 3. 롱 서비스 라인 (복식, 후방 0.76m)
        const longServiceY = my + ((courtLength - 0.76) / courtLength) * mh;
        ctx.beginPath();
        ctx.moveTo(mx, longServiceY);
        ctx.lineTo(mx + mw, longServiceY);
        ctx.stroke();

        // 4. 단식 사이드 라인 (좌우 0.46m 안쪽)
        const singlesSideOffset = (0.46 / courtWidth) * mw;
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
        ctx.lineWidth = 1;

        ctx.beginPath();
        ctx.moveTo(mx + singlesSideOffset, my);
        ctx.lineTo(mx + singlesSideOffset, my + mh);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(mx + mw - singlesSideOffset, my);
        ctx.lineTo(mx + mw - singlesSideOffset, my + mh);
        ctx.stroke();

        // 5. 네트 위치 (상단, 굵은 선)
        ctx.strokeStyle = 'rgba(255, 255, 255, 1)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(mx, my);
        ctx.lineTo(mx + mw, my);
        ctx.stroke();

        // 미니맵 낙구 점 (빛나는 효과)
        if (px >= mx - 10 && px <= mx + mw + 10 && py >= my - 10 && py <= my + mh + 10) {
            ctx.shadowBlur = 10;
            ctx.shadowColor = color;
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(px, py, 10, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = 'white';
            ctx.lineWidth = 3;
            ctx.stroke();
            ctx.shadowBlur = 0;
        }
    }

    // 카드 하단 정보 텍스트
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';

    // POS 텍스트
    ctx.fillStyle = '#666';
    ctx.font = 'bold 16px Courier New, monospace';  // 18px → 16px
    const posText = landing.pos
        ? `POS: ${landing.pos[0].toFixed(2)}, ${landing.pos[1].toFixed(2)}`
        : 'POS: N/A';
    ctx.fillText(posText, cardX + mPad, cardY + cardH - 75);

    // RESULT 텍스트
    ctx.fillStyle = color;
    ctx.font = 'bold 28px Arial Black, sans-serif';  // 32px → 28px
    ctx.fillText(
        `RESULT: ${landing.is_in_court ? 'IN' : 'OUT'}`,
        cardX + mPad,
        cardY + cardH - 45
    );
}

