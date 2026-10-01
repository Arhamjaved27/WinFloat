"""The main OnTop window: pick windows, manage active PiPs/pins, and edit settings."""
from __future__ import annotations

import logging

from PyQt5.QtCore import QFileInfo, QRect, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QKeySequence, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QFileIconProvider, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSlider, QSpinBox, QStackedWidget, QStyle,
    QStyledItemDelegate, QVBoxLayout, QWidget,
)

from . import autostart, winapi, windows_list
from .controller import Controller, Target
from .hotkeys import HotkeyManager, parse_hotkey
from .settings import DEFAULT_HOTKEYS, DEFAULTS, Settings
from .smooth_scroll import SmoothScroller
from .tray import make_icon

log = logging.getLogger(__name__)

HOTKEY_LABELS = {
    "pip_foreground": ("PiP the foreground window", "Press again on a PiP to close it"),
    "toggle_topmost": ("Toggle always-on-top", "Window under the cursor, else the focused window"),
    "opacity_up": ("Opacity up", "Same target window"),
    "opacity_down": ("Opacity down", "Same target window"),
    "toggle_click_through": ("Toggle click-through", "All PiP windows"),
    "reset_all": ("Close PiPs and restore windows", "Panic button: undoes everything"),
}
REFRESH_MS = 1000
ROLE_HWND, ROLE_SUB = Qt.UserRole, Qt.UserRole + 1

BG, SIDEBAR, CARD, BORDER = "#0f1115", "#0b0d10", "#171a21", "#242936"
TEXT, MUTED, ACCENT, ACCENT_SOFT = "#e6e9ef", "#8a93a3", "#5b8cff", "#1d2a4a"

STYLE = f"""
* {{ font-family: "Segoe UI Variable Text", "Segoe UI"; font-size: 13px; color: {TEXT}; outline: none; }}
QWidget#root, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BG}; }}
QFrame#sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QLabel {{ background: transparent; }}
QLabel#brand {{ font-size: 18px; font-weight: 700; }}
QLabel#tagline, QLabel#muted {{ color: {MUTED}; font-size: 12px; }}
QLabel#pageTitle {{ font-size: 22px; font-weight: 700; }}
QLabel#cardTitle {{ font-size: 14px; font-weight: 600; }}
QLabel#empty {{ color: {MUTED}; font-size: 14px; }}
QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#card QLabel {{ background: transparent; }}
QPushButton#nav {{ text-align: left; padding: 10px 14px; border: none; border-left: 3px solid transparent;
                   border-radius: 8px; background: transparent; color: #aab2c0; font-weight: 500; }}
QPushButton#nav:hover {{ background: #161a22; color: white; }}
QPushButton#nav:checked {{ background: {ACCENT_SOFT}; color: white; border-left: 3px solid {ACCENT}; }}
QPushButton {{ background: #202533; border: 1px solid #2d3445; border-radius: 8px; padding: 8px 16px; }}
QPushButton:hover {{ background: #283044; }}
QPushButton:pressed {{ background: #1b2030; }}
QPushButton:disabled {{ color: #5d6575; background: #171b25; border-color: #202533; }}
QPushButton#primary {{ background: {ACCENT}; border-color: {ACCENT}; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: #7aa2ff; }}
QPushButton#primary:disabled {{ background: #2a3658; border-color: #2a3658; color: #7d88a8; }}
QPushButton#ghost {{ background: transparent; border-color: transparent; color: {MUTED}; }}
QPushButton#ghost:hover {{ background: #161a22; color: white; }}
QPushButton#danger:hover {{ background: #5b2323; border-color: #8a3333; }}
QPushButton#keycap {{ background: #0f1218; border: 1px solid #2d3445; border-bottom: 2px solid #2d3445;
                      border-radius: 8px; padding: 7px 14px; min-width: 170px; font-weight: 600; }}
QPushButton#keycap:hover {{ border-color: {ACCENT}; }}
QPushButton#keycap[capturing="true"] {{ border-color: {ACCENT}; background: {ACCENT_SOFT}; color: #c9d8ff; }}
QLineEdit, QSpinBox {{ background: #0f1218; border: 1px solid #2d3445; border-radius: 8px; padding: 8px 12px;
                       selection-background-color: {ACCENT}; }}
QLineEdit:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}
QListWidget {{ background: transparent; border: none; }}
QCheckBox {{ spacing: 10px; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid #3a4256; background: #0f1218; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QCheckBox::indicator:disabled {{ background: #171b25; border-color: #242936; }}
QSlider::groove:horizontal {{ height: 6px; background: #2a3042; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{ width: 16px; height: 16px; margin: -5px 0; background: white; border-radius: 8px; }}
QSlider::handle:horizontal:disabled {{ background: #6b7280; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2d3445; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #3a4256; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QToolTip {{ background: #202533; color: {TEXT}; border: 1px solid #2d3445; padding: 4px 8px; }}
"""


def sequence_to_text(seq: QKeySequence) -> str:
    """First chord of a key sequence as e.g. 'ctrl+alt+p' ('' if empty)."""
    return "" if seq.isEmpty() else QKeySequence(seq[0]).toString(QKeySequence.PortableText).lower()


class HotkeyEdit(QPushButton):
    """Click, then press the new combination. Esc cancels. Global hotkeys are paused while recording."""

    changed = pyqtSignal()
    capturing = pyqtSignal(bool)
    MODIFIER_KEYS = {Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr, Qt.Key_CapsLock}

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("keycap")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click, then press the new shortcut. Esc cancels.")
        self._hotkey = ""
        self._recording = False
        self._hint = ""
        self.clicked.connect(self._begin)
        self._refresh()

    def hotkey(self) -> str:
        return self._hotkey

    def set_hotkey(self, text: str) -> None:
        self._hotkey = text
        self._refresh()

    def _refresh(self) -> None:
        if self._recording:
            label = self._hint or "Press the new shortcut…"
        elif self._hotkey:
            label = QKeySequence(self._hotkey.replace("win", "meta"), QKeySequence.PortableText).toString(QKeySequence.NativeText)
        else:
            label = "Not set"
        self.setText(label)
        self.setProperty("capturing", self._recording)
        self.style().unpolish(self)
        self.style().polish(self)

    def _begin(self) -> None:
        if not self._recording:
            self._recording = True
            self._hint = ""
            self.capturing.emit(True)
            self._refresh()

    def _end(self) -> None:
        if self._recording:
            self._recording = False
            self._hint = ""
            self.capturing.emit(False)
            self._refresh()

    def focusNextPrevChild(self, next_child: bool) -> bool:
        return False if self._recording else super().focusNextPrevChild(next_child)

    def focusOutEvent(self, event) -> None:
        self._end()
        super().focusOutEvent(event)

    def keyPressEvent(self, event) -> None:
        if not self._recording:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key_Escape:
            self._end()
            return
        if key in self.MODIFIER_KEYS or key == Qt.Key_unknown:
            return
        mods = event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.ShiftModifier | Qt.MetaModifier)
        if not mods:
            self._hint = "Add Ctrl, Alt, Shift or Win…"
            self._refresh()
            return
        self._hotkey = QKeySequence(int(mods) | key).toString(QKeySequence.PortableText).lower()
        self._end()
        self.changed.emit()


class NoWheelSpinBox(QSpinBox):
    """Scrolling the page over this box must scroll the page, not silently change the value."""

    def wheelEvent(self, event) -> None:
        event.ignore()


class RowDelegate(QStyledItemDelegate):
    """Paints list rows as rounded cards: app icon, bold title, muted subtitle."""

    def sizeHint(self, option, index) -> QSize:
        return QSize(0, 58)

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(2, 2, -2, -2)
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        if selected or hovered:
            path = QPainterPath()
            path.addRoundedRect(rect, 10, 10)
            painter.fillPath(path, QColor(ACCENT_SOFT if selected else "#161a22"))
            if selected:
                painter.setPen(QPen(QColor(ACCENT), 1))
                painter.drawPath(path)
        icon = index.data(Qt.DecorationRole)
        left = rect.left() + 14
        if isinstance(icon, QIcon):
            icon.paint(painter, QRect(int(left), int(rect.center().y() - 15), 30, 30))
        left += 44
        width = int(rect.right() - left - 12)
        title_font = QFont(option.font)
        title_font.setWeight(QFont.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QColor(TEXT))
        title = painter.fontMetrics().elidedText(index.data(Qt.DisplayRole) or "", Qt.ElideRight, width)
        painter.drawText(QRect(int(left), int(rect.top() + 9), width, 20), Qt.AlignVCenter | Qt.AlignLeft, title)
        sub_font = QFont(option.font)
        sub_font.setPointSizeF(max(8.0, option.font.pointSizeF() - 1.5))
        painter.setFont(sub_font)
        painter.setPen(QColor(MUTED))
        sub = painter.fontMetrics().elidedText(index.data(ROLE_SUB) or "", Qt.ElideRight, width)
        painter.drawText(QRect(int(left), int(rect.top() + 29), width, 18), Qt.AlignVCenter | Qt.AlignLeft, sub)
        painter.restore()


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    return frame, layout


def _label(text: str, name: str = "") -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    return label


class MainWindow(QWidget):
    hover_arrow_changed = pyqtSignal(bool)

    def __init__(self, controller: Controller, settings: Settings, hotkeys: HotkeyManager, notify):
        super().__init__()
        self.setObjectName("root")
        self._ctrl = controller
        self._settings = settings
        self._hotkeys = hotkeys
        self._notify = notify
        self._told_about_tray = False
        self._icons = QFileIconProvider()
        self._icon_cache: dict[str, QIcon] = {}
        self._all_windows: list[windows_list.WindowInfo] = []
        self._active_items: list = []
        self.setWindowTitle("OnTop")
        self.setWindowIcon(make_icon())
        self.resize(900, 620)
        self.setMinimumSize(780, 520)
        self.setStyleSheet(STYLE)

        self._stack = QStackedWidget()
        self._nav: list[QPushButton] = []
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        root.addWidget(self._stack, 1)
        self._add_page("Windows", self._build_windows_page())
        self._add_page("Active", self._build_active_page())
        self._add_page("Settings", self._build_settings_page())
        self._go(0)

        self._timer = QTimer(self, interval=REFRESH_MS)
        self._timer.timeout.connect(self._refresh_active)

    # -- shell --------------------------------------------------------------

    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(210)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(14, 22, 14, 16)
        layout.setSpacing(4)
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(make_icon().pixmap(34, 34))
        title = QVBoxLayout()
        title.setSpacing(0)
        title.addWidget(_label("OnTop", "brand"))
        title.addWidget(_label("PiP · Pin · Opacity", "tagline"))
        brand.addWidget(logo)
        brand.addLayout(title, 1)
        layout.addLayout(brand)
        layout.addSpacing(22)
        self._nav_layout = layout
        layout.addStretch(1)
        quit_btn = QPushButton("Quit OnTop")
        quit_btn.setObjectName("ghost")
        quit_btn.clicked.connect(QApplication.quit)
        tray_hint = _label("Closing this window keeps OnTop running in the tray.", "muted")
        tray_hint.setWordWrap(True)
        layout.addWidget(tray_hint)
        layout.addWidget(quit_btn)
        return side

    def _add_page(self, name: str, page: QWidget) -> None:
        index = self._stack.addWidget(page)
        button = QPushButton(name)
        button.setObjectName("nav")
        button.setCheckable(True)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda _=False, i=index: self._go(i))
        self._nav.append(button)
        self._nav_layout.insertWidget(self._nav_layout.count() - 3, button)

    def _go(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        for i, button in enumerate(self._nav):
            button.setChecked(i == index)
        if index == 0:
            self._refresh_windows()
        elif index == 1:
            self._refresh_active()

    @staticmethod
    def _page(title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(14)
        layout.addWidget(_label(title, "pageTitle"))
        layout.addWidget(_label(subtitle, "muted"))
        layout.addSpacing(6)
        return page, layout

    def _icon_for(self, path: str) -> QIcon:
        if path not in self._icon_cache:
            self._icon_cache[path] = (
                self._icons.icon(QFileInfo(path)) if path else QApplication.style().standardIcon(QStyle.SP_ComputerIcon)
            )
        return self._icon_cache[path]

    def _make_list(self) -> QListWidget:
        view = QListWidget()
        view.setItemDelegate(RowDelegate(view))
        view.setMouseTracking(True)
        view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        view.setSpacing(2)
        view.setIconSize(QSize(30, 30))
        SmoothScroller(view)
        return view

    # -- Windows page -------------------------------------------------------

    def _build_windows_page(self) -> QWidget:
        page, layout = self._page("Windows", "Pick any open window to mirror it in a floating PiP or keep it on top.")
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search windows…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._fill_windows)
        self._win_list = self._make_list()
        self._win_list.itemDoubleClicked.connect(lambda _item: self._pip_selected())
        self._win_list.currentItemChanged.connect(lambda *_: self._sync_window_buttons())

        card, card_layout = _card()
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.addWidget(self._win_list)

        self._pip_btn = QPushButton("Show in PiP")
        self._pip_btn.setObjectName("primary")
        self._pip_btn.clicked.connect(self._pip_selected)
        self._pin_btn = QPushButton("Pin on top / unpin")
        self._pin_btn.clicked.connect(self._pin_selected)
        refresh = QPushButton("Refresh")
        refresh.setObjectName("ghost")
        refresh.clicked.connect(self._refresh_windows)
        buttons = QHBoxLayout()
        buttons.addWidget(refresh)
        buttons.addStretch(1)
        buttons.addWidget(self._pin_btn)
        buttons.addWidget(self._pip_btn)
        layout.addWidget(self._search)
        layout.addWidget(card, 1)
        layout.addLayout(buttons)
        self._sync_window_buttons()
        return page

    def _selected_window(self) -> int | None:
        item = self._win_list.currentItem()
        return item.data(ROLE_HWND) if item else None

    def _sync_window_buttons(self) -> None:
        has = self._selected_window() is not None
        self._pip_btn.setEnabled(has)
        self._pin_btn.setEnabled(has)

    def _pip_selected(self) -> None:
        hwnd = self._selected_window()
        if hwnd:
            self._ctrl.open_pip(hwnd)

    def _pin_selected(self) -> None:
        hwnd = self._selected_window()
        if hwnd:
            self._ctrl.toggle_topmost(Target("pin", hwnd))

    def _refresh_windows(self) -> None:
        self._all_windows = windows_list.list_windows()
        self._fill_windows()

    def _fill_windows(self) -> None:
        current = self._selected_window()
        needle = self._search.text().strip().lower()
        self._win_list.clear()
        for win in self._all_windows:
            if needle and needle not in win.title.lower() and needle not in win.exe.lower():
                continue
            item = QListWidgetItem(self._icon_for(win.path), win.title)
            item.setData(ROLE_HWND, win.hwnd)
            item.setData(ROLE_SUB, win.exe or "unknown app")
            self._win_list.addItem(item)
            if win.hwnd == current:
                self._win_list.setCurrentItem(item)
        self._sync_window_buttons()

    # -- Active page --------------------------------------------------------

    def _build_active_page(self) -> QWidget:
        page, layout = self._page("Active", "PiP windows and pinned windows OnTop is managing right now.")
        self._active_list = self._make_list()
        self._active_list.currentItemChanged.connect(lambda *_: self._sync_active_controls())
        list_card, list_layout = _card()
        list_layout.setContentsMargins(12, 12, 12, 12)
        list_layout.addWidget(self._active_list)
        self._empty = _label("Nothing active yet.\nPick a window on the Windows page.", "empty")
        self._empty.setAlignment(Qt.AlignCenter)
        list_layout.addWidget(self._empty)

        controls, c_layout = _card()
        self._opacity = QSlider(Qt.Horizontal)
        self._opacity.setRange(winapi.MIN_OPACITY, 100)
        self._opacity.valueChanged.connect(self._on_opacity)
        self._opacity_label = _label("", "cardTitle")
        self._opacity_label.setMinimumWidth(46)
        row = QHBoxLayout()
        row.addWidget(_label("Opacity", "cardTitle"))
        row.addSpacing(8)
        row.addWidget(self._opacity, 1)
        row.addWidget(self._opacity_label)
        self._topmost = QCheckBox("Always on top")
        self._topmost.clicked.connect(self._on_topmost)
        self._ghost = QCheckBox("Click-through (video area only; the control strip stays clickable)")
        self._ghost.clicked.connect(self._on_ghost)
        self._close_btn = QPushButton("Close")
        self._close_btn.setObjectName("danger")
        self._close_btn.clicked.connect(self._on_close_item)
        foot = QHBoxLayout()
        foot.addStretch(1)
        foot.addWidget(self._close_btn)
        c_layout.addLayout(row)
        c_layout.addWidget(self._topmost)
        c_layout.addWidget(self._ghost)
        c_layout.addLayout(foot)
        layout.addWidget(list_card, 1)
        layout.addWidget(controls)
        return page

    def _selected_item(self):
        row = self._active_list.currentRow()
        return self._active_items[row] if 0 <= row < len(self._active_items) else None

    def _refresh_active(self) -> None:
        selected = self._selected_item()
        self._active_items = self._ctrl.active_items()
        self._active_list.blockSignals(True)
        self._active_list.clear()
        for info in self._active_items:
            is_pip = info.target.kind == "pip"
            flags = [f"{info.opacity}%"] + (["on top"] if info.topmost else []) + (["click-through"] if info.click_through else [])
            item = QListWidgetItem(self._icon_for(info.path), info.title or "(untitled)")
            item.setData(ROLE_SUB, f"{'PiP mirror' if is_pip else 'Pinned window'}  ·  " + "  ·  ".join(flags))
            self._active_list.addItem(item)
            if selected and info.target == selected.target:
                self._active_list.setCurrentRow(self._active_list.count() - 1)
        self._active_list.blockSignals(False)
        has_items = bool(self._active_items)
        self._active_list.setVisible(has_items)
        self._empty.setVisible(not has_items)
        self._sync_active_controls()

    def _sync_active_controls(self) -> None:
        info = self._selected_item()
        for widget in (self._opacity, self._topmost, self._ghost, self._close_btn):
            widget.setEnabled(info is not None)
        if info is None:
            self._opacity_label.setText("")
            self._close_btn.setText("Close")
            return
        is_pip = info.target.kind == "pip"
        if not self._opacity.isSliderDown():
            self._opacity.blockSignals(True)
            self._opacity.setValue(info.opacity)
            self._opacity.blockSignals(False)
        self._opacity_label.setText(f"{info.opacity}%")
        self._topmost.setChecked(info.topmost)
        self._ghost.setEnabled(is_pip)
        self._ghost.setChecked(info.click_through)
        self._close_btn.setText("Close PiP" if is_pip else "Restore window")

    def _on_opacity(self, value: int) -> None:
        info = self._selected_item()
        if info:
            self._ctrl.set_opacity(info.target, value)
            self._opacity_label.setText(f"{value}%")

    def _on_topmost(self) -> None:
        info = self._selected_item()
        if info:
            self._ctrl.toggle_topmost(info.target)

    def _on_ghost(self, checked: bool) -> None:
        info = self._selected_item()
        if info and info.target.kind == "pip":
            self._ctrl.set_click_through(info.target.hwnd, checked)

    def _on_close_item(self) -> None:
        info = self._selected_item()
        if info is None:
            return
        if info.target.kind == "pip":
            self._ctrl.close_pip(info.target.hwnd)
        else:
            self._ctrl.unpin(info.target.hwnd)
        self._refresh_active()

    # -- Settings page ------------------------------------------------------

    def _build_settings_page(self) -> QWidget:
        page, layout = self._page("Settings", "Global shortcuts work in any application.")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        SmoothScroller(scroll)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 8, 0)
        inner_layout.setSpacing(14)

        keys_card, keys_layout = _card()
        keys_layout.addWidget(_label("Keyboard shortcuts", "cardTitle"))
        keys_layout.addWidget(_label("Click a shortcut, then press the new keys. Esc cancels.", "muted"))
        self._key_edits: dict[str, HotkeyEdit] = {}
        for action, (name, hint) in HOTKEY_LABELS.items():
            edit = HotkeyEdit()
            edit.capturing.connect(self._on_capturing)
            self._key_edits[action] = edit
            text = QVBoxLayout()
            text.setSpacing(0)
            text.addWidget(_label(name))
            text.addWidget(_label(hint, "muted"))
            row = QHBoxLayout()
            row.addLayout(text, 1)
            row.addWidget(edit)
            keys_layout.addLayout(row)

        general_card, general_layout = _card()
        general_layout.addWidget(_label("General", "cardTitle"))
        self._step = NoWheelSpinBox()
        self._step.setRange(1, 50)
        self._step.setSuffix(" %")
        self._step.setFixedWidth(110)
        step_row = QHBoxLayout()
        step_row.addWidget(_label("Opacity change per key press"), 1)
        step_row.addWidget(self._step)
        self._autostart = QCheckBox("Start OnTop with Windows (minimised to the tray)")
        self._autostart.clicked.connect(self._on_autostart)
        self._hover = QCheckBox("Show an arrow when the cursor reaches the top-centre of a window")
        general_layout.addLayout(step_row)
        general_layout.addWidget(self._hover)
        general_layout.addWidget(self._autostart)

        inner_layout.addWidget(keys_card)
        inner_layout.addWidget(general_card)
        inner_layout.addStretch(1)
        scroll.setWidget(inner)

        self._status = QLabel()
        self._status.setWordWrap(True)
        apply_btn = QPushButton("Save && apply")
        apply_btn.setObjectName("primary")
        apply_btn.clicked.connect(self._apply_settings)
        reset_btn = QPushButton("Reset to defaults")
        reset_btn.setToolTip("Restore the default shortcuts, opacity step and hover arrow, and apply them now")
        reset_btn.clicked.connect(self._reset_settings)
        buttons = QHBoxLayout()
        buttons.addWidget(reset_btn)
        buttons.addStretch(1)
        buttons.addWidget(apply_btn)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._status)
        layout.addLayout(buttons)
        self._load_settings_into_form()
        return page

    def _on_capturing(self, recording: bool) -> None:
        """Global hotkeys would swallow the very keys being recorded, so pause them meanwhile."""
        if recording:
            self._hotkeys.unregister_all()
        else:
            self._hotkeys.unregister_all()
            self._hotkeys.register_all(self._settings.hotkeys)

    def _show_hotkeys(self, bindings: dict[str, str]) -> None:
        for action, edit in self._key_edits.items():
            edit.set_hotkey(bindings.get(action, ""))

    def _load_settings_into_form(self) -> None:
        self._show_hotkeys(self._settings.hotkeys)
        self._step.setValue(self._settings.opacity_step)
        self._hover.setChecked(self._settings.hover_arrow)
        self._autostart.setChecked(autostart.is_enabled())

    def _reset_settings(self) -> None:
        self._show_hotkeys(DEFAULT_HOTKEYS)
        self._step.setValue(DEFAULTS["opacity_step"])
        self._hover.setChecked(DEFAULTS["hover_arrow"])
        self._apply_settings()
        if self._status.text().startswith("Saved."):  # not the "Saved, but a hotkey is taken" warning
            self._set_status("Defaults restored and applied.")

    def _set_status(self, text: str, error: bool = False) -> None:
        self._status.setStyleSheet(f"color: {'#ff7b72' if error else MUTED};")
        self._status.setText(text)

    def _apply_settings(self) -> None:
        bindings = {action: edit.hotkey() for action, edit in self._key_edits.items()}
        problems = []
        for action, text in bindings.items():
            try:
                parse_hotkey(text)
            except ValueError as exc:
                problems.append(f"{HOTKEY_LABELS[action][0]}: {exc}")
        if len(set(bindings.values())) != len(bindings):
            problems.append("Two actions use the same shortcut.")
        if problems:
            self._set_status("Not saved:\n" + "\n".join(problems), error=True)
            return

        self._settings.data["hotkeys"] = bindings
        self._settings.data["opacity_step"] = self._step.value()
        self._settings.data["hover_arrow"] = self._hover.isChecked()
        try:
            self._settings.save()
        except OSError as exc:
            log.error("Could not save settings: %s", exc)
            self._set_status(f"Could not save settings: {exc}", error=True)
            return
        self.hover_arrow_changed.emit(self._hover.isChecked())
        self._hotkeys.unregister_all()
        failures = self._hotkeys.register_all(bindings)
        if failures:
            self._set_status("Saved, but another program already uses:\n" + "\n".join(failures), error=True)
        else:
            self._set_status("Saved. Shortcuts are active.")

    def _on_autostart(self, checked: bool) -> None:
        try:
            autostart.set_enabled(checked)
        except OSError as exc:
            log.error("Could not change autostart: %s", exc)
            self._autostart.setChecked(autostart.is_enabled())
            self._set_status(f"Could not change start-with-Windows: {exc}", error=True)

    # -- lifecycle ----------------------------------------------------------

    def show_settings(self) -> None:
        self._go(2)
        self.show_window()

    def show_window(self) -> None:
        self._load_settings_into_form()
        self._go(self._stack.currentIndex())
        self._timer.start()
        self.showNormal()
        winapi.set_dark_title_bar(int(self.winId()))
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        event.ignore()  # keep running in the tray
        self._timer.stop()
        self.hide()
        if not self._told_about_tray:
            self._told_about_tray = True
            self._notify("OnTop is still running in the system tray. Quit it from the tray menu or the window's Quit button.")
