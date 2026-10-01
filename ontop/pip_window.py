"""Mirror mode: a small floating window showing a live DWM thumbnail of another window.

A DWM thumbnail is composed above every child widget of its destination window, so the
controls live in a strip above the video instead of overlaying it.
"""
from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes

from PyQt5.QtCore import QRect, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QSlider, QToolButton, QWidget

from . import winapi

log = logging.getLogger(__name__)

STRIP_H = 28
MIN_W = 180
DEFAULT_W = 360
EDGE = 6
POLL_MS = 500

LEFT, RIGHT, TOP, BOTTOM = 1, 2, 4, 8

STYLE = """
#strip { background: #1d2026; }
QLabel { color: #c9d1dc; font-size: 11px; }
QToolButton { color: #c9d1dc; background: transparent; border: none; border-radius: 4px;
              min-width: 22px; max-width: 22px; min-height: 20px; max-height: 20px; font-size: 12px; }
QToolButton:hover { background: #2e343e; }
QToolButton:checked { color: #4c9aff; }
#close:hover { background: #c0392b; color: white; }
QSlider { max-width: 70px; min-width: 70px; }
QSlider::groove:horizontal { height: 4px; background: #3a414d; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #4c9aff; border-radius: 2px; }
QSlider::handle:horizontal { width: 10px; margin: -4px 0; background: #e6ebf2; border-radius: 5px; }
"""


def resized_rect(
    edges: int, rect: tuple[int, int, int, int], dx: int, dy: int, aspect: float,
    strip_h: int = STRIP_H, min_w: int = MIN_W, max_w: int | None = None,
) -> tuple[int, int, int, int]:
    """New (x, y, w, h) when dragging `edges` of `rect` by (dx, dy), keeping the video aspect ratio."""
    x, y, w, h = rect
    if edges & RIGHT:
        new_w = w + dx
    elif edges & LEFT:
        new_w = w - dx
    else:
        new_h = h - strip_h + (dy if edges & BOTTOM else -dy)
        new_w = round(new_h * aspect)
    new_w = max(min_w, new_w)
    if max_w:
        new_w = min(new_w, max_w)
    new_h = strip_h + round(new_w / aspect)
    if edges & LEFT:
        x += w - new_w
    if edges & TOP:
        y += h - new_h
    return x, y, new_w, new_h


def _cursor_for(edges: int) -> Qt.CursorShape | None:
    if edges in (LEFT | TOP, RIGHT | BOTTOM):
        return Qt.SizeFDiagCursor
    if edges in (RIGHT | TOP, LEFT | BOTTOM):
        return Qt.SizeBDiagCursor
    if edges in (LEFT, RIGHT):
        return Qt.SizeHorCursor
    if edges in (TOP, BOTTOM):
        return Qt.SizeVerCursor
    return None


class PipWindow(QWidget):
    closed = pyqtSignal(int)  # source hwnd

    def __init__(self, source_hwnd: int, title: str):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setStyleSheet(STYLE)
        self.source_hwnd = source_hwnd
        self._click_through = False  # read by nativeEvent, which Qt calls during window creation
        self._hwnd = int(self.winId())  # forces creation of the native window
        self._thumb: int | None = None
        self._minimized = winapi.is_iconic(source_hwnd)
        self._opacity = 100
        self._drag: tuple[int, object, QRect] | None = None
        self._poll_warned = False
        self._build_strip(title)

        self._thumb = winapi.register_thumbnail(self._hwnd, source_hwnd)
        self._source_size = self._query_size() or (16, 9)
        self.set_opacity(100)  # makes the window layered so click-through works later
        self.resize(DEFAULT_W, self._height_for(DEFAULT_W))

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(POLL_MS)

    # -- public API ---------------------------------------------------------

    @property
    def opacity(self) -> int:
        return self._opacity

    @property
    def click_through(self) -> bool:
        return self._click_through

    def is_topmost(self) -> bool:
        return winapi.is_topmost(self._hwnd)

    def set_topmost(self, on: bool) -> None:
        winapi.set_topmost(self._hwnd, on)
        self._pin_btn.setChecked(on)

    def set_opacity(self, percent: int) -> None:
        percent = winapi.clamp_percent(percent)
        winapi.set_layered(self._hwnd, winapi.percent_to_alpha(percent))
        self._opacity = percent
        self._slider.blockSignals(True)
        self._slider.setValue(percent)
        self._slider.blockSignals(False)

    def set_click_through(self, on: bool) -> None:
        self._click_through = on
        self._ghost_btn.setChecked(on)
        self.update()
        self._update_thumbnail()

    def place(self, x: int, y: int, width: int) -> None:
        width = max(MIN_W, width)
        self.setGeometry(x, y, width, self._height_for(width))

    def snapshot(self) -> dict:
        return {"pip_geometry": [self.x(), self.y(), self.width()], "pip_opacity": self._opacity}

    # -- construction -------------------------------------------------------

    def _build_strip(self, title: str) -> None:
        strip = QWidget(self)
        strip.setObjectName("strip")
        strip.setMouseTracking(True)
        self._strip = strip
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(EDGE + 2, 0, EDGE + 2, 0)
        layout.setSpacing(4)

        self._title = QLabel(title)
        self._title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(winapi.MIN_OPACITY, 100)
        self._slider.setToolTip("Opacity")
        self._slider.valueChanged.connect(self.set_opacity)
        self._ghost_btn = self._button("◌", "Click-through: clicks on the video pass to the window underneath", checkable=True)
        self._ghost_btn.clicked.connect(self.set_click_through)
        self._pin_btn = self._button("▲", "Keep on top", checkable=True)
        self._pin_btn.setChecked(True)
        self._pin_btn.clicked.connect(self.set_topmost)
        close_btn = self._button("✕", "Close", name="close")
        close_btn.clicked.connect(self.close)

        layout.addWidget(self._title, 1)
        for widget in (self._slider, self._ghost_btn, self._pin_btn, close_btn):
            layout.addWidget(widget)

    @staticmethod
    def _button(text: str, tip: str, checkable: bool = False, name: str = "") -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setCheckable(checkable)
        btn.setFocusPolicy(Qt.NoFocus)
        if name:
            btn.setObjectName(name)
        return btn

    # -- geometry -----------------------------------------------------------

    @property
    def _aspect(self) -> float:
        w, h = self._source_size
        return w / h

    def _height_for(self, width: int) -> int:
        return STRIP_H + round(width / self._aspect)

    def _query_size(self) -> tuple[int, int] | None:
        try:
            w, h = winapi.thumbnail_source_size(self._thumb)
        except OSError as exc:
            if not self._poll_warned:
                log.warning("Cannot read source size of %#x: %s", self.source_hwnd, exc)
                self._poll_warned = True
            return None
        return (w, h) if w > 0 and h > 0 else None

    def _update_thumbnail(self) -> None:
        if self._thumb is None:
            return
        width, height = winapi.client_size(self._hwnd)
        top = round(STRIP_H * self.devicePixelRatioF())
        winapi.update_thumbnail(
            self._thumb, (1, top, width - 1, height - 1), visible=not self._minimized
        )

    def _poll(self) -> None:
        if not winapi.is_window(self.source_hwnd):
            self.close()
            return
        minimized = winapi.is_iconic(self.source_hwnd)
        if minimized != self._minimized:
            self._minimized = minimized
            self._update_thumbnail()
            self.update()
        if minimized:
            return
        title = winapi.window_title(self.source_hwnd)
        if title != self._title.text():
            self._title.setText(title)
        size = self._query_size()
        if size and size != self._source_size:
            self._source_size = size
            self.resize(self.width(), self._height_for(self.width()))

    # -- events -------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._update_thumbnail()
        handle = self.windowHandle()
        if handle:
            handle.screenChanged.connect(lambda _screen: self._update_thumbnail())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._strip.setGeometry(0, 0, self.width(), STRIP_H)
        self._update_thumbnail()

    def nativeEvent(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            # layered: needed for opacity; tool window and not app window: no taskbar button, no Alt+Tab entry
            winapi.enforce_ex_style_bits(
                msg, keep=winapi.WS_EX_LAYERED | winapi.WS_EX_TOOLWINDOW, drop=winapi.WS_EX_APPWINDOW
            )
            if self._click_through and msg.message == winapi.WM_NCHITTEST and self._over_video(msg.lParam):
                return True, winapi.HTTRANSPARENT
        return False, 0

    def _over_video(self, lparam: int) -> bool:
        """True if the screen point packed in a WM_NCHITTEST lParam is on the video, not the control strip."""
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        _cx, cy = winapi.screen_to_client(self._hwnd, x, y)
        return cy >= round(STRIP_H * self.devicePixelRatioF())

    def closeEvent(self, event) -> None:
        self._timer.stop()
        # DWM drops the thumbnail itself when the source window is destroyed, so only unregister live ones.
        if self._thumb is not None and winapi.is_window(self.source_hwnd):
            try:
                winapi.unregister_thumbnail(self._thumb)
            except OSError as exc:
                log.warning("Could not unregister thumbnail: %s", exc)
        self._thumb = None
        self.closed.emit(self.source_hwnd)
        super().closeEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#101216"))
        if self._minimized:
            area = QRect(0, STRIP_H, self.width(), self.height() - STRIP_H)
            p.setPen(QColor("#8b93a1"))
            p.drawText(area, Qt.AlignCenter, "Source window is minimized")
        p.setPen(QPen(QColor("#4c9aff") if self._click_through else QColor("#2e343e"), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def _edges_at(self, pos) -> int:
        edges = 0
        if pos.x() < EDGE:
            edges |= LEFT
        elif pos.x() >= self.width() - EDGE:
            edges |= RIGHT
        if pos.y() < EDGE:
            edges |= TOP
        elif pos.y() >= self.height() - EDGE:
            edges |= BOTTOM
        return edges

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag = (self._edges_at(event.pos()), event.globalPos(), self.geometry())

    def mouseMoveEvent(self, event) -> None:
        if self._drag is None:
            shape = _cursor_for(self._edges_at(event.pos()))
            if shape is None:
                self.unsetCursor()
            else:
                self.setCursor(shape)
            return
        edges, start, geom = self._drag
        delta = event.globalPos() - start
        if not edges:
            self.move(geom.topLeft() + delta)
            return
        max_w = self.screen().availableGeometry().width() if self.screen() else None
        x, y, w, h = resized_rect(
            edges, (geom.x(), geom.y(), geom.width(), geom.height()), delta.x(), delta.y(), self._aspect, max_w=max_w
        )
        self.setGeometry(x, y, w, h)

    def mouseReleaseEvent(self, _event) -> None:
        self._drag = None
