"""
배드민턴 코트 규격 상수
BWF (Badminton World Federation) 공식 규격
"""

# 단위: 미터
class CourtDimensions:
    """배드민턴 코트 규격 (BWF 기준)"""
    
    # 전체 코트 크기
    TOTAL_LENGTH = 13.4  # 미터
    SINGLES_WIDTH = 5.18  # 단식 너비
    DOUBLES_WIDTH = 6.1   # 복식 너비
    
    # 라인 두께
    LINE_WIDTH = 0.04  # 4cm
    
    # 네트
    NET_HEIGHT_CENTER = 1.524  # 중앙 높이
    NET_HEIGHT_EDGE = 1.55     # 양끝 높이
    
    # 서비스 라인 (네트로부터의 거리)
    SHORT_SERVICE_LINE = 1.98   # 숏 서비스 라인
    LONG_SERVICE_LINE_DOUBLES = 0.76  # 롱 서비스 라인 (복식, 베이스라인으로부터)
    
    # 계산된 값들
    BACK_BOUNDARY_LINE = TOTAL_LENGTH / 2  # 베이스라인 (중심으로부터)
    CENTER_LINE_LENGTH = SHORT_SERVICE_LINE  # 센터라인 길이 (네트~숏서비스라인)
    
    @classmethod
    def get_singles_court_template(cls):
        """
        단식 코트 템플릿 좌표 생성
        원점(0, 0)을 코트 중심(네트 중앙)으로 설정
        
        Returns:
            dict: 코트의 주요 포인트들
        """
        half_width = cls.SINGLES_WIDTH / 2
        
        # T자 기준점 (숏 서비스 라인과 센터라인 교차점)
        # 사용자 코트 쪽 (네트에서 가까운 쪽)
        t_reference_point = {
            'x': 0,  # 센터
            'y': cls.SHORT_SERVICE_LINE  # 네트로부터
        }
        
        # 사용자 코트 (네트 앞쪽)
        user_court = {
            # 코너 4개 (시계방향)
            'top_left': [-half_width, 0],  # 네트 왼쪽
            'top_right': [half_width, 0],  # 네트 오른쪽
            'bottom_right': [half_width, cls.BACK_BOUNDARY_LINE],  # 베이스라인 오른쪽
            'bottom_left': [-half_width, cls.BACK_BOUNDARY_LINE],  # 베이스라인 왼쪽
            
            # 주요 라인들
            'short_service_left': [-half_width, cls.SHORT_SERVICE_LINE],
            'short_service_right': [half_width, cls.SHORT_SERVICE_LINE],
            'center_top': [0, 0],  # 네트 중앙
            'center_short_service': [0, cls.SHORT_SERVICE_LINE],  # T자 기준점
            'center_baseline': [0, cls.BACK_BOUNDARY_LINE],
        }
        
        # 상대 코트 (네트 반대편) - 참고용
        opponent_court = {
            'top_left': [-half_width, 0],
            'top_right': [half_width, 0],
            'bottom_right': [half_width, -cls.BACK_BOUNDARY_LINE],
            'bottom_left': [-half_width, -cls.BACK_BOUNDARY_LINE],
        }
        
        return {
            't_reference': t_reference_point,
            'user_court': user_court,
            'opponent_court': opponent_court,
            'dimensions': {
                'length': cls.BACK_BOUNDARY_LINE,
                'width': cls.SINGLES_WIDTH,
                'short_service_line': cls.SHORT_SERVICE_LINE,
            }
        }
    
    @classmethod
    def get_t_guide_lines(cls):
        """
        T자 가이드 라인 좌표
        
        Returns:
            dict: T자 형태의 라인 정의
        """
        half_width = cls.SINGLES_WIDTH / 2
        
        return {
            # 세로선 (센터라인): 숏서비스라인에서 베이스라인 방향으로
            'vertical': {
                'start': [0, cls.SHORT_SERVICE_LINE],  # 숏 서비스 라인 (T자 교차점)
                'end': [0, cls.BACK_BOUNDARY_LINE]      # 베이스라인 방향
            },
            # 가로선 (숏서비스라인): 왼쪽 ~ 오른쪽
            'horizontal': {
                'start': [-half_width, cls.SHORT_SERVICE_LINE],
                'end': [half_width, cls.SHORT_SERVICE_LINE]
            },
            # T자 교차점
            'intersection': [0, cls.SHORT_SERVICE_LINE]
        }


# 편의를 위한 상수
COURT_TEMPLATE = CourtDimensions.get_singles_court_template()
T_GUIDE = CourtDimensions.get_t_guide_lines()