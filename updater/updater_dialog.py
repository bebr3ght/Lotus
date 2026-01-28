#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal Win32 dialog for the standalone updater.
Shows a simple progress window during update.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Dict, Optional

from .updater_win32 import (
    COLOR_WINDOW,
    CREATESTRUCTW,
    DEFAULT_GUI_FONT,
    IDC_ARROW,
    LPARAM,
    MAKELPARAM,
    PBM_SETMARQUEE,
    PBM_SETRANGE,
    PBS_MARQUEE,
    PM_REMOVE,
    SM_CXSCREEN,
    SM_CYSCREEN,
    SW_SHOWNORMAL,
    WNDCLASSEXW,
    WNDPROC,
    WPARAM,
    WM_CLOSE,
    WM_CREATE,
    WM_DESTROY,
    WM_NCCREATE,
    WM_NCDESTROY,
    WM_SETFONT,
    WS_CAPTION,
    WS_CHILD,
    WS_EX_APPWINDOW,
    WS_MINIMIZEBOX,
    WS_SYSMENU,
    WS_VISIBLE,
    gdi32,
    init_common_controls,
    kernel32,
    user32,
)


class UpdaterDialog:
    """Minimal Win32 dialog for showing update progress."""

    _registered_classes: Dict[str, int] = {}
    _instances: Dict[int, "UpdaterDialog"] = {}
    _wnd_proc: Optional[WNDPROC] = None

    STATUS_ID = 1001
    PROGRESS_ID = 1002

    def __init__(self, title: str = "Rose Updater") -> None:
        self.title = title
        self.width = 400
        self.height = 100
        self.hwnd: Optional[wintypes.HWND] = None
        self.status_hwnd: Optional[wintypes.HWND] = None
        self.progress_hwnd: Optional[wintypes.HWND] = None
        self.h_instance = kernel32.GetModuleHandleW(None)
        self.default_font = gdi32.GetStockObject(DEFAULT_GUI_FONT)
        self._lp_create_param = ctypes.py_object(self)
        self._lp_create_param_ptr = ctypes.pointer(self._lp_create_param)
        self._marquee_enabled = False
        self._allow_close = False

        init_common_controls()
        self._register_class()
        self._create_window()

    @classmethod
    def _get_wnd_proc(cls) -> WNDPROC:
        if cls._wnd_proc is None:
            cls._wnd_proc = WNDPROC(cls._global_wnd_proc)
        return cls._wnd_proc

    def _register_class(self) -> None:
        class_name = "RoseUpdaterDialog"
        if class_name in self._registered_classes:
            self.class_name = class_name
            return

        wnd_class = WNDCLASSEXW()
        wnd_class.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wnd_class.style = 0
        wnd_class.lpfnWndProc = self._get_wnd_proc()
        wnd_class.cbClsExtra = 0
        wnd_class.cbWndExtra = 0
        wnd_class.hInstance = self.h_instance
        wnd_class.hIcon = None
        wnd_class.hCursor = user32.LoadCursorW(None, IDC_ARROW)
        wnd_class.hbrBackground = user32.GetSysColorBrush(COLOR_WINDOW)
        wnd_class.lpszMenuName = None
        wnd_class.lpszClassName = class_name
        wnd_class.hIconSm = None

        atom = user32.RegisterClassExW(ctypes.byref(wnd_class))
        if atom:
            self._registered_classes[class_name] = atom
        self.class_name = class_name

    @classmethod
    def _global_wnd_proc(
        cls,
        hwnd: wintypes.HWND,
        msg: int,
        w_param: int,
        l_param: int,
    ) -> int:
        if msg == WM_NCCREATE:
            create_struct = ctypes.cast(l_param, ctypes.POINTER(CREATESTRUCTW)).contents
            py_obj = ctypes.cast(
                create_struct.lpCreateParams, ctypes.POINTER(ctypes.py_object)
            ).contents.value
            cls._instances[int(hwnd)] = py_obj
            py_obj.hwnd = hwnd

        instance = cls._instances.get(int(hwnd))
        if instance is not None:
            result = instance._wnd_proc_handler(hwnd, msg, w_param, l_param)
            if result is not None:
                return result

        if msg == WM_NCDESTROY:
            cls._instances.pop(int(hwnd), None)

        return user32.DefWindowProcW(hwnd, msg, WPARAM(w_param), LPARAM(l_param))

    def _wnd_proc_handler(
        self, hwnd: wintypes.HWND, msg: int, w_param: int, l_param: int
    ) -> Optional[int]:
        if msg == WM_CREATE:
            return self._on_create()
        if msg == WM_CLOSE:
            if not self._allow_close:
                return 0  # Prevent close during update
            user32.DestroyWindow(self.hwnd)
            return 0
        if msg == WM_DESTROY:
            return 0
        if msg == 0x00138:  # WM_CTLCOLORSTATIC
            hdc = ctypes.cast(w_param, ctypes.c_void_p)
            gdi32.SetBkMode(hdc, 2)  # OPAQUE
            gdi32.SetBkColor(hdc, user32.GetSysColor(COLOR_WINDOW))
            return user32.GetSysColorBrush(COLOR_WINDOW)
        return None

    def _on_create(self) -> int:
        margin = 20
        content_width = self.width - 2 * margin - 20

        # Status label
        self.status_hwnd = user32.CreateWindowExW(
            0,
            "STATIC",
            "Preparing update...",
            WS_CHILD | WS_VISIBLE,
            margin,
            15,
            content_width,
            20,
            self.hwnd,
            wintypes.HMENU(self.STATUS_ID),
            self.h_instance,
            None,
        )
        if self.status_hwnd:
            user32.SendMessageW(self.status_hwnd, WM_SETFONT, self.default_font, True)

        # Progress bar (marquee mode)
        self.progress_hwnd = user32.CreateWindowExW(
            0,
            "msctls_progress32",
            "",
            WS_CHILD | WS_VISIBLE | PBS_MARQUEE,
            margin,
            42,
            content_width,
            16,
            self.hwnd,
            wintypes.HMENU(self.PROGRESS_ID),
            self.h_instance,
            None,
        )
        if self.progress_hwnd:
            user32.SendMessageW(
                self.progress_hwnd, PBM_SETRANGE, 0, MAKELPARAM(0, 100)
            )
            # Start marquee animation
            user32.SendMessageW(self.progress_hwnd, PBM_SETMARQUEE, 1, 40)
            self._marquee_enabled = True

        return 0

    def _create_window(self) -> None:
        screen_w = user32.GetSystemMetrics(SM_CXSCREEN)
        screen_h = user32.GetSystemMetrics(SM_CYSCREEN)
        x = max(0, (screen_w - self.width) // 2)
        y = max(0, (screen_h - self.height) // 2)

        self.hwnd = user32.CreateWindowExW(
            WS_EX_APPWINDOW,
            self.class_name,
            self.title,
            WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
            x,
            y,
            self.width,
            self.height,
            None,
            None,
            self.h_instance,
            ctypes.cast(self._lp_create_param_ptr, wintypes.LPVOID),
        )

        if self.hwnd:
            user32.ShowWindow(self.hwnd, SW_SHOWNORMAL)
            user32.UpdateWindow(self.hwnd)

    def set_status(self, text: str) -> None:
        """Update the status text."""
        if self.status_hwnd:
            user32.SetWindowTextW(self.status_hwnd, text)
            user32.InvalidateRect(self.status_hwnd, None, True)
        self.pump_messages()

    def pump_messages(self) -> bool:
        """Process pending Win32 messages. Returns False if window closed."""
        msg = wintypes.MSG()
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
            if msg.message == 0x0012:  # WM_QUIT
                return False
        return True

    def allow_close(self) -> None:
        """Allow the window to be closed."""
        self._allow_close = True

    def close(self) -> None:
        """Close the dialog."""
        self._allow_close = True
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        self.status_hwnd = None
        self.progress_hwnd = None
