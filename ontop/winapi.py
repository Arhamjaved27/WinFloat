"""Thin ctypes wrappers for the Win32 and DWM calls OnTop needs.

Functions that can fail raise OSError carrying the Win32 error text so callers
decide how to report it.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_LAYERED = 0x00080000
LWA_COLORKEY = 0x1
LWA_ALPHA = 0x2
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
GW_OWNER = 4
GA_ROOT = 2
DWMWA_CLOAKED = 14
DWM_TNP_RECTDESTINATION = 0x1
DWM_TNP_OPACITY = 0x4
DWM_TNP_VISIBLE = 0x8
DWM_TNP_SOURCECLIENTAREAONLY = 0x10
WM_HOTKEY = 0x0312
WM_STYLECHANGING = 0x007C
WM_NCHITTEST = 0x0084
HTTRANSPARENT = -1
ERROR_ALREADY_EXISTS = 183

MIN_OPACITY = 20  # below this a window is effectively invisible and hard to recover

LONG_PTR = ctypes.c_ssize_t
HTHUMBNAIL = wintypes.HANDLE
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _sig(fn, restype, *argtypes):
    fn.restype = restype
    fn.argtypes = argtypes
    return fn


_IsWindow = _sig(user32.IsWindow, wintypes.BOOL, wintypes.HWND)
_IsWindowVisible = _sig(user32.IsWindowVisible, wintypes.BOOL, wintypes.HWND)
_IsIconic = _sig(user32.IsIconic, wintypes.BOOL, wintypes.HWND)
_GetWindow = _sig(user32.GetWindow, wintypes.HWND, wintypes.HWND, wintypes.UINT)
_GetAncestor = _sig(user32.GetAncestor, wintypes.HWND, wintypes.HWND, wintypes.UINT)
_GetWindowTextLengthW = _sig(user32.GetWindowTextLengthW, ctypes.c_int, wintypes.HWND)
_GetWindowTextW = _sig(user32.GetWindowTextW, ctypes.c_int, wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
_GetClassNameW = _sig(user32.GetClassNameW, ctypes.c_int, wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
_GetWindowThreadProcessId = _sig(
    user32.GetWindowThreadProcessId, wintypes.DWORD, wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
)
_GetWindowLongPtrW = _sig(user32.GetWindowLongPtrW, LONG_PTR, wintypes.HWND, ctypes.c_int)
_SetWindowLongPtrW = _sig(user32.SetWindowLongPtrW, LONG_PTR, wintypes.HWND, ctypes.c_int, LONG_PTR)
_SetWindowPos = _sig(
    user32.SetWindowPos, wintypes.BOOL, wintypes.HWND, wintypes.HWND,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT,
)
_SetLayeredWindowAttributes = _sig(
    user32.SetLayeredWindowAttributes, wintypes.BOOL, wintypes.HWND, wintypes.COLORREF, ctypes.c_ubyte, wintypes.DWORD
)
_GetLayeredWindowAttributes = _sig(
    user32.GetLayeredWindowAttributes, wintypes.BOOL, wintypes.HWND,
    ctypes.POINTER(wintypes.COLORREF), ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(wintypes.DWORD),
)
_GetForegroundWindow = _sig(user32.GetForegroundWindow, wintypes.HWND)
_GetCursorPos = _sig(user32.GetCursorPos, wintypes.BOOL, ctypes.POINTER(wintypes.POINT))
_WindowFromPoint = _sig(user32.WindowFromPoint, wintypes.HWND, wintypes.POINT)
_GetClientRect = _sig(user32.GetClientRect, wintypes.BOOL, wintypes.HWND, ctypes.POINTER(wintypes.RECT))
_EnumWindows = _sig(user32.EnumWindows, wintypes.BOOL, WNDENUMPROC, wintypes.LPARAM)
_RegisterHotKey = _sig(user32.RegisterHotKey, wintypes.BOOL, wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
_UnregisterHotKey = _sig(user32.UnregisterHotKey, wintypes.BOOL, wintypes.HWND, ctypes.c_int)

_OpenProcess = _sig(kernel32.OpenProcess, wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_CloseHandle = _sig(kernel32.CloseHandle, wintypes.BOOL, wintypes.HANDLE)
_QueryFullProcessImageNameW = _sig(
    kernel32.QueryFullProcessImageNameW, wintypes.BOOL, wintypes.HANDLE, wintypes.DWORD,
    wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
)
_CreateMutexW = _sig(kernel32.CreateMutexW, wintypes.HANDLE, wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)

_DwmGetWindowAttribute = _sig(
    dwmapi.DwmGetWindowAttribute, ctypes.c_long, wintypes.HWND, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD
)
_DwmSetWindowAttribute = _sig(
    dwmapi.DwmSetWindowAttribute, ctypes.c_long, wintypes.HWND, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD
)
_DwmRegisterThumbnail = _sig(
    dwmapi.DwmRegisterThumbnail, ctypes.c_long, wintypes.HWND, wintypes.HWND, ctypes.POINTER(HTHUMBNAIL)
)
_DwmUnregisterThumbnail = _sig(dwmapi.DwmUnregisterThumbnail, ctypes.c_long, HTHUMBNAIL)
_DwmQueryThumbnailSourceSize = _sig(
    dwmapi.DwmQueryThumbnailSourceSize, ctypes.c_long, HTHUMBNAIL, ctypes.POINTER(wintypes.SIZE)
)


class _ThumbnailProperties(ctypes.Structure):
    _fields_ = [
        ("dwFlags", wintypes.DWORD),
        ("rcDestination", wintypes.RECT),
        ("rcSource", wintypes.RECT),
        ("opacity", ctypes.c_ubyte),
        ("fVisible", wintypes.BOOL),
        ("fSourceClientAreaOnly", wintypes.BOOL),
    ]


_DwmUpdateThumbnailProperties = _sig(
    dwmapi.DwmUpdateThumbnailProperties, ctypes.c_long, HTHUMBNAIL, ctypes.POINTER(_ThumbnailProperties)
)


def _fail(what: str) -> OSError:
    code = ctypes.get_last_error()
    return OSError(f"{what} failed: {ctypes.FormatError(code).strip()} (error {code})")


def _hresult(hr: int, what: str) -> None:
    if hr != 0:
        raise OSError(f"{what} failed (HRESULT 0x{hr & 0xFFFFFFFF:08X})")


# --- opacity helpers -------------------------------------------------------

def clamp_percent(percent: int) -> int:
    return max(MIN_OPACITY, min(100, int(percent)))


def percent_to_alpha(percent: int) -> int:
    return round(clamp_percent(percent) * 255 / 100)


def alpha_to_percent(alpha: int) -> int:
    return round(alpha * 100 / 255)


# --- window queries --------------------------------------------------------

def is_window(hwnd: int) -> bool:
    return bool(_IsWindow(hwnd))


def is_visible(hwnd: int) -> bool:
    return bool(_IsWindowVisible(hwnd))


def is_iconic(hwnd: int) -> bool:
    return bool(_IsIconic(hwnd))


def get_owner(hwnd: int) -> int:
    return int(_GetWindow(hwnd, GW_OWNER) or 0)


def window_title(hwnd: int) -> str:
    length = _GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    _GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    _GetClassNameW(hwnd, buf, 256)
    return buf.value


def window_pid(hwnd: int) -> int:
    pid = wintypes.DWORD(0)
    _GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def process_path(hwnd: int) -> str:
    """Full path of the window's executable, or '' if it cannot be queried (e.g. elevated)."""
    handle = _OpenProcess(0x1000, False, window_pid(hwnd))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        return buf.value if _QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)) else ""
    finally:
        _CloseHandle(handle)


def process_exe(hwnd: int) -> str:
    return os.path.basename(process_path(hwnd))


def set_dark_title_bar(hwnd: int) -> bool:
    """Cosmetic: dark caption on Windows 10 2004+/11. Returns False where unsupported."""
    value = ctypes.c_int(1)
    return _DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)) == 0  # DWMWA_USE_IMMERSIVE_DARK_MODE


def is_cloaked(hwnd: int) -> bool:
    cloaked = ctypes.c_int(0)
    if _DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)) != 0:
        return False
    return cloaked.value != 0


def client_size(hwnd: int) -> tuple[int, int]:
    rect = wintypes.RECT()
    if not _GetClientRect(hwnd, ctypes.byref(rect)):
        raise _fail("GetClientRect")
    return rect.right - rect.left, rect.bottom - rect.top


def foreground_window() -> int:
    return int(_GetForegroundWindow() or 0)


def cursor_pos() -> tuple[int, int]:
    pt = wintypes.POINT()
    if not _GetCursorPos(ctypes.byref(pt)):
        raise _fail("GetCursorPos")
    return pt.x, pt.y


def root_window_at(x: int, y: int) -> int:
    hwnd = _WindowFromPoint(wintypes.POINT(x, y))
    if not hwnd:
        return 0
    return int(_GetAncestor(hwnd, GA_ROOT) or hwnd)


def enum_windows() -> list[int]:
    found: list[int] = []

    @WNDENUMPROC
    def callback(hwnd, _lparam):
        found.append(int(hwnd))
        return True

    if not _EnumWindows(callback, 0):
        raise _fail("EnumWindows")
    return found


# --- window state ----------------------------------------------------------

def get_ex_style(hwnd: int) -> int:
    ctypes.set_last_error(0)
    value = _GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    if value == 0 and ctypes.get_last_error() != 0:
        raise _fail("GetWindowLongPtr")
    return value & 0xFFFFFFFF


def update_ex_style(hwnd: int, add: int = 0, remove: int = 0) -> None:
    value = (get_ex_style(hwnd) | add) & ~remove
    ctypes.set_last_error(0)
    previous = _SetWindowLongPtrW(hwnd, GWL_EXSTYLE, value)
    if previous == 0 and ctypes.get_last_error() != 0:
        raise _fail("SetWindowLongPtr")


def is_topmost(hwnd: int) -> bool:
    return bool(get_ex_style(hwnd) & WS_EX_TOPMOST)


def set_topmost(hwnd: int, on: bool) -> None:
    after = HWND_TOPMOST if on else HWND_NOTOPMOST
    if not _SetWindowPos(hwnd, after, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE):
        raise _fail("SetWindowPos")


def get_layered_attrs(hwnd: int) -> tuple[int, int, int] | None:
    """(color key, alpha, flags) of a layered window, or None if it uses UpdateLayeredWindow."""
    key, alpha, flags = wintypes.COLORREF(), ctypes.c_ubyte(), wintypes.DWORD()
    if not _GetLayeredWindowAttributes(hwnd, ctypes.byref(key), ctypes.byref(alpha), ctypes.byref(flags)):
        return None
    return key.value, alpha.value, flags.value


def set_layered(hwnd: int, alpha: int, key: int = 0, flags: int = LWA_ALPHA) -> None:
    update_ex_style(hwnd, add=WS_EX_LAYERED)
    if not _SetLayeredWindowAttributes(hwnd, key, alpha, flags):
        raise _fail("SetLayeredWindowAttributes")


class _StyleStruct(ctypes.Structure):
    _fields_ = [("styleOld", wintypes.DWORD), ("styleNew", wintypes.DWORD)]


def enforce_ex_style_bits(msg: wintypes.MSG, keep: int, drop: int = 0) -> None:
    """For a WM_STYLECHANGING message: veto removal of `keep` bits and addition of `drop` bits.

    Qt strips WS_EX_LAYERED from frameless windows it considers opaque, which would
    silently undo our opacity.
    """
    if msg.message == WM_STYLECHANGING and ctypes.c_int(msg.wParam & 0xFFFFFFFF).value == GWL_EXSTYLE:
        style = _StyleStruct.from_address(msg.lParam)
        style.styleNew = (style.styleNew | keep) & ~drop


def screen_to_client(hwnd: int, x: int, y: int) -> tuple[int, int]:
    pt = wintypes.POINT(x, y)
    if not user32.ScreenToClient(hwnd, ctypes.byref(pt)):
        raise _fail("ScreenToClient")
    return pt.x, pt.y


# --- DWM thumbnails --------------------------------------------------------

def register_thumbnail(dest_hwnd: int, source_hwnd: int) -> int:
    handle = HTHUMBNAIL()
    _hresult(_DwmRegisterThumbnail(dest_hwnd, source_hwnd, ctypes.byref(handle)), "DwmRegisterThumbnail")
    return handle.value


def unregister_thumbnail(thumb: int) -> None:
    _hresult(_DwmUnregisterThumbnail(thumb), "DwmUnregisterThumbnail")


def thumbnail_source_size(thumb: int) -> tuple[int, int]:
    size = wintypes.SIZE()
    _hresult(_DwmQueryThumbnailSourceSize(thumb, ctypes.byref(size)), "DwmQueryThumbnailSourceSize")
    return size.cx, size.cy


def update_thumbnail(
    thumb: int, dest: tuple[int, int, int, int], opacity: int = 255, visible: bool = True, client_only: bool = True
) -> None:
    """dest is (left, top, right, bottom) in physical pixels of the destination window's client area."""
    props = _ThumbnailProperties()
    props.dwFlags = DWM_TNP_RECTDESTINATION | DWM_TNP_OPACITY | DWM_TNP_VISIBLE | DWM_TNP_SOURCECLIENTAREAONLY
    props.rcDestination = wintypes.RECT(*dest)
    props.opacity = opacity
    props.fVisible = visible
    props.fSourceClientAreaOnly = client_only
    _hresult(_DwmUpdateThumbnailProperties(thumb, ctypes.byref(props)), "DwmUpdateThumbnailProperties")


# --- hotkeys / process -----------------------------------------------------

def register_hotkey(hotkey_id: int, modifiers: int, vk: int) -> None:
    if not _RegisterHotKey(None, hotkey_id, modifiers, vk):
        raise _fail("RegisterHotKey")


def unregister_hotkey(hotkey_id: int) -> None:
    _UnregisterHotKey(None, hotkey_id)


def acquire_single_instance(name: str) -> int | None:
    """Returns a mutex handle to keep alive, or None if another instance already holds it."""
    handle = _CreateMutexW(None, False, name)
    if not handle:
        raise _fail("CreateMutex")
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        _CloseHandle(handle)
        return None
    return handle
