/**
 * CalibrationPage - Enhanced with Auto-Detection
 * 코트 캘리브레이션 페이지 (자동 검출 + 수동 조정)
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCalibration } from '../../hooks/useCalibration';
import './CalibrationPage.css';

const API_BASE_URL = import.meta.env.VITE_ANALYSIS_API_BASE_URL || 'http://localhost:8000';

// 신뢰도 임계값
const CONFIDENCE_THRESHOLDS = {
    EXCELLENT: 0.80,  // 80% 이상: 바로 진행
    GOOD: 0.70,       // 70-80%: 확인 후 진행
    WARNING: 0.60,    // 60-70%: 경고 + 수동 조정 권장
    POOR: 0.60        // 60% 미만: 수동 조정 필수
};

export function CalibrationPage() {
    const navigate = useNavigate();
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
        autoDetect,
        setDetectionMode,
        reset,
        isReady,
        isCalibrated,
        confidence,
        overlayUrl,
        detectionMode,
    } = useCalibration();

    const canvasRef = useRef<HTMLCanvasElement>(null);
    const imageRef = useRef<HTMLImageElement>(null);
    const [selectedCornerIndex, setSelectedCornerIndex] = useState<number>(0);
    const [showManualMode, setShowManualMode] = useState<boolean>(false);

    // 이미지 로드 시 Canvas에 그리기
    useEffect(() => {
        console.log('[CalibrationPage] Image load effect triggered', { imageUrl, canvasRef: !!canvasRef.current, showManualMode });

        if (!imageUrl || !canvasRef.current) return;

        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const img = new Image();
        img.onload = () => {
            console.log('[CalibrationPage] Image loaded successfully', { width: img.width, height: img.height });
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);
            imageRef.current = img;

            // 코너 그리기
            drawCorners(ctx);
        };
        img.onerror = (error) => {
            console.error('[CalibrationPage] Image load failed', { imageUrl, error });
        };
        img.src = imageUrl;
        console.log('[CalibrationPage] Image src set to:', imageUrl);
    }, [imageUrl, showManualMode]);

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

        // 선택된 코너 강조 (수동 모드일 때만)
        if (showManualMode && corners[selectedCornerIndex]) {
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
     * Canvas 클릭 핸들러 (수동 모드)
     */
    const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!showManualMode || !canvasRef.current) return;

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
            const uploadResponse = await uploadImage(file);
            setSelectedCornerIndex(0);
            setShowManualMode(false);

            // Use session_id from upload response
            await handleAutoDetect(uploadResponse.session_id);
        } catch (error) {
            console.error('Upload failed:', error);
        }
    };

    /**
     * Auto-detection execution
     */
    const handleAutoDetect = async (sessionIdParam?: string) => {
        try {
            // 파라미터가 있으면 그것을, 없으면 state의 sessionId를 사용
            // 중요: 이벤트 객체가 들어오는 것을 방지하기 위해 타입 체크
            const targetSessionId = (typeof sessionIdParam === 'string' && sessionIdParam) ? sessionIdParam : sessionId;

            if (!targetSessionId) {
                console.error('No session ID available');
                setShowManualMode(true);
                return;
            }

            console.log('Starting auto-detection with session:', targetSessionId);

            // Call autoDetect hook directly with session ID
            await autoDetect(targetSessionId);

        } catch (error) {
            console.error('Auto-detection failed:', error);
            setShowManualMode(true);
        }
    };

    /**
     * 수동 조정 모드로 전환
     */
    const handleSwitchToManual = () => {
        console.log('[CalibrationPage] Switching to manual mode', {
            currentMode: showManualMode,
            imageUrl,
            corners
        });
        setShowManualMode(true);
        setDetectionMode('manual');
    };

    /**
     * 캘리브레이션 실행 (수동 모드)
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

    /**
     * 신뢰도 레벨 가져오기
     */
    const getConfidenceLevel = (): 'excellent' | 'good' | 'warning' | 'poor' | null => {
        if (!confidence) return null;
        const overall = confidence.overall;

        if (overall >= CONFIDENCE_THRESHOLDS.EXCELLENT) return 'excellent';
        if (overall >= CONFIDENCE_THRESHOLDS.GOOD) return 'good';
        if (overall >= CONFIDENCE_THRESHOLDS.WARNING) return 'warning';
        return 'poor';
    };

    const confidenceLevel = getConfidenceLevel();

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

            {/* 자동 검출 진행 중 */}
            {sessionId && isLoading && !showManualMode && (
                <div className="auto-detect-loading">
                    <h2>🔍 자동 검출 중...</h2>
                    <p>AI가 코트 코너를 자동으로 찾고 있습니다.</p>
                    <div className="loading-spinner"></div>
                </div>
            )}

            {/* 자동 검출 결과 */}
            {sessionId && confidence && !showManualMode && (
                <div className="auto-detect-result">
                    <h2>2. 자동 검출 결과</h2>

                    {/* 신뢰도 표시 */}
                    <div className={`confidence-card confidence-${confidenceLevel}`}>
                        <h3>
                            {confidenceLevel === 'excellent' && '✅ 우수한 검출 품질'}
                            {confidenceLevel === 'good' && '✓ 양호한 검출 품질'}
                            {confidenceLevel === 'warning' && '⚠️ 검출 품질 주의'}
                            {confidenceLevel === 'poor' && '❌ 낮은 검출 품질'}
                        </h3>
                        <div className="confidence-overall">
                            <span className="confidence-label">전체 신뢰도:</span>
                            <span className="confidence-value">{(confidence.overall * 100).toFixed(1)}%</span>
                        </div>
                        <div className="confidence-details">
                            <div className="confidence-item">
                                <span>마스크 품질:</span>
                                <span>{(confidence.mask_quality * 100).toFixed(0)}%</span>
                            </div>
                            <div className="confidence-item">
                                <span>형상 품질:</span>
                                <span>{(confidence.geometry_quality * 100).toFixed(0)}%</span>
                            </div>
                            <div className="confidence-item">
                                <span>캘리브레이션 품질:</span>
                                <span>{(confidence.calibration_quality * 100).toFixed(0)}%</span>
                            </div>
                        </div>
                    </div>

                    {/* 오버레이 이미지 */}
                    {overlayUrl && (
                        <div className="overlay-preview">
                            <h3>검출된 코트 라인</h3>
                            <img
                                src={`${API_BASE_URL}${overlayUrl}`}
                                alt="Court Overlay"
                                style={{ maxWidth: '100%', border: '2px solid #ccc' }}
                            />
                        </div>
                    )}

                    {/* 검출된 코너 정보 */}
                    <div className="corners-info">
                        <h3>검출된 코너 좌표</h3>
                        <div className="corners-grid">
                            {corners.map((corner, index) => (
                                <div key={index} className="corner-item">
                                    <span className="corner-label">{['TL', 'TR', 'BR', 'BL'][index]}:</span>
                                    <span className="corner-coords">
                                        ({corner[0].toFixed(1)}, {corner[1].toFixed(1)})
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* 액션 버튼 */}
                    <div className="action-buttons">
                        {confidenceLevel === 'excellent' || confidenceLevel === 'good' ? (
                            <>
                                <button
                                    onClick={() => navigate(`/analysis/video?session_id=${sessionId}`)}
                                    className="primary-button"
                                >
                                    ✓ 확인 및 비디오 분석 시작 →
                                </button>
                                <button
                                    onClick={handleSwitchToManual}
                                    className="secondary-button"
                                >
                                    ✋ 수동 조정
                                </button>
                            </>
                        ) : (
                            <>
                                <button
                                    onClick={handleSwitchToManual}
                                    className="primary-button"
                                >
                                    ✋ 수동 조정 필요
                                </button>
                                <button
                                    onClick={() => handleAutoDetect()}
                                    className="secondary-button"
                                >
                                    🔄 다시 검출
                                </button>
                            </>
                        )}
                    </div>
                </div>
            )}

            {/* 수동 조정 모드 */}
            {showManualMode && imageUrl && (
                <div className="manual-mode">
                    <h2>2. 코트 4개 코너 지정 (수동 조정)</h2>
                    <p className="manual-hint">
                        {confidence && confidence.overall < CONFIDENCE_THRESHOLDS.GOOD
                            ? '⚠️ 자동 검출 신뢰도가 낮아 수동 조정이 필요합니다.'
                            : '자동 검출된 코너를 수동으로 조정할 수 있습니다.'}
                    </p>
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

                    {isReady && (
                        <button
                            onClick={handleCalibrate}
                            disabled={isLoading}
                            className="calibrate-button"
                        >
                            {isLoading ? '처리 중...' : '캘리브레이션 실행'}
                        </button>
                    )}
                </div>
            )}

            {/* 캘리브레이션 결과 (수동 모드) */}
            {calibrationResult && showManualMode && (
                <div className="result-section">
                    <h2>3. 캘리브레이션 결과</h2>
                    <div className="result-card">
                        <p>✅ 상태: {calibrationResult.validation.is_valid ? '성공' : '실패'}</p>
                        <p>📏 Pixels per meter: {calibrationResult.pixels_per_meter.toFixed(2)}</p>
                        <p>📐 코트 면적: {calibrationResult.court_area.toFixed(0)} px²</p>
                        <p>💬 {calibrationResult.validation.message}</p>
                    </div>

                    <button
                        onClick={() => window.location.href = `/analysis/video?session_id=${sessionId}`}
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
