import cv2
import numpy as np
import os

def concat_videos_h():
    video1_path = "match2_rebuilt.mp4"
    video2_path = "m3_hhss.mp4"
    output_path = "result_hconcat.mp4"
    
    cap1 = cv2.VideoCapture(video1_path)
    cap2 = cv2.VideoCapture(video2_path)
    
    if not cap1.isOpened() or not cap2.isOpened():
        print("Error: Could not open one of the videos.")
        return
    
    # Get properties
    fps1 = cap1.get(cv2.CAP_PROP_FPS)
    w1 = int(cap1.get(cv2.CAP_PROP_FRAME_WIDTH))
    h1 = int(cap1.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    fps2 = cap2.get(cv2.CAP_PROP_FPS)
    w2 = int(cap2.get(cv2.CAP_PROP_FRAME_WIDTH))
    h2 = int(cap2.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Target height (minimum of the two or fixed 720)
    target_h = min(h1, h2)
    # Scale widths to maintain aspect ratio with target_h
    new_w1 = int(w1 * (target_h / h1))
    new_w2 = int(w2 * (target_h / h2))
    
    # Final width
    final_w = new_w1 + new_w2
    final_h = target_h
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps1, (final_w, final_h))
    
    print(f"Concatenating {video1_path} and {video2_path}...")
    print(f"Output resolution: {final_w}x{final_h}")
    
    while True:
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()
        
        if not ret1 or not ret2:
            break
            
        # Resize frames to match target height
        frame1_resized = cv2.resize(frame1, (new_w1, target_h))
        frame2_resized = cv2.resize(frame2, (new_w2, target_h))
        
        # Horizontal concatenation
        combined = np.hstack((frame1_resized, frame2_resized))
        out.write(combined)
        
    cap1.release()
    cap2.release()
    out.release()
    print(f"Done! Result saved to {output_path}")

if __name__ == "__main__":
    concat_videos_h()
