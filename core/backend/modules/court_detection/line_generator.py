"""Court Line Generator - Full Court Support

Generates all badminton court lines in world coordinates based on BWF specifications.
Supports FULL COURT (both sides) with vibrant color coding.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from constants import CourtDimensions


class CourtLineGenerator:
    """
    Generate all badminton court lines in world coordinates for FULL COURT.
    
    The coordinate system:
    - Origin (0, 0) at net center
    - X-axis: left (-) to right (+)
    - Y-axis: opponent baseline (-6.7m) → net (0) → player baseline (+6.7m)
    - Units: meters
    
    Supports both singles and doubles court lines with distinct colors.
    """
    
    def __init__(self, court_type: str = 'singles'):
        """
        Initialize court line generator for FULL COURT.
        
        Args:
            court_type: 'singles' or 'doubles'
        """
        if court_type not in ['singles', 'doubles']:
            raise ValueError(f"Invalid court_type: {court_type}. Must be 'singles' or 'doubles'")
        
        self.court_type = court_type
        self.dims = CourtDimensions()
        
        # Court dimensions
        self.singles_width = self.dims.SINGLES_WIDTH
        self.doubles_width = self.dims.DOUBLES_WIDTH
        self.singles_half_width = self.singles_width / 2
        self.doubles_half_width = self.doubles_width / 2
        
        # Full court length (both sides)
        self.half_length = self.dims.BACK_BOUNDARY_LINE  # 6.7m (one side)
        self.total_length = self.dims.TOTAL_LENGTH  # 13.4m (both sides)
        
        self.short_service = self.dims.SHORT_SERVICE_LINE  # 1.98m
        self.long_service_doubles = self.dims.LONG_SERVICE_LINE_DOUBLES  # 0.76m
    
    def generate_all_lines(self, include_net: bool = True, include_doubles: bool = True) -> Dict[str, List[Tuple[float, float]]]:
        """
        Generate all court lines for FULL COURT (both sides).
        
        Args:
            include_net: Whether to include net line
            include_doubles: Whether to include doubles sidelines
            
        Returns:
            Dictionary with line names as keys and list of (x, y) points as values
        """
        lines = {}
        
        # 1. Outer boundary (full court)
        if include_doubles:
            lines['outer_boundary'] = self._generate_doubles_boundary()
        else:
            lines['outer_boundary'] = self._generate_singles_boundary()
        
        # 2. Net line (center of court)
        if include_net:
            lines['net_line'] = self._generate_net_line(use_doubles=include_doubles)
        
        # 3. Center lines (both sides)
        lines['center_line_player'] = self._generate_center_line_player()
        lines['center_line_opponent'] = self._generate_center_line_opponent()
        
        # 4. Short service lines (both sides)
        lines['short_service_line_player'] = self._generate_short_service_line_player(use_doubles=include_doubles)
        lines['short_service_line_opponent'] = self._generate_short_service_line_opponent(use_doubles=include_doubles)
        
        # 5. Singles sidelines (both sides)
        lines['singles_sideline_left'] = self._generate_singles_left_sideline()
        lines['singles_sideline_right'] = self._generate_singles_right_sideline()
        
        # 6. Doubles sidelines (both sides)
        if include_doubles:
            lines['doubles_sideline_left'] = self._generate_doubles_left_sideline()
            lines['doubles_sideline_right'] = self._generate_doubles_right_sideline()
        
        # 7. Baselines (both sides)
        lines['baseline_player'] = self._generate_baseline_player(use_doubles=include_doubles)
        lines['baseline_opponent'] = self._generate_baseline_opponent(use_doubles=include_doubles)
        
        # 8. Long service lines for doubles (both sides)
        if include_doubles:
            lines['long_service_line_doubles_player'] = self._generate_long_service_line_doubles_player()
            lines['long_service_line_doubles_opponent'] = self._generate_long_service_line_doubles_opponent()
        
        return lines
    
    # Boundary generation (full court)
    def _generate_doubles_boundary(self) -> List[Tuple[float, float]]:
        """Generate doubles court outer boundary (full court)."""
        return [
            (-self.doubles_half_width, -self.half_length),  # Opponent baseline left
            (self.doubles_half_width, -self.half_length),   # Opponent baseline right
            (self.doubles_half_width, self.half_length),    # Player baseline right
            (-self.doubles_half_width, self.half_length),   # Player baseline left
            (-self.doubles_half_width, -self.half_length)   # Close
        ]
    
    def _generate_singles_boundary(self) -> List[Tuple[float, float]]:
        """Generate singles court outer boundary (full court)."""
        return [
            (-self.singles_half_width, -self.half_length),  # Opponent baseline left
            (self.singles_half_width, -self.half_length),   # Opponent baseline right
            (self.singles_half_width, self.half_length),    # Player baseline right
            (-self.singles_half_width, self.half_length),   # Player baseline left
            (-self.singles_half_width, -self.half_length)   # Close
        ]
    
    # Net line
    def _generate_net_line(self, use_doubles: bool = True) -> List[Tuple[float, float]]:
        """Generate net line at y=0."""
        half_w = self.doubles_half_width if use_doubles else self.singles_half_width
        return [
            (-half_w, 0.0),
            (half_w, 0.0)
        ]
    
    # Center lines (both sides)
    def _generate_center_line_player(self) -> List[Tuple[float, float]]:
        """Generate center line on player side (short service to baseline)."""
        return [
            (0.0, self.short_service),
            (0.0, self.half_length)
        ]
    
    def _generate_center_line_opponent(self) -> List[Tuple[float, float]]:
        """Generate center line on opponent side (short service to baseline)."""
        return [
            (0.0, -self.short_service),
            (0.0, -self.half_length)
        ]
    
    # Short service lines (both sides)
    def _generate_short_service_line_player(self, use_doubles: bool = True) -> List[Tuple[float, float]]:
        """Generate short service line on player side."""
        half_w = self.doubles_half_width if use_doubles else self.singles_half_width
        return [
            (-half_w, self.short_service),
            (half_w, self.short_service)
        ]
    
    def _generate_short_service_line_opponent(self, use_doubles: bool = True) -> List[Tuple[float, float]]:
        """Generate short service line on opponent side."""
        half_w = self.doubles_half_width if use_doubles else self.singles_half_width
        return [
            (-half_w, -self.short_service),
            (half_w, -self.short_service)
        ]
    
    # Long service lines for doubles (both sides)
    def _generate_long_service_line_doubles_player(self) -> List[Tuple[float, float]]:
        """Generate long service line for doubles on player side."""
        long_service_y = self.half_length - self.long_service_doubles
        return [
            (-self.doubles_half_width, long_service_y),
            (self.doubles_half_width, long_service_y)
        ]
    
    def _generate_long_service_line_doubles_opponent(self) -> List[Tuple[float, float]]:
        """Generate long service line for doubles on opponent side."""
        long_service_y = -self.half_length + self.long_service_doubles
        return [
            (-self.doubles_half_width, long_service_y),
            (self.doubles_half_width, long_service_y)
        ]
    
    # Baselines (both sides)
    def _generate_baseline_player(self, use_doubles: bool = True) -> List[Tuple[float, float]]:
        """Generate baseline on player side."""
        half_w = self.doubles_half_width if use_doubles else self.singles_half_width
        return [
            (-half_w, self.half_length),
            (half_w, self.half_length)
        ]
    
    def _generate_baseline_opponent(self, use_doubles: bool = True) -> List[Tuple[float, float]]:
        """Generate baseline on opponent side."""
        half_w = self.doubles_half_width if use_doubles else self.singles_half_width
        return [
            (-half_w, -self.half_length),
            (half_w, -self.half_length)
        ]
    
    # Vertical lines (sidelines - full court)
    def _generate_singles_left_sideline(self) -> List[Tuple[float, float]]:
        """Generate singles left sideline (full court)."""
        return [
            (-self.singles_half_width, -self.half_length),
            (-self.singles_half_width, self.half_length)
        ]
    
    def _generate_singles_right_sideline(self) -> List[Tuple[float, float]]:
        """Generate singles right sideline (full court)."""
        return [
            (self.singles_half_width, -self.half_length),
            (self.singles_half_width, self.half_length)
        ]
    
    def _generate_doubles_left_sideline(self) -> List[Tuple[float, float]]:
        """Generate doubles left sideline (full court)."""
        return [
            (-self.doubles_half_width, -self.half_length),
            (-self.doubles_half_width, self.half_length)
        ]
    
    def _generate_doubles_right_sideline(self) -> List[Tuple[float, float]]:
        """Generate doubles right sideline (full court)."""
        return [
            (self.doubles_half_width, -self.half_length),
            (self.doubles_half_width, self.half_length)
        ]
    
    def get_line_styles(self) -> Dict[str, Dict[str, any]]:
        """
        Get vibrant color scheme for each line type.
        
        Colors:
        - Net: Orange
        - Short Service: Yellow
        - Long Service (Doubles): Cyan
        - Baseline: Lime Green
        - Center: Blue
        - Sideline (Doubles): Magenta
        - Sideline (Singles): Pink
        """
        return {
            'net_line': {
                'color': (0, 165, 255),  # Orange (BGR)
                'thickness': 3,
                'line_type': 'solid',
                'description': 'Net line'
            },
            'short_service_line_player': {
                'color': (0, 255, 255),  # Yellow (BGR)
                'thickness': 3,
                'line_type': 'solid',
                'description': 'Short service (player)'
            },
            'short_service_line_opponent': {
                'color': (0, 255, 255),  # Yellow (BGR)
                'thickness': 3,
                'line_type': 'solid',
                'description': 'Short service (opponent)'
            },
            'long_service_line_doubles_player': {
                'color': (255, 255, 0),  # Cyan (BGR)
                'thickness': 3,
                'line_type': 'solid',
                'description': 'Long service doubles (player)'
            },
            'long_service_line_doubles_opponent': {
                'color': (255, 255, 0),  # Cyan (BGR)
                'thickness': 3,
                'line_type': 'solid',
                'description': 'Long service doubles (opponent)'
            },
            'baseline_player': {
                'color': (0, 255, 0),  # Lime Green (BGR)
                'thickness': 3,
                'line_type': 'solid',
                'description': 'Baseline (player)'
            },
            'baseline_opponent': {
                'color': (0, 255, 0),  # Lime Green (BGR)
                'thickness': 3,
                'line_type': 'solid',
                'description': 'Baseline (opponent)'
            },
            'center_line_player': {
                'color': (255, 0, 0),  # Blue (BGR)
                'thickness': 3,
                'line_type': 'solid',
                'description': 'Center line (player)'
            },
            'center_line_opponent': {
                'color': (255, 0, 0),  # Blue (BGR)
                'thickness': 3,
                'line_type': 'solid',
                'description': 'Center line (opponent)'
            },
            'doubles_sideline_left': {
                'color': (255, 0, 255),  # Magenta (BGR)
                'thickness': 3,
                'line_type': 'solid',
                'description': 'Doubles sideline (left)'
            },
            'doubles_sideline_right': {
                'color': (255, 0, 255),  # Magenta (BGR)
                'thickness': 3,
                'line_type': 'solid',
                'description': 'Doubles sideline (right)'
            },
            'singles_sideline_left': {
                'color': (255, 128, 255),  # Light Magenta/Pink (BGR)
                'thickness': 3,
                'line_type': 'solid',
                'description': 'Singles sideline (left)'
            },
            'singles_sideline_right': {
                'color': (255, 128, 255),  # Light Magenta/Pink (BGR)
                'thickness': 3,
                'line_type': 'solid',
                'description': 'Singles sideline (right)'
            },
            'outer_boundary': {
                'color': (255, 255, 255),  # White
                'thickness': 2,
                'line_type': 'solid',
                'description': 'Outer boundary'
            }
        }
    
    def get_court_info(self) -> Dict[str, any]:
        """Get court information and dimensions."""
        return {
            'type': self.court_type,
            'singles_width': self.singles_width,
            'doubles_width': self.doubles_width,
            'half_length': self.half_length,
            'total_length': self.total_length,
            'short_service_line': self.short_service,
            'long_service_line_doubles': self.long_service_doubles,
            'coordinate_system': {
                'origin': 'Net center',
                'x_axis': 'Left (-) to Right (+)',
                'y_axis': 'Opponent baseline (-6.7m) → Net (0) → Player baseline (+6.7m)',
                'units': 'meters',
                'note': 'FULL COURT (both sides)'
            }
        }
    
    def __repr__(self):
        return f"CourtLineGenerator(type='{self.court_type}', full_court={self.total_length}m)"


# Convenience function
def generate_court_lines(court_type: str = 'singles', include_net: bool = True, include_doubles: bool = True) -> Dict[str, List[Tuple[float, float]]]:
    """
    Convenience function to generate court lines for FULL COURT.
    
    Args:
        court_type: 'singles' or 'doubles'
        include_net: Whether to include net line
        include_doubles: Whether to include doubles sidelines
        
    Returns:
        Dictionary of line names to point lists
    """
    generator = CourtLineGenerator(court_type=court_type)
    return generator.generate_all_lines(include_net=include_net, include_doubles=include_doubles)


if __name__ == "__main__":
    # Test the generator
    print("=" * 70)
    print("Court Line Generator Test (FULL COURT)")
    print("=" * 70)
    
    generator = CourtLineGenerator(court_type='singles')
    
    print(f"\n{generator}")
    print(f"\nCourt Info:")
    info = generator.get_court_info()
    for key, value in info.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    
    print(f"\nGenerating all lines (singles only)...")
    lines = generator.generate_all_lines(include_net=True, include_doubles=False)
    
    print(f"\nGenerated {len(lines)} line types:")
    for line_name in lines.keys():
        print(f"  - {line_name}")
    
    print("\n" + "=" * 70)
    print("✅ Full Court Line Generator Test Complete")
    print("=" * 70)
