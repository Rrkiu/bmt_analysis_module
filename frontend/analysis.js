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
let lastProcessedImage = null; // 분석된 프레임 이미지 객체
let lastLanding = null;        // {is_landed, pos, is_in_court}

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
        lastLanding = null;
        lastProcessedImage = null;
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
    // 1. 영상 재생은 항상 원본 비디오를 기준으로 (60fps의 부드러움 유지)
    ctx.drawImage(videoPlayer, 0, 0, canvas.width, canvas.height);

    // 2. 코트 영역 및 코너 오버레이 (정상/디버그 모드 자동 처리)
    if (showOverlay && calibrationData) {
        drawOverlay();
    }

    // 3. 셔틀콕 궤적 오버레이
    if (currentShuttlecock && currentShuttlecock.visibility === 1) {
        drawShuttlecock(currentShuttlecock);
    }

    // 4. 낙구 판정 오버레이 (백엔드가 그려준 스타일을 프론트에서 재현)
    if (lastLanding) {
        drawLandingOverlay(lastLanding);
    }

    // 5. 실시간 분석 요청
    if (!videoPlayer.paused && !videoPlayer.ended) {
        requestFrameAnalysis();
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

// 낙하 지점 및 판정 결과 오버레이 (마일스톤 4)
// 낙하 지점 및 판정 결과 오버레이 (백엔드 카드 스타일 재현)
function drawLandingOverlay(landing) {
    if (!landing) return;

    // 20초 유지 로직 (프론트엔드 기준)
    const currentTime = videoPlayer.currentTime;
    const displayTime = landing.time_since !== undefined ? landing.time_since : (currentTime - landing.video_time);

    // 낙하 중이 아니고 판정 후 20초가 지났으면 표시 안 함
    if (displayTime > 20.0 && !landing.is_landed) return;

    const color = landing.is_in_court ? '#00ff00' : '#ff0000';
    const scaleX = canvas.width / (calibrationData.image_shape ? calibrationData.image_shape[1] : 1280);
    const scaleY = canvas.height / (calibrationData.image_shape ? calibrationData.image_shape[0] : 720);

    const lx = landing.image_x * scaleX;
    const ly = landing.image_y * scaleY;

    ctx.save();

    // 1. 메인 낙구 표시 (X 마크 + 원형 내부 점)
    ctx.beginPath();
    ctx.arc(lx, ly, 15, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = 'white';
    ctx.lineWidth = 3;
    ctx.stroke();

    ctx.beginPath();
    const s = 30;
    ctx.moveTo(lx - s, ly - s); ctx.lineTo(lx + s, ly + s);
    ctx.moveTo(lx + s, ly - s); ctx.lineTo(lx - s, ly + s);
    ctx.strokeStyle = 'white';
    ctx.lineWidth = 5;
    ctx.stroke();

    // 2. 우측 상단 요약 카드 (사용자 요청 이미지 스타일)
    const cardW = 260;
    const cardH = 340;
    const cardX = canvas.width - cardW - 30;
    const cardY = 30;

    // 카드 외곽 배경 (연한 회색)
    ctx.fillStyle = "rgba(210, 212, 210, 0.95)";
    ctx.strokeStyle = "rgba(180, 180, 180, 1)";
    ctx.lineWidth = 3;
    if (ctx.roundRect) {
        ctx.beginPath();
        ctx.roundRect(cardX, cardY, cardW, cardH, 12);
        ctx.fill();
        ctx.stroke();
    } else {
        ctx.fillRect(cardX, cardY, cardW, cardH);
        ctx.strokeRect(cardX, cardY, cardW, cardH);
    }

    // 카드 내부 미니맵 영역 (진한 회색 배경)
    const mPad = 15;
    const mSizeH = cardH - 120;
    const mx = cardX + mPad;
    const my = cardY + mPad;
    const mw = cardW - mPad * 2;
    const mh = mSizeH;

    ctx.fillStyle = "rgba(160, 162, 160, 1)";
    ctx.fillRect(mx, my, mw, mh);
    ctx.strokeStyle = "white";
    ctx.lineWidth = 2;
    ctx.strokeRect(mx, my, mw, mh);

    // 미니맵 내부 코트 라인 및 낙구 전용 매핑
    if (landing.pos) {
        const [wx, wy] = landing.pos; // Backend: wx(-2.59~2.59), wy(0~6.7)

        // 1. 좌표 매핑 (네트 상단, 베이스라인 하단)
        const px = mx + ((wx + 2.59) / 5.18) * mw;
        const py = my + (wy / 6.7) * mh;

        // 2. 코트 가이드라인 (중앙선 및 숏 서비스 라인)
        ctx.strokeStyle = "rgba(255,255,255,0.3)";
        ctx.lineWidth = 1;
        // 중앙선
        ctx.beginPath(); ctx.moveTo(mx + mw / 2, my); ctx.lineTo(mx + mw / 2, my + mh); ctx.stroke();
        // 숏 서비스 라인 (네트로부터 약 1.98m 지점)
        const srvY = my + (1.98 / 6.7) * mh;
        ctx.beginPath(); ctx.moveTo(mx, srvY); ctx.lineTo(mx + mw, srvY); ctx.stroke();

        // 3. 미니맵 낙구 점 (빛나는 효과 추가)
        if (px >= mx - 10 && px <= mx + mw + 10 && py >= my - 10 && py <= my + mh + 10) {
            ctx.shadowBlur = 10;
            ctx.shadowColor = color;
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(px, py, 10, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = "white";
            ctx.lineWidth = 3;
            ctx.stroke();
            ctx.shadowBlur = 0;
        }
    }

    // 카드 하단 정보 텍스트 (POS, RESULT)
    ctx.textAlign = "left";
    ctx.textBaseline = "top";

    // POS 텍스트 (흰색/회색)
    ctx.fillStyle = "#666";
    ctx.font = "bold 18px Courier New, monospace";
    const posText = landing.pos ? `POS: ${landing.pos[0].toFixed(2)}, ${landing.pos[1].toFixed(2)}` : "POS: N/A";
    ctx.fillText(posText, cardX + mPad, cardY + cardH - 75);

    // RESULT 텍스트 (판정에 따른 색상)
    ctx.fillStyle = color;
    ctx.font = "bold 32px Arial Black, sans-serif";
    ctx.fillText(`RESULT: ${landing.is_in_court ? 'IN' : 'OUT'}`, cardX + mPad, cardY + cardH - 45);

    // 3. 하단 중앙 배너 (JUDGMENT: OUT/IN)
    const bannerText = `JUDGMENT: ${landing.is_in_court ? 'IN' : 'OUT'}`;
    ctx.font = "bold 60px Arial Black, sans-serif";
    const textMeasure = ctx.measureText(bannerText);
    const bW = textMeasure.width + 60;
    const bH = 80;
    const bX = (canvas.width - bW) / 2;
    const bY = canvas.height - 120;

    // 검정색 배경 박스
    ctx.fillStyle = "rgba(0, 0, 0, 0.85)";
    ctx.fillRect(bX, bY, bW, bH);

    // 텍스트 출력
    ctx.fillStyle = color;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(bannerText, canvas.width / 2, bY + bH / 2 + 5);

    ctx.restore();
}

function drawMinimapOverlay(landing) {
    // 덮어씌우기 위해 빈 함수로 둠 (drawLandingOverlay 내부로 통합됨)
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

        const currentVideoTime = videoPlayer.currentTime;
        // console.log(`[Flow] Sending analysis request for time: ${currentVideoTime.toFixed(3)}s`);

        const formData = new FormData();
        formData.append('session_id', sessionId);
        formData.append('file', blob, 'frame.jpg');
        formData.append('video_time', String(currentVideoTime));

        try {
            const response = await fetch(`${API_BASE_URL}/api/analysis/frame-predict`, {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    currentShuttlecock = result.tracknet;
                    lastLanding = result.landing;

                    if (result.tracknet && result.tracknet.landing_debug) {
                        // const dbg = result.tracknet.landing_debug;
                        // console.log(`[Landing Debug] Vis: ${dbg.visibility}, Stay: ${dbg.stay_counter}, Dist: ${dbg.dist.toFixed(2)}, Reason: ${dbg.reason}`);
                    }

                    if (result.processed_image) {
                        const img = new Image();
                        img.onload = () => {
                            lastProcessedImage = img;
                            // console.log(`[Flow] New processed image received and loaded (Time: ${currentVideoTime.toFixed(2)}s)`);
                        };
                        img.src = result.processed_image;
                    }
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