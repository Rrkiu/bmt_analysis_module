"""Court Overlay Renderer

Renders court lines on original image using inverse homography transformation.
Takes world coordinates from CourtLineGenerator and transforms them to image coordinates.
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from modules.calibration.geometry import HomographyTransform
from .line_generator import CourtLineGenerator


class CourtOverlayRenderer:
    """
    Render court lines on original image using homography transformation.
    
    This class takes world coordinates (meters) and transforms them to image
    coordinates (pixels) using the inverse homography matrix, then draws
    the lines on the image.
    
    Example:
        >>> renderer = CourtOverlayRenderer(homography_matrix)
        >>> lines = generator.generate_all_lines()
        >>> overlay_img = renderer.render(original_img, lines)
    """
    
    def __init__(self, homography_matrix: np.ndarray):
        """
        Initialize renderer with homography matrix.
        
        Args:
            homography_matrix: 3x3 homography matrix (image -> world)
        """
        self.ht = HomographyTransform()
        self.ht.homography_matrix = np.array(homography_matrix, dtype=np.float32)
        
        # Compute inverse for world -> image transformation
        try:
            self.ht.inv_homography_matrix = np.linalg.inv(self.ht.homography_matrix)
        except np.linalg.LinAlgError:
            raise ValueError("Homography matrix is singular and cannot be inverted")
    
    def world_to_image(self, world_point: Tuple[float, float]) -> Tuple[int, int]:
        """
        Transform world coordinates to image coordinates.
        
        Args:
            world_point: (x, y) in meters
            
        Returns:
            (x, y) in pixels
        """
        img_point = self.ht.world_to_image(world_point)
        if img_point is None:
            raise ValueError(f"Failed to transform point: {world_point}")
        
        return (int(round(img_point[0])), int(round(img_point[1])))
    
    def transform_line(self, world_line: List[Tuple[float, float]]) -> List[Tuple[int, int]]:
        """
        Transform a line from world to image coordinates.
        
        Args:
            world_line: List of (x, y) points in meters
            
        Returns:
            List of (x, y) points in pixels
        """
        return [self.world_to_image(pt) for pt in world_line]
    
    def render(
        self,
        image: np.ndarray,
        world_lines: Dict[str, List[Tuple[float, float]]],
        styles: Optional[Dict[str, Dict[str, Any]]] = None,
        alpha: float = 1.0,
        draw_corners: bool = True,
        detected_corners: Optional[Dict[str, List[float]]] = None
    ) -> np.ndarray:
        """
        Render court lines on image.
        
        Args:
            image: Original BGR image
            world_lines: Dictionary of line names to world coordinate points
            styles: Optional custom styles (if None, uses default from CourtLineGenerator)
            alpha: Transparency (0.0 = transparent, 1.0 = opaque)
            draw_corners: Whether to draw corner markers
            
        Returns:
            Image with court lines overlaid
        """
        # Create copy for overlay
        overlay = image.copy()
        
        # Get default styles if not provided
        if styles is None:
            generator = CourtLineGenerator()
            styles = generator.get_line_styles()
        
        # Draw each line
        for line_name, world_points in world_lines.items():
            if line_name not in styles:
                continue
            
            style = styles[line_name]
            
            try:
                # Transform to image coordinates
                image_points = self.transform_line(world_points)
                
                # Draw line
                self._draw_line(
                    overlay,
                    image_points,
                    color=style.get('color', (255, 255, 255)),
                    thickness=style.get('thickness', 2),
                    line_type=style.get('line_type', 'solid')
                )
                
            except Exception as e:
                print(f"Warning: Failed to draw {line_name}: {e}")
                continue
        
        # Draw corner markers if requested
        if draw_corners and detected_corners is not None:
            # Use detected corners (original image coordinates)
            corner_order = ['TL', 'TR', 'BR', 'BL']
            for i, corner_name in enumerate(corner_order):
                if corner_name in detected_corners:
                    try:
                        corner_pt = detected_corners[corner_name]
                        img_pt = (int(round(corner_pt[0])), int(round(corner_pt[1])))
                        self._draw_corner_marker(overlay, img_pt, i)
                    except Exception as e:
                        print(f"Warning: Failed to draw corner {corner_name}: {e}")
        
        # Blend with original if alpha < 1.0
        if alpha < 1.0:
            result = cv2.addWeighted(image, 1 - alpha, overlay, alpha, 0)
        else:
            result = overlay
        
        return result
    
    def _draw_line(
        self,
        image: np.ndarray,
        points: List[Tuple[int, int]],
        color: Tuple[int, int, int],
        thickness: int,
        line_type: str
    ):
        """
        Draw a line on image.
        
        Args:
            image: Image to draw on
            points: List of (x, y) pixel coordinates
            color: BGR color tuple
            thickness: Line thickness
            line_type: 'solid' or 'dashed'
        """
        if len(points) < 2:
            return
        
        if line_type == 'dashed':
            # Draw dashed line
            self._draw_dashed_line(image, points, color, thickness)
        else:
            # Draw solid line
            if len(points) == 2:
                # Simple line
                cv2.line(image, points[0], points[1], color, thickness, cv2.LINE_AA)
            else:
                # Polyline
                pts_array = np.array(points, dtype=np.int32)
                is_closed = (points[0] == points[-1])
                cv2.polylines(image, [pts_array], is_closed, color, thickness, cv2.LINE_AA)
    
    def _draw_dashed_line(
        self,
        image: np.ndarray,
        points: List[Tuple[int, int]],
        color: Tuple[int, int, int],
        thickness: int,
        dash_length: int = 10,
        gap_length: int = 5
    ):
        """
        Draw dashed line.
        
        Args:
            image: Image to draw on
            points: List of (x, y) pixel coordinates
            color: BGR color tuple
            thickness: Line thickness
            dash_length: Length of each dash in pixels
            gap_length: Length of gap between dashes in pixels
        """
        for i in range(len(points) - 1):
            pt1 = np.array(points[i], dtype=np.float32)
            pt2 = np.array(points[i + 1], dtype=np.float32)
            
            # Calculate line vector and length
            vec = pt2 - pt1
            length = np.linalg.norm(vec)
            
            if length < 1:
                continue
            
            # Unit vector
            unit_vec = vec / length
            
            # Draw dashes
            current_pos = 0
            while current_pos < length:
                # Dash start
                start = pt1 + unit_vec * current_pos
                
                # Dash end
                end_pos = min(current_pos + dash_length, length)
                end = pt1 + unit_vec * end_pos
                
                # Draw dash
                cv2.line(
                    image,
                    (int(start[0]), int(start[1])),
                    (int(end[0]), int(end[1])),
                    color,
                    thickness,
                    cv2.LINE_AA
                )
                
                # Move to next dash
                current_pos += dash_length + gap_length
    
    def _draw_corner_marker(
        self,
        image: np.ndarray,
        point: Tuple[int, int],
        corner_index: int
    ):
        """
        Draw corner marker with label.
        
        Args:
            image: Image to draw on
            point: (x, y) pixel coordinate
            corner_index: 0=TL, 1=TR, 2=BR, 3=BL
        """
        labels = ['TL', 'TR', 'BR', 'BL']
        colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (255, 255, 0)]  # Red, Green, Blue, Yellow
        
        label = labels[corner_index]
        color = colors[corner_index]
        
        # Draw circle
        cv2.circle(image, point, 8, color, -1, cv2.LINE_AA)
        cv2.circle(image, point, 10, (255, 255, 255), 2, cv2.LINE_AA)
        
        # Draw label
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        font_thickness = 2
        
        # Get text size for background
        (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, font_thickness)
        
        # Text position (offset from corner)
        text_x = point[0] + 15
        text_y = point[1] - 15
        
        # Draw background rectangle
        cv2.rectangle(
            image,
            (text_x - 2, text_y - text_height - 2),
            (text_x + text_width + 2, text_y + baseline + 2),
            (0, 0, 0),
            -1
        )
        
        # Draw text
        cv2.putText(
            image,
            label,
            (text_x, text_y),
            font,
            font_scale,
            color,
            font_thickness,
            cv2.LINE_AA
        )
    
    def render_with_info(
        self,
        image: np.ndarray,
        world_lines: Dict[str, List[Tuple[float, float]]],
        calibration_info: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> np.ndarray:
        """
        Render court lines with additional calibration info overlay.
        
        Args:
            image: Original BGR image
            world_lines: Dictionary of line names to world coordinate points
            calibration_info: Optional calibration metadata to display
            **kwargs: Additional arguments for render()
            
        Returns:
            Image with court lines and info overlaid
        """
        # Render lines
        result = self.render(image, world_lines, **kwargs)
        
        # Add info text if provided
        if calibration_info:
            self._draw_info_panel(result, calibration_info)
        
        return result
    
    def _draw_info_panel(
        self,
        image: np.ndarray,
        info: Dict[str, Any]
    ):
        """
        Draw information panel on image.
        
        Args:
            image: Image to draw on
            info: Dictionary with calibration information
        """
        H, W = image.shape[:2]
        
        # Panel position (top-left)
        panel_x = 10
        panel_y = 10
        line_height = 25
        
        # Info lines
        lines = []
        if 'pixels_per_meter' in info:
            lines.append(f"Pixels/meter: {info['pixels_per_meter']:.2f}")
        if 'detection_metadata' in info:
            meta = info['detection_metadata']
            if 'mask_coverage_ratio' in meta:
                lines.append(f"Mask coverage: {meta['mask_coverage_ratio']:.2%}")
        
        if not lines:
            return
        
        # Draw background
        panel_width = 250
        panel_height = len(lines) * line_height + 20
        
        overlay = image.copy()
        cv2.rectangle(
            overlay,
            (panel_x, panel_y),
            (panel_x + panel_width, panel_y + panel_height),
            (40, 40, 40),
            -1
        )
        cv2.addWeighted(overlay, 0.7, image, 0.3, 0, image)
        
        # Draw border
        cv2.rectangle(
            image,
            (panel_x, panel_y),
            (panel_x + panel_width, panel_y + panel_height),
            (200, 200, 200),
            2
        )
        
        # Draw text
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        font_thickness = 1
        
        for i, line in enumerate(lines):
            text_y = panel_y + 20 + i * line_height
            cv2.putText(
                image,
                line,
                (panel_x + 10, text_y),
                font,
                font_scale,
                (255, 255, 255),
                font_thickness,
                cv2.LINE_AA
            )


# Convenience function
def render_court_overlay(
    image: np.ndarray,
    homography_matrix: np.ndarray,
    court_type: str = 'singles',
    include_net: bool = True,
    alpha: float = 1.0,
    draw_corners: bool = True
) -> np.ndarray:
    """
    Convenience function to render court overlay.
    
    Args:
        image: Original BGR image
        homography_matrix: 3x3 homography matrix
        court_type: 'singles' or 'doubles'
        include_net: Whether to include net line
        alpha: Transparency (0.0 = transparent, 1.0 = opaque)
        draw_corners: Whether to draw corner markers
        
    Returns:
        Image with court lines overlaid
        
    Example:
        >>> overlay_img = render_court_overlay(img, h_matrix)
    """
    # Generate lines
    generator = CourtLineGenerator(court_type=court_type)
    world_lines = generator.generate_all_lines(include_net=include_net)
    styles = generator.get_line_styles()
    
    # Render
    renderer = CourtOverlayRenderer(homography_matrix)
    return renderer.render(image, world_lines, styles, alpha, draw_corners)


if __name__ == "__main__":
    print("=" * 70)
    print("Court Overlay Renderer Test")
    print("=" * 70)
    print("\nThis module requires:")
    print("  1. An image")
    print("  2. A homography matrix")
    print("  3. World coordinate lines")
    print("\nUse test_milestone3.py for full integration test.")
    print("=" * 70)
