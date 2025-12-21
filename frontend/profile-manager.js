// 프로파일 관리 스크립트

const API_BASE_URL = 'http://localhost:8000';

let currentProfileId = null;
let currentSessionId = null;  // 캘리브레이션에서 전달받음

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function () {
    loadProfiles();

    // URL 파라미터에서 session_id 확인 (캘리브레이션 완료 후)
    const urlParams = new URLSearchParams(window.location.search);
    currentSessionId = urlParams.get('session_id');

    if (currentSessionId) {
        // 캘리브레이션 직후면 저장 모달 자동 표시
        showSaveProfileModal();
    }
});

// 프로파일 목록 로드
async function loadProfiles() {
    console.log('🔄 프로파일 목록 로드 시작...');
    showLoading();

    try {
        console.log('📡 API 호출:', `${API_BASE_URL}/api/calibration/profiles`);
        const response = await fetch(`${API_BASE_URL}/api/calibration/profiles`);
        console.log('📨 응답 상태:', response.status, response.statusText);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();
        console.log('📦 응답 데이터:', result);

        if (result.success && result.profiles && result.profiles.length > 0) {
            console.log(`✅ 프로파일 ${result.profiles.length}개 발견`);
            displayProfiles(result.profiles);
            document.getElementById('emptyState').style.display = 'none';
        } else {
            console.log('ℹ️  저장된 프로파일 없음');
            document.getElementById('emptyState').style.display = 'block';
            document.getElementById('profilesContainer').innerHTML = '';
        }
    } catch (error) {
        console.error('❌ 프로파일 로드 실패:', error);

        // 더 상세한 에러 메시지
        let errorMessage = '프로파일 목록을 불러올 수 없습니다.\n\n';

        if (error.message.includes('Failed to fetch')) {
            errorMessage += '백엔드 서버가 실행 중인지 확인하세요.\n';
            errorMessage += '예상 주소: http://localhost:8000\n\n';
            errorMessage += '서버 실행 방법:\n';
            errorMessage += 'cd backend\n';
            errorMessage += 'python main.py';
        } else {
            errorMessage += '오류: ' + error.message;
        }

        alert(errorMessage);

        // 빈 상태 표시
        document.getElementById('emptyState').style.display = 'block';
        document.getElementById('profilesContainer').innerHTML = '';
    } finally {
        hideLoading();
    }
}

// 프로파일 카드 표시
function displayProfiles(profiles) {
    const container = document.getElementById('profilesContainer');
    container.innerHTML = '';

    // 새 프로파일 생성 카드
    const createCard = document.createElement('div');
    createCard.className = 'profile-card create-new-card';
    createCard.innerHTML = `
        <div class="create-icon">+</div>
        <div style="font-size: 18px; font-weight: bold; color: #6366f1;">
            새 캘리브레이션 생성
        </div>
    `;
    createCard.onclick = () => goToCalibration();
    container.appendChild(createCard);

    // 프로파일 카드들
    profiles.forEach(profile => {
        const card = createProfileCard(profile);
        container.appendChild(card);
    });
}

// 프로파일 카드 생성
function createProfileCard(profile) {
    const card = document.createElement('div');
    card.className = 'profile-card';

    const createdDate = new Date(profile.created_at).toLocaleDateString('ko-KR');
    const courtName = profile.metadata?.court_name || '코트 정보 없음';
    const venue = profile.metadata?.venue || '';

    card.innerHTML = `
        <img src="${profile.thumbnail_base64 || 'placeholder.jpg'}" 
             class="profile-thumbnail" 
             alt="${profile.profile_name}">
        
        <div class="profile-info">
            <div class="profile-name">${profile.profile_name}</div>
            <div class="profile-meta">📍 ${courtName}</div>
            ${venue ? `<div class="profile-meta">🏢 ${venue}</div>` : ''}
            <div class="profile-meta">📅 ${createdDate}</div>
        </div>
        
        <div class="profile-actions">
            <button class="btn-use" onclick="useProfile('${profile.profile_id}', event)">
                사용
            </button>
            <button class="btn-edit" onclick="editProfile('${profile.profile_id}', event)">
                편집
            </button>
            <button class="btn-delete" onclick="deleteProfile('${profile.profile_id}', event)">
                삭제
            </button>
        </div>
    `;

    return card;
}

// 프로파일 사용
async function useProfile(profileId, event) {
    event.stopPropagation();

    try {
        const response = await fetch(`${API_BASE_URL}/api/calibration/profile/${profileId}`);
        const result = await response.json();

        if (result.success) {
            // LocalStorage에 저장
            localStorage.setItem('selected_profile_id', profileId);
            localStorage.setItem('selected_profile_data', JSON.stringify(result.profile));

            // 분석 모드로 이동
            alert(`프로파일 "${result.profile.profile_name}"이(가) 선택되었습니다.\n분석 모드로 이동합니다.`);

            // TODO: 실제 분석 페이지로 이동
            window.location.href = 'analysis.html';
        }
    } catch (error) {
        console.error('프로파일 로드 실패:', error);
        alert('프로파일을 불러올 수 없습니다.');
    }
}

// 프로파일 편집
async function editProfile(profileId, event) {
    event.stopPropagation();

    showLoading();

    try {
        const response = await fetch(`${API_BASE_URL}/api/calibration/profile/${profileId}`);
        const result = await response.json();

        if (result.success) {
            currentProfileId = profileId;
            const profile = result.profile;

            document.getElementById('editProfileName').value = profile.profile_name;
            document.getElementById('editCourtName').value = profile.metadata?.court_name || '';
            document.getElementById('editVenue').value = profile.metadata?.venue || '';
            document.getElementById('editNotes').value = profile.metadata?.notes || '';

            document.getElementById('editProfileModal').classList.add('active');
        }
    } catch (error) {
        console.error('프로파일 로드 실패:', error);
        alert('프로파일을 불러올 수 없습니다.');
    } finally {
        hideLoading();
    }
}

// 프로파일 업데이트 확인
async function updateProfileConfirm() {
    const profileName = document.getElementById('editProfileName').value.trim();

    if (!profileName) {
        alert('프로파일 이름을 입력하세요.');
        return;
    }

    showLoading();

    try {
        const metadata = {
            court_name: document.getElementById('editCourtName').value.trim(),
            venue: document.getElementById('editVenue').value.trim(),
            notes: document.getElementById('editNotes').value.trim()
        };

        const response = await fetch(`${API_BASE_URL}/api/calibration/profile/${currentProfileId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile_name: profileName,
                metadata: metadata
            })
        });

        const result = await response.json();

        if (result.success) {
            alert('프로파일이 업데이트되었습니다.');
            closeEditProfileModal();
            loadProfiles();
        }
    } catch (error) {
        console.error('업데이트 실패:', error);
        alert('프로파일 업데이트에 실패했습니다.');
    } finally {
        hideLoading();
    }
}

// 프로파일 삭제
async function deleteProfile(profileId, event) {
    event.stopPropagation();

    if (!confirm('이 프로파일을 삭제하시겠습니까?\n삭제된 데이터는 복구할 수 없습니다.')) {
        return;
    }

    showLoading();

    try {
        const response = await fetch(`${API_BASE_URL}/api/calibration/profile/${profileId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert('프로파일이 삭제되었습니다.');
            loadProfiles();
        }
    } catch (error) {
        console.error('삭제 실패:', error);
        alert('프로파일 삭제에 실패했습니다.');
    } finally {
        hideLoading();
    }
}

// 새 캘리브레이션으로 이동
function goToCalibration() {
    window.location.href = 'index.html';
}

// 저장 모달 표시
function showSaveProfileModal() {
    document.getElementById('saveProfileModal').classList.add('active');
}

// 저장 모달 닫기
function closeSaveProfileModal() {
    document.getElementById('saveProfileModal').classList.remove('active');
}

// 편집 모달 닫기
function closeEditProfileModal() {
    document.getElementById('editProfileModal').classList.remove('active');
}

// 프로파일 저장 확인
async function saveProfileConfirm() {
    const profileName = document.getElementById('profileName').value.trim();

    if (!profileName) {
        alert('프로파일 이름을 입력하세요.');
        return;
    }

    if (!currentSessionId) {
        alert('세션 정보가 없습니다. 캘리브레이션을 먼저 완료하세요.');
        return;
    }

    showLoading();

    try {
        const profileId = document.getElementById('profileId').value.trim();

        const metadata = {
            court_name: document.getElementById('courtName').value.trim(),
            venue: document.getElementById('venue').value.trim(),
            notes: document.getElementById('notes').value.trim()
        };

        const response = await fetch(`${API_BASE_URL}/api/calibration/profile`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile_id: profileId || undefined,
                profile_name: profileName,
                session_id: currentSessionId,
                metadata: metadata
            })
        });

        const result = await response.json();

        if (result.success) {
            alert('프로파일이 저장되었습니다!');
            closeSaveProfileModal();

            // URL 파라미터 제거하고 목록 새로고침
            window.history.replaceState({}, document.title, window.location.pathname);
            loadProfiles();
        }
    } catch (error) {
        console.error('저장 실패:', error);
        alert('프로파일 저장에 실패했습니다.');
    } finally {
        hideLoading();
    }
}

// 로딩 표시
function showLoading() {
    document.getElementById('loadingOverlay').classList.add('active');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.remove('active');
}