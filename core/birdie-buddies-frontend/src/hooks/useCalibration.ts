/**
 * useCalibration Hook
 * 캘리브레이션 프로세스 관리
 */

import { useState, useCallback } from 'react';
import * as analysisAPI from '../services/analysisAPI';

interface CalibrationState {
    sessionId: string | null;
    imageUrl: string | null;
    imageSize: { width: number; height: number } | null;
    corners: number[][];
    calibrationResult: analysisAPI.CalibrationResponse['data'] | null;
    isLoading: boolean;
    error: string | null;
    // Auto-detection fields
    autoDetectResult: analysisAPI.AutoDetectResponse | null;
    confidence: analysisAPI.AutoDetectResponse['confidence'] | null;
    overlayUrl: string | null;
    detectionMode: 'auto' | 'manual';
}

export function useCalibration() {
    const [state, setState] = useState<CalibrationState>({
        sessionId: null,
        imageUrl: null,
        imageSize: null,
        corners: [],
        calibrationResult: null,
        isLoading: false,
        error: null,
        autoDetectResult: null,
        confidence: null,
        overlayUrl: null,
        detectionMode: 'auto',
    });

    /**
     * 이미지 업로드
     */
    const uploadImage = useCallback(async (file: File) => {
        setState(prev => ({ ...prev, isLoading: true, error: null }));

        try {
            const response = await analysisAPI.uploadImage(file);

            // 서버에서 제공하는 이미지 URL 사용 (blob URL 대신)
            const API_BASE_URL = import.meta.env.VITE_ANALYSIS_API_BASE_URL || 'http://localhost:8000';
            const serverImageUrl = response.data.image_url
                ? `${API_BASE_URL}${response.data.image_url}`
                : URL.createObjectURL(file); // fallback

            console.log('[useCalibration] Upload response:', response);
            console.log('[useCalibration] Server image URL:', serverImageUrl);

            setState(prev => ({
                ...prev,
                sessionId: response.session_id,
                imageUrl: serverImageUrl,
                imageSize: {
                    width: response.data.width,
                    height: response.data.height,
                },
                corners: [],
                calibrationResult: null,
                isLoading: false,
            }));

            return response;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Upload failed';
            setState(prev => ({ ...prev, isLoading: false, error: errorMessage }));
            throw error;
        }
    }, []);

    /**
     * 코너 추가/업데이트
     */
    const setCorner = useCallback((index: number, x: number, y: number) => {
        setState(prev => {
            const newCorners = [...prev.corners];
            newCorners[index] = [x, y];
            return { ...prev, corners: newCorners };
        });
    }, []);

    /**
     * 모든 코너 설정
     */
    const setCorners = useCallback((corners: number[][]) => {
        setState(prev => ({ ...prev, corners }));
    }, []);

    /**
     * 캘리브레이션 실행
     */
    const calibrate = useCallback(async () => {
        if (!state.sessionId || !state.imageSize || state.corners.length !== 4) {
            throw new Error('Invalid calibration state');
        }

        setState(prev => ({ ...prev, isLoading: true, error: null }));

        try {
            const response = await analysisAPI.alignCorners({
                session_id: state.sessionId,
                corners: state.corners,
                image_width: state.imageSize.width,
                image_height: state.imageSize.height,
            });

            setState(prev => ({
                ...prev,
                calibrationResult: response.data,
                isLoading: false,
            }));

            return response;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Calibration failed';
            setState(prev => ({ ...prev, isLoading: false, error: errorMessage }));
            throw error;
        }
    }, [state.sessionId, state.imageSize, state.corners]);

    /**
     * 자동 코트 검출 실행
     */
    const autoDetect = useCallback(async (sessionIdOverride?: string) => {
        const targetSessionId = sessionIdOverride || state.sessionId;

        if (!targetSessionId) {
            throw new Error('No session ID');
        }

        setState(prev => ({ ...prev, isLoading: true, error: null }));

        try {
            const response = await analysisAPI.autoDetectCourt({
                session_id: targetSessionId,
                include_doubles: true,
                overlay_alpha: 1.0,
                draw_corners: true,
                save_overlay: true,
            });

            if (!response.success) {
                throw new Error(response.error || 'Auto-detection failed');
            }

            // Convert corners from object to array
            const cornersArray = response.corners
                ? [
                    response.corners.TL,
                    response.corners.TR,
                    response.corners.BR,
                    response.corners.BL,
                ]
                : [];

            setState(prev => ({
                ...prev,
                autoDetectResult: response,
                confidence: response.confidence || null,
                overlayUrl: response.overlay_url || null,
                corners: cornersArray,
                calibrationResult: response.calibration ? {
                    court_corners: cornersArray,
                    pixels_per_meter: response.calibration.pixels_per_meter,
                    court_area: 0, // Not provided by auto-detect
                    validation: {
                        is_valid: (response.confidence?.overall || 0) >= 0.7,
                        message: `Auto-detection confidence: ${((response.confidence?.overall || 0) * 100).toFixed(1)}%`
                    }
                } : null,
                isLoading: false,
            }));

            return response;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Auto-detection failed';
            setState(prev => ({ ...prev, isLoading: false, error: errorMessage }));
            throw error;
        }
    }, [state.sessionId]);

    /**
     * 검출 모드 전환
     */
    const setDetectionMode = useCallback((mode: 'auto' | 'manual') => {
        setState(prev => ({ ...prev, detectionMode: mode }));
    }, []);

    /**
     * 초기화
     */
    const reset = useCallback(() => {
        setState({
            sessionId: null,
            imageUrl: null,
            imageSize: null,
            corners: [],
            calibrationResult: null,
            isLoading: false,
            error: null,
            autoDetectResult: null,
            confidence: null,
            overlayUrl: null,
            detectionMode: 'auto',
        });
    }, []);

    return {
        ...state,
        uploadImage,
        setCorner,
        setCorners,
        calibrate,
        autoDetect,
        setDetectionMode,
        reset,
        isReady: state.corners.length === 4,
        isCalibrated: state.calibrationResult !== null,
    };
}
