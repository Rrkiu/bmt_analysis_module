import cv2
import numpy as np
import pandas as pd
import os
import sys
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shuttlecock_tracker import ShuttlecockLandingDetector
from geometry import HomographyTransform, CourtGeometry
from visualization_service import VisualizationService
from constants import COURT_TEMPLATE

def test_milestone3():
    # 1. 환경 설정
    csv_path = "/mnt/b/cd_p/bmt_demo/core/trackernet/TrackNetV3/prediction/match2_rebuilt_ball.csv"
    output_path = "/mnt/b/cd_p/bmt_demo/backend/storage/m3_hhss.mp4"
    
    # Milestone 1: 프로파일 데이터 (profile_1765956553)
    corners_image = [
        [464.897391116592, 498.8563310053509],  # TL
        [910.0957402367183, 501.4772925342629], # TR
        [1276.4979213709814, 717.706618669503], # BR
        [101.12174891519092, 713.7751763761349]  # BL
    ]
    user_court = COURT_TEMPLATE['user_court']
    corners_world = [
        user_court['top_left'],
        user_court['top_right'],
        user_court['bottom_right'],
        user_court['bottom_left']
    ]
    
    # Homography 초기화
    ht = HomographyTransform()
    ht.compute_homography(
        np.array(corners_image, dtype=np.float32),
        np.array(corners_world, dtype=np.float32),
        method=0
    )
    
    # 2. 데이터 로드
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return
    df = pd.read_csv(csv_path)
    
    # 3. 비디오 작성기 초기화
    width, height = 1280, 720
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, 30, (width, height))
    
    # 4. 낙하 감지기 초기화 (사용자 요청 값: stay_threshold=3.0, stay_frames=6)
    detector = ShuttlecockLandingDetector(stay_threshold=3.0, stay_frames=6)
    
    landed_info = None
    world_pos = None
    is_in_court = False
    
    print(f"Processing Milestone 3 Pipeline...")
    
    for _, row in df.iterrows():
        frame_idx = int(row['Frame'])
        visibility = int(row['Visibility'])
        x, y = float(row['X']), float(row['Y'])
        
        # 4-1. 흰색 배경 생성
        frame_img = np.ones((height, width, 3), dtype=np.uint8) * 255
        
        # 4-2. 코트 영역 오버레이 (Milestone 1)
        frame_img = VisualizationService.draw_court_region(frame_img, corners_image)
        
        # 4-3. 낙하 감지 업데이트
        new_landing = detector.update(x, y, visibility, frame_idx)
        if new_landing:
            landed_info = detector.get_landing_info()
            # 실세계 좌표 변환
            world_pos = ht.image_to_world((landed_info['x'], landed_info['y']))
            # 코트 내/외 판별
            is_in_court = CourtGeometry.is_point_in_court(world_pos)
            print(f"Landing detected! Image: ({landed_info['x']:.1f}, {landed_info['y']:.1f}), World: {world_pos}, In-Court: {is_in_court}")
            
        # 4-4. 셔틀콕 시각화
        if visibility == 1:
            cv2.circle(frame_img, (int(x), int(y)), 6, (0, 0, 255), -1)
            
        # 궤적 표시
        for pos in detector.position_history:
            cv2.circle(frame_img, (int(pos[0]), int(pos[1])), 2, (150, 150, 255), -1)
            
        # 4-5. 미니맵 시각화 (낙하 감지 시)
        if landed_info:
            frame_img = VisualizationService.draw_minimap(
                frame_img, 
                world_point=world_pos, 
                is_in_court=is_in_court
            )
            # 낙하 지점 강조
            cv2.drawMarker(frame_img, (int(landed_info['x']), int(landed_info['y'])), 
                          (0, 100, 0) if is_in_court else (0, 0, 255), 
                          cv2.MARKER_TILTED_CROSS, 25, 3)
            
        # 프레임 번호
        cv2.putText(frame_img, f"Frame: {frame_idx}", (20, 700), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        
        out.write(frame_img)
        
    out.release()
    print(f"Video saved to {output_path}")

if __name__ == "__main__":
    test_milestone3()
