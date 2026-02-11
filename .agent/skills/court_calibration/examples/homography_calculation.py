#!/usr/bin/env python3
"""
Homography Calculation Example

Demonstrates how to compute and use homography transformation
for badminton court calibration.
"""

import numpy as np
import cv2
from typing import Tuple, List


class HomographyExample:
    """Example implementation of homography transformation"""
    
    # BWF Official Court Dimensions (meters)
    SINGLES_WIDTH = 5.18
    COURT_HALF_LENGTH = 6.7
    
    def __init__(self):
        self.H = None  # Homography matrix (image → world)
        self.H_inv = None  # Inverse homography (world → image)
    
    def compute_from_corners(
        self,
        image_corners: List[Tuple[float, float]],
        court_type: str = 'singles'
    ) -> bool:
        """
        Compute homography from 4 image corners
        
        Args:
            image_corners: [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
                          Order: TL, TR, BR, BL
            court_type: 'singles' or 'doubles'
        
        Returns:
            Success status
        """
        # Define real-world court corners (meters)
        # Origin: Center of net
        # X-axis: Left (-) to Right (+)
        # Y-axis: Net (0) to Back boundary (+)
        
        width = self.SINGLES_WIDTH if court_type == 'singles' else 6.1
        half_width = width / 2
        
        world_corners = np.array([
            [-half_width, 0],                      # Top-left
            [half_width, 0],                       # Top-right
            [half_width, self.COURT_HALF_LENGTH],  # Bottom-right
            [-half_width, self.COURT_HALF_LENGTH]  # Bottom-left
        ], dtype=np.float32)
        
        image_corners_np = np.array(image_corners, dtype=np.float32)
        
        # Compute homography
        self.H, _ = cv2.findHomography(
            image_corners_np,
            world_corners,
            cv2.RANSAC,
            ransacReprojThreshold=5.0
        )
        
        if self.H is None:
            return False
        
        # Compute inverse
        self.H_inv = np.linalg.inv(self.H)
        
        return True
    
    def image_to_world(self, point: Tuple[float, float]) -> Tuple[float, float]:
        """Transform image pixel to world coordinates (meters)"""
        if self.H is None:
            raise ValueError("Homography not computed yet")
        
        pt = np.array([[point]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, self.H)
        
        return (float(transformed[0][0][0]), float(transformed[0][0][1]))
    
    def world_to_image(self, point: Tuple[float, float]) -> Tuple[float, float]:
        """Transform world coordinates (meters) to image pixels"""
        if self.H_inv is None:
            raise ValueError("Homography not computed yet")
        
        pt = np.array([[point]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, self.H_inv)
        
        return (float(transformed[0][0][0]), float(transformed[0][0][1]))
    
    def is_in_court(self, world_point: Tuple[float, float], margin: float = 0.0) -> bool:
        """Check if point is within court boundaries"""
        x, y = world_point
        half_width = self.SINGLES_WIDTH / 2
        
        in_x = (-half_width - margin) <= x <= (half_width + margin)
        in_y = (0 - margin) <= y <= (self.COURT_HALF_LENGTH + margin)
        
        return in_x and in_y


def example_usage():
    """Example usage of homography transformation"""
    
    print("=" * 60)
    print("Homography Transformation Example")
    print("=" * 60)
    
    # Example: User clicked 4 corners on a 1920x1080 image
    image_corners = [
        (245, 120),   # Top-left
        (1675, 118),  # Top-right
        (1720, 960),  # Bottom-right
        (200, 962)    # Bottom-left
    ]
    
    print("\n1. Image Corners (pixels):")
    for i, corner in enumerate(image_corners):
        labels = ['TL', 'TR', 'BR', 'BL']
        print(f"   {labels[i]}: {corner}")
    
    # Compute homography
    homography = HomographyExample()
    success = homography.compute_from_corners(image_corners, court_type='singles')
    
    if not success:
        print("\n❌ Failed to compute homography")
        return
    
    print("\n✓ Homography computed successfully")
    print(f"\nHomography Matrix:")
    print(homography.H)
    
    # Example: Transform shuttlecock detection to world coordinates
    print("\n2. Shuttlecock Detection → World Coordinates:")
    
    detections = [
        (960, 540, "Center of image"),
        (1200, 300, "Right side, near net"),
        (800, 800, "Left side, back court")
    ]
    
    for pixel_x, pixel_y, description in detections:
        world_x, world_y = homography.image_to_world((pixel_x, pixel_y))
        is_in = homography.is_in_court((world_x, world_y))
        
        print(f"\n   Detection: {description}")
        print(f"   Image: ({pixel_x}, {pixel_y}) px")
        print(f"   World: ({world_x:.2f}, {world_y:.2f}) m")
        print(f"   In Court: {'✓ Yes' if is_in else '✗ No'}")
    
    # Example: Transform court positions to image for minimap
    print("\n3. World Coordinates → Image (for minimap):")
    
    court_positions = [
        (0, 0, "Net center"),
        (0, 6.7, "Back boundary center"),
        (2.59, 3.35, "Right corner, mid-court"),
        (-2.59, 1.98, "Left service line")
    ]
    
    for world_x, world_y, description in court_positions:
        pixel_x, pixel_y = homography.world_to_image((world_x, world_y))
        
        print(f"\n   Position: {description}")
        print(f"   World: ({world_x:.2f}, {world_y:.2f}) m")
        print(f"   Image: ({pixel_x:.0f}, {pixel_y:.0f}) px")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    example_usage()
