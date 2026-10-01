"""Persistent settings: hotkeys plus per-app profiles, stored as JSON in %APPDATA%\\OnTop."""
from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

APP_NAME = "OnTop"

DEFAULT_HOTKEYS = {
    "pip_foreground": "ctrl+alt+p",
    "toggle_topmost": "ctrl+alt+t",
    "opacity_up": "ctrl+alt+up",
    "opacity_down": "ctrl+alt+down",
    "toggle_click_through": "ctrl+alt+c",
    "reset_all": "ctrl+alt+x",
}
DEFAULTS = {"version": 1, "opacity_step": 10, "hover_arrow": True, "hotkeys": DEFAULT_HOTKEYS, "profiles": {}}


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value


class Settings:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "settings.json"
        self.data: dict = copy.deepcopy(DEFAULTS)

    def load(self) -> None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        try:
            loaded = json.loads(raw)
            if not isinstance(loaded, dict):
                raise ValueError("top-level JSON value must be an object")
        except ValueError as exc:
            backup = self.path.with_suffix(".json.bad")
            os.replace(self.path, backup)
            log.error("Invalid settings file moved to %s (%s); using defaults", backup, exc)
            return
        _merge(self.data, loaded)

    def save(self) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    @property
    def hotkeys(self) -> dict[str, str]:
        return self.data["hotkeys"]

    @property
    def opacity_step(self) -> int:
        step = self.data["opacity_step"]
        if isinstance(step, int) and not isinstance(step, bool) and 1 <= step <= 50:
            return step
        log.warning("Ignoring invalid opacity_step %r; using %d", step, DEFAULTS["opacity_step"])
        return DEFAULTS["opacity_step"]

    @property
    def hover_arrow(self) -> bool:
        value = self.data["hover_arrow"]
        if isinstance(value, bool):
            return value
        log.warning("Ignoring invalid hover_arrow %r; using %s", value, DEFAULTS["hover_arrow"])
        return DEFAULTS["hover_arrow"]

    def profile(self, exe: str) -> dict:
        return self.data["profiles"].get(exe.lower(), {})

    def update_profile(self, exe: str, **fields) -> None:
        if exe:
            self.data["profiles"].setdefault(exe.lower(), {}).update(fields)
