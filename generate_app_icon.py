"""Build square app_icon.ico with solid white background (no transparency)."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

WHITE = (255, 255, 255)
ICON_SIZE = 256
MARGIN_RATIO = 0.10


def _source_path(root: Path) -> Path | None:
    for name in ("app_icon.png", "xteink_logo.png"):
        path = root / name
        if path.is_file():
            return path
    return None


def _flatten_on_white(img: Image.Image) -> Image.Image:
    """Composite RGBA onto opaque white — removes transparent background."""
    rgba = img.convert("RGBA")
    base = Image.new("RGB", rgba.size, WHITE)
    base.paste(rgba, mask=rgba.split()[3])
    return base


def _content_bbox(rgb: Image.Image, pad: int = 6, white_threshold: int = 248) -> tuple[int, int, int, int]:
    px = rgb.load()
    w, h = rgb.size
    min_x, min_y = w, h
    max_x, max_y = 0, 0
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if r < white_threshold or g < white_threshold or b < white_threshold:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < min_x:
        return 0, 0, w, h
    min_x = max(0, min_x - pad)
    min_y = max(0, min_y - pad)
    max_x = min(w - 1, max_x + pad)
    max_y = min(h - 1, max_y + pad)
    return min_x, min_y, max_x + 1, max_y + 1


def _square_white_icon(rgb: Image.Image, size: int = ICON_SIZE) -> Image.Image:
    cropped = rgb.crop(_content_bbox(rgb))
    cw, ch = cropped.size
    inner = max(cw, ch)
    side = max(1, int(round(inner / (1 - 2 * MARGIN_RATIO))))
    square = Image.new("RGB", (side, side), WHITE)
    ox = (side - cw) // 2
    oy = (side - ch) // 2
    square.paste(cropped, (ox, oy))
    return square.resize((size, size), Image.Resampling.LANCZOS)


def _save_windows_ico(square_rgb: Image.Image, ico_path: Path) -> None:
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [
        square_rgb.resize((s, s), Image.Resampling.LANCZOS).convert("RGB")
        for s in sizes
    ]
    frames[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )


def main() -> int:
    root = Path(__file__).resolve().parent
    src = _source_path(root)
    if src is None:
        print("Missing app_icon.png or xteink_logo.png", file=sys.stderr)
        return 1

    ico_path = root / "app_icon.ico"
    preview_path = root / "app_icon_preview.png"

    flat = _flatten_on_white(Image.open(src))
    square = _square_white_icon(flat, ICON_SIZE)
    square.save(preview_path, format="PNG")
    _save_windows_ico(square, ico_path)
    print(f"Wrote {ico_path} from {src.name} (solid white background, RGB, no alpha)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
