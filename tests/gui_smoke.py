"""Prueba de integración de Tk y procesos; ejecutar en Windows con escritorio disponible."""
import multiprocessing
import sys
import time
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import pymupdf

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
    app.update_idletasks()
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
            pane = app.preview
            for label, layer in [("Al fondo", "background"), ("Delante del texto", "foreground"),
                                 ("Al medio (debajo del texto)", "middle")]:
                app.layer_value.set(label)
                wait_until(app, lambda: app.preview_image is not None and not app.preview_busy)
                assert app.options().layer == layer
                base = pane.canvas.find_withtag("base")[0]
                stamp = pane.canvas.find_withtag("stamp")[0]
                assert (stamp < base) if layer == "background" else (base < stamp)
                if layer == "middle":
                    assert stamp < pane.canvas.find_withtag("text")[0]
            # Zoom no cambia las medidas, ni la posición de impresión.
            original_options = app.options()
            pane.change_zoom(1.25)
            assert app.options() == original_options
            # Arrastre con zoom y desplazamiento: comprobar conversión de coordenadas.
            pane.zoom = 2
            pane.redraw()
            left, top, right, bottom = pane.bounds
            pane.canvas.xview_moveto(max(0, (left + right) / 2 - pane.canvas.winfo_width() / 2) / pane.region[0])
            pane.canvas.yview_moveto(max(0, (top + bottom) / 2 - pane.canvas.winfo_height() / 2) / pane.region[1])
            start = SimpleNamespace(x=(left + right) / 2 - pane.canvas.canvasx(0),
                                    y=(top + bottom) / 2 - pane.canvas.canvasy(0))
            pane.begin_drag(start)
            assert pane.drag is not None
            end = SimpleNamespace(x=start.x - 40 * pane.scale, y=start.y + 65 * pane.scale)
            pane.drag_to(end)
            pane.end_drag(end)
            moved = app.options()
            assert moved.layer == "middle"
            # Tk convierte coordenadas de ratón a píxeles enteros.
            tolerance = 1 / pane.scale + .01
            assert abs((moved.top_mm - original_options.top_mm) * 72 / 25.4 - 65) < tolerance
            assert abs((moved.right_mm - original_options.right_mm) * 72 / 25.4 - 40) < tolerance
            assert moved.width_mm == original_options.width_mm
            pane.fit()
            assert app.options() == moved
            app.save()
            wait_until(app, lambda: bool(results) or bool(errors))
            assert not errors, errors
            assert len(results[0].succeeded) == 2
            assert (Path(app.output) / "informe.csv").exists()
            for name, _ in results[0].succeeded:
                with pymupdf.open(Path(app.output) / name) as doc:
                    for page in doc:
                        bbox = page.get_image_info()[0]["bbox"]
                        assert abs(bbox[1] - moved.top_mm * 72 / 25.4) < .01
                        assert abs(page.rect.width - bbox[2] - moved.right_mm * 72 / 25.4) < .01
            with patch("app.filedialog.askopenfilename", return_value=str(fixture.folder / "uno.pdf")):
                app.choose_pdf()
            assert app.folder is None
            assert app.save_button["text"] == "Guardar PDF sellado…"
            print("GUI OK: tres capas, carpeta, zoom, arrastre conservando capa y posición, exportación de lote y modo individual.")
    finally:
        if app.worker:
            app.worker.join(timeout=5)
        app.destroy()
        fixture.tearDown()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
