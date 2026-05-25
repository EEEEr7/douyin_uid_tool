"""Build a full-bleed square app_icon.ico for Windows desktop shortcuts."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def _luminance(r: int, g: int, b: int) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


def _collect_wool_pixels(rgba: Image.Image) -> tuple[list[int], list[int]]:
    px = rgba.load()
    w, h = rgba.size
    xs: list[int] = []
    ys: list[int] = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 20:
                continue
            if r >= 212 and g >= 212 and b >= 212:
                xs.append(x)
                ys.append(y)
    if len(xs) < 40:
        xs.clear()
        ys.clear()
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a >= 20 and _luminance(r, g, b) >= 95:
                    xs.append(x)
                    ys.append(y)
    return xs, ys


def _crop_subject(source: Image.Image) -> Image.Image:
    rgba = source.convert("RGBA")
    xs, ys = _collect_wool_pixels(rgba)
    if not xs:
        return rgba.crop(_alpha_bbox(rgba))
    pad = 2
    min_x = max(0, min(xs) - pad)
    min_y = max(0, min(ys) - pad)
    max_x = min(rgba.width - 1, max(xs) + pad)
    max_y = min(rgba.height - 1, max(ys) + pad)
    return rgba.crop((min_x, min_y, max_x + 1, max_y + 1))


def _alpha_bbox(rgba: Image.Image, pad: int = 2) -> tuple[int, int, int, int]:
    px = rgba.load()
    w, h = rgba.size
    min_x, min_y = w, h
    max_x, max_y = 0, 0
    for y in range(h):
        for x in range(w):
            if px[x, y][3] >= 16:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < min_x:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        return left, top, left + side, top + side
    min_x = max(0, min_x - pad)
    min_y = max(0, min_y - pad)
    max_x = min(w - 1, max_x + pad)
    max_y = min(h - 1, max_y + pad)
    return min_x, min_y, max_x + 1, max_y + 1


def _square_fill(subject: Image.Image, size: int = 256, bg: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    rgba = subject.convert("RGBA")
    sw, sh = rgba.size
    side = max(sw, sh)
    square = Image.new("RGBA", (side, side), (*bg, 255))
    ox = (side - sw) // 2
    oy = (side - sh) // 2
    square.paste(rgba, (ox, oy), rgba)
    square = square.resize((size, size), Image.Resampling.LANCZOS)
    return square.convert("RGB")


def _save_windows_ico(square_rgb: Image.Image, ico_path: Path) -> None:
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [square_rgb.resize((s, s), Image.Resampling.LANCZOS) for s in sizes]
    frames[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )


def main() -> int:
    root = Path(__file__).resolve().parent
    png_path = root / "app_icon.png"
    ico_path = root / "app_icon.ico"
    preview_path = root / "app_icon_preview.png"
    if not png_path.is_file():
        print(f"Missing {png_path}", file=sys.stderr)
        return 1

    subject = _crop_subject(Image.open(png_path))
    square = _square_fill(subject, 256)
    square.save(preview_path, format="PNG")
    _save_windows_ico(square, ico_path)
    print(f"Wrote {ico_path} (subject {subject.size[0]}x{subject.size[1]}, wool crop, full-bleed RGB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
