"""Eased, gentler mouse-wheel scrolling for scroll areas and item views."""
from __future__ import annotations

from PyQt5.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt
from PyQt5.QtWidgets import QAbstractScrollArea


class SmoothScroller(QObject):
    STEP_PX = 54      # distance of one wheel notch (Qt's default is ~3x faster)
    DURATION_MS = 260

    def __init__(self, area: QAbstractScrollArea):
        super().__init__(area)
        self._bar = area.verticalScrollBar()
        self._bar.setSingleStep(24)
        self._anim = QPropertyAnimation(self._bar, b"value", self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setDuration(self.DURATION_MS)
        area.viewport().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Wheel or event.modifiers() != Qt.NoModifier:
            return False
        delta = event.angleDelta().y()
        if delta == 0 or self._bar.maximum() == 0:
            return False
        running = self._anim.state() == QPropertyAnimation.Running
        base = self._anim.endValue() if running else self._bar.value()
        target = round(base - delta / 120 * self.STEP_PX)
        target = max(self._bar.minimum(), min(self._bar.maximum(), target))
        self._anim.stop()
        self._anim.setStartValue(self._bar.value())
        self._anim.setEndValue(target)
        self._anim.start()
        event.accept()
        return True
