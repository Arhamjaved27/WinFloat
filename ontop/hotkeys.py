"""Global hotkeys via RegisterHotKey, delivered through a Qt native event filter."""
from __future__ import annotations

import logging
from ctypes import wintypes

from PyQt5.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, pyqtSignal

from . import winapi

log = logging.getLogger(__name__)

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
MODIFIERS = {"alt": MOD_ALT, "ctrl": MOD_CONTROL, "shift": MOD_SHIFT, "win": MOD_WIN, "meta": MOD_WIN}
NAMED_KEYS = {
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "space": 0x20, "tab": 0x09, "enter": 0x0D, "esc": 0x1B,
    "pageup": 0x21, "pagedown": 0x22, "end": 0x23, "home": 0x24, "insert": 0x2D, "delete": 0x2E,
    # Qt's portable key names, produced by the settings UI
    "pgup": 0x21, "pgdown": 0x22, "ins": 0x2D, "del": 0x2E, "return": 0x0D, "escape": 0x1B,
}


def parse_hotkey(text: str) -> tuple[int, int]:
    """'ctrl+alt+p' -> (modifier flags, virtual-key code). Raises ValueError if invalid."""
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if len(parts) < 2:
        raise ValueError(f"{text!r}: need at least one modifier and a key")
    *mods, key = parts
    flags = 0
    for mod in mods:
        if mod not in MODIFIERS:
            raise ValueError(f"{text!r}: unknown modifier {mod!r}")
        flags |= MODIFIERS[mod]
    if key in NAMED_KEYS:
        vk = NAMED_KEYS[key]
    elif len(key) == 1 and key.isalnum() and key.isascii():
        vk = ord(key.upper())
    elif key[0] == "f" and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError(f"{text!r}: unknown key {key!r}")
    return flags, vk


class _Filter(QAbstractNativeEventFilter):
    def __init__(self, on_hotkey):
        super().__init__()
        self._on_hotkey = on_hotkey

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == winapi.WM_HOTKEY and self._on_hotkey(msg.wParam):
                return True, 0
        return False, 0


class HotkeyManager(QObject):
    triggered = pyqtSignal(str)  # action name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._actions: dict[int, str] = {}
        self._filter = _Filter(self._dispatch)
        QCoreApplication.instance().installNativeEventFilter(self._filter)

    def register_all(self, bindings: dict[str, str]) -> list[str]:
        """Registers each action's hotkey; returns human-readable failures (never raises)."""
        failures = []
        for action, text in bindings.items():
            try:
                mods, vk = parse_hotkey(text)
                hotkey_id = len(self._actions) + 1
                winapi.register_hotkey(hotkey_id, mods | MOD_NOREPEAT, vk)
            except (ValueError, OSError) as exc:
                log.error("Hotkey %s=%s not registered: %s", action, text, exc)
                failures.append(f"{action} ({text}): {exc}")
                continue
            self._actions[hotkey_id] = action
        return failures

    def unregister_all(self) -> None:
        for hotkey_id in self._actions:
            winapi.unregister_hotkey(hotkey_id)
        self._actions.clear()

    def _dispatch(self, hotkey_id: int) -> bool:
        action = self._actions.get(hotkey_id)
        if action is None:
            return False
        self.triggered.emit(action)
        return True
