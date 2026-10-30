import hashlib
import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageChops, ImageStat

from stamping import MM, StampOptions, load_stamp, render_preview, stamp_pdf


class StampingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.source = self.folder / "documento.pdf"
        self.stamp = self.folder / "sello.png"
        self.target = self.folder / "resultado.pdf"
        image = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 99, 99), fill=(255, 0, 0, 255))
        draw.rectangle((100, 0, 199, 99), fill=(0, 0, 255, 255))
        image.save(self.stamp)
        with pymupdf.open() as doc:
            for rotation in (0, 90, 180, 270):
                page = doc.new_page(width=600, height=800)
                page.insert_text((60, 300), f"Contenido original {rotation}")
                page.set_rotation(rotation)
            page = doc.new_page(width=900, height=650)
            page.insert_text((80, 300), "Pagina recortada")
            page.set_cropbox(pymupdf.Rect(40, 30, 840, 600))
            page.set_rotation(90)
            doc.set_metadata({"title": "Prueba de preservacion"})
            doc.set_toc([[1, "Inicio", 1]])
            doc.save(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_rotations_crop_and_original_preserved(self):
        digest = hashlib.sha256(self.source.read_bytes()).digest()
        progress = []
        count = stamp_pdf(self.source, self.stamp, self.target,
                          progress=lambda n, total: progress.append((n, total)))
        self.assertEqual(count, 5)
        self.assertEqual(progress, [(n, 5) for n in range(1, 6)])
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).digest(), digest)
        with pymupdf.open(self.target) as result, pymupdf.open(self.source) as original:
            self.assertEqual(result.metadata["title"], original.metadata["title"])
            self.assertEqual(result.get_toc(), original.get_toc())
            for i, page in enumerate(result):
                self.assertEqual(page.rotation, original[i].rotation)
                self.assertEqual(page.cropbox, original[i].cropbox)
                self.assertEqual(page.get_text(), original[i].get_text())
                pix = page.get_pixmap(alpha=False)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                x = page.rect.width - (10 + 35) * MM
                y = 10 * MM
                red = image.getpixel((int(x + 35 * MM * .25), int(y + 17.5 * MM * .5)))
                blue = image.getpixel((int(x + 35 * MM * .75), int(y + 17.5 * MM * .5)))
                self.assertEqual(red, (255, 0, 0), f"Orientación roja en página {i + 1}")
                self.assertEqual(blue, (0, 0, 255), f"Orientación azul en página {i + 1}")

    def test_preview_matches_output(self):
        options = StampOptions(42, 16, 8)
        stamp_pdf(self.source, self.stamp, self.target, options)
        for number in range(5):
            preview, _ = render_preview(self.source, number, load_stamp(self.stamp), options)
            actual, _ = render_preview(self.target, number, None, options)
            self.assertEqual(preview.size, actual.size)
            # La serialización PDF redondea coordenadas; tolerar antialiasing subpíxel.
            diff = ImageStat.Stat(ImageChops.difference(preview, actual))
            self.assertLess(max(diff.mean), 0.1)

    def test_text_remains_visible_over_stamp(self):
        source = self.folder / "texto_sobre_sello.pdf"
        with pymupdf.open() as doc:
            page = doc.new_page(width=600, height=800)
            page.insert_text((480, 58), "TEXTO", fontsize=22, color=(0, 0, 0))
            doc.save(source)
        stamp_pdf(source, self.stamp, self.target)
        with pymupdf.open(source) as original, pymupdf.open(self.target) as result:
            before = original[0].get_pixmap(alpha=False)
            after = result[0].get_pixmap(alpha=False)
            black_pixels = [(x, y) for x in range(475, 570) for y in range(30, 75)
                            if max(before.pixel(x, y)) < 20]
            self.assertGreater(len(black_pixels), 100)
            self.assertTrue(all(max(after.pixel(x, y)) < 20 for x, y in black_pixels),
                            "El sello está tapando el texto original")
            self.assertEqual(after.pixel(480, 32), (255, 0, 0))
            self.assertEqual(result[0].get_text(), original[0].get_text())
        preview, _ = render_preview(source, 0, load_stamp(self.stamp), StampOptions())
        actual, _ = render_preview(self.target, 0, None, StampOptions())
        diff = ImageStat.Stat(ImageChops.difference(preview, actual))
        self.assertLess(max(diff.mean), 0.1)

    def test_original_cannot_be_output(self):
        with self.assertRaises(ValueError):
            stamp_pdf(self.source, self.stamp, self.source)

    def test_image_cannot_be_output(self):
        with self.assertRaises(ValueError):
            stamp_pdf(self.source, self.stamp, self.stamp)

    def test_invalid_options(self):
        for options in (StampOptions(-1), StampOptions(0), StampOptions(float("nan")),
                        StampOptions(float("inf")), StampOptions(35, -1), StampOptions(35, 10, -1)):
            with self.subTest(options=options), self.assertRaises(ValueError):
                stamp_pdf(self.source, self.stamp, self.target, options)
        self.assertFalse(self.target.exists())

    def test_oversize_leaves_existing_destination_untouched(self):
        self.target.write_bytes(b"contenido anterior")
        with self.assertRaisesRegex(ValueError, "no cabe"):
            stamp_pdf(self.source, self.stamp, self.target, StampOptions(500))
        self.assertEqual(self.target.read_bytes(), b"contenido anterior")

    def test_password_protected_pdf(self):
        encrypted = self.folder / "protegido.pdf"
        with pymupdf.open(self.source) as doc:
            doc.save(encrypted, encryption=pymupdf.PDF_ENCRYPT_AES_256,
                     owner_pw="owner", user_pw="password")
        with self.assertRaises(ValueError):
            stamp_pdf(encrypted, self.stamp, self.target)

    def test_invalid_image(self):
        self.stamp.write_bytes(b"imagen invalida")
        with self.assertRaises(Exception):
            stamp_pdf(self.source, self.stamp, self.target)
        self.assertFalse(self.target.exists())

    def test_transparency(self):
        image = Image.new("RGBA", (100, 100), (0, 255, 0, 0))
        ImageDraw.Draw(image).rectangle((20, 20, 80, 80), fill=(0, 128, 0, 255))
        image.save(self.stamp)
        stamp_pdf(self.source, self.stamp, self.target)
        with pymupdf.open(self.target) as doc:
            page = doc[0]
            pix = page.get_pixmap(alpha=False)
            x = int(page.rect.width - 45 * MM + 2)
            self.assertEqual(pix.pixel(x, int(10 * MM + 2)), (255, 255, 255))

    def test_jpeg_input(self):
        jpg = self.folder / "sello.jpg"
        with Image.open(self.stamp) as image:
            image.convert("RGB").save(jpg)
        self.assertEqual(stamp_pdf(self.source, jpg, self.target), 5)


if __name__ == "__main__":
    unittest.main()
