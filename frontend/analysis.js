// 실시간 비디오 분석 스크립트 (실시간 동기화 방식)

const API_BASE_URL = 'http://localhost:8000';

let videoPlayer = null;
let canvas = null;
let ctx = null;
let calibrationData = null;
let displayMode = 'debug';
let showOverlay = true;
let animationFrameId = null;

let lastAnalysisTime = 0;
const ANALYSIS_INTERVAL = 100; // 100ms 마다 추적 (약 10fps)
let currentShuttlecock = null; // {x, y, visibility}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function () {
    console.log('🎥 실시간 분석 페이지 로드');

    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    const videoPath = urlParams.get('video_path');
    const mode = urlParams.get('mode') || 'debug';

    if (!sessionId || !videoPath) {
        alert('필수 파라미터가 없습니다.');
        goBack();
        return;
    }

    initializePlayer(sessionId, videoPath, mode);
});

// 플레이어 초기화
async function initializePlayer(sessionId, videoPath, mode) {
    showLoading();

    try {
        canvas = document.getElementById('videoCanvas');
        ctx = canvas.getContext('2d');
        videoPlayer = document.getElementById('videoPlayer');

        displayMode = mode;
        document.getElementById('displayMode').value = mode;

        // 1. 세션에서 캘리브레이션 데이터 로드
        const calibResponse = await fetch(`${API_BASE_URL}/api/session/${sessionId}/calibration`);
        if (!calibResponse.ok) throw new Error('캘리브레이션 데이터를 불러올 수 없습니다');
        const calibResult = await calibResponse.json();
        calibrationData = calibResult.calibration_result;

        // 2. 비디오 로드 (정적 마운트 경로 사용)
        const videoUrl = `${API_BASE_URL}/${videoPath}`;
        console.log('🚀 Final Video URL:', videoUrl);
        videoPlayer.src = videoUrl;

        await new Promise((resolve, reject) => {
            videoPlayer.onloadedmetadata = resolve;
            videoPlayer.onerror = reject;
        });

        // 3. 캔버스 크기 설정
        canvas.width = videoPlayer.videoWidth;
        canvas.height = videoPlayer.videoHeight;

        displayInfo();
        setupVideoEvents();
        startRendering();

        hideLoading();

    } catch (error) {
        console.error('❌ 초기화 실패:', error);
        alert('초기화 실패: ' + error.message);
        hideLoading();
    }
}

// 비디오 이벤트 설정
function setupVideoEvents() {
    const seekBar = document.getElementById('seekBar');

    videoPlayer.addEventListener('timeupdate', function () {
        const progress = (videoPlayer.currentTime / videoPlayer.duration) * 100;
        seekBar.value = progress;
        updateTimeDisplay();
    });

    seekBar.addEventListener('input', function () {
        const time = (seekBar.value / 100) * videoPlayer.duration;
        videoPlayer.currentTime = time;
        currentShuttlecock = null; // 탐색 시 이전 위치 초기화
    });

    videoPlayer.addEventListener('ended', function () {
        updatePlayPauseIcon(false);
    });
}

// 렌더링 시작
function startRendering() {
    function render() {
        drawFrame();
        animationFrameId = requestAnimationFrame(render);
    }
    render();
}

// 프레임 그리기
function drawFrame() {
    // 1. 비디오 프레임 그리기
    ctx.drawImage(videoPlayer, 0, 0, canvas.width, canvas.height);

    // 2. 실시간 분석 요청 (재생 중일 때만)
    if (!videoPlayer.paused && !videoPlayer.ended) {
        requestFrameAnalysis();
    }

    // 3. 코트 오버레이 그리기
    if (showOverlay && calibrationData) {
        drawOverlay();
    }

    // 4. 셔틀콕 그리기 (분석 데이터가 있을 경우)
    if (currentShuttlecock && currentShuttlecock.visibility === 1) {
        drawShuttlecock(currentShuttlecock);
    }
}

// 오버레이 그리기
function drawOverlay() {
    const corners = calibrationData.court_corners_image;
    if (!corners || corners.length !== 4) return;

    const scaleX = canvas.width / calibrationData.image_shape[1];
    const scaleY = canvas.height / calibrationData.image_shape[0];

    const scaledCorners = corners.map(([x, y]) => [x * scaleX, y * scaleY]);

    if (displayMode === 'normal') {
        drawNormalOverlay(scaledCorners);
    } else {
        drawDebugOverlay(scaledCorners);
    }
}

function drawNormalOverlay(corners) {
    ctx.fillStyle = 'rgba(0, 255, 0, 0.15)';
    ctx.beginPath();
    ctx.moveTo(corners[0][0], corners[0][1]);
    corners.forEach(([x, y]) => ctx.lineTo(x, y));
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = 'rgba(255, 255, 0, 0.8)';
    ctx.lineWidth = 3;
    ctx.stroke();
}

function drawDebugOverlay(corners) {
    ctx.fillStyle = 'rgba(0, 255, 0, 0.3)';
    ctx.beginPath();
    ctx.moveTo(corners[0][0], corners[0][1]);
    corners.forEach(([x, y]) => ctx.lineTo(x, y));
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = 'rgba(0, 255, 255, 0.9)';
    ctx.lineWidth = 3;
    ctx.stroke();

    const colors = ['#00ff00', '#ff0000', '#0000ff', '#ffff00'];
    const labels = ['TL', 'TR', 'BR', 'BL'];

    corners.forEach(([x, y], i) => {
        ctx.fillStyle = colors[i];
        ctx.beginPath();
        ctx.arc(x, y, 10, 0, 2 * Math.PI);
        ctx.fill();
        ctx.fillStyle = 'white';
        ctx.font = 'bold 14px Arial';
        ctx.fillText(labels[i], x + 15, y - 5);
    });
}

// 셔틀콕 시각화
function drawShuttlecock(pred) {
    const scaleX = canvas.width / calibrationData.image_shape[1];
    const scaleY = canvas.height / calibrationData.image_shape[0];

    // TrackNet 좌표는 512x288 기준이므로 이를 원본 이미지 비율로 먼저 환산해야 함 
    // VideoAnalysisService에서 이미 원래 이미지 해상도로 보정해서 주는지 확인 필요.
    // 현재 TrackNetService.get_prediction()은 원본 해상도로 보정해서 반환함.

    const x = pred.x * (canvas.width / calibrationData.image_shape[1]);
    const y = pred.y * (canvas.height / calibrationData.image_shape[0]);

    ctx.save();
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
    ctx.restore();
}

// 실시간 프레임 분석 요청
async function requestFrameAnalysis() {
    const now = Date.now();
    if (now - lastAnalysisTime < ANALYSIS_INTERVAL) return;
    lastAnalysisTime = now;

    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');

    // 현재 캔버스 화면을 이미지로 변환
    canvas.toBlob(async (blob) => {
        if (!blob) return;

        const formData = new FormData();
        formData.append('session_id', sessionId);
        formData.append('file', blob, 'frame.jpg');

        try {
            const response = await fetch(`${API_BASE_URL}/api/analysis/frame-predict`, {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success && result.tracknet) {
                    currentShuttlecock = result.tracknet;
                }
            }
        } catch (error) {
            console.error('Frame analysis error:', error);
        }
    }, 'image/jpeg', 0.6); // 품질을 약간 낮춰서 전송 속도 향상
}

// 정보 표시
function displayInfo() {
    const duration = formatTime(videoPlayer.duration);
    const resolution = `${videoPlayer.videoWidth}x${videoPlayer.videoHeight}`;
    document.getElementById('videoInfo').innerHTML = `
        <p><strong>해상도:</strong> ${resolution}</p>
        <p><strong>길이:</strong> ${duration}</p>
    `;

    const ppm = calibrationData.pixels_per_meter.toFixed(1);
    document.getElementById('calibrationInfo').innerHTML = `
        <p><strong>Pixels/Meter:</strong> ${ppm}</p>
    `;
}

// 재생 관련 유틸리티
function togglePlayPause() {
    if (videoPlayer.paused) { videoPlayer.play(); updatePlayPauseIcon(true); }
    else { videoPlayer.pause(); updatePlayPauseIcon(false); }
}

function updatePlayPauseIcon(isPlaying) {
    document.getElementById('playIcon').style.display = isPlaying ? 'none' : 'inline';
    document.getElementById('pauseIcon').style.display = isPlaying ? 'inline' : 'none';
}

function updateTimeDisplay() {
    const current = formatTime(videoPlayer.currentTime);
    const total = formatTime(videoPlayer.duration);
    document.getElementById('timeDisplay').textContent = `${current} / ${total}`;
}

function formatTime(seconds) {
    if (isNaN(seconds)) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function changePlaybackRate() {
    videoPlayer.playbackRate = parseFloat(document.getElementById('playbackRate').value);
}

function changeDisplayMode() {
    displayMode = document.getElementById('displayMode').value;
}

function toggleOverlay() {
    showOverlay = document.getElementById('showOverlay').checked;
}

function toggleFullscreen() {
    const container = document.querySelector('.video-container');
    if (!document.fullscreenElement) container.requestFullscreen();
    else document.exitFullscreen();
}

function goBack() { window.history.back(); }
function showLoading() { document.getElementById('loadingOverlay').classList.add('active'); }
function hideLoading() { document.getElementById('loadingOverlay').classList.remove('active'); }

window.addEventListener('beforeunload', function () {
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    if (videoPlayer) { videoPlayer.pause(); videoPlayer.src = ''; }
});