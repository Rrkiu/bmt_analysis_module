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
    });

    /**
     * 이미지 업로드
     */
    const uploadImage = useCallback(async (file: File) => {
        setState(prev => ({ ...prev, isLoading: true, error: null }));

        try {
            const response = await analysisAPI.uploadImage(file);

            setState(prev => ({
                ...prev,
                sessionId: response.session_id,
                imageUrl: URL.createObjectURL(file),
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
        });
    }, []);

    return {
        ...state,
        uploadImage,
        setCorner,
        setCorners,
        calibrate,
        reset,
        isReady: state.corners.length === 4,
        isCalibrated: state.calibrationResult !== null,
    };
}
