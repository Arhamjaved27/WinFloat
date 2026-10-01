"""OnTop: picture-in-picture, always-on-top and opacity for any Windows window."""
import atexit
import faulthandler
import logging
import logging.handlers
import signal
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QLabel, QMessageBox

from ontop import winapi
from ontop.controller import Controller
from ontop.hotkeys import HotkeyManager
from ontop.hover_launcher import HoverLauncher
from ontop.main_window import MainWindow
from ontop.pin_manager import PinManager
from ontop.settings import Settings, data_dir
from ontop.tray import Tray


_crash_log = None  # kept open for faulthandler


def setup_logging() -> None:
    handler = logging.handlers.RotatingFileHandler(
        data_dir() / "ontop.log", maxBytes=512_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    # native crashes (access violations etc.) bypass Python logging; dump their traceback to a file
    global _crash_log
    _crash_log = open(data_dir() / "crash.log", "a", encoding="utf-8")
    faulthandler.enable(_crash_log)

    def log_uncaught(exc_type, exc, tb):
        logging.getLogger("ontop").critical("Uncaught exception", exc_info=(exc_type, exc, tb))

    sys.excepthook = log_uncaught


def warm_up_text_rendering() -> None:
    """Qt's first styled-text render takes seconds on some machines; pay it at launch, not on the first PiP."""
    probe = QLabel("OnTop")
    probe.setStyleSheet("QLabel { color: white; }")
    probe.grab()


def main() -> int:
    setup_logging()
    log = logging.getLogger("ontop")

    mutex = winapi.acquire_single_instance("Local\\OnTop.SingleInstance")
    if mutex is None:
        log.info("Another OnTop instance is already running; exiting")
        app = QApplication(sys.argv)
        QMessageBox.information(
            None, "OnTop",
            "OnTop is already running. Look for its icon in the system tray (click the ^ arrow if hidden) "
            "and click it to open the window.",
        )
        return 0

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # lives in the tray
    warm_up_text_rendering()

    settings = Settings()
    settings.load()
    pins = PinManager()
    atexit.register(pins.restore_all)  # last resort if Qt shutdown is skipped
    controller = Controller(settings, pins)

    hotkeys = HotkeyManager()
    hotkeys.triggered.connect(controller.handle_hotkey)
    tray = Tray(controller, str(settings.path), on_open=lambda: window.show_window())
    window = MainWindow(controller, settings, hotkeys, tray.notify)
    launcher = HoverLauncher(controller, open_settings=window.show_settings)
    launcher.set_enabled(settings.hover_arrow)
    window.hover_arrow_changed.connect(launcher.set_enabled)
    failures = hotkeys.register_all(settings.hotkeys)
    if failures:
        tray.notify("Some hotkeys could not be registered:\n" + "\n".join(failures))

    app.aboutToQuit.connect(hotkeys.unregister_all)
    app.aboutToQuit.connect(controller.shutdown)

    signal.signal(signal.SIGINT, lambda *_: app.quit())  # Ctrl+C when run from a console
    wake = QTimer()
    wake.timeout.connect(lambda: None)  # lets Python handle the signal while Qt runs
    wake.start(500)

    log.info("OnTop started")
    if not tray.available:
        log.error("No system tray available; OnTop will run without a tray icon")
    if "--tray" in sys.argv:
        tray.notify("OnTop is running in the tray. Click its icon to open the window.")
    else:
        window.show_window()
    code = app.exec_()
    log.info("OnTop exited with code %s", code)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logging.getLogger("ontop").exception("Fatal error during startup")
        raise
