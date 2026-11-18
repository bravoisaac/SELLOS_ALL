"""Prueba de integración de Tk y procesos; ejecutar en Windows con escritorio disponible."""
import multiprocessing
import sys
import time
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import pymupdf
from PIL import ImageGrab

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


def check_responsive_layout(app):
    options = app.options()
    app.deiconify()
    for size, mode in [("1180x820", "wide"), ("800x600", "compact"), ("640x520", "compact"), ("1024x640", "wide")]:
        app.geometry(size + "+20+20")
        app.update()
        wait_until(app, lambda: app.layout_mode == mode)
        assert app.save_button.winfo_ismapped()
        assert app.save_button.winfo_rooty() + app.save_button.winfo_height() <= app.winfo_rooty() + app.winfo_height()
        if mode == "compact":
            app.active_panel.set("settings")
            app.show_panel()
            app.update()
            app.settings_panel.reveal(app.layer_selector)
            app.update()
            assert app.layer_selector.winfo_rooty() >= app.settings_panel.canvas.winfo_rooty()
            assert app.layer_selector.winfo_rooty() + app.layer_selector.winfo_height() <= app.settings_panel.canvas.winfo_rooty() + app.settings_panel.canvas.winfo_height()
            app.active_panel.set("preview")
            app.show_panel()
            app.update()
            assert app.preview_panel.winfo_ismapped()
            assert not app.settings_panel.winfo_ismapped()
        else:
            assert app.preview_panel.winfo_ismapped() and app.settings_panel.winfo_ismapped()
        assert app.preview.canvas.winfo_width() > 250
        assert app.preview.canvas.winfo_height() > 70
        assert app.options() == options
    app.geometry("1180x820+20+20")
    app.update()


def capture(app, name):
    destination = Path(__file__).resolve().parents[1] / "tmp" / "qa"
    destination.mkdir(parents=True, exist_ok=True)
    app.attributes("-topmost", True)
    app.update()
    # Allow the preview's resize debounce to settle before capturing our own test window.
    deadline = time.monotonic() + .3
    while time.monotonic() < deadline:
        app.update()
        time.sleep(.02)
    x, y = app.winfo_rootx(), app.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height())).save(destination / name)
    app.attributes("-topmost", False)


def main():
    fixture = BatchTests()
    fixture.setUp()
    library_dir = fixture.folder / "library"
    app = StampApp(library_dir=library_dir)
    app.update_idletasks()
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
            wait_until(app, lambda: app.preview_image is not None and not app.preview_busy)
            check_responsive_layout(app)
            with patch("app.simpledialog.askstring", return_value="Firma oficina"):
                app.save_stamp_to_library()
            assert len(app.saved_stamps) == 1
            saved_options = app.options()
            saved_path = Path(app.stamp_path)
            assert saved_path.parent == library_dir
            # Cancelar un reemplazo no debe alterar el sello guardado.
            before = saved_path.read_bytes()
            with patch("app.simpledialog.askstring", return_value="Firma oficina"), patch("app.messagebox.askyesno", return_value=False):
                app.save_stamp_to_library()
            assert saved_path.read_bytes() == before
            capture(app, "responsive-wide.png")
            app.geometry("640x520+20+20")
            app.active_panel.set("settings")
            app.update()
            app.show_panel()
            app.settings_panel.canvas.yview_moveto(0)
            capture(app, "responsive-compact-settings.png")
            app.active_panel.set("preview")
            app.show_panel()
            capture(app, "responsive-compact-preview.png")
            app.destroy()
            original_moved = fixture.image.with_name("original-movido.png")
            fixture.image.rename(original_moved)
            # Una nueva ventana vuelve a leer la biblioteca sin depender de la imagen original.
            app = StampApp(library_dir=library_dir)
            app.update()
            assert len(app.saved_stamps) == 1
            app.library_selector.current(0)
            app.select_saved_stamp()
            assert app.options() == saved_options
            assert Path(app.stamp_path) == saved_path
            with patch("app.filedialog.askopenfilename", return_value=str(fixture.folder / "uno.pdf")):
                app.choose_pdf()
            wait_until(app, lambda: app.preview_image is not None and not app.preview_busy)
            target = fixture.folder / "reutilizado.pdf"
            with patch("app.filedialog.asksaveasfilename", return_value=str(target)):
                app.save()
            wait_until(app, lambda: not app.busy)
            assert target.exists()
            with pymupdf.open(target) as doc:
                assert all(page.get_images() for page in doc)
            with patch("app.messagebox.askyesno", return_value=True):
                app.delete_saved_stamp()
            assert not saved_path.exists()
            assert original_moved.exists()
            assert not app.saved_stamps and app.stamp is None
            assert not errors, errors
            print("GUI OK: capas, exportación, cuatro tamaños, biblioteca persistente, reutilización tras reinicio y eliminación sin tocar originales.")
    finally:
        if app.worker:
            app.worker.join(timeout=5)
        app.destroy()
        fixture.tearDown()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
