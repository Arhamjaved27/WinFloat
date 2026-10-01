"""Finds the windows a user would consider "real" application windows."""
from __future__ import annotations

import os
from dataclasses import dataclass

from . import winapi

SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    title: str
    exe: str
    path: str = ""


def is_candidate(
    *, visible: bool, has_owner: bool, ex_style: int, title: str, cloaked: bool,
    class_name: str, pid: int, own_pid: int,
) -> bool:
    return (
        visible
        and not has_owner
        and not ex_style & winapi.WS_EX_TOOLWINDOW
        and bool(title.strip())
        and not cloaked
        and class_name not in SHELL_CLASSES
        and pid != own_pid
    )


def describe(hwnd: int, own_pid: int | None = None) -> WindowInfo | None:
    """WindowInfo if hwnd is a manageable application window, else None."""
    if not winapi.is_window(hwnd):
        return None
    title = winapi.window_title(hwnd)
    try:
        ex_style = winapi.get_ex_style(hwnd)
    except OSError:
        return None  # window was destroyed between the checks
    ok = is_candidate(
        visible=winapi.is_visible(hwnd),
        has_owner=bool(winapi.get_owner(hwnd)),
        ex_style=ex_style,
        title=title,
        cloaked=winapi.is_cloaked(hwnd),
        class_name=winapi.class_name(hwnd),
        pid=winapi.window_pid(hwnd),
        own_pid=os.getpid() if own_pid is None else own_pid,
    )
    if not ok:
        return None
    path = winapi.process_path(hwnd)
    return WindowInfo(hwnd, title, os.path.basename(path), path)


def list_windows() -> list[WindowInfo]:
    own_pid = os.getpid()
    found = (describe(hwnd, own_pid) for hwnd in winapi.enum_windows())
    return sorted((w for w in found if w), key=lambda w: w.title.lower())
