from box import Box
import time
import functools
import inspect
import logging
from typing import Optional, Callable, Any, TypeVar


def get_nba_stats_result(endpoint, result_set_name = None):
    box = Box(**endpoint.get_dict())
    result_sets: dict[str, Box] = {}
    for resultSet in box.resultSets:
        result_sets[resultSet.name] = []
        for row in resultSet.rowSet:
            result_sets[resultSet.name].append(Box(**dict(zip([header.lower() for header in resultSet.headers], row))))
    if result_set_name is None:
        return result_sets
    return result_sets[result_set_name]

def invoke_endpoint(class_ref, logger, **kwargs):
    endpoint_instance = class_ref(**kwargs)
    name = class_ref.__name__
    invoker = timed(name, logger)(get_nba_stats_result)
    return invoker(endpoint_instance, result_set_name=class_ref.__name__)

def timed(identifier: str, logger: Optional[logging.Logger]):
    """
    Decorator factory that accepts an identifier string and a logger.
    The wrapped function is timed; logger.info is called before and after,
    and logger.exception is called on errors (then the exception is re-raised).
    Works for sync and async functions. If logger is None, timing still occurs
    but no logging is emitted.
    """
    def decorator(func: Callable):
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                if logger:
                    logger.info("starting %s: %s", identifier, func.__qualname__)
                start = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                except Exception:
                    elapsed = time.perf_counter() - start
                    if logger:
                        logger.exception("error in %s: %s (%.3fs)", identifier, func.__qualname__, elapsed)
                    raise
                elapsed = time.perf_counter() - start
                if logger:
                    logger.info("finished %s: %s (%.3fs)", identifier, func.__qualname__, elapsed)
                return result
            return async_wrapper
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                if logger:
                    logger.info("starting %s: %s", identifier, func.__qualname__)
                start = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                except Exception:
                    elapsed = time.perf_counter() - start
                    if logger:
                        logger.exception("error in %s: %s (%.3fs)", identifier, func.__qualname__, elapsed)
                    raise
                elapsed = time.perf_counter() - start
                if logger:
                    logger.info("finished %s: %s (%.3fs)", identifier, func.__qualname__, elapsed)
                return result
            return wrapper
    return decorator

