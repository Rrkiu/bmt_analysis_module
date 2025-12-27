/**
 * CalibrationPage
 * 코트 캘리브레이션 페이지
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';  // [추가됨]
import { useCalibration } from '../../hooks/useCalibration';
import './CalibrationPage.css';

export function CalibrationPage() {
    const navigate = useNavigate();  // [추가됨]
    const {
        sessionId,
        imageUrl,
        imageSize,
        corners,
        calibrationResult,
        isLoading,
        error,
        uploadImage,
        setCorner,
        calibrate,
        reset,
        isReady,
        isCalibrated,
    } = useCalibration();

    const canvasRef = useRef<HTMLCanvasElement>(null);
    const imageRef = useRef<HTMLImageElement>(null);
    const [selectedCornerIndex, setSelectedCornerIndex] = useState<number>(0);

    // 이미지 로드 시 Canvas에 그리기
    useEffect(() => {
        if (!imageUrl || !canvasRef.current) return;

        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const img = new Image();
        img.onload = () => {
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);
            imageRef.current = img;

            // 코너 그리기
            drawCorners(ctx);
        };
        img.src = imageUrl;
    }, [imageUrl]);

    // 코너 변경 시 다시 그리기
    useEffect(() => {
        if (!canvasRef.current || !imageRef.current) return;

        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // 이미지 다시 그리기
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(imageRef.current, 0, 0);

        // 코너 그리기
        drawCorners(ctx);
    }, [corners]);

    /**
     * Canvas에 코너 그리기
     */
    const drawCorners = (ctx: CanvasRenderingContext2D) => {
        const colors = ['#00FF00', '#0000FF', '#FF0000', '#FFFF00']; // TL, TR, BR, BL
        const labels = ['TL', 'TR', 'BR', 'BL'];

        corners.forEach((corner, index) => {
            if (corner) {
                const [x, y] = corner;

                // 원 그리기
                ctx.fillStyle = colors[index];
                ctx.beginPath();
                ctx.arc(x, y, 10, 0, 2 * Math.PI);
                ctx.fill();

                // 외곽선
                ctx.strokeStyle = '#FFFFFF';
                ctx.lineWidth = 2;
                ctx.stroke();

                // 레이블
                ctx.fillStyle = '#FFFFFF';
                ctx.font = 'bold 14px Arial';
                ctx.fillText(labels[index], x + 15, y - 10);
            }
        });

        // 선택된 코너 강조
        if (corners[selectedCornerIndex]) {
            const [x, y] = corners[selectedCornerIndex];
            ctx.strokeStyle = '#00FFFF';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(x, y, 15, 0, 2 * Math.PI);
            ctx.stroke();
        }

        // 코너가 4개 모두 있으면 폴리곤 그리기
        if (corners.length === 4 && corners.every(c => c)) {
            ctx.strokeStyle = '#00FFFF';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(corners[0][0], corners[0][1]);
            corners.forEach(corner => ctx.lineTo(corner[0], corner[1]));
            ctx.closePath();
            ctx.stroke();
        }
    };

    /**
     * Canvas 클릭 핸들러
     */
    const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!canvasRef.current) return;

        const canvas = canvasRef.current;
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;

        const x = (e.clientX - rect.left) * scaleX;
        const y = (e.clientY - rect.top) * scaleY;

        setCorner(selectedCornerIndex, x, y);

        // 다음 코너로 자동 이동
        if (selectedCornerIndex < 3) {
            setSelectedCornerIndex(selectedCornerIndex + 1);
        }
    };

    /**
     * 파일 업로드 핸들러
     */
    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        try {
            await uploadImage(file);
            setSelectedCornerIndex(0);
        } catch (error) {
            console.error('Upload failed:', error);
        }
    };

    /**
     * 캘리브레이션 실행
     */
    const handleCalibrate = async () => {
        try {
            await calibrate();
            alert('캘리브레이션 완료!');
        } catch (error) {
            console.error('Calibration failed:', error);
            alert('캘리브레이션 실패: ' + (error instanceof Error ? error.message : 'Unknown error'));
        }
    };

    return (
        <div className="calibration-page">
            <h1>코트 캘리브레이션</h1>

            {/* 파일 업로드 */}
            {!sessionId && (
                <div className="upload-section">
                    <h2>1. 이미지 업로드</h2>
                    <input
                        type="file"
                        accept="image/*"
                        onChange={handleFileUpload}
                        disabled={isLoading}
                    />
                </div>
            )}

            {/* 캔버스 */}
            {imageUrl && (
                <div className="canvas-section">
                    <h2>2. 코트 4개 코너 지정</h2>
                    <p>
                        현재 선택: <strong>{['좌상단(TL)', '우상단(TR)', '우하단(BR)', '좌하단(BL)'][selectedCornerIndex]}</strong>
                    </p>

                    <div className="corner-selector">
                        {['TL', 'TR', 'BR', 'BL'].map((label, index) => (
                            <button
                                key={label}
                                onClick={() => setSelectedCornerIndex(index)}
                                className={selectedCornerIndex === index ? 'active' : ''}
                                disabled={isLoading}
                            >
                                {label} {corners[index] ? '✓' : ''}
                            </button>
                        ))}
                    </div>

                    <canvas
                        ref={canvasRef}
                        onClick={handleCanvasClick}
                        style={{ maxWidth: '100%', cursor: 'crosshair', border: '2px solid #ccc' }}
                    />
                </div>
            )}

            {/* 캘리브레이션 버튼 */}
            {isReady && !isCalibrated && (
                <div className="calibrate-section">
                    <button
                        onClick={handleCalibrate}
                        disabled={isLoading}
                        className="calibrate-button"
                    >
                        {isLoading ? '처리 중...' : '캘리브레이션 실행'}
                    </button>
                </div>
            )}

            {/* 결과 */}
            {calibrationResult && (
                <div className="result-section">
                    <h2>3. 캘리브레이션 결과</h2>
                    <div className="result-card">
                        <p>✅ 상태: {calibrationResult.validation.is_valid ? '성공' : '실패'}</p>
                        <p>📏 Pixels per meter: {calibrationResult.pixels_per_meter.toFixed(2)}</p>
                        <p>📐 코트 면적: {calibrationResult.court_area.toFixed(0)} px²</p>
                        <p>💬 {calibrationResult.validation.message}</p>
                    </div>

                    <button
                        onClick={() => {
                            // [디버깅] 직접 URL 변경으로 테스트
                            console.log('🚀 비디오 분석 버튼 클릭');
                            console.log('Session ID:', sessionId);
                            const targetUrl = `/analysis/video?session_id=${sessionId}`;
                            console.log('Target URL:', targetUrl);

                            // window.location.href로 직접 이동 (테스트)
                            window.location.href = targetUrl;
                        }}
                        className="video-analysis-button"
                    >
                        비디오 분석 시작 →
                    </button>
                </div>
            )}

            {/* 에러 */}
            {error && (
                <div className="error-message">
                    ❌ {error}
                </div>
            )}

            {/* 초기화 */}
            {sessionId && (
                <button onClick={reset} className="reset-button">
                    처음부터 다시 시작
                </button>
            )}
        </div>
    );
}
