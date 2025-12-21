import time
from functools import wraps
import inspect

def time_logger(name: str):
    """
    Function/Method 실행 시간을 측정하여 출력하는 데코레이터
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            result = await func(*args, **kwargs)
            duration = (time.time() - start) * 1000
            print(f"⏱️ [{name}] {duration:.1f}ms")
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = (time.time() - start) * 1000
            print(f"⏱️ [{name}] {duration:.1f}ms")
            return result
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator
