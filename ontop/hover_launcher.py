"""Hover launcher: a thin arrow appears at the top-centre of any window; clicking it opens a small action panel.

All geometry from Win32 is in physical pixels, so the arrow and panel are positioned natively
and sized by the target window's DPI.
"""
from __future__ import annotations

import logging
import time

from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from . import winapi, windows_list
from .controller import Controller, Target
from .main_window import ACCENT, ACCENT_SOFT, BORDER, CARD, TEXT
from .windows_list import WindowInfo

log = logging.getLogger(__name__)

ARROW_W, ARROW_H = 56, 18   # logical px
ZONE_W, ZONE_H = 260, 36    # cursor trigger zone at the window's top-centre, logical px
MIN_WINDOW_W = 320          # ignore tiny windows (popups, widgets)
TICK_MS = 100
GRACE_S = 0.4               # keep the arrow briefly after the cursor leaves, to avoid flicker
VK_LBUTTON = 0x01

PANEL_STYLE = f"""
* {{ font-family: "Segoe UI Variable Text", "Segoe UI"; font-size: 13px; color: {TEXT}; }}
QFrame#panelCard {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px; }}
QToolTip {{ background: #202533; color: {TEXT}; border: 1px solid #2d3445; padding: 4px 8px; }}
"""


class ArrowTab(QWidget):
    """The thin downward arrow. Never takes focus, so the target window stays active."""

    clicked = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.resize(ARROW_W, ARROW_H)
        self._hover = False
        self._open = False

    def set_open(self, is_open: bool) -> None:
        self._open = is_open
        self.update()

    def enterEvent(self, _event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, _event) -> None:
        self._hover = False
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        body = QPainterPath()
        body.addRoundedRect(QRectF(0.5, -12, w - 1, h + 11.5), 9, 9)  # top corners hang off-screen: flat top edge
        fill = QColor(ACCENT) if (self._hover or self._open) else QColor("#1d2a4a")
        fill.setAlpha(235)
        p.fillPath(body, fill)
        p.setPen(QPen(QColor(ACCENT), 1))
        p.drawPath(body)
        p.setPen(QPen(QColor("white"), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cx, cy, d = w / 2, h / 2, 3.0 if not self._open else -3.0
        p.drawPolyline(QPointF(cx - 7, cy - d), QPointF(cx, cy + d), QPointF(cx + 7, cy - d))


class IconButton(QPushButton):
    """A square button whose icon is drawn with QPainter (no image files). Checked = feature is on."""

    SIZE = 42

    def __init__(self, kind: str, tooltip: str, checkable: bool = False) -> None:
        super().__init__()
        self._kind = kind
        self._tip = tooltip
        self.setCheckable(checkable)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip(tooltip)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.isChecked():
            bg, fg = QColor(ACCENT_SOFT), QColor("#8fb2ff")
        else:
            bg, fg = QColor("#222838" if self.underMouse() else "transparent"), QColor("#c3cad8")
        if self.isDown():
            bg = bg.darker(120)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10)
        p.fillPath(path, bg)
        if self.isChecked():
            p.setPen(QPen(QColor(ACCENT), 1))
            p.drawPath(path)
        p.translate(self.width() / 2 - 11, self.height() / 2 - 11)  # 22x22 icon box
        p.setPen(QPen(fg, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        getattr(self, f"_draw_{self._kind}")(p, fg)

    @staticmethod
    def _draw_pip(p: QPainter, fg: QColor) -> None:
        p.drawRoundedRect(QRectF(1, 3, 20, 16), 3, 3)
        p.setBrush(fg)
        p.drawRoundedRect(QRectF(11, 10, 8, 6), 1.5, 1.5)  # the small floating window

    @staticmethod
    def _draw_top(p: QPainter, _fg: QColor) -> None:
        p.drawLine(QPointF(4, 3), QPointF(18, 3))          # the "ceiling"
        p.drawLine(QPointF(11, 19), QPointF(11, 8))        # arrow stem
        p.drawPolyline(QPointF(5.5, 12.5), QPointF(11, 7), QPointF(16.5, 12.5))

    @staticmethod
    def _draw_gear(p: QPainter, _fg: QColor) -> None:
        p.translate(11, 11)
        for _ in range(8):
            p.drawLine(QPointF(0, -7.6), QPointF(0, -10))  # teeth
            p.rotate(45)
        p.drawEllipse(QPointF(0, 0), 6.4, 6.4)
        p.drawEllipse(QPointF(0, 0), 2.4, 2.4)


class ActionPanel(QWidget):
    """Small horizontal icon bar under the arrow. Closes itself on any click outside."""

    closed = pyqtSignal()

    def __init__(self, controller: Controller, open_settings) -> None:
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(PANEL_STYLE)
        self._ctrl = controller
        self._open_settings = open_settings
        self._hwnd = 0

        card = QFrame()
        card.setObjectName("panelCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(6)
        self._pip = IconButton("pip", "Picture-in-Picture", checkable=True)
        self._top = IconButton("top", "Always on top", checkable=True)
        self._settings = IconButton("gear", "Settings")
        self._pip.clicked.connect(self._toggle_pip)
        self._top.clicked.connect(self._toggle_top)
        self._settings.clicked.connect(self._show_settings)
        for button in (self._pip, self._top, self._settings):
            row.addWidget(button)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 8)
        outer.addWidget(card)

    def show_for(self, info: WindowInfo, centre_x: int, top_y: int, dpr: float) -> None:
        self._hwnd = info.hwnd
        self._sync()
        self.adjustSize()
        width, height = round(self.width() * dpr), round(self.height() * dpr)
        self.show()
        winapi.set_window_rect(int(self.winId()), centre_x - width // 2, top_y, width, height)

    def _sync(self) -> None:
        self._pip.setChecked(self._ctrl.is_pip_open(self._hwnd))
        try:
            self._top.setChecked(winapi.is_topmost(self._hwnd))
        except OSError:
            self._top.setChecked(False)  # the window vanished; the next hover tick closes the panel

    def _toggle_pip(self) -> None:
        if self._ctrl.is_pip_open(self._hwnd):
            self._ctrl.close_pip(self._hwnd)
        else:
            self._ctrl.open_pip(self._hwnd)
        self._sync()

    def _toggle_top(self) -> None:
        self._ctrl.toggle_topmost(Target("pin", self._hwnd))
        self._sync()

    def _show_settings(self) -> None:
        self.close()
        self._open_settings()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.closed.emit()


class HoverLauncher:
    def __init__(self, controller: Controller, open_settings) -> None:
        self._tab = ArrowTab()
        self._panel = ActionPanel(controller, open_settings)
        self._tab.clicked.connect(self._toggle_panel)
        self._panel.closed.connect(self._on_panel_closed)
        self._target: WindowInfo | None = None
        self._bounds: tuple[int, int, int] | None = None  # target (left, top, right) when the arrow was placed
        self._dpr = 1.0
        self._tab_rect: tuple[int, int, int, int] | None = None
        self._left_at: float | None = None
        self._timer = QTimer(interval=TICK_MS)
        self._timer.timeout.connect(self._tick)

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self._timer.start()
        else:
            self._timer.stop()
            self._panel.close()
            self._hide_tab()

    # -- tracking -----------------------------------------------------------

    def _tick(self) -> None:
        try:
            pos = winapi.cursor_pos()
        except OSError:
            return  # no cursor access (e.g. secure desktop); try again next tick
        if self._panel.isVisible():
            self._watch_panel()
            return
        if self._over_tab(pos):
            self._left_at = None
            return
        found = self._candidate_at(pos)
        if found:
            self._left_at = None
            self._show_tab(*found)
        elif self._tab.isVisible():
            now = time.monotonic()
            self._left_at = self._left_at or now
            if now - self._left_at >= GRACE_S:
                self._hide_tab()

    def _over_tab(self, pos: tuple[int, int]) -> bool:
        if not (self._tab.isVisible() and self._tab_rect):
            return False
        left, top, right, bottom = self._tab_rect
        return left <= pos[0] < right and top <= pos[1] < bottom

    def _candidate_at(self, pos: tuple[int, int]):
        if winapi.is_key_down(VK_LBUTTON):
            return None  # dragging or clicking: stay out of the way
        root = winapi.root_window_at(*pos)
        if not root:
            return None
        try:
            left, top, right, _bottom = winapi.window_bounds(root)
        except OSError:
            return None  # window disappeared under the cursor
        dpr = winapi.window_dpi(root) / 96
        centre = (left + right) / 2
        if not (top <= pos[1] < top + ZONE_H * dpr and abs(pos[0] - centre) <= ZONE_W * dpr / 2):
            return None
        if right - left < MIN_WINDOW_W * dpr:
            return None
        info = windows_list.describe(root)
        return (info, (left, top, right), dpr) if info else None

    # -- arrow / panel ------------------------------------------------------

    def _show_tab(self, info: WindowInfo, bounds: tuple[int, int, int], dpr: float) -> None:
        if self._tab.isVisible() and self._target == info and self._bounds == bounds:
            return
        left, top, right = bounds
        width, height = round(ARROW_W * dpr), round(ARROW_H * dpr)
        x, y = (left + right) // 2 - width // 2, top
        self._target, self._bounds, self._dpr = info, bounds, dpr
        self._tab_rect = (x, y, x + width, y + height)
        if not self._tab.isVisible():
            self._tab.show()
        winapi.set_window_rect(int(self._tab.winId()), x, y, width, height)

    def _hide_tab(self) -> None:
        self._tab.hide()
        self._tab_rect = self._target = self._bounds = self._left_at = None

    def _toggle_panel(self) -> None:
        if self._panel.isVisible():
            self._panel.close()
            return
        if not (self._target and self._tab_rect):
            return
        left, top, right, bottom = self._tab_rect
        self._tab.set_open(True)
        self._panel.show_for(self._target, (left + right) // 2, bottom + round(2 * self._dpr), self._dpr)

    def _on_panel_closed(self) -> None:
        self._tab.set_open(False)
        self._left_at = time.monotonic()  # let the arrow fade out if the cursor is elsewhere

    def _watch_panel(self) -> None:
        """Close the panel if its window moved or went away, since the panel is anchored to it."""
        target = self._target
        if target is None or not winapi.is_window(target.hwnd):
            self._panel.close()
            return
        try:
            left, top, right, _bottom = winapi.window_bounds(target.hwnd)
        except OSError:
            self._panel.close()
            return
        if (left, top, right) != self._bounds:
            self._panel.close()
