# 영속적 캘리브레이션 시스템 설계

## 데이터 구조

### 1. Calibration Profile (캘리브레이션 프로파일)

```json
{
  "profile_id": "court_a_camera_1",  // 사용자 정의 ID
  "profile_name": "A코트 카메라1",
  "created_at": "2024-12-16T10:30:00Z",
  "updated_at": "2024-12-16T10:30:00Z",
  
  "camera_info": {
    "device_id": "user_smartphone_123",
    "resolution": [1920, 1080],
    "fps": 30,
    "position": "baseline_right",  // 촬영 위치
    "height_cm": 160  // 카메라 높이
  },
  
  "calibration_data": {
    // 이미지 좌표 (픽셀)
    "corners_image": [
      [320, 216],   // TL
      [1600, 216],  // TR
      [1600, 864],  // BR
      [320, 864]    // BL
    ],
    
    // 실세계 좌표 (미터)
    "corners_world": [
      [-2.59, 1.98],   // TL
      [2.59, 1.98],    // TR
      [2.59, 6.7],     // BR
      [-2.59, 6.7]     // BL
    ],
    
    // Homography 행렬
    "homography_matrix": [
      [1.2, 0.1, -100],
      [0.05, 1.5, -50],
      [0.0001, 0.0002, 1]
    ],
    
    // 역변환 행렬
    "inverse_homography": [...],
    
    // 변환 정보
    "pixels_per_meter": 75.2,
    "court_area_pixels": 1234567
  },
  
  "validation": {
    "is_valid": true,
    "reprojection_error": 2.3,  // 픽셀
    "validation_time": "2024-12-16T10:30:05Z"
  },
  
  "reference_image": {
    "thumbnail_base64": "data:image/jpeg;base64,...",  // 썸네일
    "full_image_path": "/storage/calibrations/court_a_camera_1/reference.jpg"
  },
  
  "metadata": {
    "court_name": "A코트",
    "court_type": "singles",  // singles/doubles
    "venue": "XX체육관",
    "tags": ["실내", "LED조명", "우측베이스라인"]
  }
}
```

### 2. 저장 위치

```
backend/storage/
├── calibrations/
│   ├── court_a_camera_1/
│   │   ├── profile.json           # 프로파일 메타데이터
│   │   ├── reference.jpg          # 참조 이미지 (전체)
│   │   ├── thumbnail.jpg          # 썸네일 (200x150)
│   │   └── overlay.png            # 코트 영역 오버레이
│   │
│   ├── court_a_camera_2/
│   └── court_b_camera_1/
│
├── sessions/
│   └── [임시 세션 데이터]
│
└── videos/
    └── [분석할 비디오 파일]
```

## API 설계

### 캘리브레이션 관리 API

#### 1. 프로파일 저장
```http
POST /api/calibration/profile
Content-Type: application/json

{
  "profile_id": "court_a_camera_1",  // Optional, 없으면 자동 생성
  "profile_name": "A코트 카메라1",
  "camera_info": {...},
  "corners": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
  "image_width": 1920,
  "image_height": 1080,
  "reference_image_session_id": "abc-123",  // 현재 세션의 이미지 사용
  "metadata": {...}
}

Response:
{
  "success": true,
  "profile_id": "court_a_camera_1",
  "message": "캘리브레이션 프로파일 저장 완료"
}
```

#### 2. 프로파일 목록 조회
```http
GET /api/calibration/profiles

Response:
{
  "success": true,
  "profiles": [
    {
      "profile_id": "court_a_camera_1",
      "profile_name": "A코트 카메라1",
      "created_at": "...",
      "thumbnail": "data:image/jpeg;base64,...",
      "metadata": {...}
    },
    ...
  ]
}
```

#### 3. 특정 프로파일 로드
```http
GET /api/calibration/profile/{profile_id}

Response:
{
  "success": true,
  "profile": {
    // 전체 프로파일 데이터
  }
}
```

#### 4. 프로파일 업데이트
```http
PUT /api/calibration/profile/{profile_id}
Content-Type: application/json

{
  "profile_name": "새로운 이름",
  "metadata": {...}
}
```

#### 5. 프로파일 삭제
```http
DELETE /api/calibration/profile/{profile_id}
```

### 비디오 분석 API

#### 1. 분석 세션 시작
```http
POST /api/analysis/start
Content-Type: application/json

{
  "profile_id": "court_a_camera_1",  // 사용할 캘리브레이션
  "video_source": "upload",  // upload/stream/webcam
  "session_name": "2024-12-16 경기"
}

Response:
{
  "success": true,
  "analysis_session_id": "analysis_xyz_789",
  "calibration": {
    // 로드된 캘리브레이션 데이터
  }
}
```

#### 2. 프레임 분석 (실시간)
```http
POST /api/analysis/frame
Content-Type: application/json

{
  "analysis_session_id": "analysis_xyz_789",
  "frame_data": "base64_encoded_frame",
  "frame_number": 123,
  "timestamp": 4.1
}

Response:
{
  "success": true,
  "detections": [
    {
      "type": "shuttlecock_landing",
      "image_position": [640, 480],
      "world_position": [0.5, 3.2],
      "zone": "오른쪽 중코트",
      "in_my_court": true,
      "confidence": 0.92
    }
  ]
}
```

#### 3. 분석 결과 조회
```http
GET /api/analysis/session/{analysis_session_id}/results

Response:
{
  "success": true,
  "summary": {
    "total_rallies": 45,
    "my_court_landings": 23,
    "opponent_court_landings": 22,
    "zones_distribution": {...}
  },
  "landings": [...]
}
```

## 프론트엔드 UI 흐름

### 1. 캘리브레이션 모드
```
┌─────────────────────────────────────┐
│  캘리브레이션 프로파일 관리         │
├─────────────────────────────────────┤
│                                     │
│  ┌─────┐  ┌─────┐  ┌─────┐  [+새로] │
│  │코트A│  │코트B│  │코트C│         │
│  │카메1│  │카메1│  │카메2│         │
│  └─────┘  └─────┘  └─────┘         │
│                                     │
│  선택: 코트A 카메1                   │
│  ┌─────────────────────────────┐   │
│  │ [참조 이미지 보기]           │   │
│  │ [수정]  [삭제]  [복제]       │   │
│  └─────────────────────────────┘   │
│                                     │
│  또는                                │
│  [새 캘리브레이션 생성]              │
└─────────────────────────────────────┘
```

### 2. 분석 모드
```
┌─────────────────────────────────────┐
│  비디오 분석                         │
├─────────────────────────────────────┤
│                                     │
│  1. 캘리브레이션 선택               │
│     [코트A 카메1 ▼]                 │
│                                     │
│  2. 비디오 소스 선택                │
│     ○ 파일 업로드                   │
│     ○ 실시간 스트림                 │
│     ○ 웹캠                          │
│                                     │
│  3. [분석 시작]                     │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ [비디오 재생 영역]           │   │
│  │                             │   │
│  │ 실시간 낙하 지점 표시        │   │
│  └─────────────────────────────┘   │
│                                     │
│  [통계]  [히트맵]  [리플레이]       │
└─────────────────────────────────────┘
```

## 데이터베이스 스키마 (SQLite)

```sql
-- 캘리브레이션 프로파일
CREATE TABLE calibration_profiles (
    profile_id TEXT PRIMARY KEY,
    profile_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 카메라 정보 (JSON)
    camera_info TEXT,
    
    -- 캘리브레이션 데이터 (JSON)
    calibration_data TEXT NOT NULL,
    
    -- 검증 정보 (JSON)
    validation TEXT,
    
    -- 참조 이미지 경로
    reference_image_path TEXT,
    thumbnail_path TEXT,
    
    -- 메타데이터 (JSON)
    metadata TEXT
);

-- 분석 세션
CREATE TABLE analysis_sessions (
    session_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    session_name TEXT,
    video_source TEXT,  -- upload/stream/webcam
    video_path TEXT,
    
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    
    -- 분석 결과 요약 (JSON)
    summary TEXT,
    
    FOREIGN KEY (profile_id) REFERENCES calibration_profiles(profile_id)
);

-- 낙하 지점 기록
CREATE TABLE landing_detections (
    detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    
    frame_number INTEGER,
    timestamp REAL,
    
    -- 이미지 좌표 (JSON: [x, y])
    image_position TEXT,
    
    -- 실세계 좌표 (JSON: [x, y])
    world_position TEXT,
    
    -- 영역 정보
    zone TEXT,
    in_my_court BOOLEAN,
    
    -- 신뢰도
    confidence REAL,
    
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (session_id) REFERENCES analysis_sessions(session_id)
);

-- 인덱스
CREATE INDEX idx_profile_created ON calibration_profiles(created_at DESC);
CREATE INDEX idx_session_profile ON analysis_sessions(profile_id);
CREATE INDEX idx_landing_session ON landing_detections(session_id);
CREATE INDEX idx_landing_timestamp ON landing_detections(timestamp);
```

## 사용 시나리오

### 시나리오 1: 첫 사용 (캘리브레이션)

```javascript
// 1. 새 프로파일 생성
async function createCalibrationProfile() {
    // 코트 영역 조정 완료 후
    const profileData = {
        profile_id: generateProfileId(),  // 또는 사용자 입력
        profile_name: "A코트 카메라1",
        corners: courtCorners.map(c => [c.x, c.y]),
        image_width: canvas.width,
        image_height: canvas.height,
        reference_image_session_id: sessionId,
        metadata: {
            court_name: "A코트",
            venue: "XX체육관"
        }
    };
    
    const response = await fetch('/api/calibration/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profileData)
    });
    
    const result = await response.json();
    console.log('프로파일 저장:', result.profile_id);
    
    // LocalStorage에도 최근 사용 프로파일 저장
    localStorage.setItem('last_used_profile', result.profile_id);
}
```

### 시나리오 2: 실시간 분석

```javascript
// 1. 저장된 프로파일 로드
async function startAnalysis() {
    const profileId = localStorage.getItem('last_used_profile') || 
                      await selectProfileFromList();
    
    // 프로파일 로드
    const response = await fetch(`/api/calibration/profile/${profileId}`);
    const profile = await response.json();
    
    // 분석 세션 시작
    const analysisResponse = await fetch('/api/analysis/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            profile_id: profileId,
            video_source: 'webcam',
            session_name: new Date().toLocaleString()
        })
    });
    
    const session = await analysisResponse.json();
    analysisSessionId = session.analysis_session_id;
    calibrationData = session.calibration;
    
    // 비디오 스트림 시작
    startVideoStream();
}

// 2. 프레임별 분석
async function analyzeFrame(frame, frameNumber, timestamp) {
    // 캘리브레이션 데이터 사용
    const landing = detectLanding(frame, calibrationData);
    
    if (landing) {
        // 서버에 전송
        await fetch('/api/analysis/frame', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                analysis_session_id: analysisSessionId,
                frame_number: frameNumber,
                timestamp: timestamp,
                detection: landing
            })
        });
        
        // UI 업데이트
        displayLanding(landing);
    }
}
```

### 시나리오 3: 사후 분석

```javascript
// 1. 저장된 비디오 + 캘리브레이션으로 분석
async function analyzeRecordedVideo(videoFile, profileId) {
    // 비디오 업로드
    const formData = new FormData();
    formData.append('video', videoFile);
    formData.append('profile_id', profileId);
    
    const response = await fetch('/api/analysis/upload-and-analyze', {
        method: 'POST',
        body: formData
    });
    
    const result = await response.json();
    
    // 진행 상황 폴링
    const intervalId = setInterval(async () => {
        const progress = await fetch(
            `/api/analysis/progress/${result.analysis_session_id}`
        );
        const data = await progress.json();
        
        updateProgressBar(data.progress);
        
        if (data.complete) {
            clearInterval(intervalId);
            showResults(result.analysis_session_id);
        }
    }, 1000);
}
```

## 마이그레이션 경로

### 기존 세션 → 프로파일 변환

```javascript
// 현재 세션을 프로파일로 저장
async function saveCurrentSessionAsProfile() {
    const profileData = {
        profile_name: prompt('프로파일 이름을 입력하세요'),
        corners: courtCorners.map(c => [c.x, c.y]),
        image_width: canvas.width,
        image_height: canvas.height,
        reference_image_session_id: sessionId
    };
    
    await fetch('/api/calibration/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profileData)
    });
    
    alert('프로파일이 저장되었습니다. 다음부터 이 설정을 재사용할 수 있습니다.');
}
```

## 장점

1. ✅ **영속성**: 데이터베이스에 저장, 서버 재시작에도 유지
2. ✅ **재사용성**: 동일 코트/카메라 설정 반복 사용
3. ✅ **확장성**: 여러 코트, 여러 카메라 관리 가능
4. ✅ **추적성**: 분석 히스토리 관리
5. ✅ **오프라인 분석**: 저장된 영상을 나중에 분석 가능