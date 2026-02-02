/**
 * useVideoAnalysis.ts
 * 비디오 분석 Custom Hook
 * 
 * [추가됨 - Step 3]
 * 30fps로 실시간 프레임 분석 수행 (YOLO 모델 사용)
 * 
 * 기능:
 * 1. 비디오 프레임 캡처 (Canvas API)
 * 2. 백엔드 API 호출 (33ms 간격 = 30fps)
 * 3. 셔틀콕 위치 및 낙하 판정 수신
 * 4. 캘리브레이션 데이터 로드
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import * as analysisAPI from '../services/analysisAPI';

// 30fps = 33ms 간격 (YOLO 모델은 빠르고 가벼워서 30fps 가능)
const ANALYSIS_INTERVAL = 33;


interface CalibrationData {
    court_corners_image: number[][];
    image_shape: number[];  // [height, width]
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

interface AnalysisState {
    calibrationData: CalibrationData | null;
    shuttlecock: ShuttlecockData | null;
    landing: LandingData | null;
    isAnalyzing: boolean;
    error: string | null;
}

export function useVideoAnalysis(sessionId: string | null, videoRef: React.RefObject<HTMLVideoElement | null>) {
    const [state, setState] = useState<AnalysisState>({
        calibrationData: null,
        shuttlecock: null,
        landing: null,
        isAnalyzing: false,
        error: null,
    });

    const lastAnalysisTimeRef = useRef<number>(0);
    const analysisIntervalRef = useRef<NodeJS.Timeout | null>(null);

    /**
     * 캘리브레이션 데이터 로드
     */
    const loadCalibration = useCallback(async () => {
        if (!sessionId) return;

        try {
            // 올바른 API 경로: /api/session/{session_id}/calibration
            const API_BASE_URL = import.meta.env.VITE_ANALYSIS_API_BASE_URL || 'http://localhost:8000';
            const response = await fetch(
                `${API_BASE_URL}/api/session/${sessionId}/calibration`
            );

            if (!response.ok) {
                throw new Error('캘리브레이션 데이터를 불러올 수 없습니다');
            }

            const result = await response.json();
            setState(prev => ({
                ...prev,
                calibrationData: result.calibration_result,
            }));
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            setState(prev => ({ ...prev, error: errorMessage }));
        }
    }, [sessionId]);

    /**
     * 프레임 캡처 및 분석 요청
     */
    const analyzeFrame = useCallback(async () => {
        if (!sessionId || !videoRef.current) return;

        const now = Date.now();
        if (now - lastAnalysisTimeRef.current < ANALYSIS_INTERVAL) return;
        lastAnalysisTimeRef.current = now;

        const video = videoRef.current;
        // 일시정지 시에만 분석 중단 (동영상 종료 후에도 분석 계속)
        if (video.paused) return;

        try {
            // Canvas에 현재 프레임 그리기
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext('2d');
            if (!ctx) return;

            ctx.drawImage(video, 0, 0);

            // Blob으로 변환
            canvas.toBlob(async (blob) => {
                if (!blob) return;

                const currentTime = video.currentTime;

                try {
                    const result = await analysisAPI.predictFrame(sessionId, blob, currentTime);

                    if (result.success) {
                        setState(prev => ({
                            ...prev,
                            shuttlecock: result.tracknet,
                            landing: result.landing,
                        }));
                    }
                } catch (error) {
                    console.error('Frame analysis error:', error);
                }
            }, 'image/jpeg', 0.7);

        } catch (error) {
            console.error('Frame capture error:', error);
        }
    }, [sessionId, videoRef]);

    /**
     * 분석 시작
     */
    const startAnalysis = useCallback(() => {
        if (analysisIntervalRef.current) return;

        setState(prev => ({ ...prev, isAnalyzing: true }));

        // 30fps로 분석 요청
        analysisIntervalRef.current = setInterval(() => {
            analyzeFrame();
        }, ANALYSIS_INTERVAL);
    }, [analyzeFrame]);


    /**
     * 분석 중지
     */
    const stopAnalysis = useCallback(() => {
        if (analysisIntervalRef.current) {
            clearInterval(analysisIntervalRef.current);
            analysisIntervalRef.current = null;
        }

        setState(prev => ({
            ...prev,
            isAnalyzing: false,
            shuttlecock: null,
            landing: null,
        }));
    }, []);

    /**
     * 초기화 시 캘리브레이션 로드
     */
    useEffect(() => {
        if (sessionId) {
            loadCalibration();
        }
    }, [sessionId, loadCalibration]);

    /**
     * 컴포넌트 언마운트 시 정리
     */
    useEffect(() => {
        return () => {
            if (analysisIntervalRef.current) {
                clearInterval(analysisIntervalRef.current);
            }
        };
    }, []);

    return {
        ...state,
        startAnalysis,
        stopAnalysis,
        loadCalibration,
    };
}
