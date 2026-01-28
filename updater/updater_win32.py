#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal Win32 utilities for the standalone updater.
Self-contained with no external dependencies.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Optional

# Win32 DLL handles
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
comctl32 = ctypes.windll.comctl32
gdi32 = ctypes.windll.gdi32

# Handle type fallbacks for older Python versions
HCURSOR = getattr(wintypes, "HCURSOR", wintypes.HANDLE)
HICON = getattr(wintypes, "HICON", wintypes.HANDLE)
HBRUSH = getattr(wintypes, "HBRUSH", wintypes.HANDLE)

# ---------------------------------------------------------------------------
# Win32 Constants
# ---------------------------------------------------------------------------

# Window messages
WM_CREATE = 0x0001
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_SETFONT = 0x0030
WM_NCCREATE = 0x0081
WM_NCDESTROY = 0x0082
WM_USER = 0x0400

PM_REMOVE = 0x0001

# Show window commands
SW_SHOWNORMAL = 1

# System metrics
SM_CXSCREEN = 0
SM_CYSCREEN = 1

# Cursor IDs
IDC_ARROW = 32512

# Colors
COLOR_WINDOW = 5

# Window styles
WS_OVERLAPPED = 0x00000000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000

WS_EX_APPWINDOW = 0x00040000

# Progress bar
PBM_SETRANGE = WM_USER + 1
PBM_SETPOS = WM_USER + 2
PBM_SETMARQUEE = WM_USER + 10
PBS_MARQUEE = 0x0008

# Common controls
ICC_PROGRESS_CLASS = 0x00000020

# Stock objects
DEFAULT_GUI_FONT = 17

# Process access rights
SYNCHRONIZE = 0x00100000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001

# Wait results
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF

# ---------------------------------------------------------------------------
# Type definitions
# ---------------------------------------------------------------------------

pointer_size = ctypes.sizeof(ctypes.c_void_p)

if hasattr(wintypes, "LRESULT"):
    LRESULT = wintypes.LRESULT
else:
    LRESULT = ctypes.c_longlong if pointer_size == 8 else ctypes.c_long

if hasattr(wintypes, "WPARAM"):
    WPARAM = wintypes.WPARAM
else:
    WPARAM = ctypes.c_ulonglong if pointer_size == 8 else ctypes.c_ulong

if hasattr(wintypes, "LPARAM"):
    LPARAM = wintypes.LPARAM
else:
    LPARAM = ctypes.c_longlong if pointer_size == 8 else ctypes.c_long

# Window procedure type
WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    WPARAM,
    LPARAM,
)


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", HICON),
    ]


class CREATESTRUCTW(ctypes.Structure):
    _fields_ = [
        ("lpCreateParams", wintypes.LPVOID),
        ("hInstance", wintypes.HINSTANCE),
        ("hMenu", wintypes.HMENU),
        ("hwndParent", wintypes.HWND),
        ("cy", ctypes.c_int),
        ("cx", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x", ctypes.c_int),
        ("style", ctypes.c_long),
        ("lpszName", wintypes.LPCWSTR),
        ("lpszClass", wintypes.LPCWSTR),
        ("dwExStyle", ctypes.c_ulong),
    ]


class INITCOMMONCONTROLSEX(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("dwICC", wintypes.DWORD),
    ]


# ---------------------------------------------------------------------------
# Function signatures
# ---------------------------------------------------------------------------

user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT

user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
user32.PostMessageW.restype = wintypes.BOOL

user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
user32.SendMessageW.restype = LRESULT

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE

kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = wintypes.BOOL


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def MAKELPARAM(low: int, high: int) -> int:
    """Create LPARAM from low and high words."""
    return ((high & 0xFFFF) << 16) | (low & 0xFFFF)


def init_common_controls() -> None:
    """Initialize common controls (progress bar)."""
    icc = INITCOMMONCONTROLSEX()
    icc.dwSize = ctypes.sizeof(INITCOMMONCONTROLSEX)
    icc.dwICC = ICC_PROGRESS_CLASS
    comctl32.InitCommonControlsEx(ctypes.byref(icc))


def wait_for_process(pid: int, timeout_ms: int = 60000) -> bool:
    """
    Wait for a process to exit.

    Args:
        pid: Process ID to wait for
        timeout_ms: Timeout in milliseconds

    Returns:
        True if process exited, False if timeout or error
    """
    handle = kernel32.OpenProcess(
        SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        pid
    )
    if not handle:
        # Process doesn't exist or already exited
        return True

    try:
        result = kernel32.WaitForSingleObject(handle, timeout_ms)
        return result == WAIT_OBJECT_0
    finally:
        kernel32.CloseHandle(handle)


def terminate_process(pid: int) -> bool:
    """
    Forcefully terminate a process.

    Args:
        pid: Process ID to terminate

    Returns:
        True if terminated, False if failed
    """
    handle = kernel32.OpenProcess(
        PROCESS_TERMINATE,
        False,
        pid
    )
    if not handle:
        return True  # Process doesn't exist

    try:
        return bool(kernel32.TerminateProcess(handle, 1))
    finally:
        kernel32.CloseHandle(handle)
