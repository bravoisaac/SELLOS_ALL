import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from stamp_library import StampLibrary
from stamping import StampOptions, load_stamp


class StampLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original = self.root / "firma.png"
        Image.new("RGBA", (120, 40), (20, 90, 150, 120)).save(self.original)
        self.png, self.ratio = load_stamp(self.original)
        self.library = StampLibrary(self.root / "library")
        self.options = StampOptions(42, 12.345678, 8.2, "middle")

    def tearDown(self):
        self.temp.cleanup()

    def test_reopen_keeps_image_transparency_and_options_after_original_removed(self):
        saved = self.library.save("Firma personal", self.png, self.options)
        self.original.unlink()
        reopened = StampLibrary(self.library.directory).list()
        self.assertEqual(reopened, [saved])
        self.assertEqual(reopened[0].options, self.options)
        self.assertEqual(load_stamp(reopened[0].path), (self.png, self.ratio))

    def test_replace_updates_one_record_and_preserves_original(self):
        saved = self.library.save("Firma", self.png, self.options)
        original_bytes = self.original.read_bytes()
        changed = self.library.save("Firma", self.png, StampOptions(20), replace_id=saved.id)
        self.assertEqual(changed.path, saved.path)
        self.assertEqual(self.library.list(), [changed])
        self.assertEqual(self.original.read_bytes(), original_bytes)

    def test_failed_replace_keeps_previous_record_and_removes_temporary(self):
        saved = self.library.save("Firma", self.png, self.options)
        before = saved.path.read_bytes()
        with patch("stamp_library.os.replace", side_effect=OSError("Disco lleno")):
            with self.assertRaises(OSError):
                self.library.save("Firma", self.png, StampOptions(22), replace_id=saved.id)
        self.assertEqual(saved.path.read_bytes(), before)
        self.assertEqual(list(self.library.directory.iterdir()), [saved.path])

    def test_duplicate_name_does_not_overwrite(self):
        saved = self.library.save("Firma", self.png, self.options)
        with self.assertRaisesRegex(ValueError, "Ya existe"):
            self.library.save(" FIRMA ", self.png, StampOptions())
        self.assertEqual(self.library.list(), [saved])

    def test_invalid_names_options_and_image_leave_no_records(self):
        for name in ("", "  ", "a" * 81, "Firma\nPersonal"):
            with self.assertRaises(ValueError):
                self.library.save(name, self.png, self.options)
        with self.assertRaises(ValueError):
            self.library.save("Firma", self.png, StampOptions(float("nan")))
        with self.assertRaises(OSError):
            self.library.save("Firma", b"invalid image", self.options)
        self.assertEqual(self.library.list(), [])
        self.assertFalse(self.library.directory.exists())

    def test_corrupt_record_does_not_hide_valid_records(self):
        saved = self.library.save("Firma", self.png, self.options)
        (self.library.directory / ("a" * 32 + ".png")).write_bytes(b"bad png")
        self.assertEqual(self.library.list(), [saved])
        self.assertEqual(self.library.unreadable_count, 1)

    def test_names_cannot_control_paths_and_invalid_ids_are_rejected(self):
        saved = self.library.save("../../Mi firma", self.png, self.options)
        self.assertEqual(saved.path.parent, self.library.directory)
        with self.assertRaises(ValueError):
            self.library.remove("../firma")
        with self.assertRaises(ValueError):
            self.library.save("Otra", self.png, self.options, replace_id="../firma")
        self.assertTrue(self.original.exists())

    def test_delete_only_removes_managed_copy(self):
        saved = self.library.save("Firma", self.png, self.options)
        self.library.remove(saved.id)
        self.assertTrue(self.original.exists())
        self.assertFalse(saved.path.exists())
        self.assertEqual(self.library.list(), [])

    def test_empty_library_does_not_create_user_files(self):
        self.assertEqual(self.library.list(), [])
        self.assertFalse(self.library.directory.exists())


if __name__ == "__main__":
    unittest.main()
