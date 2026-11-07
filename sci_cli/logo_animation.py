"""Build the shared braille-dot rotation: python -m sci_cli.logo_animation."""

import json
import math
from functools import lru_cache
from importlib.resources import files

# Braille bit positions, in pixel order (two columns, four rows per cell).
DOTS = ((1, 8), (2, 16), (4, 32), (64, 128))


def rotation_frame(lines, angle):
    """Project the existing dotted artwork as a thin rotating plaque."""
    if abs(angle) < 1e-9:
        return list(lines)
    width, height = max(map(len, lines)), len(lines)
    cx, cy = width - 0.5, height * 2 - 0.5
    cells = [[0] * width for _ in lines]
    yaw, tilt = math.cos(angle), math.sin(angle) * 0.10
    # A little thickness keeps the edge visible as the face turns away.
    for row, line in enumerate(lines):
        for col, char in enumerate(line):
            bits = ord(char) - 0x2800
            if not 0 <= bits <= 255:
                continue
            for dy, masks in enumerate(DOTS):
                for dx, mask in enumerate(masks):
                    if not bits & mask:
                        continue
                    x, y = col * 2 + dx - cx, row * 4 + dy - cy
                    for depth in (-0.8, 0.0, 0.8):
                        z = -x * math.sin(angle) + depth * yaw
                        scale = 150 / (150 + z)
                        px = round(cx + (x * yaw + depth * math.sin(angle)) * scale)
                        py = round(cy + (y * math.cos(tilt) - z * math.sin(tilt)) * scale)
                        if 0 <= px < width * 2 and 0 <= py < height * 4:
                            cells[py // 4][px // 2] |= DOTS[py % 4][px % 2]
    return [''.join(chr(0x2800 + bits) for bits in row) for row in cells]


@lru_cache(maxsize=1)
def logo_frames():
    return json.loads(files('sci_cli').joinpath('data/boltzmann-spin.json').read_text(encoding='utf-8'))


if __name__ == '__main__':
    from sci_cli.banner_science import science_art
    from pathlib import Path

    # One second face-on, six seconds of eased rotation, one second settled.
    frames = []
    for index in range(96):
        fraction = min(1.0, max(0.0, (index - 12) / 72))
        angle = math.tau * (fraction * fraction * (3 - 2 * fraction))
        frames.append(rotation_frame(science_art()['boltzmann'], angle if fraction < 1 else 0))
    target = Path(__file__).with_name('data') / 'boltzmann-spin.json'
    target.write_text(json.dumps({'frame_ms': 1000 / 12, 'frames': frames}, ensure_ascii=False) + '\n', encoding='utf-8')
