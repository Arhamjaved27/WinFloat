"""Writes installer/WinFloat.ico (multi-size, PNG-compressed) from the same drawing the app uses."""
import struct
import sys
from pathlib import Path

from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
from PyQt5.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ontop.tray import ICON_SIZES, render_icon  # noqa: E402


def png_bytes(size: int) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    if not render_icon(size).save(buf, "PNG"):
        raise RuntimeError(f"Could not encode {size}px icon")
    return bytes(data)


def main() -> None:
    app = QApplication(sys.argv)  # noqa: F841 - QPixmap needs an application object
    images = [(size, png_bytes(size)) for size in ICON_SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for size, png in images:
        dim = 0 if size >= 256 else size  # 0 means 256 in the ICO format
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        blobs += png
        offset += len(png)
    out = Path(__file__).resolve().parent / "WinFloat.ico"
    out.write_bytes(header + entries + blobs)
    print(f"Wrote {out} ({out.stat().st_size} bytes, sizes {ICON_SIZES})")


if __name__ == "__main__":
    main()
