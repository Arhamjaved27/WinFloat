"""Thin ctypes wrappers for the Win32 and DWM calls WinFloat needs.

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
SWP_NOZORDER = 0x0004
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
_GetWindowRect = _sig(user32.GetWindowRect, wintypes.BOOL, wintypes.HWND, ctypes.POINTER(wintypes.RECT))
_GetAsyncKeyState = _sig(user32.GetAsyncKeyState, ctypes.c_short, ctypes.c_int)
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


def window_bounds(hwnd: int) -> tuple[int, int, int, int]:
    """Visible (left, top, right, bottom) of a window in physical pixels, excluding the invisible resize border."""
    rect = wintypes.RECT()
    if _DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)) != 0:  # DWMWA_EXTENDED_FRAME_BOUNDS
        if not _GetWindowRect(hwnd, ctypes.byref(rect)):
            raise _fail("GetWindowRect")
    return rect.left, rect.top, rect.right, rect.bottom


def window_dpi(hwnd: int) -> int:
    get_dpi = getattr(user32, "GetDpiForWindow", None)  # Windows 10 1607+
    return (get_dpi(hwnd) or 96) if get_dpi else 96


def set_window_rect(hwnd: int, x: int, y: int, width: int, height: int, topmost: bool = True) -> None:
    """Move/size a window in physical pixels without activating it."""
    after = HWND_TOPMOST if topmost else 0
    if not _SetWindowPos(hwnd, after, x, y, width, height, SWP_NOACTIVATE):
        raise _fail("SetWindowPos")


def is_key_down(vk: int) -> bool:
    return bool(_GetAsyncKeyState(vk) & 0x8000)


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


def client_screen_rect(hwnd: int) -> tuple[int, int, int, int]:
    """(left, top, width, height) of a window's client area in screen pixels."""
    pt = wintypes.POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(pt)):
        raise _fail("ClientToScreen")
    width, height = client_size(hwnd)
    return pt.x, pt.y, width, height


# --- parking a minimized window (keeps a PiP source live) --------------------
#
# Windows does not draw minimized windows, and apps such as VLC stop presenting video when their window is
# off-screen. So a minimized source is restored *on-screen* but made fully transparent and click-through:
# it keeps rendering for the mirror (a DWM thumbnail ignores the source's alpha) while the user sees nothing.

SW_SHOWNORMAL, SW_SHOWMAXIMIZED, SW_SHOWNOACTIVATE, SW_SHOWMINNOACTIVE = 1, 3, 4, 7
WPF_RESTORETOMAXIMIZED = 0x2


class _Placement(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT), ("flags", wintypes.UINT), ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT), ("ptMaxPosition", wintypes.POINT), ("rcNormalPosition", wintypes.RECT),
    ]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


class ParkedWindow:
    """What park() changed, so unpark() can put it back."""

    def __init__(self, placement: _Placement, ex_style: int, layered: tuple[int, int, int] | None):
        self.placement = placement
        self.ex_style = ex_style
        self.layered = layered


_GetWindowPlacement = _sig(user32.GetWindowPlacement, wintypes.BOOL, wintypes.HWND, ctypes.POINTER(_Placement))
_SetWindowPlacement = _sig(user32.SetWindowPlacement, wintypes.BOOL, wintypes.HWND, ctypes.POINTER(_Placement))
_MonitorFromRect = _sig(user32.MonitorFromRect, wintypes.HANDLE, ctypes.POINTER(wintypes.RECT), wintypes.DWORD)
_GetMonitorInfoW = _sig(user32.GetMonitorInfoW, wintypes.BOOL, wintypes.HANDLE, ctypes.POINTER(_MonitorInfo))


def _placement(hwnd: int) -> _Placement:
    placement = _Placement()
    placement.length = ctypes.sizeof(_Placement)
    if not _GetWindowPlacement(hwnd, ctypes.byref(placement)):
        raise _fail("GetWindowPlacement")
    return placement


def _apply_placement(hwnd: int, placement: _Placement) -> None:
    if not _SetWindowPlacement(hwnd, ctypes.byref(placement)):
        raise _fail("SetWindowPlacement")


def _maximized_size(hwnd: int, near: wintypes.RECT) -> tuple[int, int]:
    """Window size (including its invisible resize border) a maximized window has on `near`'s monitor."""
    monitor = _MonitorFromRect(ctypes.byref(near), 2)  # MONITOR_DEFAULTTONEAREST
    info = _MonitorInfo()
    info.cbSize = ctypes.sizeof(_MonitorInfo)
    if not monitor or not _GetMonitorInfoW(monitor, ctypes.byref(info)):
        raise _fail("GetMonitorInfo")
    outer, frame = wintypes.RECT(), wintypes.RECT()
    if not _GetWindowRect(hwnd, ctypes.byref(outer)):
        raise _fail("GetWindowRect")
    if _DwmGetWindowAttribute(hwnd, 9, ctypes.byref(frame), ctypes.sizeof(frame)) != 0:  # EXTENDED_FRAME_BOUNDS
        frame = outer
    border_w = (outer.right - outer.left) - (frame.right - frame.left)
    border_h = (outer.bottom - outer.top) - (frame.bottom - frame.top)
    work = info.rcWork
    return work.right - work.left + border_w, work.bottom - work.top + border_h


def park(hwnd: int) -> ParkedWindow:
    """Restores a minimized window invisibly (fully transparent, click-through) without activating it."""
    original = _placement(hwnd)
    ex_style = get_ex_style(hwnd)
    layered = get_layered_attrs(hwnd)
    if ex_style & WS_EX_LAYERED and layered is None:
        raise OSError("the window draws its own transparency, so it cannot be hidden")
    parked = ParkedWindow(original, ex_style, layered)
    try:
        # hide it first so it never flashes on screen while restoring
        set_layered(hwnd, 0)
        update_ex_style(hwnd, add=WS_EX_TRANSPARENT)
        restored = _Placement.from_buffer_copy(original)
        restored.showCmd = SW_SHOWNOACTIVATE
        _apply_placement(hwnd, restored)
        if original.flags & WPF_RESTORETOMAXIMIZED:
            # it restores to its (smaller) normal size; give it the maximized size back so the mirror keeps
            # the same layout and aspect ratio
            width, height = _maximized_size(hwnd, original.rcNormalPosition)
            if not _SetWindowPos(hwnd, 0, 0, 0, width, height, SWP_NOMOVE | SWP_NOACTIVATE | SWP_NOZORDER):
                raise _fail("SetWindowPos")
    except OSError:
        unpark(hwnd, parked, minimized=True)
        raise
    return parked


def unpark(hwnd: int, parked: ParkedWindow, minimized: bool) -> None:
    """Undo park(): back to the minimized state (`minimized`) or to its normal/maximized position."""
    restored = _Placement.from_buffer_copy(parked.placement)
    if minimized:
        restored.showCmd = SW_SHOWMINNOACTIVE
    else:
        restored.showCmd = SW_SHOWMAXIMIZED if parked.placement.flags & WPF_RESTORETOMAXIMIZED else SW_SHOWNORMAL
    _apply_placement(hwnd, restored)
    if parked.layered:
        key, alpha, flags = parked.layered
        set_layered(hwnd, alpha, key, flags)
    update_ex_style(hwnd, remove=(WS_EX_TRANSPARENT | WS_EX_LAYERED) & ~parked.ex_style)


# --- posting input to another window ---------------------------------------

WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_MOUSEMOVE, WM_MOUSEWHEEL = 0x0200, 0x020A
BUTTON_MESSAGES = {  # Qt button name -> (down, up, double-click, MK_ flag)
    "left": (0x0201, 0x0202, 0x0203, 0x0001),
    "right": (0x0204, 0x0205, 0x0206, 0x0002),
    "middle": (0x0207, 0x0208, 0x0209, 0x0010),
}
EXTENDED_KEYS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x6F, 0xA3, 0xA5}
CWP_SKIPINVISIBLE, CWP_SKIPTRANSPARENT = 0x1, 0x4

_PostMessageW = _sig(user32.PostMessageW, wintypes.BOOL, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_ChildWindowFromPointEx = _sig(
    user32.ChildWindowFromPointEx, wintypes.HWND, wintypes.HWND, wintypes.POINT, wintypes.UINT
)
_MapVirtualKeyW = _sig(user32.MapVirtualKeyW, wintypes.UINT, wintypes.UINT, wintypes.UINT)


class _GuiThreadInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND), ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT),
    ]


_GetGUIThreadInfo = _sig(user32.GetGUIThreadInfo, wintypes.BOOL, wintypes.DWORD, ctypes.POINTER(_GuiThreadInfo))


def post_message(hwnd: int, msg: int, wparam: int, lparam: int) -> None:
    """Raises OSError when Windows refuses (e.g. the target runs elevated, or it has no message queue)."""
    if not _PostMessageW(hwnd, msg, wparam, lparam):
        raise _fail("PostMessage")


def make_lparam(x: int, y: int) -> int:
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def child_window_at(root: int, x: int, y: int) -> tuple[int, int, int]:
    """Deepest child of `root` at screen point (x, y): (hwnd, client x, client y) in that child."""
    hwnd = root
    for _ in range(16):  # nesting depth guard
        cx, cy = screen_to_client(hwnd, x, y)
        child = _ChildWindowFromPointEx(hwnd, wintypes.POINT(cx, cy), CWP_SKIPINVISIBLE | CWP_SKIPTRANSPARENT)
        if not child or int(child) == hwnd:
            break
        hwnd = int(child)
    cx, cy = screen_to_client(hwnd, x, y)
    return hwnd, cx, cy


def focus_window_of(hwnd: int) -> int:
    """The control that has keyboard focus inside hwnd's thread, or 0 (Windows only reports one while the window is active)."""
    info = _GuiThreadInfo()
    info.cbSize = ctypes.sizeof(_GuiThreadInfo)
    thread = _GetWindowThreadProcessId(hwnd, None)
    if thread and _GetGUIThreadInfo(thread, ctypes.byref(info)) and info.hwndFocus:
        return int(info.hwndFocus)
    return 0


def key_lparam(vk: int, down: bool, repeat: bool) -> int:
    scan = _MapVirtualKeyW(vk, 0)  # MAPVK_VK_TO_VSC
    lparam = 1 | (scan << 16) | ((1 << 24) if vk in EXTENDED_KEYS else 0)
    if not down:
        lparam |= (1 << 30) | (1 << 31)
    elif repeat:
        lparam |= 1 << 30
    return lparam


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
