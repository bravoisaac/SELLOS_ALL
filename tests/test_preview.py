import math
import unittest

import pymupdf
from PIL import Image, ImageChops, ImageStat

import test_stamping
from preview import moved_options
from stamping import MM, StampOptions, load_stamp, render_preview_layer, stamp_pdf


class PreviewTests(unittest.TestCase):
    def test_drag_converts_to_margins(self):
        result = moved_options((600, 800), .5, StampOptions(), 150, 220)
        self.assertAlmostEqual(result.top_mm * MM, 220, places=4)
        self.assertAlmostEqual(600 - (result.right_mm + result.width_mm) * MM, 150, places=4)

    def test_drag_clamps_all_edges(self):
        for x, y in [(-100, -100), (10000, 10000), (-100, 10000), (10000, -100)]:
            result = moved_options((600, 800), .5, StampOptions(), x, y)
            self.assertGreaterEqual(result.top_mm, 0)
            self.assertGreaterEqual(result.right_mm, 0)
            self.assertLessEqual((result.width_mm + result.right_mm) * MM, 600)
            self.assertLessEqual((result.width_mm * .5 + result.top_mm) * MM, 800)

    def test_invalid_drag_rejected(self):
        for x in (math.nan, math.inf):
            with self.assertRaises(ValueError):
                moved_options((600, 800), .5, StampOptions(), x, 20)
        with self.assertRaises(ValueError):
            moved_options((60, 80), .5, StampOptions(), 0, 0)

    def test_layers_match_pdf_after_drag_on_rotated_and_cropped_pages(self):
        fixture = test_stamping.StampingTests()
        fixture.setUp()
        try:
            options = moved_options((600, 800), .5, StampOptions(), 170, 240)
            stamp_pdf(fixture.source, fixture.stamp, fixture.target, options)
            with Image.open(fixture.stamp) as stamp, pymupdf.open(fixture.target) as result:
                for page in range(5):
                    layer, count, size = render_preview_layer(fixture.source, page)
                    self.assertEqual(count, 5)
                    scale = layer.width / size[0]
                    width = options.width_mm * MM
                    x = size[0] - options.right_mm * MM - width
                    y = options.top_mm * MM
                    canvas = Image.new("RGBA", layer.size, "white")
                    resized = stamp.resize((round(width * scale), round(width * .5 * scale)))
                    canvas.alpha_composite(resized, (round(x * scale), round(y * scale)))
                    canvas.alpha_composite(layer)
                    pix = result[page].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                    actual = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    self.assertEqual(canvas.size, actual.size)
                    diff = ImageStat.Stat(ImageChops.difference(canvas.convert("RGB"), actual))
                    self.assertLess(max(diff.mean), .5)
        finally:
            fixture.tearDown()

    def test_opaque_document_background_stays_above_stamp(self):
        fixture = test_stamping.StampingTests()
        fixture.setUp()
        try:
            path = fixture.folder / "fondo.pdf"
            with pymupdf.open() as doc:
                page = doc.new_page()
                page.draw_rect(page.rect, fill=(1, 1, 1), color=None)
                doc.save(path)
            image, _, _ = render_preview_layer(path, 0)
            self.assertEqual(image.getpixel((100, 100)), (255, 255, 255, 255))
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
