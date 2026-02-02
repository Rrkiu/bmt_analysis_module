"""
Performance Profiler

성능 측정 및 분석을 위한 프로파일러입니다.
각 단계별 실행 시간을 측정하고 통계를 제공합니다.
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import statistics


@dataclass
class TimingRecord:
    """단일 타이밍 레코드"""
    name: str
    duration_ms: float
    timestamp: float
    metadata: Dict = field(default_factory=dict)


class PerformanceProfiler:
    """
    성능 프로파일러
    
    사용 예시:
        profiler = PerformanceProfiler()
        
        with profiler.measure("court_detection"):
            detect_court()
        
        with profiler.measure("frame_processing"):
            process_frame()
        
        stats = profiler.get_stats()
        profiler.print_summary()
    """
    
    def __init__(self, name: str = "default"):
        self.name = name
        self.records: List[TimingRecord] = []
        self.category_times: Dict[str, List[float]] = defaultdict(list)
        self.enabled = True
        
    def measure(self, category: str, metadata: Optional[Dict] = None):
        """
        컨텍스트 매니저로 시간 측정
        
        Args:
            category: 측정 카테고리 (예: "yolo_detection", "court_detection")
            metadata: 추가 메타데이터
        """
        return TimingContext(self, category, metadata or {})
    
    def record(self, category: str, duration_ms: float, metadata: Optional[Dict] = None):
        """
        시간 기록 추가
        
        Args:
            category: 카테고리
            duration_ms: 소요 시간 (밀리초)
            metadata: 추가 정보
        """
        if not self.enabled:
            return
        
        record = TimingRecord(
            name=category,
            duration_ms=duration_ms,
            timestamp=time.time(),
            metadata=metadata or {}
        )
        
        self.records.append(record)
        self.category_times[category].append(duration_ms)
    
    def get_stats(self, category: Optional[str] = None) -> Dict:
        """
        통계 정보 반환
        
        Args:
            category: 특정 카테고리만 (None이면 전체)
            
        Returns:
            통계 딕셔너리
        """
        if category:
            times = self.category_times.get(category, [])
            if not times:
                return {}
            
            return {
                'category': category,
                'count': len(times),
                'total_ms': sum(times),
                'mean_ms': statistics.mean(times),
                'median_ms': statistics.median(times),
                'min_ms': min(times),
                'max_ms': max(times),
                'std_ms': statistics.stdev(times) if len(times) > 1 else 0.0
            }
        
        # 전체 통계
        all_stats = {}
        for cat in self.category_times.keys():
            all_stats[cat] = self.get_stats(cat)
        
        return all_stats
    
    def print_summary(self, top_n: int = 10):
        """
        요약 출력
        
        Args:
            top_n: 상위 N개 카테고리만 표시
        """
        print("\n" + "=" * 70)
        print(f"📊 Performance Summary: {self.name}")
        print("=" * 70)
        
        if not self.category_times:
            print("No timing data recorded.")
            return
        
        # 카테고리별 통계
        stats_list = []
        for category, times in self.category_times.items():
            if times:
                stats_list.append({
                    'category': category,
                    'count': len(times),
                    'total_ms': sum(times),
                    'mean_ms': statistics.mean(times),
                    'median_ms': statistics.median(times),
                    'min_ms': min(times),
                    'max_ms': max(times)
                })
        
        # 평균 시간 기준 정렬
        stats_list.sort(key=lambda x: x['mean_ms'], reverse=True)
        
        # 상위 N개만
        stats_list = stats_list[:top_n]
        
        # 테이블 출력
        print(f"\n{'Category':<30} {'Count':>8} {'Mean':>10} {'Median':>10} {'Min':>10} {'Max':>10}")
        print("-" * 70)
        
        for stat in stats_list:
            print(
                f"{stat['category']:<30} "
                f"{stat['count']:>8} "
                f"{stat['mean_ms']:>9.1f}ms "
                f"{stat['median_ms']:>9.1f}ms "
                f"{stat['min_ms']:>9.1f}ms "
                f"{stat['max_ms']:>9.1f}ms"
            )
        
        # 전체 통계
        total_time = sum(sum(times) for times in self.category_times.values())
        total_count = sum(len(times) for times in self.category_times.values())
        
        print("-" * 70)
        print(f"{'TOTAL':<30} {total_count:>8} {total_time:>9.1f}ms")
        print("=" * 70)
    
    def print_detailed_breakdown(self):
        """상세 분석 출력"""
        print("\n" + "=" * 70)
        print(f"📈 Detailed Performance Breakdown: {self.name}")
        print("=" * 70)
        
        for category in sorted(self.category_times.keys()):
            stats = self.get_stats(category)
            if not stats:
                continue
            
            print(f"\n📌 {category}")
            print(f"   Count:    {stats['count']}")
            print(f"   Total:    {stats['total_ms']:.1f}ms")
            print(f"   Mean:     {stats['mean_ms']:.1f}ms")
            print(f"   Median:   {stats['median_ms']:.1f}ms")
            print(f"   Min:      {stats['min_ms']:.1f}ms")
            print(f"   Max:      {stats['max_ms']:.1f}ms")
            print(f"   Std Dev:  {stats['std_ms']:.1f}ms")
    
    def reset(self):
        """통계 초기화"""
        self.records.clear()
        self.category_times.clear()
    
    def export_to_dict(self) -> Dict:
        """딕셔너리로 내보내기 (JSON 직렬화 가능)"""
        return {
            'name': self.name,
            'stats': self.get_stats(),
            'total_records': len(self.records),
            'categories': list(self.category_times.keys())
        }


class TimingContext:
    """시간 측정 컨텍스트 매니저"""
    
    def __init__(self, profiler: PerformanceProfiler, category: str, metadata: Dict):
        self.profiler = profiler
        self.category = category
        self.metadata = metadata
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        self.profiler.record(self.category, duration_ms, self.metadata)
        return False


# 전역 프로파일러 인스턴스
_global_profiler = PerformanceProfiler("global")


def get_profiler(name: str = "global") -> PerformanceProfiler:
    """
    프로파일러 인스턴스 가져오기
    
    Args:
        name: 프로파일러 이름
        
    Returns:
        PerformanceProfiler 인스턴스
    """
    if name == "global":
        return _global_profiler
    return PerformanceProfiler(name)


def measure(category: str, metadata: Optional[Dict] = None):
    """
    전역 프로파일러로 시간 측정
    
    사용 예시:
        with measure("yolo_detection"):
            detect()
    """
    return _global_profiler.measure(category, metadata)
