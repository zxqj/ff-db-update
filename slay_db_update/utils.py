from enum import IntEnum
from json import JSONDecodeError

from box import Box
import time
import functools
import inspect
import logging
from typing import Optional, Callable, Any
from pathlib import Path


def parse_intenum(enum_cls, value_str):
    """
    Parse a string into an IntEnum member.

    Args:
        enum_cls: The IntEnum class to parse into.
        value_str: The string representation (name or integer value).

    Returns:
        An instance of enum_cls.

    Raises:
        ValueError: If the string cannot be parsed into a valid enum member.
    """
    if not issubclass(enum_cls, IntEnum):
        raise TypeError(f"{enum_cls.__name__} is not an IntEnum subclass")

    # Try parsing by name (case-sensitive)
    try:
        return enum_cls[value_str.upper()]
    except KeyError:
        pass  # Not a valid name

    # Try parsing by integer value
    try:
        int_value = int(value_str)
        return enum_cls(int_value)
    except (ValueError, KeyError):
        pass  # Not a valid integer or not in enum

    # If both attempts fail, raise an error
    raise ValueError(f"'{value_str}' is not a valid {enum_cls.__name__}")

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
    name = class_ref.__name__
    def f(**_kwargs):
        # Avoid printing huge kwargs directly; just show the names
        try:
            return class_ref(**_kwargs)
        except JSONDecodeError as e:
            argstr = ",".join([f"{k}: {str(v)[:100]}" for k, v in kwargs.items()])
            raise RuntimeError(f"JSON decode error invoking {name} with args {argstr}") from e

    invoker = timed(name, logger)(f)
    return get_nba_stats_result(invoker(**kwargs), result_set_name=name)

def find_project_root(start: Optional[Path | str] = None) -> Path:
    """Walk up from `start` (or this file's parent) to find a directory that contains
    both a `.git` directory and either a `pyproject.yaml` (preferred per request)
    or `pyproject.toml`. Returns the Path to that directory. Raises RuntimeError if none is found.

    """
    if start is None:
        p = Path(__file__).resolve().parent
    else:
        p = Path(start).resolve()
        if p.is_file():
            p = p.parent

    root = p
    while True:
        git_dir = root / '.git'
        pyproject_yaml = root / 'pyproject.yaml'
        pyproject_toml = root / 'pyproject.toml'
        if git_dir.is_dir() and (pyproject_yaml.is_file() or pyproject_toml.is_file()):
            return root
        if root.parent == root:
            raise RuntimeError('project root with .git and pyproject.yaml/pyproject.toml not found')
        root = root.parent

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
