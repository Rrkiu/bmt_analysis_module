"""
Visualization Utilities

검출 결과를 시각화하는 유틸리티 함수들입니다.
"""

from typing import List, Tuple, Optional
import numpy as np
import cv2

from ..models.base_detector import Detection


def draw_detections(
    frame: np.ndarray,
    detections: List[Detection],
    color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
    show_confidence: bool = True,
    font_scale: float = 0.5,
) -> np.ndarray:
    """
    프레임에 검출 결과를 그립니다.
    
    Args:
        frame: 원본 이미지
        detections: 검출 결과 리스트
        color: 바운딩 박스 색상 (BGR)
        thickness: 선 두께
        show_confidence: 신뢰도 표시 여부
        font_scale: 폰트 크기
        
    Returns:
        시각화된 이미지
    """
    vis_frame = frame.copy()
    
    for det in detections:
        # 바운딩 박스 그리기
        x1, y1, x2, y2 = map(int, det.bbox)
        cv2.rectangle(vis_frame, (x1, y1), (x2, y2), color, thickness)
        
        # 중심점 그리기
        center = (int(det.x), int(det.y))
        cv2.circle(vis_frame, center, 3, color, -1)
        
        # 신뢰도 표시
        if show_confidence:
            label = f"{det.confidence:.2f}"
            label_size, _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1
            )
            
            # 텍스트 배경
            cv2.rectangle(
                vis_frame,
                (x1, y1 - label_size[1] - 4),
                (x1 + label_size[0], y1),
                color,
                -1
            )
            
            # 텍스트
            cv2.putText(
                vis_frame,
                label,
                (x1, y1 - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (255, 255, 255),
                1
            )
    
    return vis_frame


def draw_trajectory(
    frame: np.ndarray,
    trajectory: List[Tuple[float, float]],
    color: Tuple[int, int, int] = (255, 0, 0),
    thickness: int = 2,
    max_length: Optional[int] = None,
) -> np.ndarray:
    """
    프레임에 궤적을 그립니다.
    
    Args:
        frame: 원본 이미지
        trajectory: 궤적 포인트 리스트 [(x, y), ...]
        color: 궤적 색상 (BGR)
        thickness: 선 두께
        max_length: 표시할 최대 궤적 길이
        
    Returns:
        시각화된 이미지
    """
    vis_frame = frame.copy()
    
    if len(trajectory) < 2:
        return vis_frame
    
    # 최근 궤적만 표시
    if max_length is not None:
        trajectory = trajectory[-max_length:]
    
    # 궤적 그리기
    points = np.array(trajectory, dtype=np.int32)
    cv2.polylines(vis_frame, [points], False, color, thickness)
    
    # 시작점과 끝점 강조
    if len(points) > 0:
        # 시작점 (작은 원)
        cv2.circle(vis_frame, tuple(points[0]), 3, color, -1)
        
        # 끝점 (큰 원)
        cv2.circle(vis_frame, tuple(points[-1]), 5, color, -1)
    
    return vis_frame


def create_heatmap(
    detections_history: List[List[Detection]],
    frame_shape: Tuple[int, int],
    colormap: int = cv2.COLORMAP_JET,
) -> np.ndarray:
    """
    검출 히스토리로부터 히트맵을 생성합니다.
    
    Args:
        detections_history: 프레임별 검출 결과 리스트
        frame_shape: 프레임 크기 (height, width)
        colormap: OpenCV 컬러맵
        
    Returns:
        히트맵 이미지
    """
    height, width = frame_shape
    heatmap = np.zeros((height, width), dtype=np.float32)
    
    # 모든 검출 위치를 히트맵에 누적
    for detections in detections_history:
        for det in detections:
            x, y = int(det.x), int(det.y)
            if 0 <= x < width and 0 <= y < height:
                # 가우시안 분포로 히트 추가
                cv2.circle(heatmap, (x, y), 10, 1.0, -1)
    
    # 정규화
    if heatmap.max() > 0:
        heatmap = (heatmap / heatmap.max() * 255).astype(np.uint8)
    else:
        heatmap = heatmap.astype(np.uint8)
    
    # 컬러맵 적용
    heatmap_colored = cv2.applyColorMap(heatmap, colormap)
    
    return heatmap_colored


def overlay_heatmap(
    frame: np.ndarray,
    heatmap: np.ndarray,
    alpha: float = 0.5,
) -> np.ndarray:
    """
    프레임에 히트맵을 오버레이합니다.
    
    Args:
        frame: 원본 이미지
        heatmap: 히트맵 이미지
        alpha: 히트맵 투명도 (0~1)
        
    Returns:
        오버레이된 이미지
    """
    return cv2.addWeighted(frame, 1 - alpha, heatmap, alpha, 0)
