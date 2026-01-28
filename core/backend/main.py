"""
FastAPI 메인 서버
배드민턴 코트 캘리브레이션 API
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import cv2
import numpy as np
import os
import uuid
import json
import base64
from datetime import datetime

from modules.calibration import CalibrationService, CalibrationProfileService
from modules.visualization import VisualizationService
from modules.analysis import VideoAnalysisService
from fastapi.staticfiles import StaticFiles
from decorators import time_logger

# FastAPI 앱 생성
app = FastAPI(
    title="Badminton Court Calibration API",
    description="T자 기준점 기반 배드민턴 코트 캘리브레이션 시스템",
    version="1.0.0"
)

# CORS 설정 (프론트엔드 연동용)
# [수정됨 - 2025-12-23] credentials: include 지원을 위해 특정 origin 명시
# [수정됨 - 2026-01-28] WSL 네트워크 주소 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite 개발 서버
        "http://localhost:5174",  # Vite 개발 서버 (포트 충돌 시)
        "http://localhost:8080",  # 기존 프론트엔드
        "http://172.17.97.97:5173",  # WSL 네트워크 (Windows 브라우저 접속)
        "http://172.17.97.97:5174",  # WSL 네트워크 (포트 5174)
        "http://10.255.255.254:5173",  # WSL 네트워크 (대체 주소)
        "http://10.255.255.254:5174",  # WSL 네트워크 (포트 5174, 대체)
    ],
    allow_credentials=True,  # credentials: include 허용
    allow_methods=["*"],
    allow_headers=["*"],
)

# 저장 디렉토리 설정 (프로젝트 루트 기준)
import pathlib

# 현재 파일(main.py)의 상위 폴더(backend)의 상위 폴더(bmt_demo)를 프로젝트 루트로 설정
BACKEND_DIR = pathlib.Path(__file__).parent.absolute()
PROJECT_ROOT = BACKEND_DIR.parent
STORAGE_DIR = PROJECT_ROOT / "storage"

UPLOAD_DIR = str(STORAGE_DIR / "uploads")
RESULT_DIR = str(STORAGE_DIR / "results")
CALIBRATION_DIR = str(STORAGE_DIR / "calibrations")

# 디렉토리 생성
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(CALIBRATION_DIR, exist_ok=True)

# 정적 파일 마운트 (비디오 스트리밍용)
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

# 저장소 경로 출력 (디버깅)
print(f"📁 Storage Root: {STORAGE_DIR}")

# 세션 저장소 (간단한 인메모리 저장소, 프로덕션에서는 Redis 등 사용)
sessions = {}

# 서비스 초기화
profile_service = CalibrationProfileService(
    storage_dir=CALIBRATION_DIR,
    db_path=str(STORAGE_DIR / "calibrations.db")
)


# Pydantic 모델
class TPointAlignment(BaseModel):
    """T자 정렬 정보"""
    session_id: str
    t_point_x: float
    t_point_y: float
    image_width: int
    image_height: int


class CornersAlignment(BaseModel):
    """4개 코너 정렬 정보"""
    session_id: str
    corners: List[List[float]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    image_width: int
    image_height: int


class ProfileSaveRequest(BaseModel):
    """프로파일 저장 요청"""
    profile_id: Optional[str] = None  # 없으면 자동 생성
    profile_name: str
    session_id: str  # 참조 이미지 세션
    camera_info: Optional[dict] = None
    metadata: Optional[dict] = None


class ProfileUpdateRequest(BaseModel):
    """프로파일 업데이트 요청"""
    profile_name: Optional[str] = None
    metadata: Optional[dict] = None


# 추후 확장: 프로파일 적응 요청 (Phase 2)
class ProfileAdaptRequest(BaseModel):
    """프로파일 적응 요청 (추후 구현)"""
    profile_id: str
    current_frame_session_id: str  # 현재 프레임
    adaptation_mode: str = "auto"  # auto, feature, line, manual


class CalibrationResponse(BaseModel):
    """캘리브레이션 응답"""
    success: bool
    session_id: str
    message: str
    data: Optional[dict] = None


# API 엔드포인트

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "Badminton Court Calibration API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "upload": "/api/upload",
            "align": "/api/align",
            "result": "/api/result/{session_id}",
            "image": "/api/image/{session_id}"
        }
    }


@app.get("/health")
async def health_check():
    """헬스체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    """
    이미지 업로드
    
    Args:
        file: 업로드된 이미지 파일
        
    Returns:
        세션 ID 및 이미지 정보
    """
    try:
        # 파일 검증
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")
        
        # 세션 ID 생성
        session_id = str(uuid.uuid4())
        
        # 파일 저장
        file_ext = os.path.splitext(file.filename)[1]
        filename = f"{session_id}{file_ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        contents = await file.read()
        with open(filepath, "wb") as f:
            f.write(contents)
        
        # 이미지 정보 읽기
        image = cv2.imread(filepath)
        if image is None:
            raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다")
        
        height, width = image.shape[:2]
        
        # 세션 정보 저장
        sessions[session_id] = {
            'filename': filename,
            'filepath': filepath,
            'original_filename': file.filename,
            'width': width,
            'height': height,
            'upload_time': datetime.now().isoformat(),
            'calibrated': False
        }
        
        # T자 가이드 오버레이 생성
        guide_overlay = VisualizationService.create_guide_overlay_template((height, width))
        guide_path = os.path.join(RESULT_DIR, f"{session_id}_guide.png")
        cv2.imwrite(guide_path, guide_overlay)
        
        return JSONResponse(content={
            "success": True,
            "session_id": session_id,
            "message": "이미지 업로드 완료",
            "data": {
                "width": width,
                "height": height,
                "filename": file.filename
            }
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"업로드 실패: {str(e)}")


@app.post("/api/align")
async def align_court(alignment: TPointAlignment):
    """
    T자 정렬 및 코트 영역 생성
    
    Args:
        alignment: T자 정렬 정보
        
    Returns:
        캘리브레이션 결과
    """
    try:
        session_id = alignment.session_id
        
        # 세션 확인
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        session = sessions[session_id]
        
        # 이미지 로드
        image = cv2.imread(session['filepath'])
        if image is None:
            raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다")
        
        # 캘리브레이션 서비스 초기화
        calibration_service = CalibrationService()
        
        # T자 기준점으로부터 캘리브레이션 수행
        t_point = (alignment.t_point_x, alignment.t_point_y)
        image_shape = (alignment.image_height, alignment.image_width)
        
        calibration_result = calibration_service.calibrate_from_t_point(
            t_point_image=t_point,
            image_shape=image_shape
        )
        
        if not calibration_result['success']:
            raise HTTPException(status_code=400, detail="캘리브레이션 실패")
        
        # 코트 영역 생성
        court_region = calibration_service.generate_court_region(calibration_result)
        
        # T자 가이드 좌표 계산
        t_guide_coords = calibration_service.get_t_guide_image_coords(calibration_result)
        
        # 시각화
        result_image = VisualizationService.draw_complete_visualization(
            image=image,
            calibration_result=calibration_result,
            t_guide_coords=t_guide_coords,
            show_t_guide=True,
            show_court_region=True
        )
        
        # 결과 이미지 저장
        result_filename = f"{session_id}_result.jpg"
        result_filepath = os.path.join(RESULT_DIR, result_filename)
        cv2.imwrite(result_filepath, result_image)
        
        # 세션 업데이트
        session['calibrated'] = True
        session['calibration_result'] = calibration_result
        session['court_region'] = court_region
        session['t_guide_coords'] = t_guide_coords
        session['result_filepath'] = result_filepath
        session['calibration_time'] = datetime.now().isoformat()
        
        # 결과 반환
        return JSONResponse(content={
            "success": True,
            "session_id": session_id,
            "message": "캘리브레이션 완료",
            "data": {
                "court_corners": calibration_result['court_corners_image'],
                "t_point": calibration_result['t_point_image'],
                "pixels_per_meter": calibration_result['pixels_per_meter'],
                "court_area": court_region['court_region']['area_pixels'],
                "validation": {
                    "is_valid": court_region['court_region']['is_valid'],
                    "message": court_region['court_region']['validation_message']
                }
            }
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"캘리브레이션 실패: {str(e)}")


@app.post("/api/align-corners")
async def align_court_corners(alignment: CornersAlignment):
    """
    4개 코너로 직접 정렬 (Microsoft Lens 스타일)
    
    Args:
        alignment: 4개 코너 정보
        
    Returns:
        캘리브레이션 결과
    """
    try:
        session_id = alignment.session_id
        
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        session = sessions[session_id]
        image = cv2.imread(session['filepath'])
        
        if image is None:
            raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다")
        
        # 캘리브레이션 서비스 초기화
        calibration_service = CalibrationService()
        corners = alignment.corners
        calibration_result = calibration_service.calibrate_from_corners(
            court_corners_image=corners,
            image_shape=(alignment.image_height, alignment.image_width)
        )
        
        if not calibration_result['success']:
            raise HTTPException(status_code=400, detail="캘리브레이션 실패")
        
        court_region = calibration_service.generate_court_region(calibration_result)
        t_guide_coords = calibration_service.get_t_guide_image_coords(calibration_result)
        
        # 시각화
        result_image = VisualizationService.draw_complete_visualization(
            image=image,
            calibration_result=calibration_result,
            t_guide_coords=t_guide_coords,
            show_t_guide=False,  # 4코너 방식에서는 T자 숨김
            show_court_region=True
        )
        
        result_filename = f"{session_id}_result.jpg"
        result_filepath = os.path.join(RESULT_DIR, result_filename)
        cv2.imwrite(result_filepath, result_image)
        
        session['calibrated'] = True
        session['calibration_result'] = calibration_result
        session['court_region'] = court_region
        session['result_filepath'] = result_filepath
        session['calibration_time'] = datetime.now().isoformat()
        
        return JSONResponse(content={
            "success": True,
            "session_id": session_id,
            "message": "캘리브레이션 완료",
            "data": {
                "court_corners": corners,
                "pixels_per_meter": calibration_result['pixels_per_meter'],
                "court_area": court_region['court_region']['area_pixels'],
                "validation": {
                    "is_valid": court_region['court_region']['is_valid'],
                    "message": court_region['court_region']['validation_message']
                }
            }
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"캘리브레이션 실패: {str(e)}")


@app.get("/api/result/{session_id}")
async def get_result(session_id: str):
    """
    캘리브레이션 결과 조회
    
    Args:
        session_id: 세션 ID
        
    Returns:
        캘리브레이션 결과 정보
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    
    session = sessions[session_id]
    
    if not session.get('calibrated'):
        raise HTTPException(status_code=400, detail="아직 캘리브레이션되지 않았습니다")
    
    return JSONResponse(content={
        "success": True,
        "session_id": session_id,
        "data": {
            "original_image": f"/api/image/{session_id}/original",
            "result_image": f"/api/image/{session_id}/result",
            "calibration_time": session.get('calibration_time'),
            "court_corners": session['calibration_result']['court_corners_image'],
            "validation": {
                "is_valid": session['court_region']['court_region']['is_valid'],
                "message": session['court_region']['court_region']['validation_message']
            }
        }
    })


@app.get("/api/image/{session_id}/{image_type}")
async def get_image(session_id: str, image_type: str):
    """
    이미지 파일 반환
    
    Args:
        session_id: 세션 ID
        image_type: 'original', 'result', 'guide'
        
    Returns:
        이미지 파일
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    
    session = sessions[session_id]
    
    if image_type == 'original':
        filepath = session['filepath']
    elif image_type == 'result':
        if not session.get('calibrated'):
            raise HTTPException(status_code=400, detail="아직 캘리브레이션되지 않았습니다")
        filepath = session['result_filepath']
    elif image_type == 'guide':
        filepath = os.path.join(RESULT_DIR, f"{session_id}_guide.png")
    else:
        raise HTTPException(status_code=400, detail="잘못된 이미지 타입입니다")
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="이미지 파일을 찾을 수 없습니다")
    
    return FileResponse(filepath)


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """
    세션 삭제
    
    Args:
        session_id: 세션 ID
        
    Returns:
        삭제 결과
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    
    session = sessions[session_id]
    
    # 파일 삭제
    try:
        if os.path.exists(session['filepath']):
            os.remove(session['filepath'])
        if session.get('result_filepath') and os.path.exists(session['result_filepath']):
            os.remove(session['result_filepath'])
    except Exception as e:
        print(f"파일 삭제 오류: {e}")
    
    # 세션 삭제
    del sessions[session_id]
    
    return JSONResponse(content={
        "success": True,
        "message": "세션이 삭제되었습니다"
    })


@app.post("/api/save-polygon/{session_id}")
async def save_polygon(session_id: str, polygon_data: dict):
    """
    폴리곤 데이터를 서버에 저장
    
    Args:
        session_id: 세션 ID
        polygon_data: 폴리곤 데이터 (corners, format 등)
        
    Returns:
        저장 결과
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    
    try:
        # 폴리곤 데이터 저장
        polygon_file = os.path.join(RESULT_DIR, f"{session_id}_polygon.json")
        
        with open(polygon_file, 'w') as f:
            json.dump(polygon_data, f, indent=2)
        
        sessions[session_id]['polygon_file'] = polygon_file
        
        return JSONResponse(content={
            "success": True,
            "message": "폴리곤 데이터 저장 완료",
            "file": polygon_file
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"저장 실패: {str(e)}")


@app.get("/api/polygon/{session_id}")
async def get_polygon(session_id: str):
    """
    저장된 폴리곤 데이터 조회
    
    Args:
        session_id: 세션 ID
        
    Returns:
        폴리곤 데이터
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    
    polygon_file = sessions[session_id].get('polygon_file')
    
    if not polygon_file or not os.path.exists(polygon_file):
        raise HTTPException(status_code=404, detail="폴리곤 데이터를 찾을 수 없습니다")
    
    try:
        with open(polygon_file, 'r') as f:
            polygon_data = json.load(f)
        
        return JSONResponse(content={
            "success": True,
            "data": polygon_data
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"조회 실패: {str(e)}")


# ============================================================================
# 캘리브레이션 프로파일 관리 API
# ============================================================================

@app.post("/api/calibration/profile")
async def save_calibration_profile(request: ProfileSaveRequest):
    """
    캘리브레이션 프로파일 저장
    
    현재 세션의 캘리브레이션 데이터를 영속적 프로파일로 저장
    
    Args:
        request: 프로파일 저장 요청
        
    Returns:
        저장된 프로파일 정보
    """
    try:
        session_id = request.session_id
        
        # 세션 확인
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        session = sessions[session_id]
        
        # 캘리브레이션 데이터 확인
        if not session.get('calibrated'):
            raise HTTPException(status_code=400, detail="캘리브레이션이 완료되지 않았습니다")
        
        calibration_result = session['calibration_result']
        
        # 프로파일 ID 생성 또는 사용
        profile_id = request.profile_id
        if not profile_id:
            # 자동 생성: profile_timestamp
            profile_id = f"profile_{int(datetime.now().timestamp())}"
        
        # 참조 이미지 로드
        reference_image = cv2.imread(session['filepath'])
        
        # 프로파일 저장
        result = profile_service.save_profile(
            profile_id=profile_id,
            profile_name=request.profile_name,
            corners_image=calibration_result['court_corners_image'],
            corners_world=calibration_result['court_corners_world'],
            homography=np.array(calibration_result['homography_matrix']),
            pixels_per_meter=calibration_result['pixels_per_meter'],
            image_width=session['width'],
            image_height=session['height'],
            reference_image=reference_image,
            camera_info=request.camera_info,
            metadata=request.metadata
        )
        
        return JSONResponse(content={
            "success": True,
            "message": "프로파일이 저장되었습니다",
            "profile": result
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로파일 저장 실패: {str(e)}")


@app.get("/api/calibration/profiles")
async def list_calibration_profiles():
    """
    저장된 모든 캘리브레이션 프로파일 목록 조회
    
    Returns:
        프로파일 리스트 (썸네일 포함)
    """
    try:
        profiles = profile_service.list_profiles()
        
        return JSONResponse(content={
            "success": True,
            "profiles": profiles,
            "count": len(profiles)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로파일 목록 조회 실패: {str(e)}")


@app.get("/api/calibration/profile/{profile_id}")
async def get_calibration_profile(profile_id: str):
    """
    특정 캘리브레이션 프로파일 조회
    
    Args:
        profile_id: 프로파일 ID
        
    Returns:
        프로파일 전체 데이터
    """
    try:
        profile = profile_service.get_profile(profile_id)
        
        if not profile:
            raise HTTPException(status_code=404, detail="프로파일을 찾을 수 없습니다")
        
        return JSONResponse(content={
            "success": True,
            "profile": profile
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로파일 조회 실패: {str(e)}")


@app.put("/api/calibration/profile/{profile_id}")
async def update_calibration_profile(profile_id: str, request: ProfileUpdateRequest):
    """
    캘리브레이션 프로파일 정보 업데이트
    
    Args:
        profile_id: 프로파일 ID
        request: 업데이트 요청
        
    Returns:
        업데이트 결과
    """
    try:
        success = profile_service.update_profile(
            profile_id=profile_id,
            profile_name=request.profile_name,
            metadata=request.metadata
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="프로파일을 찾을 수 없습니다")
        
        return JSONResponse(content={
            "success": True,
            "message": "프로파일이 업데이트되었습니다"
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로파일 업데이트 실패: {str(e)}")


@app.delete("/api/calibration/profile/{profile_id}")
async def delete_calibration_profile(profile_id: str):
    """
    캘리브레이션 프로파일 삭제
    
    Args:
        profile_id: 프로파일 ID
        
    Returns:
        삭제 결과
    """
    try:
        success = profile_service.delete_profile(profile_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="프로파일을 찾을 수 없습니다")
        
        return JSONResponse(content={
            "success": True,
            "message": "프로파일이 삭제되었습니다"
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로파일 삭제 실패: {str(e)}")


@app.get("/api/calibration/profile/{profile_id}/image")
async def get_profile_reference_image(profile_id: str, type: str = "reference"):
    """
    프로파일 참조 이미지 조회
    
    Args:
        profile_id: 프로파일 ID
        type: 이미지 타입 (reference, thumbnail, overlay)
        
    Returns:
        이미지 파일
    """
    try:
        profile = profile_service.get_profile(profile_id)
        
        if not profile:
            raise HTTPException(status_code=404, detail="프로파일을 찾을 수 없습니다")
        
        # 이미지 경로 결정
        if type == "thumbnail" and profile.get('thumbnail_path'):
            image_path = profile['thumbnail_path']
        elif type == "overlay":
            image_path = os.path.join(CALIBRATION_DIR, profile_id, "overlay.png")
        else:
            image_path = profile.get('reference_image_path')
        
        if not image_path or not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다")
        
        return FileResponse(image_path)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 조회 실패: {str(e)}")


# ============================================================================
# Phase 2: 프로파일 적응 API (추후 구현을 위한 Placeholder)
# ============================================================================

@app.post("/api/calibration/adapt-profile")
async def adapt_profile_to_current(request: ProfileAdaptRequest):
    """
    저장된 프로파일을 현재 프레임에 자동 적응
    
    [Phase 2에서 구현 예정]
    - 특징점 기반 자동 정렬
    - 코트 라인 검출
    - 편차 측정 및 경고
    
    Args:
        request: 프로파일 적응 요청
        
    Returns:
        적응된 캘리브레이션 데이터
    """
    raise HTTPException(
        status_code=501,
        detail="이 기능은 Phase 2에서 구현 예정입니다. 현재는 프로파일을 그대로 사용하거나 수동 조정하세요."
    )


# ============================================================================
# 비디오 분석 API
# ============================================================================

class VideoAnalysisRequest(BaseModel):
    """비디오 분석 요청"""
    session_id: str
    video_path: Optional[str] = None  # None이면 웹캠
    mode: str = "normal"  # "normal" | "debug"


@app.get("/api/videos/list")
async def list_available_videos():
    """
    storage/videos 디렉토리의 비디오 목록 조회
    
    Returns:
        비디오 파일 목록
    """
    try:
        # PROJECT_ROOT/storage/videos
        videos_dir = STORAGE_DIR / "videos"
        os.makedirs(videos_dir, exist_ok=True)
        
        print(f"📂 Scanning videos in: {videos_dir}")
        
        # 지원 비디오 확장자
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
        
        videos = []
        
        # 비디오 파일 스캔
        if videos_dir.exists():
            for filename in os.listdir(videos_dir):
                filepath = videos_dir / filename
                
                # 파일인지 확인
                if not os.path.isfile(filepath):
                    continue
                
                # 확장자 확인
                _, ext = os.path.splitext(filename)
                if ext.lower() not in video_extensions:
                    continue
                
                # 파일 정보
                stat = os.stat(filepath)
                file_size_mb = stat.st_size / (1024 * 1024)
                
                # 경로는 클라이언트에게 상대 경로(storage/videos/...)로 전달
                # PROJECT_ROOT 기준 상대 경로
                rel_path = f"storage/videos/{filename}"
                
                videos.append({
                    "filename": filename,
                    "path": rel_path,  # 클라이언트가 요청할 때 사용할 경로
                    "size_mb": round(file_size_mb, 2),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        # 최근 수정일 기준 정렬
        videos.sort(key=lambda x: x['modified'], reverse=True)
        
        return JSONResponse(content={
            "success": True,
            "videos": videos,
            "count": len(videos),
            "videos_dir": str(videos_dir)
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"비디오 목록 조회 실패: {str(e)}")


@app.post("/api/analysis/process-video")
async def process_video_analysis(request: VideoAnalysisRequest):
    """
    비디오 분석 처리
    
    Args:
        request: 비디오 분석 요청
            - session_id: 세션 ID (캘리브레이션 데이터)
            - video_path: 비디오 파일 경로 (None이면 웹캠)
            - mode: "normal" | "debug"
    
    Returns:
        처리 결과
    """
    try:
        session_id = request.session_id
        
        # 세션 확인
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        session = sessions[session_id]
        
        # 캘리브레이션 확인
        if not session.get('calibrated'):
            raise HTTPException(status_code=400, detail="캘리브레이션이 완료되지 않았습니다")
        
        calibration_result = session['calibration_result']
        
        # 디버깅: calibration_result 구조 확인
        print(f"📊 Calibration Result Keys: {list(calibration_result.keys())}")
        
        # 비디오 분석 서비스 초기화
        try:
            video_service = VideoAnalysisService(calibration_result)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"캘리브레이션 데이터 오류: {str(e)}")
        
        if request.video_path:
            # 비디오 파일 처리
            if not os.path.exists(request.video_path):
                raise HTTPException(status_code=404, detail=f"비디오 파일을 찾을 수 없습니다: {request.video_path}")
            
            # 출력 경로
            output_filename = f"{session_id}_analyzed.mp4"
            output_path = os.path.join(RESULT_DIR, output_filename)
            
            # 처리
            result = video_service.process_video_file(
                video_path=request.video_path,
                mode=request.mode,
                output_path=output_path
            )
            
            # 세션에 저장
            session['analysis_video_path'] = output_path
            
            return JSONResponse(content={
                "success": True,
                "message": "비디오 처리 완료",
                "result": result,
                "output_url": f"/api/video/{session_id}"
            })
        else:
            # 웹캠 처리 (비동기 처리 필요)
            return JSONResponse(content={
                "success": False,
                "message": "웹캠 처리는 클라이언트에서 직접 수행하세요"
            })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"비디오 분석 실패: {str(e)}")


@app.post("/api/analysis/frame-predict")
@time_logger("API: Total Frame Predict")
async def predict_frame(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    video_time: float = Form(0.0) # 비디오 시간 추가
):
    """
    실시간 프레임 분석 API
    """
    # print(f"📥 Received frame-predict request for session: {session_id}")
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    
    session = sessions[session_id]
    
    # 해당 세션용 VideoAnalysisService가 없으면 생성
    if 'analysis_service' not in session:
        if not session.get('calibrated'):
            raise HTTPException(status_code=400, detail="캘리브레이션이 완료되지 않았습니다")
        session['analysis_service'] = VideoAnalysisService(session_id, session['calibration_result'])
    
    service = session['analysis_service']
    
    # 이미지 읽기
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # 분석 수행
    processed_frame, info = service.process_frame(frame, video_time=video_time)
    
    # 분석된 프레임을 base64로 인코딩 (필요한 경우 프론트엔드에서 사용)
    _, buffer = cv2.imencode('.jpg', processed_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    
    # JSON 직렬화 오류 방지를 위해 NumPy 타입 변환 (info 내의 landing 데이터 등)
    def sanitize_info(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.float32) or isinstance(obj, np.float64):
            return float(obj)
        if isinstance(obj, np.int32) or isinstance(obj, np.int64):
            return int(obj)
        if isinstance(obj, dict):
            return {k: sanitize_info(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize_info(v) for v in obj]
        return obj

    sanitized_info = sanitize_info(info)
    
    return JSONResponse(content={
        "success": True,
        "tracknet": sanitized_info.get('tracknet'),
        "landing": sanitized_info.get('landing'),
        "processed_image": f"data:image/jpeg;base64,{img_base64}"
    })


@app.get("/api/video/{session_id}")
async def get_analyzed_video(session_id: str):
    """
    분석된 비디오 다운로드
    
    Args:
        session_id: 세션 ID
        
    Returns:
        비디오 파일
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    
    video_path = sessions[session_id].get('analysis_video_path')
    
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="분석된 비디오를 찾을 수 없습니다")
    
    return FileResponse(video_path, media_type="video/mp4")




@app.get("/api/session/{session_id}/calibration")
async def get_session_calibration(session_id: str):
    """
    세션의 캘리브레이션 데이터 조회
    
    Args:
        session_id: 세션 ID
        
    Returns:
        캘리브레이션 데이터
    """
    print(f"📡 캘리브레이션 데이터 요청: session_id={session_id}")
    print(f"   현재 세션 목록: {list(sessions.keys())}")
    
    if session_id not in sessions:
        print(f"   ❌ 세션을 찾을 수 없음")
        raise HTTPException(status_code=404, detail=f"세션을 찾을 수 없습니다: {session_id}")
    
    session = sessions[session_id]
    print(f"   세션 정보: calibrated={session.get('calibrated')}")
    
    if not session.get('calibrated'):
        print(f"   ❌ 캘리브레이션 미완료")
        raise HTTPException(status_code=400, detail="캘리브레이션이 완료되지 않았습니다")
    
    print(f"   ✅ 캘리브레이션 데이터 반환")
    return JSONResponse(content={
        "success": True,
        "session_id": session_id,
        "calibration_result": session['calibration_result']
    })


@app.get("/api/videos/stream")
async def stream_video(path: str):
    """
    비디오 스트리밍
    
    Args:
        path: 비디오 파일 경로 (절대 경로 또는 프로젝트 루트 기준 상대 경로)
        
    Returns:
        비디오 스트림
    """
    print(f"📹 비디오 스트리밍 요청: path={path}")
    
    try:
        # 상대 경로인 경우 프로젝트 루트 기준으로 변환
        if not os.path.isabs(path):
            abs_path = PROJECT_ROOT / path
            print(f"   🔄 상대 경로 변환: {path} -> {abs_path}")
            path = str(abs_path)
            
        if not os.path.exists(path):
            print(f"   ❌ 비디오 파일 없음: {path}")
            raise HTTPException(status_code=404, detail=f"비디오 파일을 찾을 수 없습니다: {path}")
        
        file_size = os.path.getsize(path)
        print(f"   ✅ 스트리밍 시작: {os.path.basename(path)} ({file_size/(1024*1024):.2f} MB)")
        
        return FileResponse(path, media_type="video/mp4")
        
    except Exception as e:
        print(f"   ❌ 스트리밍 에러: {str(e)}")
        raise


# ============================================================================
# Milestone 5: Auto Court Detection Endpoint
# ============================================================================

class AutoDetectRequest(BaseModel):
    """자동 코트 검출 요청"""
    session_id: str
    include_doubles: bool = True
    overlay_alpha: float = 1.0
    draw_corners: bool = True
    save_overlay: bool = True


class AutoDetectResponse(BaseModel):
    """자동 코트 검출 응답"""
    success: bool
    session_id: str
    message: str
    confidence: Optional[dict] = None
    corners: Optional[dict] = None
    calibration: Optional[dict] = None
    overlay_url: Optional[str] = None
    metadata: Optional[dict] = None
    error: Optional[str] = None


@app.post("/api/detect-court-auto", response_model=AutoDetectResponse)
@time_logger("Auto Detect")
async def detect_court_auto(request: AutoDetectRequest):
    """
    자동 코트 검출 및 캘리브레이션 (Milestone 5)
    
    이 엔드포인트는:
    1. 자동으로 코트 코너를 검출
    2. 캘리브레이션 수행
    3. 코트 라인 오버레이 생성
    4. 신뢰도 점수 계산
    5. 검증 UI용 데이터 반환
    
    Args:
        request: AutoDetectRequest
            - session_id: 업로드된 이미지 세션 ID
            - include_doubles: 복식 라인 포함 여부
            - overlay_alpha: 오버레이 투명도 (0.0-1.0)
            - draw_corners: 코너 마커 표시 여부
            - save_overlay: 오버레이 이미지 저장 여부
            
    Returns:
        AutoDetectResponse with:
        - success: 성공 여부
        - confidence: 신뢰도 점수
        - corners: 검출된 코너 좌표
        - calibration: 캘리브레이션 정보
        - overlay_url: 오버레이 이미지 URL
        - metadata: 추가 메타데이터
    """
    from modules.court_detection.api_integration import detect_court_with_overlay
    
    print(f"\n🎯 자동 코트 검출 요청")
    print(f"   Session ID: {request.session_id}")
    print(f"   Include doubles: {request.include_doubles}")
    print(f"   Overlay alpha: {request.overlay_alpha}")
    
    # 세션 확인
    if request.session_id not in sessions:
        print(f"   ❌ 세션을 찾을 수 없음")
        return AutoDetectResponse(
            success=False,
            session_id=request.session_id,
            message="세션을 찾을 수 없습니다",
            error=f"Invalid session_id: {request.session_id}"
        )
    
    session = sessions[request.session_id]
    filepath = session['filepath']
    
    print(f"   이미지: {session['original_filename']}")
    print(f"   크기: {session['width']}x{session['height']}")
    
    try:
        # 이미지 로드
        image = cv2.imread(filepath)
        if image is None:
            raise ValueError(f"Failed to load image: {filepath}")
        
        # 자동 검출 실행
        print(f"   🔍 자동 검출 시작...")
        result = detect_court_with_overlay(
            image=image,
            ensemble_mode='conservative',
            use_extrapolation=False,
            include_doubles=request.include_doubles,
            overlay_alpha=request.overlay_alpha,
            draw_corners=request.draw_corners,
            return_separate_images=False
        )
        
        if not result['success']:
            error_msg = result.get('error', 'Unknown error')
            print(f"   ❌ 검출 실패: {error_msg}")
            return AutoDetectResponse(
                success=False,
                session_id=request.session_id,
                message="자동 검출 실패",
                error=error_msg
            )
        
        # 신뢰도 점수
        confidence = result['confidence']
        print(f"   📊 신뢰도: {confidence['overall']:.2%}")
        print(f"      - Mask: {confidence['mask_quality']:.2%}")
        print(f"      - Geometry: {confidence['geometry_quality']:.2%}")
        print(f"      - Calibration: {confidence['calibration_quality']:.2%}")
        
        # 오버레이 이미지 저장
        overlay_url = None
        if request.save_overlay:
            overlay_filename = f"{request.session_id}_overlay.jpg"
            overlay_path = os.path.join(RESULT_DIR, overlay_filename)
            cv2.imwrite(overlay_path, result['overlay_image'])
            overlay_url = f"/storage/results/{overlay_filename}"
            print(f"   💾 오버레이 저장: {overlay_filename}")
        
        # 세션에 캘리브레이션 결과 저장
        session['calibrated'] = True
        session['calibration_result'] = {
            'homography_matrix': result['calibration']['homography_matrix'],
            'pixels_per_meter': result['calibration']['pixels_per_meter'],
            'court_corners_world': result['calibration']['court_corners_world'],
            'court_corners_image': {
                k: [float(v[0]), float(v[1])] 
                for k, v in result['corners'].items()
            }
        }
        session['auto_detect_confidence'] = confidence
        session['auto_detect_time'] = datetime.now().isoformat()
        
        # 응답 준비
        corners_json = {
            k: [float(v[0]), float(v[1])] 
            for k, v in result['corners'].items()
        }
        
        print(f"   ✅ 자동 검출 완료")
        
        return AutoDetectResponse(
            success=True,
            session_id=request.session_id,
            message="자동 검출 성공",
            confidence=confidence,
            corners=corners_json,
            calibration={
                'pixels_per_meter': result['calibration']['pixels_per_meter'],
                'homography_matrix': result['calibration']['homography_matrix']
            },
            overlay_url=overlay_url,
            metadata={
                'image_shape': result['metadata']['image_shape'],
                'include_doubles': request.include_doubles,
                'detection_time': session['auto_detect_time']
            }
        )
        
    except Exception as e:
        print(f"   ❌ 에러 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return AutoDetectResponse(
            success=False,
            session_id=request.session_id,
            message="자동 검출 중 오류 발생",
            error=str(e)
        )


@app.get("/api/detect-court-auto/status/{session_id}")
async def get_auto_detect_status(session_id: str):
    """
    자동 검출 상태 조회
    
    Args:
        session_id: 세션 ID
        
    Returns:
        검출 상태 및 결과
    """
    print(f"\n📊 자동 검출 상태 조회: {session_id}")
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    
    session = sessions[session_id]
    
    if not session.get('calibrated'):
        return JSONResponse(content={
            "success": True,
            "session_id": session_id,
            "status": "not_detected",
            "message": "아직 검출되지 않았습니다"
        })
    
    return JSONResponse(content={
        "success": True,
        "session_id": session_id,
        "status": "detected",
        "confidence": session.get('auto_detect_confidence'),
        "calibration": session.get('calibration_result'),
        "detection_time": session.get('auto_detect_time')
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)