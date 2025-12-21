// API 설정
const API_BASE_URL = 'http://localhost:8000';

// 전역 변수
let sessionId = null;
let uploadedImage = null;
let canvas = null;
let ctx = null;
let isDragging = false;
let draggedCornerIndex = -1;

// 코트 4개 코너 (시계방향: TL, TR, BR, BL)
let courtCorners = [
    { x: 0, y: 0, label: 'TL', color: '#00ff00' },  // Top-Left (Green)
    { x: 0, y: 0, label: 'TR', color: '#0000ff' },  // Top-Right (Blue)
    { x: 0, y: 0, label: 'BR', color: '#ff0000' },  // Bottom-Right (Red)
    { x: 0, y: 0, label: 'BL', color: '#ffff00' }   // Bottom-Left (Yellow)
];

// DOM 요소
const steps = {
    step1: document.getElementById('step1'),
    step2: document.getElementById('step2'),
    step3: document.getElementById('step3')
};

// 초기화
document.addEventListener('DOMContentLoaded', function () {
    console.log('Initializing...');
    init();
});

function init() {
    canvas = document.getElementById('alignmentCanvas');
    ctx = canvas.getContext('2d');
    setupEventListeners();
}

function setupEventListeners() {
    // 업로드
    document.getElementById('uploadArea').addEventListener('click', () => {
        document.getElementById('fileInput').click();
    });

    document.getElementById('fileInput').addEventListener('change', handleFileSelect);

    // 버튼
    document.getElementById('uploadBtn').addEventListener('click', () => goToStep(2));
    document.getElementById('backBtn').addEventListener('click', () => goToStep(1));
    document.getElementById('alignBtn').addEventListener('click', performAlignment);
    document.getElementById('newCalibration').addEventListener('click', resetApp);
    document.getElementById('downloadBtn').addEventListener('click', downloadResult);

    // 캔버스 이벤트
    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('mouseleave', handleMouseUp);
}

function goToStep(stepNumber) {
    console.log('Going to step:', stepNumber);

    Object.values(steps).forEach(step => step.classList.remove('active'));
    steps[`step${stepNumber}`].classList.add('active');

    if (stepNumber === 2 && uploadedImage) {
        setTimeout(setupCanvas, 200);
    }
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;
    uploadImage(file);
}

async function uploadImage(file) {
    showLoading();

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE_URL}/api/upload`, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        console.log('Upload result:', result);

        if (result.success) {
            sessionId = result.session_id;
            loadImagePreview(file);
        }
    } catch (error) {
        alert('업로드 실패: ' + error.message);
    } finally {
        hideLoading();
    }
}

function loadImagePreview(file) {
    const reader = new FileReader();
    reader.onload = function (e) {
        uploadedImage = new Image();
        uploadedImage.onload = function () {
            console.log('Image loaded:', uploadedImage.width, 'x', uploadedImage.height);

            document.getElementById('uploadArea').innerHTML = `
                <img src="${e.target.result}" style="max-width: 100%; max-height: 300px; border-radius: 10px;">
                <p style="margin-top: 15px; color: #48bb78; font-weight: bold;">✓ 업로드 완료</p>
            `;
            document.getElementById('uploadBtn').style.display = 'block';
        };
        uploadedImage.src = e.target.result;
    };
    reader.readAsDataURL(file);
}

function setupCanvas() {
    console.log('Setting up canvas...');

    if (!uploadedImage || !uploadedImage.complete) {
        console.error('Image not ready');
        return;
    }

    // 캔버스 크기 설정
    canvas.width = uploadedImage.width;
    canvas.height = uploadedImage.height;
    canvas.style.width = '100%';
    canvas.style.height = 'auto';

    // 초기 코너 위치 자동 추정
    estimateInitialCorners();

    // 그리기
    drawCanvas();
}

function estimateInitialCorners() {
    const w = canvas.width;
    const h = canvas.height;

    // 초기 추정: 이미지의 중앙 영역을 코트로 가정
    // 약간의 마진을 두고 사각형 생성
    const marginX = w * 0.15;  // 좌우 15% 마진
    const marginTop = h * 0.20;  // 상단 20% 마진 (네트 쪽)
    const marginBottom = h * 0.05;  // 하단 5% 마진

    courtCorners[0] = { x: marginX, y: marginTop, label: 'TL', color: '#00ff00' };
    courtCorners[1] = { x: w - marginX, y: marginTop, label: 'TR', color: '#0000ff' };
    courtCorners[2] = { x: w - marginX, y: h - marginBottom, label: 'BR', color: '#ff0000' };
    courtCorners[3] = { x: marginX, y: h - marginBottom, label: 'BL', color: '#ffff00' };

    console.log('Initial corners estimated:', courtCorners);
}

function drawCanvas() {
    if (!ctx || !uploadedImage) return;

    // 배경 이미지
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(uploadedImage, 0, 0, canvas.width, canvas.height);

    // 코트 영역 그리기
    drawCourtRegion();

    // 코너 포인트 그리기
    drawCornerPoints();
}

function drawCourtRegion() {
    // 반투명 채우기
    ctx.fillStyle = 'rgba(0, 255, 0, 0.15)';
    ctx.beginPath();
    ctx.moveTo(courtCorners[0].x, courtCorners[0].y);
    courtCorners.forEach(corner => ctx.lineTo(corner.x, corner.y));
    ctx.closePath();
    ctx.fill();

    // 경계선
    ctx.strokeStyle = '#00ffff';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(courtCorners[0].x, courtCorners[0].y);
    courtCorners.forEach(corner => ctx.lineTo(corner.x, corner.y));
    ctx.closePath();
    ctx.stroke();
}

function drawCornerPoints() {
    courtCorners.forEach((corner, index) => {
        // 드래그 중인 코너 강조
        const radius = (index === draggedCornerIndex) ? 18 : 15;
        const lineWidth = (index === draggedCornerIndex) ? 3 : 2;

        // 외곽 원 (흰색)
        ctx.strokeStyle = 'white';
        ctx.lineWidth = lineWidth + 1;
        ctx.beginPath();
        ctx.arc(corner.x, corner.y, radius + 2, 0, Math.PI * 2);
        ctx.stroke();

        // 내부 원 (색상)
        ctx.fillStyle = corner.color;
        ctx.beginPath();
        ctx.arc(corner.x, corner.y, radius, 0, Math.PI * 2);
        ctx.fill();

        // 레이블
        ctx.fillStyle = 'white';
        ctx.strokeStyle = 'black';
        ctx.lineWidth = 3;
        ctx.font = 'bold 14px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.strokeText(corner.label, corner.x, corner.y);
        ctx.fillText(corner.label, corner.x, corner.y);
    });

    // 안내 텍스트
    ctx.fillStyle = 'white';
    ctx.strokeStyle = 'black';
    ctx.lineWidth = 4;
    ctx.font = 'bold 18px sans-serif';
    ctx.textAlign = 'left';

    const text = '각 코너를 드래그하여 코트 영역을 조정하세요';
    ctx.strokeText(text, 20, 30);
    ctx.fillText(text, 20, 30);
}

function handleMouseDown(e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    // 가장 가까운 코너 찾기
    courtCorners.forEach((corner, index) => {
        const dist = Math.sqrt((x - corner.x) ** 2 + (y - corner.y) ** 2);
        if (dist < 30) {
            isDragging = true;
            draggedCornerIndex = index;
            canvas.style.cursor = 'grabbing';
        }
    });
}

function handleMouseMove(e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    if (isDragging && draggedCornerIndex >= 0) {
        // 코너 이동 (경계 체크)
        courtCorners[draggedCornerIndex].x = Math.max(0, Math.min(x, canvas.width));
        courtCorners[draggedCornerIndex].y = Math.max(0, Math.min(y, canvas.height));
        drawCanvas();
    } else {
        // 마우스 커서 변경
        let nearCorner = false;
        courtCorners.forEach(corner => {
            const dist = Math.sqrt((x - corner.x) ** 2 + (y - corner.y) ** 2);
            if (dist < 30) nearCorner = true;
        });
        canvas.style.cursor = nearCorner ? 'grab' : 'default';
    }
}

function handleMouseUp() {
    isDragging = false;
    draggedCornerIndex = -1;
    canvas.style.cursor = 'default';
}

async function performAlignment() {
    if (!sessionId) {
        alert('세션 없음');
        return;
    }

    showLoading();

    try {
        // 4개 코너 데이터 준비
        const corners = courtCorners.map(c => [c.x, c.y]);

        // 폴리곤 데이터 로컬 저장
        savePolygonLocally(corners);

        const data = {
            session_id: sessionId,
            corners: corners,
            image_width: canvas.width,
            image_height: canvas.height
        };

        console.log('Aligning with corners:', data);

        const response = await fetch(`${API_BASE_URL}/api/align-corners`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();
        console.log('Result:', result);

        if (result.success) {
            displayResult(result);
            goToStep(3);
        }
    } catch (error) {
        alert('실패: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 폴리곤 로컬 저장 (LocalStorage)
function savePolygonLocally(corners) {
    const polygonData = {
        session_id: sessionId,
        corners: corners,
        image_width: canvas.width,
        image_height: canvas.height,
        timestamp: new Date().toISOString()
    };

    // LocalStorage에 저장
    localStorage.setItem(`court_polygon_${sessionId}`, JSON.stringify(polygonData));

    // 전체 히스토리에도 추가
    let history = JSON.parse(localStorage.getItem('court_polygon_history') || '[]');
    history.push(polygonData);
    // 최근 10개만 유지
    if (history.length > 10) {
        history = history.slice(-10);
    }
    localStorage.setItem('court_polygon_history', JSON.stringify(history));

    console.log('Polygon saved locally:', polygonData);
}

// 폴리곤 JSON 파일로 다운로드
function downloadPolygonJSON() {
    const corners = courtCorners.map(c => [c.x, c.y]);

    const polygonData = {
        session_id: sessionId,
        corners: corners,
        image_width: canvas.width,
        image_height: canvas.height,
        timestamp: new Date().toISOString(),
        format: 'court_polygon_v1'
    };

    const dataStr = JSON.stringify(polygonData, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `court_polygon_${sessionId}.json`;
    link.click();

    URL.revokeObjectURL(url);
    console.log('Polygon JSON downloaded');
}

// COCO Format으로 저장 (객체 검출 데이터셋 형식)
function downloadPolygonCOCO() {
    const corners = courtCorners.map(c => [c.x, c.y]);

    // COCO segmentation format
    const cocoData = {
        "info": {
            "description": "Badminton Court Polygon",
            "version": "1.0",
            "year": new Date().getFullYear(),
            "date_created": new Date().toISOString()
        },
        "images": [{
            "id": 1,
            "width": canvas.width,
            "height": canvas.height,
            "file_name": `image_${sessionId}.jpg`
        }],
        "annotations": [{
            "id": 1,
            "image_id": 1,
            "category_id": 1,
            "segmentation": [
                corners.flat()  // [x1, y1, x2, y2, x3, y3, x4, y4]
            ],
            "area": calculatePolygonArea(corners),
            "bbox": calculateBoundingBox(corners),
            "iscrowd": 0
        }],
        "categories": [{
            "id": 1,
            "name": "badminton_court",
            "supercategory": "sports_area"
        }]
    };

    const dataStr = JSON.stringify(cocoData, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `court_polygon_coco_${sessionId}.json`;
    link.click();

    URL.revokeObjectURL(url);
    console.log('COCO format downloaded');
}

// SVG 형식으로 저장
function downloadPolygonSVG() {
    const corners = courtCorners.map(c => [c.x, c.y]);

    const points = corners.map(([x, y]) => `${x},${y}`).join(' ');

    const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg width="${canvas.width}" height="${canvas.height}" xmlns="http://www.w3.org/2000/svg">
  <polygon points="${points}" 
           fill="rgba(0,255,0,0.3)" 
           stroke="cyan" 
           stroke-width="3"/>
  ${corners.map(([x, y], i) => `
  <circle cx="${x}" cy="${y}" r="10" fill="${courtCorners[i].color}"/>
  <text x="${x + 15}" y="${y - 10}" font-size="12" fill="white">${courtCorners[i].label}</text>
  `).join('')}
</svg>`;

    const blob = new Blob([svg], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `court_polygon_${sessionId}.svg`;
    link.click();

    URL.revokeObjectURL(url);
    console.log('SVG downloaded');
}

// 폴리곤 면적 계산 (Shoelace formula)
function calculatePolygonArea(corners) {
    let area = 0;
    const n = corners.length;

    for (let i = 0; i < n; i++) {
        const j = (i + 1) % n;
        area += corners[i][0] * corners[j][1];
        area -= corners[j][0] * corners[i][1];
    }

    return Math.abs(area / 2);
}

// Bounding Box 계산 (COCO format)
function calculateBoundingBox(corners) {
    const xs = corners.map(c => c[0]);
    const ys = corners.map(c => c[1]);

    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xs);
    const maxY = Math.max(...ys);

    // [x, y, width, height] format
    return [minX, minY, maxX - minX, maxY - minY];
}

// 저장된 폴리곤 불러오기
function loadPolygonFromLocal(sessionId) {
    const data = localStorage.getItem(`court_polygon_${sessionId}`);
    if (data) {
        const polygonData = JSON.parse(data);
        console.log('Loaded polygon:', polygonData);
        return polygonData;
    }
    return null;
}

// 히스토리 조회
function getPolygonHistory() {
    const history = localStorage.getItem('court_polygon_history');
    if (history) {
        return JSON.parse(history);
    }
    return [];
}

function displayResult(result) {
    const data = result.data;

    document.getElementById('resultInfo').innerHTML = `
        <h3>✓ 캘리브레이션 완료!</h3>
        <p><strong>스케일:</strong> ${data.pixels_per_meter.toFixed(1)} px/m</p>
        <p><strong>코트 면적:</strong> ${data.court_area.toFixed(0)} px²</p>
        <p><strong>검증:</strong> ${data.validation.message}</p>
    `;

    document.getElementById('resultImage').src =
        `${API_BASE_URL}/api/image/${sessionId}/result?t=${Date.now()}`;
}

function downloadResult() {
    if (!sessionId) return;
    const link = document.createElement('a');
    link.href = `${API_BASE_URL}/api/image/${sessionId}/result`;
    link.download = 'court_result.jpg';
    link.click();
}

function resetApp() {
    sessionId = null;
    uploadedImage = null;

    document.getElementById('uploadArea').innerHTML = `
        <div class="upload-placeholder">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            <p>클릭하여 이미지 업로드</p>
            <span>또는 드래그 앤 드롭</span>
        </div>
    `;
    document.getElementById('uploadBtn').style.display = 'none';
    goToStep(1);
}

function showLoading() {
    document.getElementById('loadingOverlay').classList.add('active');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.remove('active');
}

// 저장 메뉴 토글
function showSaveMenu() {
    const menu = document.getElementById('saveMenu');
    menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
}

// 클립보드에 복사
async function copyPolygonToClipboard() {
    const corners = courtCorners.map(c => [c.x, c.y]);

    const polygonData = {
        session_id: sessionId,
        corners: corners,
        image_width: canvas.width,
        image_height: canvas.height,
        timestamp: new Date().toISOString()
    };

    try {
        await navigator.clipboard.writeText(JSON.stringify(polygonData, null, 2));
        alert('✓ 폴리곤 데이터가 클립보드에 복사되었습니다!');
        console.log('Copied to clipboard:', polygonData);
    } catch (err) {
        console.error('Failed to copy:', err);
        alert('클립보드 복사 실패');
    }
}

// ============================================================================
// 프로파일 저장 기능
// ============================================================================

// 프로파일 저장 모달 열기
function openSaveProfileModal() {
    document.getElementById('saveProfileModal').classList.add('active');
}

// 프로파일 저장 모달 닫기
function closeSaveProfileModal() {
    document.getElementById('saveProfileModal').classList.remove('active');
}

// 프로파일 저장 확인
async function saveProfileConfirm() {
    const profileName = document.getElementById('profileName').value.trim();

    if (!profileName) {
        alert('프로파일 이름을 입력하세요.');
        return;
    }

    if (!sessionId) {
        alert('세션 정보가 없습니다. 캘리브레이션을 먼저 완료하세요.');
        return;
    }

    showLoading();

    try {
        const profileId = document.getElementById('profileId').value.trim();
        const courtName = document.getElementById('courtName').value.trim();
        const venue = document.getElementById('venue').value.trim();
        const notes = document.getElementById('notes').value.trim();

        const metadata = {
            court_name: courtName || '코트 정보 없음',
            venue: venue || '',
            notes: notes || ''
        };

        const response = await fetch(`${API_BASE_URL}/api/calibration/profile`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile_id: profileId || undefined,
                profile_name: profileName,
                session_id: sessionId,
                metadata: metadata
            })
        });

        const result = await response.json();

        if (result.success) {
            alert('✅ 프로파일이 저장되었습니다!\n\n프로파일 ID: ' + result.profile.profile_id);
            closeSaveProfileModal();

            // 입력 필드 초기화
            document.getElementById('profileName').value = '';
            document.getElementById('profileId').value = '';
            document.getElementById('courtName').value = '';
            document.getElementById('venue').value = '';
            document.getElementById('notes').value = '';

            // 프로파일 관리 페이지로 이동 여부 확인
            const goToProfiles = confirm('프로파일 관리 페이지로 이동하시겠습니까?');
            if (goToProfiles) {
                window.location.href = 'profile-manager.html';
            }
        } else {
            alert('프로파일 저장에 실패했습니다.\n' + (result.detail || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('프로파일 저장 실패:', error);
        alert('프로파일 저장 중 오류가 발생했습니다.');
    } finally {
        hideLoading();
    }
}

// 결과 다운로드
function downloadResult() {
    const resultImage = document.getElementById('resultImage');
    if (!resultImage.src) {
        alert('다운로드할 결과가 없습니다.');
        return;
    }

    const link = document.createElement('a');
    link.href = resultImage.src;
    link.download = `calibration_result_${sessionId}.jpg`;
    link.click();
}

// ============================================================================
// 비디오 분석 기능
// ============================================================================

// 비디오 분석 모달 열기
async function openAnalysisModal() {
    document.getElementById('analysisModal').classList.add('active');

    // 저장된 비디오 목록 로드
    await loadStoredVideos();
}

// 비디오 분석 모달 닫기
function closeAnalysisModal() {
    document.getElementById('analysisModal').classList.remove('active');
}

// 저장된 비디오 목록 로드
async function loadStoredVideos() {
    try {
        console.log('📹 저장된 비디오 목록 로드 중...');

        const response = await fetch(`${API_BASE_URL}/api/videos/list`);
        const result = await response.json();

        console.log('📦 비디오 목록:', result);

        const videoSelect = document.getElementById('videoSelect');
        videoSelect.innerHTML = '';

        if (result.success && result.videos.length > 0) {
            // 비디오 옵션 추가
            result.videos.forEach(video => {
                const option = document.createElement('option');
                option.value = video.path;
                option.textContent = `${video.filename} (${video.size_mb} MB)`;
                option.dataset.info = JSON.stringify(video);
                videoSelect.appendChild(option);
            });

            // 첫 번째 비디오 정보 표시
            updateVideoInfo();

            console.log(`✅ ${result.videos.length}개 비디오 로드 완료`);
        } else {
            // 비디오 없음
            const option = document.createElement('option');
            option.value = '';
            option.textContent = '저장된 비디오가 없습니다';
            option.disabled = true;
            videoSelect.appendChild(option);

            document.getElementById('videoInfo').textContent =
                `💡 비디오를 storage/videos/ 폴더에 추가하세요. 경로: ${result.videos_dir}`;
            document.getElementById('videoInfo').style.color = '#f59e0b';
        }
    } catch (error) {
        console.error('❌ 비디오 목록 로드 실패:', error);

        const videoSelect = document.getElementById('videoSelect');
        videoSelect.innerHTML = '<option value="">비디오 로드 실패</option>';

        document.getElementById('videoInfo').textContent =
            '⚠️ 비디오 목록을 불러올 수 없습니다. 백엔드 서버를 확인하세요.';
        document.getElementById('videoInfo').style.color = '#ef4444';
    }
}

// 비디오 정보 업데이트
function updateVideoInfo() {
    const videoSelect = document.getElementById('videoSelect');
    const selectedOption = videoSelect.options[videoSelect.selectedIndex];

    if (selectedOption && selectedOption.dataset.info) {
        const video = JSON.parse(selectedOption.dataset.info);
        document.getElementById('videoInfo').innerHTML =
            `📁 ${video.size_mb} MB | 📅 ${new Date(video.modified).toLocaleString('ko-KR')}`;
        document.getElementById('videoInfo').style.color = '#666';
    }
}

// 비디오 소스 변경 핸들러
function handleVideoSourceChange() {
    const source = document.getElementById('videoSource').value;

    // 모든 그룹 숨기기
    document.getElementById('videoStorageGroup').style.display = 'none';
    document.getElementById('videoCustomGroup').style.display = 'none';
    document.getElementById('videoWebcamGroup').style.display = 'none';

    // 선택된 소스만 표시
    if (source === 'storage') {
        document.getElementById('videoStorageGroup').style.display = 'block';
        updateVideoInfo();
    } else if (source === 'custom') {
        document.getElementById('videoCustomGroup').style.display = 'block';
    } else if (source === 'webcam') {
        document.getElementById('videoWebcamGroup').style.display = 'block';
    }
}

// 비디오 선택 변경 시 정보 업데이트
document.addEventListener('DOMContentLoaded', function () {
    const videoSelect = document.getElementById('videoSelect');
    if (videoSelect) {
        videoSelect.addEventListener('change', updateVideoInfo);
    }
});

// 비디오 소스에 따라 파일 입력 토글 (이전 버전 호환)
function toggleVideoFileInput() {
    handleVideoSourceChange();
}

// 비디오 분석 시작
async function startVideoAnalysis() {
    const source = document.getElementById('videoSource').value;
    const mode = document.getElementById('analysisMode').value;

    let videoPath = null;

    // 소스별 경로 결정
    if (source === 'storage') {
        const videoSelect = document.getElementById('videoSelect');
        videoPath = videoSelect.value;

        if (!videoPath) {
            alert('비디오를 선택하세요.');
            return;
        }
    } else if (source === 'custom') {
        videoPath = document.getElementById('videoPath').value.trim();

        if (!videoPath) {
            alert('비디오 파일 경로를 입력하세요.');
            return;
        }
    } else if (source === 'webcam') {
        alert('웹캠 기능은 현재 제한적입니다.\nPython 스크립트를 사용하세요:\n\npython3 backend/test_video_analysis.py --webcam');
        return;
    }

    if (!sessionId) {
        alert('세션 정보가 없습니다. 캘리브레이션을 먼저 완료하세요.');
        return;
    }

    // 분석 페이지로 이동 (실시간 재생)
    const analysisUrl = `analysis.html?session_id=${sessionId}&video_path=${encodeURIComponent(videoPath)}&mode=${mode}`;
    console.log('🎥 분석 페이지로 이동:', analysisUrl);
    window.location.href = analysisUrl;
}