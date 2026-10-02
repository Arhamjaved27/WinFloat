"""Forwards mouse and keyboard input from a PiP window to the window it mirrors.

Input is *posted* to the source's message queue, so the source never has to come to the front.
Apps that read raw input or the physical keyboard state (games, some video players) ignore it,
and modifier keys cannot be reproduced this way, so only plain keys are forwarded.
"""
from __future__ import annotations

import logging

from . import winapi

log = logging.getLogger(__name__)


class InputForwarder:
    def __init__(self, source_hwnd: int):
        self._source = source_hwnd
        self._target = 0       # child window that received the current mouse press
        self._focus = 0        # last keyboard-focus control seen while the source was active
        self._button = ""
        self._warned = False

    def mouse_press(self, button: str, x: int, y: int, double: bool = False) -> None:
        """x, y: screen position on the source window."""
        down, _up, dbl, mk = winapi.BUTTON_MESSAGES[button]

        def send() -> None:
            target, cx, cy = winapi.child_window_at(self._source, x, y)
            winapi.post_message(target, dbl if double else down, mk, winapi.make_lparam(cx, cy))
            self._target, self._button = target, button

        self._guard(send)

    def mouse_move(self, x: int, y: int) -> None:
        if not self._target:
            return
        mk = winapi.BUTTON_MESSAGES[self._button][3]

        def send() -> None:
            cx, cy = winapi.screen_to_client(self._target, x, y)
            winapi.post_message(self._target, winapi.WM_MOUSEMOVE, mk, winapi.make_lparam(cx, cy))

        self._guard(send)

    def mouse_release(self, x: int, y: int) -> None:
        if not self._target:
            return
        target, button = self._target, self._button
        self._target, self._button = 0, ""
        up = winapi.BUTTON_MESSAGES[button][1]

        def send() -> None:
            cx, cy = winapi.screen_to_client(target, x, y)
            winapi.post_message(target, up, 0, winapi.make_lparam(cx, cy))

        self._guard(send)

    def wheel(self, delta: int, x: int, y: int) -> None:
        def send() -> None:
            target, _cx, _cy = winapi.child_window_at(self._source, x, y)
            winapi.post_message(target, winapi.WM_MOUSEWHEEL, (delta & 0xFFFF) << 16, winapi.make_lparam(x, y))

        self._guard(send)

    def remember_focus(self) -> None:
        """Windows reports the focused control only while its window is active, so remember it for later."""
        self._focus = winapi.focus_window_of(self._source) or self._focus

    def key(self, vk: int, down: bool, repeat: bool) -> None:
        def send() -> None:
            self.remember_focus()
            target = self._focus if self._focus and winapi.is_window(self._focus) else self._source
            msg = winapi.WM_KEYDOWN if down else winapi.WM_KEYUP
            winapi.post_message(target, msg, vk, winapi.key_lparam(vk, down, repeat))

        self._guard(send)

    def _guard(self, send) -> None:
        try:
            send()
        except OSError as exc:  # source closed, or Windows refuses input to an elevated window
            if not self._warned:
                self._warned = True
                log.warning("Input could not be forwarded to %#x: %s", self._source, exc)
