"""
Thread-local logging utilities for CityGML conversion.

This module provides global logging functions that write to both console and
thread-local log files. This allows all conversion functions to write to a
conversion-specific log file without passing log file handles around.

Usage:
    from services.citygml.utils.logging import log, set_log_file, close_log_file

    # At conversion start
    log_file = open("conversion.log", "w")
    set_log_file(log_file)

    # During conversion
    log("Processing building...")

    # At conversion end (always use try/finally)
    try:
        # ... conversion logic ...
    finally:
        close_log_file()
"""

import threading
from typing import Optional, TextIO


# Thread-local storage for log file
# This allows each conversion (thread) to have its own log file
_thread_local = threading.local()


def log(message: str) -> None:
    """
    Log a message to both console and thread-local log file.

    This function writes to:
    1. Standard output (always)
    2. Thread-local log file if one is set via set_log_file()

    Args:
        message: Message to log (newline automatically appended for file output)

    Example:
        >>> log("Processing building 123...")
        Processing building 123...
    """
    print(message)
    log_file = getattr(_thread_local, 'log_file', None)
    if log_file:
        try:
            log_file.write(message + "\n")
            log_file.flush()
        except Exception:
            # Silently fail if log file is closed or unavailable
            # This prevents logging errors from breaking the conversion
            pass


def set_log_file(log_file: Optional[TextIO]) -> None:
    """
    Set the log file for the current thread.

    After calling this function, all subsequent log() calls in the same thread
    will write to the specified file in addition to console output.

    Args:
        log_file: File object to write logs to, or None to disable file logging

    Example:
        >>> with open("conversion.log", "w") as f:
        ...     set_log_file(f)
        ...     log("Starting conversion...")
        ...     # ... conversion logic ...
        ...     set_log_file(None)  # Or use close_log_file()
    """
    _thread_local.log_file = log_file


def close_log_file() -> None:
    """
    Close and clear the thread-local log file if one is open.

    This function:
    1. Clears the log file reference (stops further logging to file)
    2. Closes the file handle if it's still open

    This function is safe to call multiple times and handles exceptions
    gracefully. It should be called in a finally block to ensure log files
    are properly closed even if an exception occurs.

    Example:
        >>> f = open("conversion.log", "w")
        >>> set_log_file(f)
        >>> try:
        ...     log("Processing...")
        ...     # ... conversion logic ...
        ... finally:
        ...     close_log_file()  # Guaranteed to execute
    """
    log_file = getattr(_thread_local, 'log_file', None)
    if log_file:
        try:
            set_log_file(None)  # Clear the reference first to prevent further writes
            log_file.close()
        except Exception:
            # Silently fail if already closed
            # This prevents double-close errors
            pass


def get_log_file() -> Optional[TextIO]:
    """
    Get the current thread's log file.

    Returns:
        Current log file object, or None if not set

    Example:
        >>> f = open("conversion.log", "w")
        >>> set_log_file(f)
        >>> get_log_file() is f
        True
    """
    return getattr(_thread_local, 'log_file', None)
