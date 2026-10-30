import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image, ImageChops, ImageStat

import test_stamping
from preview import moved_options
from stamping import MM, StampOptions, render_preview_layer, stamp_pdf


class LayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.source = self.folder / "original.pdf"
        self.image = self.folder / "sello.png"
        Image.new("RGB", (200, 100), "red").save(self.image)
        with pymupdf.open() as doc:
            page = doc.new_page(width=600, height=800)
            page.draw_rect(page.rect, fill=(0, 1, 0), color=None)
            page.insert_text((480, 58), "TEXTO", fontsize=22, color=(0, 0, 0))
            doc.save(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_three_distinct_layers_preserve_searchable_text(self):
        with pymupdf.open(self.source) as original:
            pix = original[0].get_pixmap(alpha=False)
            black = [(x, y) for x in range(480, 565) for y in range(35, 65)
                     if max(pix.pixel(x, y)) < 20]
            self.assertGreater(len(black), 100)
            original_text = original[0].get_text()
        for layer in ("background", "middle", "foreground"):
            with self.subTest(layer=layer):
                output = self.folder / f"{layer}.pdf"
                stamp_pdf(self.source, self.image, output, StampOptions(layer=layer))
                with pymupdf.open(output) as doc:
                    pix = doc[0].get_pixmap(alpha=False)
                    self.assertEqual(pix.pixel(480, 32), (0, 255, 0) if layer == "background" else (255, 0, 0))
                    if layer == "foreground":
                        self.assertTrue(all(pix.pixel(x, y) == (255, 0, 0) for x, y in black))
                    else:
                        self.assertTrue(all(max(pix.pixel(x, y)) < 20 for x, y in black))
                    self.assertEqual(doc[0].get_text(), original_text)

    def test_middle_handles_rotation_crop_and_nested_forms(self):
        fixture = test_stamping.StampingTests()
        fixture.setUp()
        try:
            output = self.folder / "rotadas.pdf"
            stamp_pdf(fixture.source, self.image, output, StampOptions(layer="middle"))
            with pymupdf.open(fixture.source) as original, pymupdf.open(output) as result:
                for index, page in enumerate(result):
                    self.assertEqual(page.get_text(), original[index].get_text())
                    self.assertEqual(page.rotation, original[index].rotation)
                    self.assertEqual(page.cropbox, original[index].cropbox)
                    pix = page.get_pixmap(alpha=False)
                    self.assertEqual(pix.pixel(int(page.rect.width - 40 * MM), int(12 * MM)), (255, 0, 0))
            nested = self.folder / "formulario.pdf"
            with pymupdf.open(self.source) as original, pymupdf.open() as doc:
                page = doc.new_page(width=600, height=800)
                page.show_pdf_page(page.rect, original, 0)
                doc.save(nested)
            stamp_pdf(nested, self.image, output, StampOptions(layer="middle"))
            with pymupdf.open(output) as doc:
                self.assertEqual(doc[0].get_text().strip(), "TEXTO")
                self.assertEqual(doc[0].get_pixmap(alpha=False).pixel(480, 32), (255, 0, 0))
        finally:
            fixture.tearDown()

    def test_layered_preview_matches_export(self):
        for layer in ("background", "middle", "foreground"):
            options = StampOptions(layer=layer)
            output = self.folder / f"preview_{layer}.pdf"
            stamp_pdf(self.source, self.image, output, options)
            source, _, size = render_preview_layer(self.source, 0, layer)
            base, top = source if isinstance(source, tuple) else (source, None)
            scale = base.width / size[0]
            width = options.width_mm * MM
            stamp = Image.open(self.image).convert("RGBA").resize((round(width * scale), round(width * .5 * scale)))
            origin = (round((size[0] - options.right_mm * MM - width) * scale), round(options.top_mm * MM * scale))
            composite = Image.new("RGBA", base.size, "white")
            if layer == "background":
                composite.alpha_composite(stamp, origin)
                composite.alpha_composite(base)
            else:
                composite.alpha_composite(base)
                composite.alpha_composite(stamp, origin)
                if top:
                    composite.alpha_composite(top)
            with pymupdf.open(output) as doc:
                pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                actual = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                diff = ImageStat.Stat(ImageChops.difference(composite.convert("RGB"), actual))
                self.assertLess(max(diff.mean), .5, layer)

    def test_middle_preserves_annotations_links_and_fields(self):
        source = self.folder / "anotado.pdf"
        with pymupdf.open(self.source) as doc:
            page = doc[0]
            page.add_rect_annot(pymupdf.Rect(50, 100, 100, 150))
            page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(50, 200, 150, 220), "uri": "https://example.com"})
            widget = pymupdf.Widget()
            widget.field_name = "nombre"
            widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
            widget.field_value = "Valor conservado"
            widget.rect = pymupdf.Rect(50, 250, 250, 280)
            page.add_widget(widget)
            doc.save(source)
        output = self.folder / "anotado_salida.pdf"
        stamp_pdf(source, self.image, output, StampOptions(layer="middle"))
        with pymupdf.open(output) as doc:
            page = doc[0]
            self.assertEqual(len(list(page.annots())), 1)
            self.assertEqual(page.get_links()[0]["uri"], "https://example.com")
            self.assertEqual(list(page.widgets())[0].field_value, "Valor conservado")

    def test_text_clipping_rejected_only_for_middle(self):
        source = self.folder / "recorte.pdf"
        with pymupdf.open() as doc:
            doc.new_page().insert_text((100, 100), "MASK", render_mode=4)
            doc.save(source)
        output = self.folder / "recorte_salida.pdf"
        with self.assertRaisesRegex(ValueError, "máscara"):
            stamp_pdf(source, self.image, output, StampOptions(layer="middle"))
        self.assertFalse(output.exists())
        stamp_pdf(source, self.image, output, StampOptions(layer="foreground"))

    def test_drag_preserves_selected_layer(self):
        for layer in ("background", "middle", "foreground"):
            result = moved_options((600, 800), .5, StampOptions(layer=layer), 250, 300)
            self.assertEqual(result.layer, layer)

    def test_middle_does_not_reveal_text_covered_by_graphics(self):
        source = self.folder / "texto_cubierto.pdf"
        with pymupdf.open() as doc:
            page = doc.new_page()
            page.insert_text((50, 100), "TEXTO OCULTO", fontsize=24)
            page.draw_rect(pymupdf.Rect(40, 60, 300, 120), fill=(1, 1, 1), color=None)
            doc.save(source)
        output = self.folder / "no_modificar.pdf"
        with self.assertRaisesRegex(ValueError, "cambiaría el aspecto"):
            stamp_pdf(source, self.image, output, StampOptions(layer="middle"))
        self.assertFalse(output.exists())

    def test_invalid_layer_rejected(self):
        with self.assertRaises(ValueError):
            StampOptions(layer="invalid").validate()

    def test_middle_on_blank_page(self):
        source = self.folder / "vacio.pdf"
        with pymupdf.open() as doc:
            doc.new_page()
            doc.save(source)
        self.assertEqual(stamp_pdf(source, self.image, self.folder / "vacio_salida.pdf", StampOptions(layer="middle")), 1)

    def test_middle_above_image_background_below_text(self):
        source = self.folder / "imagen_y_texto.pdf"
        background = self.folder / "fondo.png"
        Image.new("RGB", (600, 800), "green").save(background)
        with pymupdf.open() as doc:
            page = doc.new_page(width=600, height=800)
            page.insert_image(page.rect, filename=str(background))
            page.insert_text((480, 58), "TEXTO", fontsize=22)
            doc.save(source)
        output = self.folder / "imagen_y_texto_salida.pdf"
        stamp_pdf(source, self.image, output, StampOptions(layer="middle"))
        with pymupdf.open(output) as doc:
            page = doc[0]
            pix = page.get_pixmap(alpha=False)
            self.assertEqual(pix.pixel(480, 32), (255, 0, 0))
            self.assertEqual(pix.pixel(200, 200), (0, 128, 0))
            self.assertEqual(page.get_text().strip(), "TEXTO")
            self.assertGreater(sum(max(pix.pixel(x, y)) < 20 for x in range(480, 565) for y in range(35, 65)), 100)


if __name__ == "__main__":
    unittest.main()
