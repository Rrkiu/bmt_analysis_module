import cv2
import numpy as np
import json
import os
from geometry import HomographyTransform
from constants import COURT_TEMPLATE

def test_calibration_with_profile():
    # profile_1765956553 data from DB check
    corners_image = [
        [464.897391116592, 498.8563310053509],  # TL
        [910.0957402367183, 501.4772925342629], # TR
        [1276.4979213709814, 717.706618669503], # BR
        [101.12174891519092, 713.7751763761349]  # BL
    ]
    
    # Official world coords from constants
    user_court = COURT_TEMPLATE['user_court']
    corners_world = [
        user_court['top_left'],
        user_court['top_right'],
        user_court['bottom_right'],
        user_court['bottom_left']
    ]
    
    print("Corners Image:", corners_image)
    print("Corners World:", corners_world)
    
    # Compute Calibration using modified service
    from calibration_service import CalibrationService
    cs = CalibrationService()
    result = cs.calibrate_from_corners(
        court_corners_image=corners_image,
        image_shape=(720, 1280)
    )
    
    print(f"Calibration success: {result['success']}")
    if result['success']:
        print("Homography Matrix:")
        h_matrix = np.array(result['homography_matrix'])
        print(h_matrix)
        
        # Initialize transformation with the calculated matrix
        ht = HomographyTransform()
        ht.homography_matrix = h_matrix
        ht.inv_homography_matrix = np.linalg.inv(h_matrix)
        
        # Test back-projection
        print("\nBack-projection Test (World -> Image):")
        for i, world_pt in enumerate(corners_world):
            img_pt = ht.world_to_image(tuple(world_pt))
            print(f"World {world_pt} -> Predicted Image {img_pt}, Actual {corners_image[i]}")
            
        # Re-projection error
        error = ht.get_reprojection_error(
            np.array(corners_image, dtype=np.float32),
            np.array(corners_world, dtype=np.float32)
        )
        print(f"\nMean Reprojection Error: {error:.4f} pixels")
        
        # Visualization
        ref_image_path = "/mnt/b/cd_p/bmt_demo/storage/calibrations/profile_1765956553/reference.jpg"
        if os.path.exists(ref_image_path):
            img = cv2.imread(ref_image_path)
            
            # Draw original corners
            for pt in corners_image:
                cv2.circle(img, (int(pt[0]), int(pt[1])), 10, (0, 0, 255), -1)
                
            # Draw court lines using Homography
            # Center line
            cl_start = ht.world_to_image((0, 0))
            cl_end = ht.world_to_image((0, 6.7))
            if cl_start and cl_end:
                cv2.line(img, (int(cl_start[0]), int(cl_start[1])), (int(cl_end[0]), int(cl_end[1])), (0, 255, 0), 2)
                
            # Short service line
            ss_left = ht.world_to_image((-2.59, 1.98))
            ss_right = ht.world_to_image((2.59, 1.98))
            if ss_left and ss_right:
                cv2.line(img, (int(ss_left[0]), int(ss_left[1])), (int(ss_right[0]), int(ss_right[1])), (255, 255, 0), 2)
                
            output_path = "/mnt/b/cd_p/bmt_demo/backend/storage/test_calibration_profile.jpg"
            cv2.imwrite(output_path, img)
            print(f"Visualization saved to {output_path}")

if __name__ == "__main__":
    test_calibration_with_profile()
