# SPDX-License-Identifier: MIT
"""Render a hero-source HTML figure to PNG at 3x DPI using Playwright.

Replaces the earlier `chrome --headless --force-device-scale-factor` pattern,
which in current Chrome versions renders content at roughly 1/4 CSS width
regardless of the DPI flag. Playwright correctly separates the device scale
factor from the CSS viewport, so `.bench`, `.hero`, or any fixed-width figure
container renders at its full CSS size and the output is a clean 3x bitmap.

Usage:
    python scripts/render-bench-png.py
        # defaults: bench.html + .bench -> docs/bench.png
    python scripts/render-bench-png.py --src docs/hero-source/hero.html \
        --selector .hero --out docs/hero.png --viewport-height 1800

Requires: `python -m pip install playwright pillow && python -m playwright install chromium`.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent


def render(src: Path, selector: str, out: Path, viewport: tuple[int, int], scale: int) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            device_scale_factor=scale,
            viewport={"width": viewport[0], "height": viewport[1]},
        )
        page = ctx.new_page()
        page.goto(src.as_uri())
        page.wait_for_load_state("networkidle")
        el = page.query_selector(selector)
        if not el:
            raise RuntimeError(f"selector {selector!r} not found in {src}")
        el.screenshot(path=str(out))
        browser.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, default=REPO / "docs" / "hero-source" / "bench.html")
    ap.add_argument("--selector", default=".bench")
    ap.add_argument("--out", type=Path, default=REPO / "docs" / "bench.png")
    ap.add_argument("--viewport-width", type=int, default=1280)
    ap.add_argument("--viewport-height", type=int, default=1400)
    ap.add_argument("--scale", type=int, default=3)
    args = ap.parse_args()

    # Resolve CLI paths so relative arguments also work. `Path.as_uri()`
    # requires an absolute path; without this, `--src docs/hero-source/hero.html`
    # raises `ValueError: relative path can't be expressed as a file URI`.
    src = (args.src if args.src.is_absolute() else REPO / args.src).resolve()
    out = (args.out if args.out.is_absolute() else REPO / args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    render(
        src=src,
        selector=args.selector,
        out=out,
        viewport=(args.viewport_width, args.viewport_height),
        scale=args.scale,
    )

    from PIL import Image

    im = Image.open(out)
    print(f"rendered: {out}")
    print(f"size: {im.size[0]}x{im.size[1]}  ({os.path.getsize(out) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
