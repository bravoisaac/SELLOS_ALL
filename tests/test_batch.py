import csv
import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image

from stamping import StampOptions, list_pdfs, stamp_folder


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.image = self.folder / "sello.png"
        Image.new("RGB", (80, 40), "red").save(self.image)
        for name in ("uno.pdf", "DOS.PDF"):
            with pymupdf.open() as doc:
                for page in range(2):
                    doc.new_page().insert_text((50, 200), f"Original {name} {page}")
                doc.save(self.folder / name)

    def tearDown(self):
        self.temp.cleanup()

    def test_batch_stamps_every_page_preserves_sources_and_reports(self):
        originals = {p.name: p.read_bytes() for p in list_pdfs(self.folder)}
        events = []
        result = stamp_folder(self.folder, self.image, progress=lambda *args: events.append(args))
        self.assertEqual(len(result.succeeded), 2)
        self.assertFalse(result.failed)
        self.assertIsNone(result.report_error)
        for name, data in originals.items():
            self.assertEqual((self.folder / name).read_bytes(), data)
            with pymupdf.open(result.output_dir / name) as doc:
                self.assertEqual(len(doc), 2)
                self.assertTrue(all(page.get_images() for page in doc))
        with (result.output_dir / "informe.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter=";"))
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["Estado"] == "Sellado" for row in rows))
        self.assertEqual(events[-1][:2], (2, 2))

    def test_failed_files_do_not_stop_batch(self):
        (self.folder / "aaa_roto.pdf").write_bytes(b"no es pdf")
        with pymupdf.open(self.folder / "uno.pdf") as doc:
            doc.save(self.folder / "protegido.pdf", encryption=pymupdf.PDF_ENCRYPT_AES_256,
                     owner_pw="owner", user_pw="secret")
        result = stamp_folder(self.folder, self.image)
        self.assertEqual(len(result.succeeded), 2)
        self.assertEqual({name for name, _ in result.failed}, {"aaa_roto.pdf", "protegido.pdf"})
        self.assertFalse((result.output_dir / "aaa_roto.pdf").exists())
        self.assertIn("aaa_roto.pdf", (result.output_dir / "informe.csv").read_text(encoding="utf-8-sig"))

    def test_repeated_run_does_not_overwrite_or_process_previous_output(self):
        first = stamp_folder(self.folder, self.image)
        original_result = (first.output_dir / "uno.pdf").read_bytes()
        second = stamp_folder(self.folder, self.image)
        self.assertEqual(first.output_dir.name, "Sellados")
        self.assertEqual(second.output_dir.name, "Sellados (2)")
        self.assertEqual(len(second.succeeded), 2)
        self.assertEqual((first.output_dir / "uno.pdf").read_bytes(), original_result)

    def test_nested_folders_and_other_files_are_excluded(self):
        nested = self.folder / "subcarpeta"
        nested.mkdir()
        (nested / "otro.pdf").write_bytes((self.folder / "uno.pdf").read_bytes())
        (self.folder / "notas.txt").write_text("No procesar")
        self.assertEqual([p.name for p in list_pdfs(self.folder)], ["DOS.PDF", "uno.pdf"])

    def test_empty_folder_and_invalid_image_create_no_output(self):
        empty = self.folder / "vacia"
        empty.mkdir()
        with self.assertRaisesRegex(ValueError, "no contiene"):
            stamp_folder(empty, self.image)
        self.assertFalse((empty / "Sellados").exists())
        self.image.write_bytes(b"invalida")
        with self.assertRaises(Exception):
            stamp_folder(self.folder, self.image)
        self.assertFalse((self.folder / "Sellados").exists())

    def test_oversize_reported_for_each_file_without_partial_pdf(self):
        result = stamp_folder(self.folder, self.image, StampOptions(1000))
        self.assertFalse(result.succeeded)
        self.assertEqual(len(result.failed), 2)
        self.assertFalse(list(result.output_dir.glob("*.pdf")))


if __name__ == "__main__":
    unittest.main()
