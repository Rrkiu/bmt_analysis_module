/**
 * Analysis API Client
 * Backend API와 통신하는 클라이언트
 * 
 * [수정됨 - 2025-12-23]
 * Birdie Buddies API와 분리하기 위해 VITE_ANALYSIS_API_BASE_URL 사용
 */

// Vite proxy 경유: 브라우저에서 /api/xxx 상대경로 요청 → Vite가 WSL 내부 127.0.0.1:8000으로 전달
// localhost:8000 직접 접근은 WSL 포트포워딩 불안정으로 사용하지 않음
const API_BASE_URL = import.meta.env.VITE_ANALYSIS_API_BASE_URL || '';


// ============================================
// Types
// ============================================

export interface UploadResponse {
    success: boolean;
    session_id: string;
    message: string;
    data: {
        width: number;
        height: number;
        filename: string;
        image_url?: string;  // 서버에 저장된 이미지 URL
    };
}

export interface CalibrationRequest {
    session_id: string;
    corners: number[][];  // [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    image_width: number;
    image_height: number;
}

export interface CalibrationResponse {
    success: boolean;
    session_id: string;
    message: string;
    data: {
        court_corners: number[][];
        pixels_per_meter: number;
        court_area: number;
        validation: {
            is_valid: boolean;
            message: string;
        };
    };
}

export interface FramePredictionResponse {
    success: boolean;
    tracknet: {
        x: number;
        y: number;
        visibility: number;
    };
    landing: {
        is_landed: boolean;
        pos: number[] | null;
        image_x: number;
        image_y: number;
        is_in_court: boolean;
        time_since: number;
    } | null;
    processed_image?: string;  // base64 encoded
}

export interface VideoListResponse {
    success: boolean;
    videos: Array<{
        filename: string;
        path: string;
        size_mb: number;
        modified: string;
    }>;
    count: number;
}

export interface AutoDetectRequest {
    session_id: string;
    include_doubles?: boolean;
    overlay_alpha?: number;
    draw_corners?: boolean;
    save_overlay?: boolean;
    roi?: {  // ROI 영역 (선택적)
        x: number;
        y: number;
        width: number;
        height: number;
    };
}

export interface AutoDetectResponse {
    success: boolean;
    session_id: string;
    message: string;
    confidence?: {
        mask_quality: number;
        geometry_quality: number;
        calibration_quality: number;
        overall: number;
    };
    corners?: {
        TL: [number, number];
        TR: [number, number];
        BR: [number, number];
        BL: [number, number];
    };
    calibration?: {
        pixels_per_meter: number;
        homography_matrix: number[][];
    };
    overlay_url?: string;
    metadata?: {
        image_shape: [number, number];
        include_doubles: boolean;
        detection_time: string;
    };
    error?: string;
}

// ============================================
// API Functions
// ============================================

/**
 * 이미지 업로드 (세션 시작)
 */
export async function uploadImage(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/upload`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
    }

    return response.json();
}

/**
 * 4점 코너로 캘리브레이션
 */
export async function alignCorners(
    request: CalibrationRequest
): Promise<CalibrationResponse> {
    const response = await fetch(`${API_BASE_URL}/api/align-corners`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        throw new Error(`Calibration failed: ${response.statusText}`);
    }

    return response.json();
}

/**
 * 프레임 단위 분석 (실시간)
 */
export async function predictFrame(
    sessionId: string,
    frameBlob: Blob,
    videoTime: number = 0
): Promise<FramePredictionResponse> {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('file', frameBlob);
    formData.append('video_time', videoTime.toString());

    const response = await fetch(`${API_BASE_URL}/api/analysis/frame-predict`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        throw new Error(`Frame prediction failed: ${response.statusText}`);
    }

    return response.json();
}

/**
 * 사용 가능한 비디오 목록 조회
 */
export async function listVideos(): Promise<VideoListResponse> {
    const response = await fetch(`${API_BASE_URL}/api/videos/list`);

    if (!response.ok) {
        throw new Error(`Failed to list videos: ${response.statusText}`);
    }

    return response.json();
}

/**
 * 자동 코트 검출 (Milestone 5)
 */
export async function autoDetectCourt(
    request: AutoDetectRequest
): Promise<AutoDetectResponse> {
    const response = await fetch(`${API_BASE_URL}/api/detect-court-auto`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error('Auto-detection API error:', errorData);
        throw new Error(`Auto-detection failed: ${response.statusText} - ${JSON.stringify(errorData)}`);
    }

    return response.json();
}

/**
 * 자동 검출 상태 조회
 */
export async function getAutoDetectStatus(sessionId: string): Promise<AutoDetectResponse> {
    const response = await fetch(`${API_BASE_URL}/api/detect-court-auto/status/${sessionId}`);

    if (!response.ok) {
        throw new Error(`Failed to get status: ${response.statusText}`);
    }

    return response.json();
}

/**
 * 업로드된 이미지 URL 가져오기
 */
export function getImageUrl(sessionId: string, type: 'original' | 'result' | 'guide'): string {
    return `${API_BASE_URL}/api/image/${sessionId}/${type}`;
}

/**
 * 비디오 스트리밍 URL 가져오기
 */
export function getVideoStreamUrl(videoPath: string): string {
    return `${API_BASE_URL}/api/videos/stream?path=${encodeURIComponent(videoPath)}`;
}
