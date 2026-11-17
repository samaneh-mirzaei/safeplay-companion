"""Render the SafePlay projector SVG into a multi-resolution Windows icon."""
from pathlib import Path
import struct

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


root = Path(__file__).resolve().parent.parent
renderer = QSvgRenderer(str(root / "assets" / "safeplay.svg"))
if not renderer.isValid():
    raise RuntimeError("Cannot load the SafePlay SVG icon")

images = []
for size in (16, 24, 32, 48, 64, 128, 256):
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"Cannot render the {size}px icon")
    images.append((size, bytes(data)))

directory = struct.pack("<HHH", 0, 1, len(images))
offset = 6 + 16 * len(images)
entries = []
for size, data in images:
    entries.append(struct.pack(
        "<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0,
        0, 0, 1, 32, len(data), offset,
    ))
    offset += len(data)

(root / "assets" / "safeplay.ico").write_bytes(
    directory + b"".join(entries) + b"".join(data for _, data in images)
)
