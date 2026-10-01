"""Owns every PiP window and pinned window; the tray and hotkeys both drive this."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import NamedTuple

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtGui import QCursor, QGuiApplication

from . import winapi, windows_list
from .pin_manager import PinManager
from .pip_window import DEFAULT_W, PipWindow
from .settings import Settings

log = logging.getLogger(__name__)

SCREEN_MARGIN = 24
PRUNE_MS = 2000
SAVE_DELAY_MS = 1000


class Target(NamedTuple):
    kind: str  # "pip": hwnd is the mirrored source window; "pin": hwnd is the real window
    hwnd: int


@dataclass(frozen=True)
class ActiveItem:
    target: Target
    title: str
    opacity: int
    topmost: bool
    click_through: bool
    path: str = ""


class Controller(QObject):
    notify = pyqtSignal(str)  # user-facing message, shown by the tray

    def __init__(self, settings: Settings, pins: PinManager, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._pins = pins
        self._pips: dict[int, PipWindow] = {}
        self._save_timer = QTimer(self, singleShot=True, interval=SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self._save)
        self._prune_timer = QTimer(self, interval=PRUNE_MS)
        self._prune_timer.timeout.connect(pins.prune)
        self._prune_timer.start()

    # -- PiP ----------------------------------------------------------------

    def open_pip(self, source: int) -> None:
        existing = self._pips.get(source)
        if existing:
            existing.raise_()
            return
        info = windows_list.describe(source)
        if info is None:
            self.notify.emit("That window can't be shown in PiP (it may have closed).")
            return
        try:
            pip = PipWindow(source, info.title)
        except OSError as exc:
            log.error("PiP for %#x failed: %s", source, exc)
            self.notify.emit(f"Could not start PiP: {exc}")
            return
        profile = self._settings.profile(info.exe)
        pip.set_opacity(profile.get("pip_opacity", 100))
        self._place(pip, profile.get("pip_geometry"))
        pip.closed.connect(lambda src, exe=info.exe: self._on_pip_closed(src, exe))
        self._pips[source] = pip
        pip.show()

    def close_pip(self, source: int) -> None:
        pip = self._pips.get(source)
        if pip:
            pip.close()

    def _on_pip_closed(self, source: int, exe: str) -> None:
        pip = self._pips.pop(source, None)
        if pip:
            self._settings.update_profile(exe, **pip.snapshot())
            self._save_later()

    def _place(self, pip: PipWindow, saved) -> None:
        if isinstance(saved, list) and len(saved) == 3 and all(isinstance(v, int) for v in saved):
            x, y, w = saved
            pip.place(x, y, w)
            if any(s.availableGeometry().intersects(pip.frameGeometry()) for s in QGuiApplication.screens()):
                return
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        pip.place(0, 0, DEFAULT_W)
        offset = SCREEN_MARGIN * len(self._pips)
        pip.move(area.right() - pip.width() - SCREEN_MARGIN - offset, area.bottom() - pip.height() - SCREEN_MARGIN - offset)

    # -- per-target operations (tray and hotkeys) ---------------------------

    def is_topmost(self, target: Target) -> bool:
        if target.kind == "pip":
            return self._pips[target.hwnd].is_topmost()
        return winapi.is_topmost(target.hwnd)

    def get_opacity(self, target: Target) -> int:
        if target.kind == "pip":
            return self._pips[target.hwnd].opacity
        return self._pins.opacity(target.hwnd)

    def toggle_topmost(self, target: Target) -> None:
        if target.kind == "pin" and self._pins.is_managed(target.hwnd) and winapi.is_topmost(target.hwnd):
            self.unpin(target.hwnd)  # unpinning puts the window back exactly as found, opacity included
            return
        was_managed = target.kind == "pin" and self._pins.is_managed(target.hwnd)
        turn_on = not self.is_topmost(target)
        if self._run(self._set_topmost, target, turn_on) and target.kind == "pin" and turn_on and not was_managed:
            self._apply_saved_pin_opacity(target.hwnd)

    def set_opacity(self, target: Target, percent: int) -> None:
        if self._run(self._write_opacity, target, percent) and target.kind == "pin":
            exe = winapi.process_exe(target.hwnd)
            self._settings.update_profile(exe, pin_opacity=winapi.clamp_percent(percent))
            self._save_later()

    def adjust_opacity(self, target: Target, delta: int) -> None:
        self.set_opacity(target, self.get_opacity(target) + delta)

    def set_click_through(self, source: int, on: bool) -> None:
        self._pips[source].set_click_through(on)

    def unpin(self, hwnd: int) -> None:
        try:
            self._pins.restore(hwnd)
        except OSError as exc:
            self.notify.emit(f"Could not fully restore the window: {exc}")

    def _set_topmost(self, target: Target, on: bool) -> None:
        if target.kind == "pip":
            self._pips[target.hwnd].set_topmost(on)
        else:
            self._pins.set_topmost(target.hwnd, on)

    def _write_opacity(self, target: Target, percent: int) -> None:
        if target.kind == "pip":
            self._pips[target.hwnd].set_opacity(percent)
        else:
            self._pins.set_opacity(target.hwnd, percent)

    def _run(self, operation, target: Target, value) -> bool:
        """Runs a window operation, reporting an OS refusal (e.g. an elevated window) to the user."""
        try:
            operation(target, value)
        except OSError as exc:
            log.warning("%s on %s failed: %s", operation.__name__, target, exc)
            self.notify.emit(f"Windows refused the change: {exc}")
            return False
        return True

    def _apply_saved_pin_opacity(self, hwnd: int) -> None:
        saved = self._settings.profile(winapi.process_exe(hwnd)).get("pin_opacity")
        if isinstance(saved, int) and saved < 100:
            try:
                self._pins.set_opacity(hwnd, saved)
            except OSError as exc:
                log.warning("Saved opacity not applied to %#x: %s", hwnd, exc)

    # -- hotkey actions -----------------------------------------------------

    def handle_hotkey(self, action: str) -> None:
        if action == "pip_foreground":
            self._toggle_pip_foreground()
        elif action == "toggle_click_through":
            self.toggle_click_through_all()
        elif action == "reset_all":
            self.reset_all()
        else:
            target = self.resolve_target()
            if target is None:
                self.notify.emit("No window to act on - focus a window or point at one first.")
            elif action == "toggle_topmost":
                self.toggle_topmost(target)
            elif action == "opacity_up":
                self.adjust_opacity(target, self._settings.opacity_step)
            elif action == "opacity_down":
                self.adjust_opacity(target, -self._settings.opacity_step)
            else:
                log.error("Unknown hotkey action %r", action)

    def resolve_target(self) -> Target | None:
        """PiP or pinned window under the cursor, else the foreground window."""
        cursor = QCursor.pos()
        for source, pip in self._pips.items():
            if pip.frameGeometry().contains(cursor):
                return Target("pip", source)
        under = winapi.root_window_at(*winapi.cursor_pos())
        if under and self._pins.is_managed(under):
            return Target("pin", under)
        for source, pip in self._pips.items():
            if pip.isActiveWindow():
                return Target("pip", source)
        foreground = winapi.foreground_window()
        if foreground and windows_list.describe(foreground):
            return Target("pin", foreground)
        return None

    def _toggle_pip_foreground(self) -> None:
        for pip in self._pips.values():
            if pip.isActiveWindow():
                pip.close()
                return
        foreground = winapi.foreground_window()
        if foreground in self._pips:
            self.close_pip(foreground)
        else:
            self.open_pip(foreground)

    def toggle_click_through_all(self) -> None:
        turn_on = not any(p.click_through for p in self._pips.values())
        for pip in self._pips.values():
            pip.set_click_through(turn_on)
        if not self._pips:
            self.notify.emit("No PiP windows are open.")

    def reset_all(self) -> None:
        for pip in list(self._pips.values()):
            pip.close()
        failed = self._pins.restore_all()
        if failed:
            self.notify.emit(f"{failed} window(s) could not be fully restored; see the log.")

    # -- state for the tray -------------------------------------------------

    @property
    def has_pips(self) -> bool:
        return bool(self._pips)

    @property
    def any_click_through(self) -> bool:
        return any(p.click_through for p in self._pips.values())

    def active_items(self) -> list[ActiveItem]:
        items = [
            ActiveItem(Target("pip", src), winapi.window_title(src), pip.opacity, pip.is_topmost(),
                       pip.click_through, winapi.process_path(src))
            for src, pip in self._pips.items()
        ]
        for hwnd in self._pins.managed():
            if winapi.is_window(hwnd):
                items.append(
                    ActiveItem(Target("pin", hwnd), winapi.window_title(hwnd), self._pins.opacity(hwnd),
                               winapi.is_topmost(hwnd), False, winapi.process_path(hwnd))
                )
        return items

    # -- persistence / shutdown --------------------------------------------

    def _save_later(self) -> None:
        self._save_timer.start()

    def _save(self) -> None:
        try:
            self._settings.save()
        except OSError as exc:
            log.error("Could not save settings: %s", exc)

    def shutdown(self) -> None:
        self._prune_timer.stop()
        self._save_timer.stop()
        self.reset_all()
        self._save()
