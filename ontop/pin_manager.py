"""Real-window mode: make another application's window always-on-top / translucent, and undo it."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from . import winapi

log = logging.getLogger(__name__)


@dataclass
class _Entry:
    orig_topmost: bool
    orig_layer: tuple[int, int, int] | None  # (color key, alpha, flags) if it was layered
    orig_layered: bool
    orig_opacity: int
    opacity_supported: bool
    opacity: int
    layer_touched: bool = False


class PinManager:
    def __init__(self) -> None:
        self._entries: dict[int, _Entry] = {}

    def is_managed(self, hwnd: int) -> bool:
        return hwnd in self._entries

    def managed(self) -> list[int]:
        return list(self._entries)

    def opacity(self, hwnd: int) -> int:
        entry = self._entries.get(hwnd)
        if entry:
            return entry.opacity
        layer = winapi.get_layered_attrs(hwnd) if winapi.get_ex_style(hwnd) & winapi.WS_EX_LAYERED else None
        return winapi.alpha_to_percent(layer[1]) if layer and layer[2] & winapi.LWA_ALPHA else 100

    def set_topmost(self, hwnd: int, on: bool) -> None:
        self._apply(hwnd, lambda _entry: winapi.set_topmost(hwnd, on))

    def set_opacity(self, hwnd: int, percent: int) -> None:
        percent = winapi.clamp_percent(percent)
        self._apply(hwnd, lambda entry: self._write_opacity(hwnd, entry, percent))

    def restore(self, hwnd: int) -> None:
        """Put the window back exactly as found. Raises OSError if part of the restore failed."""
        entry = self._entries.pop(hwnd, None)
        if entry is None or not winapi.is_window(hwnd):
            return
        errors: list[str] = []
        try:
            if winapi.is_topmost(hwnd) != entry.orig_topmost:
                winapi.set_topmost(hwnd, entry.orig_topmost)
        except OSError as exc:
            errors.append(str(exc))
        if entry.layer_touched:
            try:
                if entry.orig_layer:
                    key, alpha, flags = entry.orig_layer
                    winapi.set_layered(hwnd, alpha, key, flags)
                elif not entry.orig_layered:
                    winapi.update_ex_style(hwnd, remove=winapi.WS_EX_LAYERED)
            except OSError as exc:
                errors.append(str(exc))
        if errors:
            raise OSError("; ".join(errors))

    def restore_all(self) -> int:
        """Best-effort restore of every managed window; returns the number that failed."""
        failed = 0
        for hwnd in list(self._entries):
            try:
                self.restore(hwnd)
            except OSError as exc:
                failed += 1
                log.error("Could not fully restore window %#x: %s", hwnd, exc)
        return failed

    def prune(self) -> None:
        """Forget windows that no longer exist."""
        for hwnd in [h for h in self._entries if not winapi.is_window(h)]:
            del self._entries[hwnd]

    # -- internals ----------------------------------------------------------

    def _apply(self, hwnd: int, change: Callable[[_Entry], None]) -> None:
        created = hwnd not in self._entries
        entry = self._entry(hwnd)
        try:
            change(entry)
        except OSError:
            if created:
                del self._entries[hwnd]
            raise
        self._settle(hwnd, entry)

    def _entry(self, hwnd: int) -> _Entry:
        entry = self._entries.get(hwnd)
        if entry:
            return entry
        layered = bool(winapi.get_ex_style(hwnd) & winapi.WS_EX_LAYERED)
        layer = winapi.get_layered_attrs(hwnd) if layered else None
        # A layered window without readable attributes draws itself (UpdateLayeredWindow);
        # forcing an alpha on it would break it, so opacity is refused for those.
        supported = not layered or layer is not None
        opacity = winapi.alpha_to_percent(layer[1]) if layer and layer[2] & winapi.LWA_ALPHA else 100
        entry = _Entry(winapi.is_topmost(hwnd), layer, layered, opacity, supported, opacity)
        self._entries[hwnd] = entry
        return entry

    @staticmethod
    def _write_opacity(hwnd: int, entry: _Entry, percent: int) -> None:
        if not entry.opacity_supported:
            raise OSError("This window manages its own transparency and cannot be faded")
        key, _alpha, flags = entry.orig_layer or (0, 255, 0)
        winapi.set_layered(hwnd, winapi.percent_to_alpha(percent), key, flags | winapi.LWA_ALPHA)
        entry.layer_touched = True
        entry.opacity = percent

    def _settle(self, hwnd: int, entry: _Entry) -> None:
        """Stop managing a window once it is back in its original state."""
        if entry.opacity == entry.orig_opacity and winapi.is_topmost(hwnd) == entry.orig_topmost:
            try:
                self.restore(hwnd)
            except OSError as exc:
                log.error("Could not fully restore window %#x: %s", hwnd, exc)
