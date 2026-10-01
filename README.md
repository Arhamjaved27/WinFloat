# WinFloat

Picture-in-picture, always-on-top and opacity for any Windows window. Lives in the system tray.

## Run

```
python main.py          # or pythonw main.py for no console window
```

Requires Python 3.11+ and PyQt5 (`pip install PyQt5`). Windows only.

## What it does

- **PiP (mirror):** a small floating live copy of any window (Windows DWM thumbnail). Drag to move, drag edges to resize (aspect ratio is kept), slider for opacity, buttons for click-through / keep-on-top / close.
- **Pin (real window):** make the actual window always-on-top and/or translucent. Everything is restored when you unpin, reset, or quit WinFloat.
- **Click-through:** mouse clicks on the video pass through a PiP to the window underneath. The control strip stays clickable, so you can turn it off with the ◌ button, the hotkey, or the tray menu.
- **Remembered per app:** PiP position/width/opacity and pinned-window opacity are stored by executable name.

## Hotkeys (editable in `%APPDATA%\WinFloat\settings.json`, restart to apply)

| Action | Default |
|---|---|
| PiP the foreground window (press again to close) | Ctrl+Alt+P |
| Toggle always-on-top on the target window | Ctrl+Alt+T |
| Opacity up / down on the target window | Ctrl+Alt+Up / Down |
| Toggle click-through on all PiPs | Ctrl+Alt+C |
| Close all PiPs and restore all pinned windows | Ctrl+Alt+X |

"Target window" = the PiP or pinned window under the mouse, otherwise the foreground window.
If a hotkey is already taken by another program, WinFloat shows a tray notification naming it; the tray menu still works.

## Limitations

- PiP is view-only; clicks and keys are not forwarded to the source window.
- A minimized source shows "Source window is minimized" instead of video.
- DRM-protected video may show black in a PiP.
- Windows of elevated (administrator) programs can't be pinned or faded unless WinFloat is also run as administrator.
- Windows that draw their own transparency can't be faded.

## Build an installer

Needs `pip install pyinstaller` and [Inno Setup](https://jrsoftware.org/isdl.php) (one-time install).

```
.\build.ps1                  # -> installer\Output\WinFloat-Setup-1.0.0.exe
.\build.ps1 -Version 1.1.0   # choose the version number
.\build.ps1 -SkipInstaller   # only dist\WinFloat\WinFloat.exe
```

The installer installs per-user by default (no admin prompt), adds a Start Menu shortcut, offers optional
desktop shortcut and start-with-Windows, and registers an uninstaller in Windows "Apps & features".
It is unsigned, so other PCs may show a SmartScreen "unknown publisher" warning.

## Tests

```
python -m unittest discover tests
```
