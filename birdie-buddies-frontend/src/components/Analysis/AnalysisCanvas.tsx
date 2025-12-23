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
    videoRef: React.RefObject<HTMLVideoElement>;
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

    // X 마크
    ctx.strokeStyle = 'white';
    ctx.lineWidth = 5;
    const s = 30;
    ctx.beginPath();
    ctx.moveTo(lx - s, ly - s);
    ctx.lineTo(lx + s, ly + s);
    ctx.moveTo(lx + s, ly - s);
    ctx.lineTo(lx - s, ly + s);
    ctx.stroke();

    // 중심 원
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(lx, ly, 15, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = 'white';
    ctx.lineWidth = 3;
    ctx.stroke();

    // 하단 판정 배너
    const bannerText = `JUDGMENT: ${landing.is_in_court ? 'IN' : 'OUT'}`;
    ctx.font = 'bold 60px Arial Black';
    const textMeasure = ctx.measureText(bannerText);
    const bW = textMeasure.width + 60;
    const bH = 80;
    const bX = (canvas.width - bW) / 2;
    const bY = canvas.height - 120;

    // 배경
    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
    ctx.fillRect(bX, bY, bW, bH);

    // 텍스트
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(bannerText, canvas.width / 2, bY + bH / 2 + 5);
}
