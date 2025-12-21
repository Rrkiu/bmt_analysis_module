import cv2
import numpy as np
from pathlib import Path

def extend_video_with_last_frame(input_path: str, output_path: str, target_duration: float = 15.0):
    """
    영상의 마지막 프레임을 반복하여 목표 길이로 확장
    
    Args:
        input_path: 입력 영상 경로 (절대경로)
        output_path: 출력 영상 경로 (절대경로)
        target_duration: 목표 영상 길이 (초), 기본값 15초
    """
    # 입력 영상 열기
    cap = cv2.VideoCapture(input_path)
    
    if not cap.isOpened():
        raise ValueError(f"영상을 열 수 없습니다: {input_path}")
    
    # 영상 정보 추출
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    original_duration = total_frames / fps
    
    print(f"원본 영상 정보:")
    print(f"  - 해상도: {width}x{height}")
    print(f"  - FPS: {fps}")
    print(f"  - 총 프레임 수: {total_frames}")
    print(f"  - 재생 시간: {original_duration:.2f}초")
    
    # VideoWriter 설정
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # 또는 'avc1', 'XVID' 등
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    if not out.isOpened():
        cap.release()
        raise ValueError(f"출력 영상을 생성할 수 없습니다: {output_path}")
    
    # 모든 프레임 읽기 및 쓰기
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
        out.write(frame)
    
    cap.release()
    
    if len(frames) == 0:
        out.release()
        raise ValueError("영상에서 프레임을 읽을 수 없습니다")
    
    # 마지막 프레임 가져오기
    last_frame = frames[-1]
    
    # 추가로 필요한 프레임 수 계산
    additional_frames_needed = int((target_duration - original_duration) * fps)
    
    print(f"\n확장 정보:")
    print(f"  - 목표 길이: {target_duration}초")
    print(f"  - 추가 프레임 수: {additional_frames_needed}")
    
    # 마지막 프레임 반복 쓰기
    for i in range(additional_frames_needed):
        out.write(last_frame)
        if (i + 1) % 30 == 0:  # 30프레임마다 진행상황 출력
            print(f"  진행: {i + 1}/{additional_frames_needed} 프레임 추가됨")
    
    out.release()
    
    final_frames = total_frames + additional_frames_needed
    final_duration = final_frames / fps
    
    print(f"\n완료!")
    print(f"  - 최종 프레임 수: {final_frames}")
    print(f"  - 최종 재생 시간: {final_duration:.2f}초")
    print(f"  - 저장 경로: {output_path}")


if __name__ == "__main__":
    # 여기에 절대경로를 직접 입력하세요
    INPUT_VIDEO = "/mnt/b/cd_p/bmt_demo/_adutils/match2_rebuilt.mp4"  # 입력 영상 경로
    OUTPUT_VIDEO = "/mnt/b/cd_p/bmt_demo/_adutils/match2_rebuilt_extend.mp4"  # 출력 영상 경로
    
    try:
        extend_video_with_last_frame(INPUT_VIDEO, OUTPUT_VIDEO, target_duration=15.0)
    except Exception as e:
        print(f"오류 발생: {e}")