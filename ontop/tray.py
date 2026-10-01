"""System tray icon and menu."""
from __future__ import annotations

import logging
import os

from PyQt5.QtCore import QRectF, Qt, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMenu, QSlider, QSystemTrayIcon, QWidget, QWidgetAction,
)

from . import autostart, winapi, windows_list
from .controller import Controller, Target

log = logging.getLogger(__name__)

MAX_LABEL = 60


ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_icon(size: int) -> QPixmap:
    """The app icon drawn natively at `size` px (designed on a 64-unit grid), so it stays sharp at any size."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 64, size / 64)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#2b3140"))
    p.drawRoundedRect(QRectF(4, 8, 56, 48), 8, 8)
    p.setBrush(QColor("#4c9aff"))
    p.drawRoundedRect(QRectF(26, 28, 26, 20), 4, 4)
    p.end()
    return pix


def make_icon() -> QIcon:
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(render_icon(size))
    return icon


def _short(text: str) -> str:
    return text if len(text) <= MAX_LABEL else text[: MAX_LABEL - 1] + "…"


class Tray:
    def __init__(self, controller: Controller, settings_path: str, on_open):
        self._ctrl = controller
        self._settings_path = settings_path
        self._on_open = on_open
        self._icon = QSystemTrayIcon(make_icon())
        self._icon.setToolTip("WinFloat")
        self._menu = QMenu()
        self._menu.aboutToShow.connect(self._rebuild)
        self._icon.setContextMenu(self._menu)
        self._icon.activated.connect(self._on_activated)
        controller.notify.connect(self.notify)
        self._icon.show()

    @property
    def available(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def notify(self, message: str) -> None:
        self._icon.showMessage("WinFloat", message, QSystemTrayIcon.Information, 5000)

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._on_open()

    def _rebuild(self) -> None:
        menu = self._menu
        menu.clear()
        windows = windows_list.list_windows()

        menu.addAction("Open WinFloat").triggered.connect(lambda _=False: self._on_open())
        menu.addSeparator()
        pip_menu = menu.addMenu("PiP a window")
        pin_menu = menu.addMenu("Pin on top / unpin a window")
        for win in windows:
            label = _short(f"{win.title}  —  {win.exe}" if win.exe else win.title)
            pip_menu.addAction(label).triggered.connect(lambda _=False, h=win.hwnd: self._ctrl.open_pip(h))
            pin = pin_menu.addAction(label)
            pin.setCheckable(True)
            pin.setChecked(self._is_topmost(win.hwnd))
            pin.triggered.connect(lambda _=False, h=win.hwnd: self._ctrl.toggle_topmost(Target("pin", h)))
        for sub in (pip_menu, pin_menu):
            sub.setEnabled(bool(windows))

        items = self._ctrl.active_items()
        if items:
            menu.addSeparator()
            for item in items:
                self._add_active(menu, item)

        menu.addSeparator()
        click = menu.addAction("Click-through on all PiPs")
        click.setCheckable(True)
        click.setChecked(self._ctrl.any_click_through)
        click.setEnabled(self._ctrl.has_pips)
        click.triggered.connect(lambda _=False: self._ctrl.toggle_click_through_all())
        menu.addAction("Close all PiPs and restore pinned windows").triggered.connect(lambda _=False: self._ctrl.reset_all())

        menu.addSeparator()
        start = menu.addAction("Start with Windows")
        start.setCheckable(True)
        start.setChecked(autostart.is_enabled())
        start.triggered.connect(self._set_autostart)
        menu.addAction("Open settings file").triggered.connect(
            lambda _=False: QDesktopServices.openUrl(QUrl.fromLocalFile(self._settings_path))
        )
        menu.addAction("Quit").triggered.connect(QApplication.quit)

    @staticmethod
    def _is_topmost(hwnd: int) -> bool:
        try:
            return winapi.is_topmost(hwnd)
        except OSError:
            return False  # window vanished while the menu was building

    def _add_active(self, menu: QMenu, item) -> None:
        kind = "PiP" if item.target.kind == "pip" else "Pinned"
        sub = menu.addMenu(_short(f"{kind}: {item.title}"))

        slider_row = QWidget()
        row = QHBoxLayout(slider_row)
        row.setContentsMargins(12, 4, 12, 4)
        row.addWidget(QLabel("Opacity"))
        slider = QSlider(Qt.Horizontal)
        slider.setRange(winapi.MIN_OPACITY, 100)
        slider.setValue(item.opacity)
        slider.valueChanged.connect(lambda v, t=item.target: self._ctrl.set_opacity(t, v))
        row.addWidget(slider)
        action = QWidgetAction(sub)
        action.setDefaultWidget(slider_row)
        sub.addAction(action)

        top = sub.addAction("Always on top")
        top.setCheckable(True)
        top.setChecked(item.topmost)
        top.triggered.connect(lambda _=False, t=item.target: self._ctrl.toggle_topmost(t))
        if item.target.kind == "pip":
            ghost = sub.addAction("Click-through")
            ghost.setCheckable(True)
            ghost.setChecked(item.click_through)
            ghost.triggered.connect(
                lambda checked, s=item.target.hwnd: self._ctrl.set_click_through(s, checked)
            )
            sub.addAction("Close PiP").triggered.connect(lambda _=False, s=item.target.hwnd: self._ctrl.close_pip(s))
        else:
            sub.addAction("Restore window").triggered.connect(lambda _=False, h=item.target.hwnd: self._ctrl.unpin(h))

    def _set_autostart(self, enabled: bool) -> None:
        try:
            autostart.set_enabled(enabled)
        except OSError as exc:
            log.error("Could not change autostart: %s", exc)
            self.notify(f"Could not change start-with-Windows: {exc}")
