"""
캘리브레이션 프로파일 관리 서비스

영속적인 캘리브레이션 데이터 저장 및 관리
"""

import os
import json
import sqlite3
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import cv2
import numpy as np
import base64


class CalibrationProfileService:
    """캘리브레이션 프로파일 관리"""
    
    def __init__(self, storage_dir: str = "storage/calibrations", db_path: str = "storage/calibrations.db"):
        """
        초기화
        
        Args:
            storage_dir: 프로파일 저장 디렉토리
            db_path: SQLite 데이터베이스 경로
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 데이터베이스 경로의 부모 디렉토리 생성
        db_path_obj = Path(db_path)
        db_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 캘리브레이션 프로파일 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calibration_profiles (
                profile_id TEXT PRIMARY KEY,
                profile_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                camera_info TEXT,
                calibration_data TEXT NOT NULL,
                validation TEXT,
                reference_image_path TEXT,
                thumbnail_path TEXT,
                metadata TEXT
            )
        ''')
        
        # 분석 세션 테이블 (Phase 3에서 사용)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_sessions (
                session_id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                session_name TEXT,
                video_source TEXT,
                video_path TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                summary TEXT,
                FOREIGN KEY (profile_id) REFERENCES calibration_profiles(profile_id)
            )
        ''')
        
        # 낙하 지점 기록 테이블 (Phase 3에서 사용)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS landing_detections (
                detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                frame_number INTEGER,
                timestamp REAL,
                image_position TEXT,
                world_position TEXT,
                zone TEXT,
                in_my_court BOOLEAN,
                confidence REAL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES analysis_sessions(session_id)
            )
        ''')
        
        # 인덱스 생성
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_profile_created 
            ON calibration_profiles(created_at DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_session_profile 
            ON analysis_sessions(profile_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_landing_session 
            ON landing_detections(session_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_landing_timestamp 
            ON landing_detections(timestamp)
        ''')
        
        conn.commit()
        conn.close()
        
        print(f"✅ 데이터베이스 초기화 완료: {self.db_path}")
    
    def save_profile(
        self,
        profile_id: str,
        profile_name: str,
        corners_image: List[List[float]],
        corners_world: List[List[float]],
        homography: np.ndarray,
        pixels_per_meter: float,
        image_width: int,
        image_height: int,
        reference_image: Optional[np.ndarray] = None,
        camera_info: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        캘리브레이션 프로파일 저장
        
        Args:
            profile_id: 프로파일 ID (예: profile_1234567890)
            profile_name: 사용자 정의 이름 (예: A코트 카메라1)
            corners_image: 이미지 좌표 4개 코너 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            corners_world: 실세계 좌표 4개 코너 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            homography: Homography 변환 행렬 (3x3)
            pixels_per_meter: 픽셀/미터 비율
            image_width: 이미지 너비 (픽셀)
            image_height: 이미지 높이 (픽셀)
            reference_image: 참조 이미지 (numpy array)
            camera_info: 카메라 정보 (dict)
            metadata: 기타 메타데이터 (dict)
            
        Returns:
            저장 결과 정보
        """
        try:
            # 프로파일 디렉토리 생성
            profile_dir = self.storage_dir / profile_id
            profile_dir.mkdir(parents=True, exist_ok=True)
            
            # 참조 이미지 저장
            reference_image_path = None
            thumbnail_path = None
            thumbnail_base64 = None
            
            if reference_image is not None:
                # 원본 이미지 저장
                reference_image_path = str(profile_dir / "reference.jpg")
                cv2.imwrite(reference_image_path, reference_image)
                
                # 썸네일 생성 (200x150)
                thumbnail = cv2.resize(reference_image, (200, 150))
                thumbnail_path = str(profile_dir / "thumbnail.jpg")
                cv2.imwrite(thumbnail_path, thumbnail)
                
                # Base64 인코딩 (프론트엔드 전송용)
                _, buffer = cv2.imencode('.jpg', thumbnail)
                thumbnail_base64 = base64.b64encode(buffer).decode('utf-8')
                
                # 오버레이 이미지 생성 (코트 영역 시각화)
                overlay = self._create_overlay_image(
                    reference_image, 
                    corners_image
                )
                overlay_path = str(profile_dir / "overlay.png")
                cv2.imwrite(overlay_path, overlay)
            
            # 캘리브레이션 데이터 구성
            calibration_data = {
                "corners_image": corners_image,
                "corners_world": corners_world,
                "homography_matrix": homography.tolist(),
                "inverse_homography": np.linalg.inv(homography).tolist(),
                "pixels_per_meter": float(pixels_per_meter),
                "image_width": int(image_width),
                "image_height": int(image_height)
            }
            
            # 검증 정보
            reprojection_error = self._calculate_reprojection_error(
                corners_image, 
                corners_world, 
                homography
            )
            
            validation = {
                "is_valid": True,
                "reprojection_error": float(reprojection_error),
                "validation_time": datetime.now().isoformat()
            }
            
            # 데이터베이스에 저장
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO calibration_profiles 
                (profile_id, profile_name, camera_info, calibration_data, 
                 validation, reference_image_path, thumbnail_path, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                profile_id,
                profile_name,
                json.dumps(camera_info) if camera_info else None,
                json.dumps(calibration_data),
                json.dumps(validation),
                reference_image_path,
                thumbnail_path,
                json.dumps(metadata) if metadata else None
            ))
            
            conn.commit()
            conn.close()
            
            print(f"✅ 프로파일 저장 완료: {profile_id}")
            
            return {
                "profile_id": profile_id,
                "profile_name": profile_name,
                "thumbnail_base64": f"data:image/jpeg;base64,{thumbnail_base64}" if thumbnail_base64 else None,
                "created_at": datetime.now().isoformat(),
                "reprojection_error": float(reprojection_error)
            }
        
        except Exception as e:
            print(f"❌ 프로파일 저장 실패: {e}")
            raise
    
    def get_profile(self, profile_id: str) -> Optional[Dict]:
        """
        프로파일 조회
        
        Args:
            profile_id: 프로파일 ID
            
        Returns:
            프로파일 데이터 (전체)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM calibration_profiles WHERE profile_id = ?
            ''', (profile_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            # JSON 필드 파싱
            profile = {
                "profile_id": row["profile_id"],
                "profile_name": row["profile_name"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "camera_info": json.loads(row["camera_info"]) if row["camera_info"] else None,
                "calibration_data": json.loads(row["calibration_data"]),
                "validation": json.loads(row["validation"]) if row["validation"] else None,
                "reference_image_path": row["reference_image_path"],
                "thumbnail_path": row["thumbnail_path"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None
            }
            
            # 썸네일 Base64 추가
            if profile["thumbnail_path"] and os.path.exists(profile["thumbnail_path"]):
                with open(profile["thumbnail_path"], "rb") as f:
                    thumbnail_base64 = base64.b64encode(f.read()).decode('utf-8')
                    profile["thumbnail_base64"] = f"data:image/jpeg;base64,{thumbnail_base64}"
            
            return profile
        
        except Exception as e:
            print(f"❌ 프로파일 조회 실패: {e}")
            raise
    
    def list_profiles(self) -> List[Dict]:
        """
        모든 프로파일 목록 조회
        
        Returns:
            프로파일 리스트 (요약 정보 + 썸네일)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT profile_id, profile_name, created_at, updated_at, 
                       thumbnail_path, metadata
                FROM calibration_profiles
                ORDER BY updated_at DESC
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            profiles = []
            for row in rows:
                profile = {
                    "profile_id": row["profile_id"],
                    "profile_name": row["profile_name"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else None
                }
                
                # 썸네일 로드
                if row["thumbnail_path"] and os.path.exists(row["thumbnail_path"]):
                    try:
                        with open(row["thumbnail_path"], "rb") as f:
                            thumbnail_base64 = base64.b64encode(f.read()).decode('utf-8')
                            profile["thumbnail_base64"] = f"data:image/jpeg;base64,{thumbnail_base64}"
                    except Exception as e:
                        print(f"⚠️  썸네일 로드 실패 ({row['profile_id']}): {e}")
                        profile["thumbnail_base64"] = None
                
                profiles.append(profile)
            
            print(f"✅ 프로파일 목록 조회: {len(profiles)}개")
            return profiles
        
        except Exception as e:
            print(f"❌ 프로파일 목록 조회 실패: {e}")
            raise
    
    def update_profile(
        self,
        profile_id: str,
        profile_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        프로파일 정보 업데이트 (이름/메타데이터만)
        
        Args:
            profile_id: 프로파일 ID
            profile_name: 새 이름
            metadata: 새 메타데이터
            
        Returns:
            성공 여부
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            updates = []
            params = []
            
            if profile_name:
                updates.append("profile_name = ?")
                params.append(profile_name)
            
            if metadata is not None:
                updates.append("metadata = ?")
                params.append(json.dumps(metadata))
            
            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(profile_id)
                
                query = f"UPDATE calibration_profiles SET {', '.join(updates)} WHERE profile_id = ?"
                cursor.execute(query, params)
                
                conn.commit()
                success = cursor.rowcount > 0
                
                if success:
                    print(f"✅ 프로파일 업데이트 완료: {profile_id}")
                else:
                    print(f"⚠️  프로파일을 찾을 수 없음: {profile_id}")
            else:
                success = False
                print("⚠️  업데이트할 내용이 없음")
            
            conn.close()
            return success
        
        except Exception as e:
            print(f"❌ 프로파일 업데이트 실패: {e}")
            raise
    
    def delete_profile(self, profile_id: str) -> bool:
        """
        프로파일 삭제 (DB + 파일)
        
        Args:
            profile_id: 프로파일 ID
            
        Returns:
            성공 여부
        """
        try:
            # 디렉토리 삭제
            profile_dir = self.storage_dir / profile_id
            if profile_dir.exists():
                shutil.rmtree(profile_dir)
                print(f"✅ 프로파일 디렉토리 삭제: {profile_dir}")
            
            # 데이터베이스에서 삭제
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM calibration_profiles WHERE profile_id = ?', (profile_id,))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            
            if success:
                print(f"✅ 프로파일 삭제 완료: {profile_id}")
            else:
                print(f"⚠️  프로파일을 찾을 수 없음: {profile_id}")
            
            return success
        
        except Exception as e:
            print(f"❌ 프로파일 삭제 실패: {e}")
            raise
    
    def _create_overlay_image(
        self, 
        image: np.ndarray, 
        corners: List[List[float]]
    ) -> np.ndarray:
        """
        코트 영역 오버레이 이미지 생성
        
        Args:
            image: 원본 이미지
            corners: 4개 코너 좌표
            
        Returns:
            오버레이가 적용된 이미지
        """
        overlay = image.copy()
        corners_array = np.array(corners, dtype=np.int32)
        
        # 반투명 녹색 채우기
        mask = np.zeros_like(overlay)
        cv2.fillPoly(mask, [corners_array], (0, 255, 0))
        overlay = cv2.addWeighted(overlay, 0.7, mask, 0.3, 0)
        
        # 경계선
        cv2.polylines(overlay, [corners_array], True, (0, 255, 255), 3)
        
        # 코너 포인트
        colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (0, 255, 255)]
        labels = ['TL', 'TR', 'BR', 'BL']
        
        for i, (corner, color, label) in enumerate(zip(corners, colors, labels)):
            x, y = int(corner[0]), int(corner[1])
            cv2.circle(overlay, (x, y), 10, color, -1)
            cv2.circle(overlay, (x, y), 12, (255, 255, 255), 2)
            cv2.putText(overlay, label, (x + 15, y - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return overlay
    
    def _calculate_reprojection_error(
        self,
        corners_image: List[List[float]],
        corners_world: List[List[float]],
        homography: np.ndarray
    ) -> float:
        """
        재투영 오차 계산 (캘리브레이션 품질 지표)
        
        Args:
            corners_image: 이미지 좌표 코너
            corners_world: 실세계 좌표 코너
            homography: Homography 행렬
            
        Returns:
            평균 재투영 오차 (픽셀)
        """
        try:
            corners_world_array = np.array(corners_world, dtype=np.float32).reshape(-1, 1, 2)
            corners_image_array = np.array(corners_image, dtype=np.float32)
            
            # 실세계 → 이미지 변환
            projected = cv2.perspectiveTransform(corners_world_array, homography)
            projected = projected.reshape(-1, 2)
            
            # 오차 계산 (유클리드 거리)
            errors = np.sqrt(np.sum((projected - corners_image_array) ** 2, axis=1))
            mean_error = np.mean(errors)
            
            return float(mean_error)
        
        except Exception as e:
            print(f"⚠️  재투영 오차 계산 실패: {e}")
            return 0.0


# ============================================================================
# Phase 2: 프로파일 적응 클래스 (추후 구현)
# ============================================================================

class ProfileAdapter:
    """
    저장된 프로파일을 현재 프레임에 자동 적응
    
    [Phase 2에서 구현 예정]
    - 특징점 기반 자동 정렬
    - 코트 라인 검출
    - 편차 측정 및 경고
    """
    
    def __init__(self, profile: Dict):
        """
        Args:
            profile: 프로파일 데이터
        """
        self.profile = profile
        self.reference_image_path = profile.get('reference_image_path')
        self.reference_corners = profile['calibration_data']['corners_image']
    
    def adapt_to_frame(self, current_frame: np.ndarray, mode: str = 'auto') -> Dict:
        """
        프로파일을 현재 프레임에 자동 적응
        
        Args:
            current_frame: 현재 프레임 이미지
            mode: 적응 모드 ('auto', 'feature', 'line', 'manual')
            
        Returns:
            {
                'status': 'ok' | 'needs_adjustment' | 'needs_recalibration',
                'adjusted_corners': [...],
                'confidence': 0.0-1.0,
                'deviation': float (픽셀),
                'method': str,
                'suggestions': [...]
            }
        """
        # TODO: Phase 2에서 구현
        raise NotImplementedError("Phase 2에서 구현 예정")


# ============================================================================
# Phase 3: 분석 세션 관리 클래스 (추후 구현)
# ============================================================================

class AnalysisSessionManager:
    """
    비디오 분석 세션 관리
    
    [Phase 3에서 구현 예정]
    - 분석 세션 생성/관리
    - 낙하 지점 기록
    - 통계 생성
    """
    
    def __init__(self, db_path: str):
        """
        Args:
            db_path: SQLite 데이터베이스 경로
        """
        self.db_path = db_path
    
    def create_session(
        self, 
        profile_id: str, 
        session_name: str,
        video_source: str
    ) -> str:
        """
        분석 세션 생성
        
        Returns:
            session_id
        """
        # TODO: Phase 3에서 구현
        raise NotImplementedError("Phase 3에서 구현 예정")
    
    def record_landing(
        self,
        session_id: str,
        frame_number: int,
        timestamp: float,
        image_position: List[float],
        world_position: List[float],
        zone: str,
        in_my_court: bool,
        confidence: float
    ):
        """
        낙하 지점 기록
        """
        # TODO: Phase 3에서 구현
        raise NotImplementedError("Phase 3에서 구현 예정")
    
    def get_session_summary(self, session_id: str) -> Dict:
        """
        세션 통계 조회
        """
        # TODO: Phase 3에서 구현
        raise NotImplementedError("Phase 3에서 구현 예정")