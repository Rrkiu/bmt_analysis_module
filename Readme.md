# 배드민턴 코트 캘리브레이션 및 분석 시스템 (Badminton Court Calibration & Analysis System)

## 프로젝트 개요
이 시스템은 배드민턴 코트의 **자동 캘리브레이션(Calibration)**과 **셔틀콕 추적(Shuttlecock Tracking)** 기능을 제공하는 백엔드 엔진입니다. 
다른 메인 시스템의 **하위 프로세스(Sub-process)** 또는 **마이크로서비스**로 동작하도록 설계되었으며, REST API를 통해 이미지/비디오 분석 결과를 반환합니다.

주요 역할:
1.  **Court Calibration**: 코트의 기준점(4점 코너)을 통해 카메라-코트 간의 호모그래피(Homography) 변환 행렬을 산출합니다.
2.  **Object Tracking**: TrackNet 기반의 셔틀콕 위치 추적 및 비디오 분석을 수행합니다.

## 프로젝트 구조

```text
.
├── backend/            # FastAPI 메인 서버 코드
├── trackernet/
│   └── TrackNetV3/     # TrackNet 모델 서버 (Inference Server)
│       └── ckpts/      # 가중치 파일 (.pt) 저장 폴더
├── storage/            # 데이터 저장소
│   ├── uploads/        # 업로드된 원본 이미지
│   ├── results/        # 분석 결과 (이미지, JSON, 영상)
│   └── videos/         # 분석용 비디오 파일
└── Readme.md
```


## 시스템 아키텍처

- **Framework**: Python FastAPI (비동기 처리 지원)
- **Computer Vision**: OpenCV, PyTorch (Deep Learning Model)
- **Communication**: HTTP REST API (Default Port: 8000)

------------------------------------------------------------------------------------------------------------------------

## API 연동 가이드

본 모듈을 하위 프로세스로 연동하기 위한 핵심 API 명세입니다.

------------------------------------------------------------------------------------------------------------------------

## 데이터 규격 및 좌표계

본 시스템에서 사용하는 모든 좌표와 단위는 다음과 같습니다.

*   **좌표계**: 이미지 좌상단을 (0, 0)으로 하는 **픽셀(Pixel) 좌표계**를 사용합니다.
*   **이미지 크기**: 원본 이미지의 해상도를 유지하며 응답하지만, 분석 엔진 내부에서는 필요에 따라 리사이징(예: 512x288) 후 다시 원본 스케일로 복원하여 반환합니다.
*   **단위**:
    *   `x, y`: 픽셀 (Pixel)
    *   `visibility`: 0 (미검출/가려짐), 1 (검출됨)
    *   `pixels_per_meter`: 1미터당 차지하는 픽셀 수 (Scale)

---

### 1. 작업 흐름 (Workflow)

본 시스템은 상위 어플리케이션(Main App) 제어 하에 동작하는 분석 엔진입니다. 전체적인 연동 시나리오는 다음과 같습니다.

#### **Scenario A: 실시간 프레임 분석 연동 (Real-time Integration)**
라이브 스트리밍이나 웹캠 입력 등을 메인 앱에서 프레임 단위로 캡처하여 분석을 요청하는 방식입니다.

1.  **초기화 (Session Init)**
    *   **Main App**: 카메라의 기준(Reference) 프레임 1장을 캡처하여 `/api/upload`로 전송합니다.
    *   **Sub-process**: 이미지를 저장하고 고유 `session_id`를 발급합니다.
2.  **캘리브레이션 (Calibration)**
    *   **Main App**: 사용자 UI를 통해 코트의 4개 모서리(TL, TR, BR, BL) 좌표를 입력받습니다.
    *   **Main App**: 입력받은 4점 좌표를 `/api/align-corners`로 전송합니다.
    *   **Sub-process**: 호모그래피 행렬을 계산하고 코트 규격을 검증한 뒤 결과를 반환합니다. (성공 시 분석 준비 완료)
3.  **실시간 분석 루프 (Analysis Loop)**
    *   **Main App**: 비디오 스트림에서 프레임을 획득할 때마다 `/api/analysis/frame-predict`로 전송합니다. (Latency 최소화 필요)
    *   **Sub-process**: 수신된 프레임에 대해 TrackNet 추론을 수행하고, 셔틀콕 좌표(x, y)를 즉시 응답합니다.

#### **Scenario B: 영상 파일 배치 분석 (Batch Processing)**
보유하고 있는 비디오 파일 전체에 대한 분석을 요청하는 방식입니다.

1.  **초기화 및 캘리브레이션**: Scenario A와 동일하게 세션을 생성하고 코트 정렬을 완료해야 합니다. (비디오의 첫 프레임 등을 사용)
2.  **비디오 분석 요청**:
    *   **Main App**: 분석할 비디오 파일의 경로와 `session_id`를 `/api/analysis/process-video`로 전송합니다.
3.  **결과 수신**:
    *   **Sub-process**: 전체 영상을 처리하여 셔틀콕 궤적, 이벤트(득점/실점 등)를 포함한 종합 리포트 및 분석된 영상을 생성합니다.
    *   **Main App**: 처리 완료 응답을 받으면 결과 영상이나 데이터를 다운로드합니다.

------------------------------------------------------------------------------------------------------------------------

### 2. 주요 API 명세

#### A. 초기화 (Initialization)

**이미지 업로드 (세션 시작)**
*   **Endpoint**: `POST /api/upload`
*   **Description**: 분석할 카메라 구도의 기준 이미지를 업로드하고 세션을 시작합니다.
*   **Input**: `multipart/form-data` - `file` (이미지 파일)
*   **Output**: 
    ```json
    {
        "success": true,
        "session_id": "uuid-string",  // 이후 모든 요청의 키
        "data": { "width": 1280, "height": 720, ... }
    }
    ```

#### B. 캘리브레이션 (Calibration)

**4점 코너 지정 정렬 (4-Corner Alignment)**
*   **Endpoint**: `POST /api/align-corners`
*   **Description**: 사용자가 코트의 4개 모서리(Top-Left, Top-Right, Bottom-Right, Bottom-Left)를 직접 지정하여 캘리브레이션을 수행합니다.
*   **Input (JSON)**:
    ```json
    {
        "session_id": "uuid-string",
        "corners": [
            [x1, y1],  // Top-Left (TL)
            [x2, y2],  // Top-Right (TR)
            [x3, y3],  // Bottom-Right (BR)
            [x4, y4]   // Bottom-Left (BL)
        ],
        "image_width": 1280,
        "image_height": 720
    }
    ```
    *(참고: 코너 순서는 UI 구현에 따라 TL -> TR -> BR -> BL 순서로 전달됨을 가정합니다)*
*   **Output**: 캘리브레이션 성공 여부, 호모그래피 행렬, 정제된 코트 영역 데이터

#### C. 분석 (Analysis) - **Core Feature for Sub-process**

**프레임 단위 셔틀콕 추적 (Frame Prediction)**
상위 시스템에서 영상을 프레임 단위로 캡처하여 요청을 보낼 때 사용합니다.

*   **Endpoint**: `POST /api/analysis/frame-predict`
*   **Type**: `multipart/form-data`
*   **Input**:
    *   `session_id` (Form): 캘리브레이션이 완료된 세션 ID
    *   `file` (File): 현재 프레임 이미지 (Binary)
*   **Output (JSON)**:
    ```json
    {
        "success": true,
        "tracknet": {
            "x": 450,          // 이미지 내 x 좌표 (없으면 null)
            "y": 300,          // 이미지 내 y 좌표 (없으면 null)
            "visibility": 1    // 0: 안보임, 1: 보임
        }
    }
    ```

**비디오 파일 일괄 처리**
서버 스토리지에 있는 비디오 파일을 분석합니다.

*   **Endpoint**: `POST /api/analysis/process-video`
*   **Input (JSON)**:
    ```json
    {
        "session_id": "uuid-string",
        "video_path": "storage/videos/match_01.mp4",
        "mode": "normal"
    }
    ```

---------------------------------------------------------------------------------------------------------------------------

## 데이터 구조 (Data Structures)

### Calibration Result (캘리브레이션 결과)
통신 시 `calibration_result` 객체로 빈번하게 주고받는 데이터입니다.

```json
{
    "homography_matrix": [[...], [...], [...]], // 3x3 변환 행렬
    "pixels_per_meter": 45.2,                   // 스케일 정보
    "court_corners_image": [[x,y], ...],        // 이미지 상의 코트 4 모서리
    "court_corners_world": [[0,0], ...],        // 실제 코트 규격 좌표 (미터 단위)
    "t_point_image": [x, y],
    "success": true
}
```

---------------------------------------------------------------------------------------------------------------------------

## 설치 및 실행 (Installation & Run)

### 필수 요구사항
*   Python 3.8+
*   CUDA (권장, TrackNet 모델 추론용)

### 실행 방법
1.  **의존성 설치**:
    ```bash
    pip install -r backend/requirements.txt
    ```
2.  **서버 실행**:
    ```bash
    cd backend
    python main.py
    ```

    # 프론트엔드 실행
    ```bash
    cd frontend
    python -m http.server 8000
    ```

------------------------------------------------------------------------------------------------------------------------------

## TrackNet 모델 서버 실행 (Docker & Manual)

TrackNet 분석 기능을 사용하려면 별도의 모델 추론 서버를 실행해야 합니다. 백엔드 서버와는 **ZeroMQ (Port: 8002)**를 통해 통신합니다.

### 0. 모델 파일(Weights) 준비
분석 시작 전, 학습된 모델 파일을 다음 경로에 반드시 배치해야 합니다.
*   **경로**: `trackernet/TrackNetV3/ckpts/`
*   **필수 파일**: `TrackNet_best.pt` (추가로 `InpaintNet_best.pt` 사용 가능)

### 1. Docker를 이용한 실행 (권장)
GPU 환경에서 가장 안정적으로 실행할 수 있는 방법입니다.

*   **배경**: TrackNetV3는 특정 버전의 CUDA와 PyTorch 환경이 필요하므로 Docker 사용을 권장합니다.
*   **이미지 빌드**:
    ```bash
    cd trackernet/TrackNetV3
    docker build -t tracknet_inference:2512 .
    ```

*   **컨테이너 실행 (GPU 사용)**:
    ```bash
    # 프로젝트 루트(/bmt_demo)에서 실행한다고 가정할 때
    docker run -d --gpus all \
        --shm-size=8gb \
        -p 8001:8000 \
        -p 8002:8002 \
        -v $(pwd):/workspace \
        -w /workspace/trackernet/TrackNetV3 \
        --name tracknet_api \
        tracknet_inference:2512 \
        python3 inference_server.py
    ```
    *(참고: 백엔드 서버와의 Port 충돌을 피하기 위해 HTTP API 포트를 8001로 맵핑합니다)*

### 2. 네트워크 및 환경 설정
백엔드와 모델 서버가 분리된 환경이거나 포트를 변경해야 할 경우 다음 설정을 확인하십시오.
*   **Backend -> Model Server**: `backend/tracknet_service.py` 파일의 `zmq_url` (기본값: `tcp://localhost:8002`)
*   **Model Server 수신 설정**: `trackernet/TrackNetV3/inference_server.py`의 `zmq_server` 함수 내 `bind` 설정
