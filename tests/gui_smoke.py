"""Prueba de integración de Tk y procesos; ejecutar en Windows con escritorio disponible."""
import multiprocessing
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import StampApp
from test_batch import BatchTests


def wait_until(app, predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while not predicate():
        app.update()
        if time.monotonic() > deadline:
            raise AssertionError(f"Tiempo agotado: {app.status.get()}")
        time.sleep(.02)


def main():
    fixture = BatchTests()
    fixture.setUp()
    app = StampApp()
    app.withdraw()
    errors = []
    results = []
    app.show_batch_result = results.append
    try:
        with patch("app.messagebox.showerror", side_effect=lambda *args: errors.append(args)):
            with patch("app.filedialog.askdirectory", return_value=str(fixture.folder)):
                app.choose_folder()
            with patch("app.filedialog.askopenfilename", return_value=str(fixture.image)):
                app.choose_stamp()
            wait_until(app, lambda: app.preview_image is not None and not app.preview_busy)
            assert app.pages == 2
            assert len(app.document_selector["values"]) == 2
            assert app.save_button["text"] == "Sellar toda la carpeta"
            app.save()
            wait_until(app, lambda: bool(results) or bool(errors))
            assert not errors, errors
            assert len(results[0].succeeded) == 2
            assert (Path(app.output) / "informe.csv").exists()
            with patch("app.filedialog.askopenfilename", return_value=str(fixture.folder / "uno.pdf")):
                app.choose_pdf()
            assert app.folder is None
            assert app.save_button["text"] == "Guardar PDF sellado…"
            print("GUI OK: selección de carpeta, vista previa, proceso de lote, resumen y regreso a PDF individual.")
    finally:
        if app.worker:
            app.worker.join(timeout=5)
        app.destroy()
        fixture.tearDown()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
