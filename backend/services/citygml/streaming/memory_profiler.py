"""
Memory Profiling Utilities for Streaming Parser

Tools for measuring and analyzing memory usage during streaming operations.

Features:
1. Real-time memory monitoring
2. Peak memory tracking
3. Memory delta calculations
4. Profile decorators for functions
"""

import tracemalloc
import gc
from typing import Callable, Any, Tuple, Optional
from functools import wraps
from contextlib import contextmanager


class MemoryProfiler:
    """
    Memory profiler for tracking memory usage.

    Uses tracemalloc for accurate Python memory tracking.
    """

    def __init__(self):
        """Initialize profiler."""
        self.is_tracing = False
        self.snapshots = []

    def start(self):
        """Start memory tracing."""
        if not self.is_tracing:
            tracemalloc.start()
            self.is_tracing = True
            self.snapshots = []

    def stop(self) -> Tuple[int, int]:
        """
        Stop memory tracing and return final statistics.

        Returns:
            Tuple of (current_bytes, peak_bytes)
        """
        if self.is_tracing:
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            self.is_tracing = False
            return (current, peak)
        return (0, 0)

    def snapshot(self, label: str = ""):
        """
        Take memory snapshot at current point.

        Args:
            label: Optional label for snapshot
        """
        if self.is_tracing:
            current, peak = tracemalloc.get_traced_memory()
            self.snapshots.append({
                'label': label,
                'current': current,
                'peak': peak
            })

    def get_current_usage(self) -> Tuple[int, int]:
        """
        Get current memory usage.

        Returns:
            Tuple of (current_bytes, peak_bytes)
        """
        if self.is_tracing:
            return tracemalloc.get_traced_memory()
        return (0, 0)

    def format_bytes(self, bytes_value: int) -> str:
        """
        Format bytes as human-readable string.

        Args:
            bytes_value: Number of bytes

        Returns:
            Formatted string (e.g., "1.5 GB")
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"

    def print_snapshots(self):
        """Print all recorded snapshots."""
        if not self.snapshots:
            print("[MEMORY] No snapshots recorded")
            return

        print("\n" + "=" * 70)
        print("Memory Usage Snapshots")
        print("=" * 70)

        for i, snap in enumerate(self.snapshots):
            label = snap['label'] or f"Snapshot {i+1}"
            current = self.format_bytes(snap['current'])
            peak = self.format_bytes(snap['peak'])

            print(f"{label}:")
            print(f"  Current: {current}")
            print(f"  Peak:    {peak}")
            print()

        print("=" * 70 + "\n")


@contextmanager
def profile_memory(label: str = "Operation", verbose: bool = True):
    """
    Context manager for profiling memory usage of a code block.

    Args:
        label: Label for the profiled operation
        verbose: Print results immediately

    Yields:
        MemoryProfiler instance

    Example:
        ```python
        with profile_memory("Building processing"):
            for building, _ in stream_parse_buildings("large.gml"):
                process_building(building)
        ```
    """
    profiler = MemoryProfiler()
    profiler.start()

    # Force garbage collection before measurement
    gc.collect()

    try:
        yield profiler
    finally:
        current, peak = profiler.stop()

        if verbose:
            profiler_instance = MemoryProfiler()
            print(f"\n[MEMORY] {label}:")
            print(f"  Current: {profiler_instance.format_bytes(current)}")
            print(f"  Peak:    {profiler_instance.format_bytes(peak)}")


def profile(label: Optional[str] = None, verbose: bool = True):
    """
    Decorator for profiling function memory usage.

    Args:
        label: Optional label (defaults to function name)
        verbose: Print results after function execution

    Example:
        ```python
        @profile(verbose=True)
        def process_large_file(path):
            ...
        ```
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            func_label = label or func.__name__

            with profile_memory(func_label, verbose=verbose) as profiler:
                result = func(*args, **kwargs)

            return result

        return wrapper

    return decorator


def compare_memory_usage(
    func1: Callable,
    func2: Callable,
    *args,
    func1_label: str = "Function 1",
    func2_label: str = "Function 2",
    **kwargs
) -> dict:
    """
    Compare memory usage of two functions.

    Args:
        func1: First function to profile
        func2: Second function to profile
        *args: Arguments to pass to both functions
        func1_label: Label for first function
        func2_label: Label for second function
        **kwargs: Keyword arguments to pass to both functions

    Returns:
        Dictionary with comparison results

    Example:
        ```python
        results = compare_memory_usage(
            legacy_parser,
            streaming_parser,
            "dataset.gml",
            func1_label="Legacy Parser",
            func2_label="Streaming Parser"
        )

        print(f"Memory reduction: {results['reduction_percent']:.1f}%")
        ```
    """
    # Profile function 1
    profiler1 = MemoryProfiler()
    profiler1.start()
    gc.collect()
    result1 = func1(*args, **kwargs)
    current1, peak1 = profiler1.stop()

    # Profile function 2
    profiler2 = MemoryProfiler()
    profiler2.start()
    gc.collect()
    result2 = func2(*args, **kwargs)
    current2, peak2 = profiler2.stop()

    # Calculate comparison metrics
    peak_reduction = ((peak1 - peak2) / peak1) * 100 if peak1 > 0 else 0
    current_reduction = ((current1 - current2) / current1) * 100 if current1 > 0 else 0

    results = {
        'func1': {
            'label': func1_label,
            'current': current1,
            'peak': peak1,
        },
        'func2': {
            'label': func2_label,
            'current': current2,
            'peak': peak2,
        },
        'peak_reduction_percent': peak_reduction,
        'current_reduction_percent': current_reduction,
    }

    # Print comparison
    formatter = MemoryProfiler()
    print("\n" + "=" * 70)
    print("Memory Usage Comparison")
    print("=" * 70)
    print(f"\n{func1_label}:")
    print(f"  Current: {formatter.format_bytes(current1)}")
    print(f"  Peak:    {formatter.format_bytes(peak1)}")
    print(f"\n{func2_label}:")
    print(f"  Current: {formatter.format_bytes(current2)}")
    print(f"  Peak:    {formatter.format_bytes(peak2)}")
    print(f"\nReduction:")
    print(f"  Peak:    {peak_reduction:+.1f}%")
    print(f"  Current: {current_reduction:+.1f}%")
    print("=" * 70 + "\n")

    return results


def assert_memory_limit(max_bytes: int, label: str = "Operation"):
    """
    Context manager that asserts memory stays below limit.

    Args:
        max_bytes: Maximum allowed memory in bytes
        label: Label for the operation

    Raises:
        AssertionError: If memory exceeds limit

    Example:
        ```python
        # Ensure processing stays under 1GB
        with assert_memory_limit(1_000_000_000, "Building processing"):
            process_buildings(...)
        ```
    """
    @contextmanager
    def _assert_limit():
        profiler = MemoryProfiler()
        profiler.start()

        try:
            yield profiler
        finally:
            current, peak = profiler.stop()

            if peak > max_bytes:
                formatter = MemoryProfiler()
                raise AssertionError(
                    f"[MEMORY] {label} exceeded limit: "
                    f"{formatter.format_bytes(peak)} > "
                    f"{formatter.format_bytes(max_bytes)}"
                )

    return _assert_limit()
