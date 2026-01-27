"""Configuration parameters for court detection

This file contains default parameters for mask generation and point detection.
Adjust these values to tune the detection performance for different court types.
"""

DEFAULT_CONFIG = {
    # ============================================================
    # Mask Generation Parameters
    # ============================================================
    'mask': {
        # Ensemble mode: 'conservative', 'moderate', or 'aggressive'
        'ensemble_mode': 'conservative',
        
        # HSV colorspace thresholds
        'hsv': {
            'conservative': {'s_max': 50, 'v_min': 180},
            'moderate': {'s_max': 70, 'v_min': 170},
            'aggressive': {'s_max': 90, 'v_min': 150},
        },
        
        # YCbCr colorspace thresholds
        'ycbcr': {
            'conservative': {'y_min': 200},
            'moderate': {'y_min': 190},
            'aggressive': {'y_min': 180},
        },
        
        # LAB colorspace thresholds
        'lab': {
            'conservative': {'l_min': 200},
            'moderate': {'l_min': 190},
            'aggressive': {'l_min': 180},
        },
        
        # Morphological operations
        'morph': {
            'open_kernel_size': 3,
            'close_kernel_size': 7,
            'min_component_area': 80,
        },
    },
    
    # ============================================================
    # Point Detection Parameters
    # ============================================================
    'detection': {
        # Bottom-up extraction
        'bottom_ratio': 0.25,           # Use bottom 25% for seed extraction
        'seed_y_bin': 10,               # Y-band size for seed extraction
        'seed_tolerance': 10.0,         # X-tolerance for seed points
        
        # Line extension
        'extend_dist_th': 8.0,          # Max distance from seed line
        'extend_x_tolerance': 15.0,     # X-tolerance when extending
        'continuity_th': 25.0,          # Max x-jump between y-bands
        'extend_y_bin': 15,             # Y-band size for extension
        
        # Noise filtering
        'k_neighbors': 12,              # Neighbors for linearity check
        'linearity_th': 4.0,            # Max residual for linearity
        
        # Final RANSAC
        'final_ransac_dist_th': 3.0,    # Distance threshold
        'final_ransac_iter': 500,       # RANSAC iterations
        
        # Horizontal removal
        'horiz_kernel_ratio': 0.25,     # Horizontal kernel as ratio of width
        'horiz_iter': 1,                # Morphological iterations
        'horiz_central_band_only': False,
        'horiz_band_y0_ratio': 0.40,
        'horiz_band_y1_ratio': 0.70,
    },
    
    # ============================================================
    # Endpoint Computation Parameters
    # ============================================================
    'endpoint': {
        'use_extrapolation': False,     # Extrapolate beyond detected points
        'top_margin': 0.02,             # Margin from top (2%)
        'bot_margin': 0.02,             # Margin from bottom (2%)
        'max_top_y_diff': 90.0,         # Max allowed TL.y - TR.y difference
    },
    
    # ============================================================
    # Visualization Parameters
    # ============================================================
    'visualization': {
        'save_intermediate': True,      # Save intermediate results
        'point_radius': 8,              # Radius for drawing points
        'line_thickness': 3,            # Thickness for drawing lines
    },
}


# ============================================================
# Preset Configurations for Different Court Types
# ============================================================

PRESETS = {
    # Professional indoor court (good lighting, clear lines)
    'pro_indoor': {
        'mask': {'ensemble_mode': 'conservative'},
        'endpoint': {'use_extrapolation': False},
    },
    
    # Amateur court (variable lighting, worn lines)
    'amateur': {
        'mask': {'ensemble_mode': 'moderate'},
        'endpoint': {'use_extrapolation': True},
    },
    
    # High-angle camera view
    'high_angle': {
        'mask': {'ensemble_mode': 'aggressive'},
        'detection': {'bottom_ratio': 0.30},
        'endpoint': {'use_extrapolation': True},
    },
    
    # Top-down view
    'top_view': {
        'mask': {'ensemble_mode': 'moderate'},
        'detection': {'bottom_ratio': 0.20},
        'endpoint': {'use_extrapolation': False},
    },
}


def get_config(preset: str = None) -> dict:
    """
    Get configuration with optional preset override.
    
    Args:
        preset: Preset name ('pro_indoor', 'amateur', 'high_angle', 'top_view')
        
    Returns:
        Configuration dictionary
    """
    config = DEFAULT_CONFIG.copy()
    
    if preset and preset in PRESETS:
        # Deep merge preset into config
        for section, params in PRESETS[preset].items():
            if section in config:
                config[section].update(params)
    
    return config
