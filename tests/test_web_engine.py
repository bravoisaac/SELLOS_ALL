import importlib.util
import io
import json
import unittest
from pathlib import Path

import pymupdf
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, NumberObject

import test_stamping

spec = importlib.util.spec_from_file_location('web_engine', Path(__file__).parents[1] / 'docs' / 'engine.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class WebEngineTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_stamping.StampingTests()
        self.fixture.setUp()
        self.data = self.fixture.source.read_bytes()
        self.image = Image.open(self.fixture.stamp).convert('RGBA')

    def tearDown(self):
        self.image.close()
        self.fixture.tearDown()

    def run_engine(self, data=None, layer='foreground', page=-1, **opts):
        options = {'width': 35, 'top': 10, 'right': 10, 'layer': layer, **opts}
        return engine.process(data or self.data, self.image.tobytes(), *self.image.size, json.dumps(options), page)

    def test_rotations_crop_metadata_and_text(self):
        for layer in ('foreground', 'background', 'middle'):
            with self.subTest(layer=layer):
                result = self.run_engine(layer=layer)
                self.assertEqual(result['pages'], 5)
                with pymupdf.open(stream=result['pdf'], filetype='pdf') as output, pymupdf.open(stream=self.data, filetype='pdf') as original:
                    self.assertEqual(output.metadata['title'], original.metadata['title'])
                    self.assertEqual(output.get_toc(), original.get_toc())
                    for index, page in enumerate(output):
                        self.assertEqual(page.rotation, original[index].rotation)
                        self.assertEqual(page.cropbox, original[index].cropbox)
                        self.assertEqual(page.get_text(), original[index].get_text())
                        pix = page.get_pixmap(alpha=False)
                        x = page.rect.width - 45 * engine.MM
                        y = 10 * engine.MM + 8.75 * engine.MM
                        self.assertEqual(pix.pixel(int(x + 8.75 * engine.MM), int(y)), (255, 0, 0))
                        self.assertEqual(pix.pixel(int(x + 26.25 * engine.MM), int(y)), (0, 0, 255))

    def test_preview_matches_export(self):
        for layer in ('foreground', 'background', 'middle'):
            exported = self.run_engine(layer=layer)
            with pymupdf.open(stream=exported['pdf'], filetype='pdf') as full:
                for number in range(5):
                    preview = self.run_engine(layer=layer, page=number)
                    with pymupdf.open(stream=preview['pdf'], filetype='pdf') as single:
                        self.assertEqual(full[number].get_pixmap().samples, single[0].get_pixmap().samples)

    def test_layers_and_middle_check(self):
        with pymupdf.open() as doc:
            page = doc.new_page(width=600, height=800)
            page.draw_rect(page.rect, fill=(0, 1, 0), color=None)
            page.insert_text((480, 58), 'TEXTO', fontsize=22)
            data = doc.tobytes()
        for layer in ('foreground', 'background', 'middle'):
            result = self.run_engine(data, layer=layer)
            with pymupdf.open(stream=result['pdf'], filetype='pdf') as doc:
                self.assertEqual(doc[0].get_text().strip(), 'TEXTO')
                self.assertEqual(doc[0].get_pixmap().pixel(480, 32), (0, 255, 0) if layer == 'background' else (255, 0, 0))
            if layer == 'middle':
                with pymupdf.open(stream=result['source'], filetype='pdf') as original, pymupdf.open(stream=result['check'], filetype='pdf') as combined:
                    self.assertEqual(original[0].get_pixmap().samples, combined[0].get_pixmap().samples)

    def test_annotations_forms_links_preserved(self):
        with pymupdf.open(stream=self.data, filetype='pdf') as doc:
            page = doc[0]
            page.add_rect_annot(pymupdf.Rect(50, 100, 100, 150))
            page.insert_link({'kind': pymupdf.LINK_URI, 'from': pymupdf.Rect(50, 200, 150, 220), 'uri': 'https://example.com'})
            widget = pymupdf.Widget()
            widget.field_name = 'nombre'
            widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
            widget.field_value = 'Valor conservado'
            widget.rect = pymupdf.Rect(50, 250, 250, 280)
            page.add_widget(widget)
            result = self.run_engine(doc.tobytes(), layer='middle')
        with pymupdf.open(stream=result['pdf'], filetype='pdf') as doc:
            self.assertEqual(len(list(doc[0].annots())), 1)
            self.assertEqual(doc[0].get_links()[0]['uri'], 'https://example.com')
            self.assertEqual(list(doc[0].widgets())[0].field_value, 'Valor conservado')

    def test_rejects_protected_and_invalid_measures(self):
        writer = PdfWriter(clone_from=PdfReader(io.BytesIO(self.data)))
        writer.encrypt('secret')
        with self.assertRaisesRegex(ValueError, 'protegido'):
            self.run_engine(engine.serialized(writer))
        for opts in ({'width': 0}, {'right': -1}, {'width': 9000}, {'top': float('nan')}):
            with self.assertRaises(ValueError):
                self.run_engine(**opts)

    def test_user_unit(self):
        writer = PdfWriter(clone_from=PdfReader(io.BytesIO(self.data)))
        for page in writer.pages:
            page[NameObject('/UserUnit')] = NumberObject(2)
        result = self.run_engine(engine.serialized(writer))
        with pymupdf.open(stream=result['pdf'], filetype='pdf') as doc:
            for page in doc:
                pix = page.get_pixmap()
                self.assertEqual(pix.pixel(int(page.rect.width - 36.25 * engine.MM), int(18.75 * engine.MM)), (255, 0, 0))

    def test_transparency(self):
        self.image = Image.new('RGBA', (80, 40), (255, 0, 0, 128))
        result = self.run_engine()
        with pymupdf.open(stream=result['pdf'], filetype='pdf') as doc:
            pixel = doc[0].get_pixmap().pixel(500, 40)
            self.assertGreaterEqual(pixel[0], 254)
            self.assertTrue(125 <= pixel[1] <= 128)

    def test_text_masks_rejected_in_middle(self):
        with pymupdf.open() as doc:
            doc.new_page().insert_text((100, 100), 'MASK', render_mode=4)
            data = doc.tobytes()
        with self.assertRaisesRegex(ValueError, 'máscara'):
            self.run_engine(data, layer='middle')
        self.run_engine(data, layer='foreground')


if __name__ == '__main__':
    unittest.main()
