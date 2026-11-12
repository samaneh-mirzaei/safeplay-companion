"""Create a simple 32x32 placeholder ICO without external dependencies."""
from pathlib import Path
import struct

size = 32
pixels = bytearray()
for y in range(size - 1, -1, -1):
    for x in range(size):
        play = 10 <= x <= 23 and abs(y - 16) <= (x - 9) * 0.65
        b, g, r, a = (245, 230, 210, 255) if play else (180, 103, 42, 255)
        pixels.extend((b, g, r, a))
mask = bytes(4 * size)
dib = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0)
data = dib + pixels + mask
directory = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(data), 22)
target = Path(__file__).resolve().parent.parent / "assets" / "safeplay.ico"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(directory + data)
