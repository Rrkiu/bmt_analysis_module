/**
 * VideoAnalysisPage.tsx
 * 비디오 분석 페이지
 * 
 * [추가됨 - 2025-12-23]
 * Step 2: 비디오 업로드 및 재생 기능 구현
 * 
 * 기능:
 * 1. 비디오 파일 선택 (로컬 파일 업로드)
 * 2. HTML5 Video Player
 * 3. 재생 컨트롤 (재생/일시정지, 탐색)
 * 4. Session ID 전달받아 캘리브레이션 데이터 활용
 */

import { useState, useRef, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useVideoAnalysis } from '../../hooks/useVideoAnalysis';  // [추가됨 - Step 3]
import { AnalysisCanvas } from '../../components/Analysis/AnalysisCanvas';  // [추가됨 - Step 3]
import './VideoAnalysisPage.css';

export function VideoAnalysisPage() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();

    // URL에서 session_id 가져오기
    const sessionId = searchParams.get('session_id');

    // 비디오 관련 상태
    const [videoFile, setVideoFile] = useState<File | null>(null);
    const [videoUrl, setVideoUrl] = useState<string | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [showOverlay, setShowOverlay] = useState(true);  // [추가됨 - Step 3]

    const videoRef = useRef<HTMLVideoElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // [추가됨 - Step 3] 분석 Hook
    const {
        calibrationData,
        shuttlecock,
        landing,
        isAnalyzing,
        startAnalysis,
        stopAnalysis,
    } = useVideoAnalysis(sessionId, videoRef);

    /**
     * 비디오 파일 선택 핸들러
     */
    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        // 비디오 파일 타입 체크
        if (!file.type.startsWith('video/')) {
            alert('비디오 파일만 선택 가능합니다.');
            return;
        }

        setVideoFile(file);

        // 기존 URL 해제
        if (videoUrl) {
            URL.revokeObjectURL(videoUrl);
        }

        // 새 URL 생성
        const url = URL.createObjectURL(file);
        setVideoUrl(url);
    };

    /**
     * 재생/일시정지 토글
     */
    const togglePlayPause = () => {
        if (!videoRef.current) return;

        if (isPlaying) {
            videoRef.current.pause();
        } else {
            videoRef.current.play();
        }
        setIsPlaying(!isPlaying);
    };

    /**
     * 비디오 시간 업데이트
     */
    const handleTimeUpdate = () => {
        if (!videoRef.current) return;
        setCurrentTime(videoRef.current.currentTime);
    };

    /**
     * 비디오 메타데이터 로드
     */
    const handleLoadedMetadata = () => {
        if (!videoRef.current) return;
        setDuration(videoRef.current.duration);
    };

    /**
     * 탐색 바 변경
     */
    const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!videoRef.current) return;
        const time = parseFloat(e.target.value);
        videoRef.current.currentTime = time;
        setCurrentTime(time);
    };

    /**
     * 시간 포맷 (초 → MM:SS)
     */
    const formatTime = (seconds: number): string => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    };

    /**
     * 컴포넌트 언마운트 시 URL 해제
     */
    useEffect(() => {
        return () => {
            if (videoUrl) {
                URL.revokeObjectURL(videoUrl);
            }
        };
    }, [videoUrl]);

    /**
     * Session ID 체크
     */
    useEffect(() => {
        if (!sessionId) {
            alert('캘리브레이션을 먼저 수행해주세요.');
            navigate('/analysis/calibration');
        }
    }, [sessionId, navigate]);

    return (
        <div className="video-analysis-page">
            <h1>비디오 분석</h1>

            {/* Session 정보 */}
            {sessionId && (
                <div className="session-info">
                    <p>📌 Session ID: <code>{sessionId}</code></p>
                    <p>✅ 캘리브레이션 완료</p>
                </div>
            )}

            {/* 비디오 파일 선택 */}
            {!videoFile && (
                <div className="upload-section">
                    <h2>1. 비디오 파일 선택</h2>
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="video/*"
                        onChange={handleFileSelect}
                        style={{ display: 'none' }}
                    />
                    <button
                        onClick={() => fileInputRef.current?.click()}
                        className="upload-button"
                    >
                        📁 비디오 파일 선택
                    </button>
                    <p className="hint">
                        지원 형식: MP4, AVI, MOV 등
                    </p>
                </div>
            )}

            {/* 비디오 플레이어 */}
            {videoUrl && (
                <div className="video-section">
                    <h2>2. 비디오 재생</h2>

                    {/* 비디오 엘리먼트 + Canvas 오버레이 */}
                    <div className="video-container" style={{ position: 'relative', width: '100%', display: 'inline-block' }}>
                        <video
                            ref={videoRef}
                            src={videoUrl}
                            onTimeUpdate={handleTimeUpdate}
                            onLoadedMetadata={handleLoadedMetadata}
                            onPlay={() => setIsPlaying(true)}
                            onPause={() => setIsPlaying(false)}
                            style={{
                                width: '100%',
                                height: 'auto',
                                backgroundColor: '#000',
                                display: 'block'
                            }}
                        />
                        {/* [추가됨 - Step 3] Canvas 오버레이 */}
                        <AnalysisCanvas
                            videoRef={videoRef}
                            calibrationData={calibrationData}
                            shuttlecock={shuttlecock}
                            landing={landing}
                            showOverlay={showOverlay}
                        />
                    </div>

                    {/* 비디오 컨트롤 */}
                    <div className="video-controls">
                        {/* 재생/일시정지 버튼 */}
                        <button onClick={togglePlayPause} className="control-button">
                            {isPlaying ? '⏸️ 일시정지' : '▶️ 재생'}
                        </button>

                        {/* 시간 표시 */}
                        <span className="time-display">
                            {formatTime(currentTime)} / {formatTime(duration)}
                        </span>

                        {/* 탐색 바 */}
                        <input
                            type="range"
                            min="0"
                            max={duration || 0}
                            value={currentTime}
                            onChange={handleSeek}
                            className="seek-bar"
                        />
                    </div>

                    {/* 비디오 정보 */}
                    <div className="video-info">
                        <p>📹 파일명: {videoFile?.name}</p>
                        <p>⏱️ 길이: {formatTime(duration)}</p>
                        <p>📏 크기: {((videoFile?.size || 0) / 1024 / 1024).toFixed(2)} MB</p>
                    </div>

                    {/* [수정됨 - Step 3] 분석 컨트롤 */}
                    <div className="analysis-section">
                        <button
                            className={isAnalyzing ? "stop-button" : "analyze-button"}
                            onClick={() => {
                                if (isAnalyzing) {
                                    stopAnalysis();
                                } else {
                                    startAnalysis();
                                }
                            }}
                        >
                            {isAnalyzing ? '⏹️ 분석 중지' : '🎯 분석 시작'}
                        </button>
                        <p className="hint">
                            {isAnalyzing
                                ? '30fps로 실시간 분석 중... 셔틀콕 위치와 낙하 지점이 표시됩니다.'
                                : '분석 시작 시 비디오의 각 프레임을 분석하여 셔틀콕을 추적합니다.'}
                        </p>

                        {/* 오버레이 토글 */}
                        <label style={{ display: 'block', marginTop: '10px' }}>
                            <input
                                type="checkbox"
                                checked={showOverlay}
                                onChange={(e) => setShowOverlay(e.target.checked)}
                            />
                            {' '}코트 오버레이 표시
                        </label>
                    </div>
                </div>
            )}

            {/* 뒤로 가기 */}
            <button
                onClick={() => navigate('/analysis/calibration')}
                className="back-button"
            >
                ← 캘리브레이션으로 돌아가기
            </button>
        </div>
    );
}
