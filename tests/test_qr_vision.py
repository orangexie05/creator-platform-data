import importlib.util
import struct
import tempfile
import unittest
import zlib
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "qr_vision.py"


def load_qr_vision():
    spec = importlib.util.spec_from_file_location("qr_vision", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_png(path: Path, pixels: list[list[tuple[int, int, int]]]) -> None:
    height = len(pixels)
    width = len(pixels[0])
    raw = b"".join(
        b"\x00" + b"".join(bytes(pixel) for pixel in row)
        for row in pixels
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def finder_pattern(matrix: list[list[int]], left: int, top: int) -> None:
    for y in range(7):
        for x in range(7):
            outer = x in {0, 6} or y in {0, 6}
            center = 2 <= x <= 4 and 2 <= y <= 4
            matrix[top + y][left + x] = 1 if outer or center else 0


def make_qr_like_png(path: Path, scale: int = 8) -> None:
    modules = 29
    matrix = [[0 for _ in range(modules)] for _ in range(modules)]
    finder_pattern(matrix, 1, 1)
    finder_pattern(matrix, modules - 8, 1)
    finder_pattern(matrix, 1, modules - 8)
    for y in range(9, modules - 9):
        for x in range(9, modules - 9):
            matrix[y][x] = 1 if (x * 3 + y * 5) % 4 in {0, 1} else 0

    pixels: list[list[tuple[int, int, int]]] = []
    for row in matrix:
        for _ in range(scale):
            pixel_row: list[tuple[int, int, int]] = []
            for value in row:
                color = (0, 0, 0) if value else (255, 255, 255)
                pixel_row.extend([color] * scale)
            pixels.append(pixel_row)
    write_png(path, pixels)


class QrVisionTests(unittest.TestCase):
    def test_detects_qr_like_png_and_rejects_blank_image(self):
        qr_vision = load_qr_vision()

        with tempfile.TemporaryDirectory() as tmp:
            qr_path = Path(tmp) / "qr.png"
            blank_path = Path(tmp) / "blank.png"
            make_qr_like_png(qr_path)
            write_png(blank_path, [[(255, 255, 255) for _ in range(240)] for _ in range(240)])

            self.assertTrue(qr_vision.image_has_qr_like_pattern(qr_path))
            self.assertFalse(qr_vision.image_has_qr_like_pattern(blank_path))


if __name__ == "__main__":
    unittest.main()
