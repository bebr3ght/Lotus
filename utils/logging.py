#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logging configuration and utilities
"""

import sys
import time
import logging
import urllib3
from urllib3.exceptions import InsecureRequestWarning


def setup_logging(verbose: bool):
    """Setup logging configuration"""
    # Handle windowed mode where stdout/stderr might be None
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(line_buffering=True)
        except (AttributeError, OSError):
            pass  # stdout doesn't support reconfigure or is redirected
    
    if sys.stderr is not None:
        try:
            sys.stderr.reconfigure(line_buffering=True)
        except (AttributeError, OSError):
            pass  # stderr doesn't support reconfigure or is redirected
    
    # Use stderr if stdout is None (windowed mode)
    output_stream = sys.stdout if sys.stdout is not None else sys.stderr
    h = logging.StreamHandler(output_stream)
    fmt = "%(_when)s | %(levelname)-7s | %(message)s"
    
    class _Fmt(logging.Formatter):
        def format(self, record):
            record._when = time.strftime("%H:%M:%S", time.localtime())
            return super().format(record)
    
    h.setFormatter(_Fmt(fmt))
    h.flush()  # Ensure immediate output
    
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(h)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Add a console print to ensure output is visible (only if we have stdout)
    if sys.stdout is not None:
        print("=" * 60, flush=True)
        print("SkinCloner - Starting...", flush=True)
        print("=" * 60, flush=True)
    
    # Suppress HTTPS/HTTP logs
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    
    # Disable SSL warnings for LCU (self-signed cert)
    urllib3.disable_warnings(InsecureRequestWarning)


def get_logger(name: str = "tracer") -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)
