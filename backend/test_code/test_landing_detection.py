import cv2
import numpy as np
import pandas as pd
import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shuttlecock_tracker import ShuttlecockLandingDetector

def test_landing_detection():
    # csv_path = "/mnt/b/cd_p/bmt_demo/trackernet/TrackNetV3/prediction/match2_rebuilt_ball.csv"
    csv_path = "/mnt/b/cd_p/bmt_demo/trackernet/TrackNetV3/prediction/match1_rebuilt_ball.csv"
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return

    # CSV 데이터 로드
    df = pd.read_csv(csv_path)
    
    # 영상 설정
    width, height = 1280, 720
    fps = 30
    output_path = "/mnt/b/cd_p/bmt_demo/backend/storage/test_landing_detection.mp4"
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # 감지기 객체 생성
    # stay_threshold와 stay_frames는 데이터에 맞춰 조정 가능
    detector = ShuttlecockLandingDetector(stay_threshold=3.0, stay_frames=6)
    
    detected_landings = []
    
    print(f"Processing {len(df)} frames...")
    
    for _, row in df.iterrows():
        frame_idx = int(row['Frame'])
        visibility = int(row['Visibility'])
        x, y = float(row['X']), float(row['Y'])
        
        # 흰색 배경 생성
        frame_img = np.ones((height, width, 3), dtype=np.uint8) * 255
        
        # 낙하 감지 업데이트
        new_landing = detector.update(x, y, visibility, frame_idx)
        if new_landing:
            landing_info = detector.get_landing_info()
            detected_landings.append(landing_info)
            print(f"Landing detected at frame {frame_idx}: ({x}, {y})")
            
        # 시각화: 궤적 (최근 히스토리)
        for i, pos in enumerate(detector.position_history):
            alpha = (i + 1) / len(detector.position_history)
            cv2.circle(frame_img, (int(pos[0]), int(pos[1])), 3, (0, 0, 255), -1)
            
        # 시각화: 현재 위치
        if visibility == 1:
            cv2.circle(frame_img, (int(x), int(y)), 8, (0, 0, 255), -1)
            cv2.circle(frame_img, (int(x), int(y)), 10, (100, 100, 255), 2)
            
        # 시각화: 이미 발견된 낙하 지점들
        for landing in detected_landings:
            lx, ly = int(landing['x']), int(landing['y'])
            cv2.drawMarker(frame_img, (lx, ly), (0, 255, 0), cv2.MARKER_CROSS, 20, 3)
            cv2.putText(frame_img, "LANDED", (lx + 15, ly - 15), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 150, 0), 2)
            
        # 정보 텍스트
        cv2.putText(frame_img, f"Frame: {frame_idx}", (50, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
        if detector.is_landed:
            cv2.putText(frame_img, "SHUTTLECOCK LANDING DETECTED!", (400, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
            
        out.write(frame_img)
        
    out.release()
    print(f"Analysis complete. Video saved to {output_path}")
    print(f"Total landings detected: {len(detected_landings)}")

if __name__ == "__main__":
    test_landing_detection()
