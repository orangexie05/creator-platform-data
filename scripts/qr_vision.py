#!/usr/bin/env python3
"""Tiny local vision checks for cropped QR-code screenshots."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def _png_luma(path: Path) -> tuple[int, int, list[int]]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG image")

    offset = len(PNG_SIGNATURE)
    width = height = color_type = bit_depth = None
    idat = bytearray()

    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", payload)
            if bit_depth != 8 or color_type not in {0, 2, 6} or interlace != 0:
                raise ValueError("unsupported PNG format")
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"IEND":
            break

    if width is None or height is None or color_type is None or bit_depth is None:
        raise ValueError("missing PNG header")

    channels = {0: 1, 2: 3, 6: 4}[color_type]
    stride = width * channels
    raw = zlib.decompress(bytes(idat))
    previous = [0] * stride
    luma: list[int] = []
    cursor = 0

    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        row = list(raw[cursor:cursor + stride])
        cursor += stride
        for index, value in enumerate(row):
            left = row[index - channels] if index >= channels else 0
            up = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 1:
                row[index] = (value + left) & 0xFF
            elif filter_type == 2:
                row[index] = (value + up) & 0xFF
            elif filter_type == 3:
                row[index] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                row[index] = (value + _paeth(left, up, upper_left)) & 0xFF
            elif filter_type != 0:
                raise ValueError("unsupported PNG filter")

        for x in range(width):
            base = x * channels
            if color_type == 0:
                luma.append(row[base])
            else:
                red, green, blue = row[base], row[base + 1], row[base + 2]
                luma.append((red * 299 + green * 587 + blue * 114) // 1000)
        previous = row

    return width, height, luma


def _sample_grid(width: int, height: int, luma: list[int], size: int = 33) -> list[list[bool]]:
    low = min(luma)
    high = max(luma)
    threshold = (low + high) // 2
    grid: list[list[bool]] = []
    for gy in range(size):
        row: list[bool] = []
        y = min(height - 1, int((gy + 0.5) * height / size))
        for gx in range(size):
            x = min(width - 1, int((gx + 0.5) * width / size))
            row.append(luma[y * width + x] < threshold)
        grid.append(row)
    return grid


def _transition_ratio(grid: list[list[bool]]) -> float:
    horizontal = sum(
        1
        for row in grid
        for index in range(1, len(row))
        if row[index] != row[index - 1]
    )
    vertical = sum(
        1
        for y in range(1, len(grid))
        for x in range(len(grid[0]))
        if grid[y][x] != grid[y - 1][x]
    )
    possible = len(grid) * (len(grid[0]) - 1) + (len(grid) - 1) * len(grid[0])
    return (horizontal + vertical) / possible


def _finder_score(grid: list[list[bool]], left: int, top: int, size: int) -> float:
    matches = 0
    total = size * size
    for y in range(size):
        for x in range(size):
            u = (x + 0.5) / size
            v = (y + 0.5) / size
            outer = u < 0.18 or u > 0.82 or v < 0.18 or v > 0.82
            center = 0.34 <= u <= 0.66 and 0.34 <= v <= 0.66
            expected_black = outer or center
            if grid[top + y][left + x] == expected_black:
                matches += 1
    return matches / total


def _corner_has_finder(grid: list[list[bool]], corner: str) -> bool:
    grid_size = len(grid)
    best = 0.0
    for size in range(6, 11):
        if corner == "top-left":
            left_values = range(0, 8)
            top_values = range(0, 8)
        elif corner == "top-right":
            left_values = range(grid_size - size - 8, grid_size - size + 1)
            top_values = range(0, 8)
        else:
            left_values = range(0, 8)
            top_values = range(grid_size - size - 8, grid_size - size + 1)
        for left in left_values:
            for top in top_values:
                if left < 0 or top < 0 or left + size > grid_size or top + size > grid_size:
                    continue
                best = max(best, _finder_score(grid, left, top, size))
    return best >= 0.72


def image_has_qr_like_pattern(path: Path | str) -> bool:
    """Return True only when a local PNG visually resembles a cropped QR code."""
    try:
        width, height, luma = _png_luma(Path(path))
    except Exception:
        return False

    if width < 120 or height < 120:
        return False
    aspect = width / height
    if aspect < 0.72 or aspect > 1.38:
        return False
    if max(luma) - min(luma) < 80:
        return False

    grid = _sample_grid(width, height, luma)
    dark_ratio = sum(cell for row in grid for cell in row) / (len(grid) * len(grid[0]))
    if dark_ratio < 0.18 or dark_ratio > 0.68:
        return False
    transition_ratio = _transition_ratio(grid)
    if transition_ratio < 0.12:
        return False

    finder_count = sum(
        _corner_has_finder(grid, corner)
        for corner in ("top-left", "top-right", "bottom-left")
    )
    if finder_count >= 2:
        return True
    if finder_count >= 1 and transition_ratio >= 0.22:
        return True
    return transition_ratio >= 0.24 and 0.22 <= dark_ratio <= 0.55
