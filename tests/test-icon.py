#!/usr/bin/env python3
"""Validate the code-native icon and rasterize the tray sizes when possible."""

from __future__ import annotations

import tempfile
import unittest
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "icons" / "xiapin.svg"
SIZES = (16, 22, 24)
COLORS = {"#050505", "#55585d", "#f7f7f5", "#24272c", "#e95420"}


class IconTest(unittest.TestCase):
    def test_svg_is_the_selected_pixel_sunglasses_mark(self) -> None:
        text = ICON.read_text(encoding="utf-8")
        root = ElementTree.fromstring(text)
        self.assertEqual(root.attrib.get("viewBox"), "0 0 24 24")
        self.assertEqual(root.attrib.get("aria-label"), "瞎拼输入法像素墨镜标志")
        self.assertNotIn("cursor", text.lower())
        self.assertNotIn(">^|", text)
        self.assertNotIn("拼</", text)
        self.assertNotRegex(text.lower(), r"#[89a-f][0-9a-f]{0,5}00[0-9a-f]*")
        self.assertEqual({value.lower() for value in root.iter() for value in
                          (value.attrib.get("fill"), value.attrib.get("stroke"))
                          if value and value.startswith("#")}, COLORS)
        paths = root.findall("{http://www.w3.org/2000/svg}path")
        self.assertEqual(len(paths), 3, "the mark must contain frame, lenses and highlights")
        circles = root.findall("{http://www.w3.org/2000/svg}circle")
        self.assertEqual(len(circles), 0, "the mark must not contain unexplained dots")

    def test_renders_at_tray_sizes(self) -> None:
        cairo_stack = None
        try:
            import cairo
            import gi

            gi.require_foreign("cairo")
            gi.require_version("Rsvg", "2.0")
            from gi.repository import Rsvg
            cairo_stack = (cairo, Rsvg)
        except (ImportError, ValueError) as exc:
            rasterizer_error = exc
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            for size in SIZES:
                target = Path(directory) / f"xiapin-{size}.png"
                if cairo_stack:
                    cairo, Rsvg = cairo_stack
                    handle = Rsvg.Handle.new_from_file(str(ICON))
                    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
                    context = cairo.Context(surface)
                    viewport = Rsvg.Rectangle()
                    viewport.x = viewport.y = 0
                    viewport.width = viewport.height = size
                    self.assertTrue(handle.render_document(context, viewport))
                    surface.write_to_png(str(target))
                else:
                    if shutil.which("ffmpeg") is None:
                        self.skipTest(f"SVG rasterizer unavailable: {rasterizer_error}")
                    subprocess.run([
                        "ffmpeg", "-hide_banner", "-loglevel", "error",
                        "-i", str(ICON), "-frames:v", "1", "-vf",
                        f"scale={size}:{size}:flags=lanczos", "-y", str(target),
                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                image = Image.open(target).convert("RGBA")
                self.assertEqual(image.size, (size, size))
                pixels = list(image.get_flattened_data())
                visible = [pixel for pixel in pixels if pixel[3] > 32]
                orange = [pixel for pixel in visible
                          if pixel[0] > 180 and 45 < pixel[1] < 150 and pixel[2] < 90]
                pale = [pixel for pixel in visible
                        if pixel[0] > 180 and pixel[1] > 180 and pixel[2] > 180]
                self.assertGreater(len(visible), size * size // 2)
                self.assertGreater(len(pale), size, f"glasses frame disappeared at {size}px")
                self.assertGreater(len(orange), 0, f"orange lens highlight disappeared at {size}px")


if __name__ == "__main__":
    unittest.main()
