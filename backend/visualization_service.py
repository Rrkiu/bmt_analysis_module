"""
시각화 서비스
이미지에 코트 영역, T자 가이드 등을 그리기
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
import base64


class VisualizationService:
    """시각화 서비스"""
    
    @staticmethod
    def draw_t_guide(
        image: np.ndarray,
        t_guide_coords: Dict,
        color: Tuple[int, int, int] = (0, 0, 255),
        thickness: int = 3
    ) -> np.ndarray:
        """
        T자 가이드 라인 그리기
        
        Args:
            image: 원본 이미지
            t_guide_coords: T자 좌표 정보
            color: 선 색상 (B, G, R)
            thickness: 선 두께
            
        Returns:
            그려진 이미지
        """
        img = image.copy()
        
        if not t_guide_coords.get('success'):
            return img
        
        t_guide = t_guide_coords['t_guide']
        
        # 세로선 (센터라인)
        if t_guide['vertical']['start'] and t_guide['vertical']['end']:
            start = tuple(map(int, t_guide['vertical']['start']))
            end = tuple(map(int, t_guide['vertical']['end']))
            cv2.line(img, start, end, color, thickness)
        
        # 가로선 (숏 서비스 라인)
        if t_guide['horizontal']['start'] and t_guide['horizontal']['end']:
            start = tuple(map(int, t_guide['horizontal']['start']))
            end = tuple(map(int, t_guide['horizontal']['end']))
            cv2.line(img, start, end, color, thickness)
        
        # T자 교차점에 원 그리기 (세로선의 시작점 = 가로선과의 교차점)
        if t_guide['vertical']['start']:
            intersection = tuple(map(int, t_guide['vertical']['start']))
            cv2.circle(img, intersection, 8, color, -1)
            cv2.circle(img, intersection, 12, (255, 255, 255), 2)
        
        return img
    
    @staticmethod
    def draw_court_region(
        image: np.ndarray,
        court_corners: List[List[float]],
        fill_color: Tuple[int, int, int] = (0, 255, 0),
        border_color: Tuple[int, int, int] = (0, 255, 255),
        alpha: float = 0.3,
        border_thickness: int = 3
    ) -> np.ndarray:
        """
        코트 영역 그리기
        
        Args:
            image: 원본 이미지
            court_corners: 코트 4개 코너 [[x,y], [x,y], [x,y], [x,y]]
            fill_color: 채우기 색상 (B, G, R)
            border_color: 경계선 색상
            alpha: 투명도 (0.0 ~ 1.0)
            border_thickness: 경계선 두께
            
        Returns:
            그려진 이미지
        """
        img = image.copy()
        overlay = image.copy()
        
        # 폴리곤 포인트 준비
        pts = np.array(court_corners, dtype=np.int32)
        
        # 반투명 채우기
        cv2.fillPoly(overlay, [pts], fill_color)
        img = cv2.addWeighted(img, 1 - alpha, overlay, alpha, 0)
        
        # 경계선 그리기
        cv2.polylines(img, [pts], isClosed=True, 
                     color=border_color, thickness=border_thickness)
        
        # 코너 포인트 그리기
        corner_colors = [
            (0, 255, 0),   # 좌상: Green
            (255, 0, 0),   # 우상: Blue
            (0, 0, 255),   # 우하: Red
            (255, 255, 0)  # 좌하: Cyan
        ]
        
        labels = ['TL', 'TR', 'BR', 'BL']
        
        for i, (corner, color, label) in enumerate(zip(court_corners, corner_colors, labels)):
            x, y = int(corner[0]), int(corner[1])
            
            # 외곽 원 (흰색)
            cv2.circle(img, (x, y), 12, (255, 255, 255), 2)
            # 내부 원 (색상)
            cv2.circle(img, (x, y), 8, color, -1)
            
            # 레이블
            cv2.putText(img, label, (x + 20, y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        return img
    
    @staticmethod
    def draw_complete_visualization(
        image: np.ndarray,
        calibration_result: Dict,
        t_guide_coords: Dict,
        show_t_guide: bool = True,
        show_court_region: bool = True
    ) -> np.ndarray:
        """
        전체 시각화 (T자 + 코트 영역)
        
        Args:
            image: 원본 이미지
            calibration_result: 캘리브레이션 결과
            t_guide_coords: T자 가이드 좌표
            show_t_guide: T자 가이드 표시 여부
            show_court_region: 코트 영역 표시 여부
            
        Returns:
            시각화된 이미지
        """
        img = image.copy()
        
        # 코트 영역 먼저 그리기 (배경)
        if show_court_region and calibration_result.get('success'):
            court_corners = calibration_result['court_corners_image']
            img = VisualizationService.draw_court_region(img, court_corners)
        
        # T자 가이드 위에 그리기
        if show_t_guide:
            img = VisualizationService.draw_t_guide(img, t_guide_coords)
        
        # 정보 텍스트 추가
        if calibration_result.get('success'):
            # 배경 박스
            cv2.rectangle(img, (10, 10), (400, 80), (0, 0, 0), -1)
            cv2.rectangle(img, (10, 10), (400, 80), (255, 255, 255), 2)
            
            # 텍스트
            cv2.putText(img, "Court Calibration Complete", (20, 35),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            pixels_per_meter = calibration_result.get('pixels_per_meter', 0)
            cv2.putText(img, f"Scale: {pixels_per_meter:.1f} pixels/meter", (20, 65),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        return img
    
    @staticmethod
    def create_guide_overlay_template(
        image_shape: Tuple[int, int],
        guide_position: str = 'center'
    ) -> np.ndarray:
        """
        프론트엔드용 T자 가이드 오버레이 템플릿 생성
        
        Args:
            image_shape: (height, width)
            guide_position: 'center' or custom position
            
        Returns:
            RGBA 오버레이 이미지 (투명 배경)
        """
        height, width = image_shape
        
        # RGBA 이미지 생성 (투명)
        overlay = np.zeros((height, width, 4), dtype=np.uint8)
        
        # T자 중심 위치 (네트 쪽, 상단 30%)
        center_x = width // 2
        center_y = int(height * 0.30)  # 상단 30% 위치 (네트 가까운 쪽)
        
        # T자 크기 (화면 크기에 비례)
        vertical_length = int(height * 0.20)   # 세로선 길이 (아래로)
        horizontal_length = int(width * 0.4)   # 가로선 길이
        
        # 색상 (빨강, BGRA)
        color = (0, 0, 255, 200)  # 반투명 빨강
        thickness = 4
        
        # 세로선 (센터라인) - T자 교차점에서 아래로
        start_v = (center_x, center_y)  # 교차점
        end_v = (center_x, center_y + vertical_length)  # 아래로
        cv2.line(overlay, start_v, end_v, color, thickness)
        
        # 가로선 (숏 서비스 라인)
        start_h = (center_x - horizontal_length // 2, center_y)
        end_h = (center_x + horizontal_length // 2, center_y)
        cv2.line(overlay, start_h, end_h, color, thickness)
        
        # 교차점
        cv2.circle(overlay, (center_x, center_y), 10, color, -1)
        cv2.circle(overlay, (center_x, center_y), 14, (255, 255, 255, 200), 2)
        
        return overlay
    
    @staticmethod
    def image_to_base64(image: np.ndarray, format: str = '.png') -> str:
        """
        이미지를 base64 문자열로 변환
        
        Args:
            image: OpenCV 이미지
            format: 이미지 포맷 ('.png', '.jpg')
            
        Returns:
            base64 인코딩된 문자열
        """
        _, buffer = cv2.imencode(format, image)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/{format[1:]};base64,{img_base64}"
    
    @staticmethod
    def base64_to_image(base64_string: str) -> Optional[np.ndarray]:
        """
        base64 문자열을 이미지로 변환
        
        Args:
            base64_string: base64 인코딩된 이미지 문자열
            
        Returns:
            OpenCV 이미지 또는 None
        """
        try:
            # data:image/png;base64, 제거
            if ',' in base64_string:
                base64_string = base64_string.split(',')[1]
            
            # 디코딩
            img_data = base64.b64decode(base64_string)
            nparr = np.frombuffer(img_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            return image
        except Exception as e:
            print(f"Base64 to image conversion error: {e}")
            return None

    @staticmethod
    def draw_minimap(
        image: np.ndarray,
        world_point: Optional[Tuple[float, float]] = None,
        is_in_court: bool = True,
        position: Tuple[int, int] = (1000, 50),
        size: Tuple[int, int] = (200, 260) # w, h
    ) -> np.ndarray:
        """
        우상단 미니맵 그리기
        
        Args:
            image: 원본 이미지
            world_point: (x, y) 실세계 좌표 (미터)
            is_in_court: 코트 내 여부
            position: 미니맵 좌상단 위치
            size: 미니맵 크기
        """
        img = image.copy()
        from constants import CourtDimensions
        
        mx, my = position
        mw, mh = size
        
        # 미니맵 배경 (반투명 어두운 회색)
        overlay = img.copy()
        cv2.rectangle(overlay, (mx - 10, my - 10), (mx + mw + 10, my + mh + 40), (40, 40, 40), -1)
        img = cv2.addWeighted(img, 0.7, overlay, 0.3, 0)
        cv2.rectangle(img, (mx - 10, my - 10), (mx + mw + 10, my + mh + 40), (200, 200, 200), 2)
        
        # 코트 외곽선 그리기
        # 실세계 좌표 (-2.59, 0) ~ (2.59, 6.7)을 미니맵 (0, 0) ~ (mw, mh)로 변환
        def world_to_mini(wx, wy):
            # wx: -2.59 ~ 2.59 -> 0 ~ mw
            # wy: 0 ~ 6.7 -> 0 ~ mh
            mini_x = int(mx + (wx + 2.59) / 5.18 * mw)
            mini_y = int(my + wy / 6.7 * mh)
            return (mini_x, mini_y)
        
        # 코트 사각형
        p1 = world_to_mini(-2.59, 0)
        p2 = world_to_mini(2.59, 0)
        p3 = world_to_mini(2.59, 6.7)
        p4 = world_to_mini(-2.59, 6.7)
        pts = np.array([p1, p2, p3, p4], dtype=np.int32)
        cv2.polylines(img, [pts], True, (255, 255, 255), 2)
        
        # 숏 서비스 라인 (1.98m)
        ss1 = world_to_mini(-2.59, 1.98)
        ss2 = world_to_mini(2.59, 1.98)
        cv2.line(img, ss1, ss2, (200, 200, 200), 1)
        
        # 센터 라인 (1.98m ~ 6.7m)
        cl1 = world_to_mini(0, 1.98)
        cl2 = world_to_mini(0, 6.7)
        cv2.line(img, cl1, cl2, (200, 200, 200), 1)
        
        # 낙하 지점 표시
        if world_point:
            px, py = world_to_mini(world_point[0], world_point[1])
            color = (0, 255, 0) if is_in_court else (0, 0, 255)
            cv2.circle(img, (px, py), 6, color, -1)
            cv2.circle(img, (px, py), 8, (255, 255, 255), 1)
            
            # 텍스트 표시
            status_text = "IN" if is_in_court else "OUT"
            cv2.putText(img, f"POS: {world_point[0]:.2f}, {world_point[1]:.2f}", (mx, my + mh + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(img, f"RESULT: {status_text}", (mx, my + mh + 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        return img