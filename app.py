"""Interfaz de escritorio de Sello PDF."""
from __future__ import annotations

import ctypes
import os
import multiprocessing
import queue
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from stamping import StampOptions, load_stamp, open_pdf, render_preview_layer, stamp_pdf, list_pdfs, stamp_folder
from preview import PreviewPane
from stamp_library import StampLibrary
from ui_components import ScrollableSettings

BG = "#f3f5f9"
INK = "#17283d"
MUTED = "#58697e"
BLUE = "#245edb"
LAYERS = {"Al fondo": "background", "Al medio (debajo del texto)": "middle", "Delante del texto": "foreground"}


def preview_worker(events, version, args):
    try:
        image, count, page_size = render_preview_layer(*args)
        events.put(("preview", version, image, None, count, page_size))
    except Exception as exc:
        events.put(("preview", version, None, str(exc), 0, None))


def batch_worker(events, args):
    try:
        result = stamp_folder(*args, progress=lambda *data: events.put(("batch_progress", *data)))
        events.put(("batch_done", result))
    except Exception as exc:
        events.put(("error", str(exc)))


def stamp_worker(events, args):
    try:
        count = stamp_pdf(*args, progress=lambda n, total: events.put(("progress", n, total)))
        events.put(("done", str(args[2]), count))
    except Exception as exc:
        events.put(("error", str(exc)))


class StampApp(tk.Tk):
    def __init__(self, library_dir=None):
        super().__init__()
        self.title("Sello PDF")
        width = min(1180, max(640, self.winfo_screenwidth() - 80))
        height = min(820, max(520, self.winfo_screenheight() - 120))
        self.geometry(f"{width}x{height}")
        self.minsize(640, 520)
        self.configure(bg=BG)
        self.pdf = None
        self.folder = None
        self.pdf_files = []
        self.stamp_path = None
        self.stamp = None
        self.library = StampLibrary(library_dir)
        self.saved_stamps = []
        self.selected_stamp_id = None
        self.layout_mode = None
        self.active_panel = tk.StringVar(value="settings")
        self.page = 0
        self.pages = 0
        self.output = None
        self.busy = False
        self.preview_busy = False
        self.preview_version = 0
        self.preview_timer = None
        self.page_size = None
        self.updating_position = False
        self.events = multiprocessing.Queue()
        self.worker = None
        self.controls = []
        self.width_value = tk.StringVar(value="35")
        self.top_value = tk.StringVar(value="10")
        self.right_value = tk.StringVar(value="10")
        self.layer_value = tk.StringVar(value="Al fondo")
        self.status = tk.StringVar(value="Selecciona un PDF o una carpeta y la imagen de tu sello.")
        self._style()
        self._layout()
        self.refresh_library()
        for value in (self.width_value, self.top_value, self.right_value):
            value.trace_add("write", self.options_changed)
        self.layer_value.trace_add("write", self.schedule_preview)
        self.bind("<Control-o>", lambda _: self.choose_pdf() if not self.busy else None)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.poll_timer = self.after(80, self.poll)

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background="white")
        style.configure("TLabel", background="white", foreground=INK, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 12))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 9), foreground=INK)
        style.configure("Primary.TButton", background=BLUE, foreground="white", borderwidth=0)
        style.map("Primary.TButton", background=[("disabled", "#b8c5db"), ("active", "#1949b3")])
        style.configure("TSpinbox", padding=7, font=("Segoe UI", 11))
        style.configure("Horizontal.TProgressbar", background=BLUE, troughcolor="#e6ebf3", borderwidth=0)
        style.configure("Panel.Toolbutton", font=("Segoe UI", 10), padding=(16, 8))

    def button(self, parent, text, command, **kwargs):
        result = ttk.Button(parent, text=text, command=command, **kwargs)
        self.controls.append(result)
        return result

    def _layout(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.header = header = tk.Frame(self, bg=INK, padx=20, pady=12)
        header.grid(row=0, column=0, sticky="ew")
        self.title_label = tk.Label(header, text="Sello PDF", font=("Segoe UI Semibold", 22), fg="white", bg=INK)
        self.title_label.pack(anchor="w")
        self.subtitle = tk.Label(header, text="Tus documentos, tus sellos. Todo en tu equipo.", font=("Segoe UI", 10),
                                 fg="#c6d4e6", bg=INK)
        self.subtitle.pack(anchor="w", pady=(3, 0))
        self.body = body = ttk.Frame(self, padding=12)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)
        self.panel_switcher = ttk.Frame(body)
        for text, panel in [("Archivos y sellos", "settings"), ("Vista previa", "preview")]:
            ttk.Radiobutton(self.panel_switcher, text=text, value=panel, variable=self.active_panel,
                            style="Panel.Toolbutton", command=self.show_panel).pack(side="left", padx=(0, 6))
        self.settings_panel = ScrollableSettings(body)
        self.settings_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        left = self.settings_panel.content
        left.columnconfigure(0, weight=1)
        ttk.Label(left, text="01   Archivos", style="Title.TLabel").grid(row=0, sticky="w")
        sources = ttk.Frame(left, style="Card.TFrame")
        sources.grid(row=1, sticky="ew", pady=(14, 5))
        self.button(sources, "Un PDF…", self.choose_pdf).pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.button(sources, "Carpeta de PDF…", self.choose_folder).pack(side="left", fill="x", expand=True)
        self.pdf_label = ttk.Label(left, text="Ningún documento seleccionado", style="Muted.TLabel", wraplength=310)
        self.pdf_label.grid(row=2, sticky="w")
        ttk.Separator(left).grid(row=3, sticky="ew", pady=16)
        ttk.Label(left, text="02   Mis sellos", style="Title.TLabel").grid(row=4, sticky="w")
        self.library_selector = ttk.Combobox(left, state="readonly")
        self.library_selector.grid(row=5, sticky="ew", pady=(10, 6))
        self.library_selector.bind("<<ComboboxSelected>>", self.select_saved_stamp)
        self.library_hint = ttk.Label(left, text="", style="Muted.TLabel", wraplength=310)
        self.library_hint.grid(row=6, sticky="w", pady=(0, 8))
        self.button(left, "Elegir imagen del sello…", self.choose_stamp).grid(row=7, sticky="ew", pady=(0, 5))
        self.stamp_label = ttk.Label(left, text="PNG, JPG, WEBP, BMP o TIFF", style="Muted.TLabel", wraplength=310)
        self.stamp_label.grid(row=8, sticky="w")
        library_actions = ttk.Frame(left, style="Card.TFrame")
        library_actions.grid(row=9, sticky="ew", pady=(10, 0))
        self.save_stamp_button = self.button(library_actions, "Guardar sello…", self.save_stamp_to_library)
        self.save_stamp_button.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.delete_stamp_button = self.button(library_actions, "Eliminar…", self.delete_saved_stamp)
        self.delete_stamp_button.pack(side="right")
        ttk.Separator(left).grid(row=10, sticky="ew", pady=16)
        ttk.Label(left, text="03   Posición y tamaño", style="Title.TLabel").grid(row=11, sticky="w")
        ttk.Label(left, text="Arrastra el sello para ubicarlo.\nLa posición se aplica a todas las páginas.",
                  style="Muted.TLabel", wraplength=310).grid(row=12, sticky="w", pady=(6, 10))
        options = ttk.Frame(left, style="Card.TFrame")
        options.grid(row=13, sticky="ew")
        options.columnconfigure(0, weight=1)
        for row, (label, value, minimum) in enumerate([
            ("Ancho del sello", self.width_value, 1),
            ("Margen superior", self.top_value, 0),
            ("Margen derecho", self.right_value, 0),
        ]):
            ttk.Label(options, text=label).grid(row=row, column=0, sticky="w", pady=5)
            spin = ttk.Spinbox(options, from_=minimum, to=500, textvariable=value, width=6)
            spin.grid(row=row, column=1, padx=(10, 6), pady=5)
            self.controls.append(spin)
            ttk.Label(options, text="mm", style="Muted.TLabel").grid(row=row, column=2)
        layer_box = ttk.Frame(left, style="Card.TFrame")
        layer_box.grid(row=14, sticky="ew", pady=(12, 0))
        ttk.Label(layer_box, text="Capa del sello").pack(anchor="w", pady=(0, 5))
        self.layer_selector = ttk.Combobox(layer_box, state="readonly", textvariable=self.layer_value,
                                           values=list(LAYERS))
        self.layer_selector.pack(fill="x")
        self.destination_label = ttk.Label(left, text="Se guarda una copia. El original se conserva.",
                                           style="Muted.TLabel", wraplength=310)
        self.destination_label.grid(row=15, sticky="w", pady=(16, 0))

        self.preview_panel = right = ttk.Frame(body, style="Card.TFrame", padding=12)
        right.grid(row=1, column=1, sticky="nsew")
        toolbar = ttk.Frame(right, style="Card.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Label(toolbar, text="Vista previa", style="Title.TLabel").pack(side="left")
        self.next_button = self.button(toolbar, "→", lambda: self.move(1), width=3)
        self.next_button.pack(side="right")
        self.page_label = ttk.Label(toolbar, text="Sin documento", style="Muted.TLabel")
        self.page_label.pack(side="right", padx=12)
        self.prev_button = self.button(toolbar, "←", lambda: self.move(-1), width=3)
        self.prev_button.pack(side="right")
        self.document_selector = ttk.Combobox(right, state="readonly")
        self.document_selector.pack(fill="x", pady=(0, 10))
        self.document_selector.bind("<<ComboboxSelected>>", self.select_document)
        self.preview_image = None
        self.preview_error = None
        self.preview = PreviewPane(right, on_move=self.position_changed)
        self.preview.pack(fill="both", expand=True)
        self.canvas = self.preview.canvas
        self.preview_hint = ttk.Label(right, text="Revisa el sello antes de guardar. Los originales se conservan.",
                                      style="Muted.TLabel", wraplength=450)
        self.preview_hint.pack(anchor="w", pady=(8, 0))
        footer = ttk.Frame(self, padding=(12, 0, 12, 12))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(footer, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.status_label = tk.Label(footer, textvariable=self.status, bg=BG, fg=MUTED, font=("Segoe UI", 10),
                                    anchor="w", wraplength=780, justify="left", height=2)
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        actions = ttk.Frame(footer)
        actions.grid(row=2, column=0, sticky="ew")
        self.open_button = ttk.Button(actions, text="Abrir resultado", command=self.open_output)
        self.open_button.pack(side="left")
        self.open_button.state(["disabled"])
        self.save_button = self.button(actions, "Guardar PDF sellado…", self.save, style="Primary.TButton")
        self.save_button.pack(side="right")
        self.bind("<Configure>", self.resize_layout, add="+")
        self.update_controls()

    def resize_layout(self, event):
        if event.widget is not self:
            return
        sidebar_width = max(350, self.settings_panel.content.winfo_reqwidth() + 20)
        mode = "compact" if event.width < sidebar_width + 480 else "wide"
        self.status_label.configure(wraplength=max(200, event.width - 32))
        self.preview_hint.configure(wraplength=max(200, self.preview_panel.winfo_width() - 30))
        if mode != self.layout_mode:
            self.layout_mode = mode
            self.settings_panel.canvas.configure(width=sidebar_width - 20)
            self.show_panel()

    def show_panel(self):
        if self.layout_mode == "compact":
            self.header.configure(pady=6)
            self.title_label.configure(font=("Segoe UI Semibold", 18))
            self.subtitle.pack_forget()
            self.preview_hint.pack_forget()
            self.preview.help_label.pack_forget()
            self.panel_switcher.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
            self.body.columnconfigure(0, weight=1)
            self.body.columnconfigure(1, weight=0)
            self.settings_panel.grid_remove()
            self.preview_panel.grid_remove()
            panel = self.preview_panel if self.active_panel.get() == "preview" else self.settings_panel
            panel.grid(row=1, column=0, sticky="nsew", padx=0)
        else:
            self.header.configure(pady=12)
            self.title_label.configure(font=("Segoe UI Semibold", 22))
            self.subtitle.pack(anchor="w", pady=(3, 0))
            self.preview_hint.pack(anchor="w", pady=(8, 0))
            self.preview.help_label.pack(anchor="w", pady=(7, 0))
            self.panel_switcher.grid_remove()
            self.body.columnconfigure(0, weight=0)
            self.body.columnconfigure(1, weight=1)
            self.settings_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
            self.preview_panel.grid(row=1, column=1, sticky="nsew", padx=0)

    def options(self):
        try:
            values = [float(v.get().strip().replace(",", ".")) for v in
                      (self.width_value, self.top_value, self.right_value)]
        except ValueError:
            raise ValueError("Introduce números en el ancho y los márgenes.") from None
        result = StampOptions(*values, layer=LAYERS[self.layer_value.get()])
        result.validate()
        return result

    def choose_pdf(self):
        path = filedialog.askopenfilename(title="Seleccionar PDF", filetypes=[("Documento PDF", "*.pdf")])
        if not path:
            return
        try:
            with open_pdf(path) as doc:
                count = len(doc)
            self.pdf, self.pages, self.page = path, count, 0
            self.folder = None
            self.pdf_files = [Path(path)]
            self.document_selector.configure(values=[Path(path).name])
            self.document_selector.current(0)
            self.pdf_label.config(text=f"{Path(path).name}\n{count} página(s)")
            self.schedule_preview()
            self.update_controls()
        except Exception as exc:
            messagebox.showerror("No se pudo abrir el PDF", str(exc))

    def choose_folder(self):
        path = filedialog.askdirectory(title="Seleccionar carpeta con archivos PDF", mustexist=True)
        if not path:
            return
        try:
            files = list_pdfs(path)
            if not files:
                raise ValueError("La carpeta no contiene PDF. Solo se incluyen archivos directamente dentro de ella.")
            self.folder, self.pdf_files = path, files
            self.pdf_label.config(text=f"{Path(path).name} · {len(files)} PDF\nSin incluir subcarpetas")
            self.document_selector.configure(values=[p.name for p in files])
            self.document_selector.current(0)
            self.select_document()
        except Exception as exc:
            messagebox.showerror("No se pudo abrir la carpeta", str(exc))

    def select_document(self, *_):
        index = self.document_selector.current()
        if index < 0 or self.busy:
            return
        self.pdf = str(self.pdf_files[index])
        self.pages, self.page = 0, 0
        self.preview_image, self.preview_error = None, None
        self.draw_preview()
        self.update_controls()
        self.schedule_preview()

    def choose_stamp(self):
        path = filedialog.askopenfilename(title="Seleccionar imagen del sello", filetypes=[
            ("Imágenes", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"), ("Todos los archivos", "*.*")])
        if not path:
            return
        try:
            stamp = load_stamp(path)
            self.stamp_path, self.stamp = path, stamp
            self.selected_stamp_id = None
            self.library_selector.set("Elige un sello guardado" if self.saved_stamps else "Sin sellos guardados")
            self.stamp_label.config(text=Path(path).name)
            self.draw_preview()
            self.update_controls()
        except Exception as exc:
            messagebox.showerror("No se pudo abrir la imagen", str(exc))

    def refresh_library(self, select_id=None):
        self.selected_stamp_id = select_id or self.selected_stamp_id
        try:
            self.saved_stamps = self.library.list()
            count = len(self.saved_stamps)
            hint = ("1 sello guardado en este equipo." if count == 1 else f"{count} sellos guardados en este equipo.") if count else "Guarda un sello y podrás reutilizarlo al volver a abrir la app."
            if self.library.unreadable_count:
                hint += f" No se pudieron leer {self.library.unreadable_count} archivo(s)."
            self.library_hint.configure(text=hint)
        except OSError:
            self.saved_stamps = []
            self.library_hint.configure(text="No se pudo leer la biblioteca. Comprueba los permisos de tu perfil.")
        self.library_selector.configure(values=[entry.name for entry in self.saved_stamps])
        index = next((i for i, entry in enumerate(self.saved_stamps) if entry.id == self.selected_stamp_id), None)
        if index is None:
            self.selected_stamp_id = None
            self.library_selector.set("Elige un sello guardado" if self.saved_stamps else "Sin sellos guardados")
        else:
            self.library_selector.current(index)
        self.update_controls()

    def save_stamp_to_library(self):
        if self.busy or not self.stamp:
            return
        try:
            options = self.options()
            selected = next((entry for entry in self.saved_stamps if entry.id == self.selected_stamp_id), None)
            initial = selected.name if selected else Path(self.stamp_path).stem
            name = simpledialog.askstring("Guardar sello", "Nombre del sello (se guardan también tamaño, posición y capa):",
                                          initialvalue=initial, parent=self)
            if name is None:
                return
            duplicate = next((entry for entry in self.library.list() if entry.name.casefold() == name.strip().casefold()), None)
            if duplicate and not messagebox.askyesno("Reemplazar sello", f'Ya existe «{duplicate.name}». ¿Reemplazar su imagen y ajustes?', parent=self):
                return
            saved = self.library.save(name, self.stamp[0], options, replace_id=duplicate.id if duplicate else None)
            self.stamp_path = str(saved.path)
            self.stamp_label.configure(text=saved.name)
            self.refresh_library(saved.id)
            self.status.set(f'Sello «{saved.name}» guardado. Podrás usarlo en otros documentos y al volver a abrir la app.')
        except (OSError, ValueError) as exc:
            messagebox.showerror("No se pudo guardar el sello", str(exc), parent=self)

    def select_saved_stamp(self, *_):
        index = self.library_selector.current()
        if self.busy or index < 0 or index >= len(self.saved_stamps):
            return
        entry = self.saved_stamps[index]
        try:
            stamp = load_stamp(entry.path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("No se pudo abrir el sello guardado", str(exc), parent=self)
            self.refresh_library()
            return
        self.stamp_path, self.stamp = str(entry.path), stamp
        self.selected_stamp_id = entry.id
        self.stamp_label.configure(text=entry.name)
        self.updating_position = True
        try:
            self.width_value.set(str(entry.options.width_mm))
            self.top_value.set(str(entry.options.top_mm))
            self.right_value.set(str(entry.options.right_mm))
            self.layer_value.set(next(label for label, layer in LAYERS.items() if layer == entry.options.layer))
        finally:
            self.updating_position = False
        self.schedule_preview()
        self.update_controls()
        self.status.set(f'Sello «{entry.name}» cargado con sus ajustes. Puedes adaptarlos a este documento.')

    def delete_saved_stamp(self):
        if self.busy or not self.selected_stamp_id:
            return
        entry = next((item for item in self.saved_stamps if item.id == self.selected_stamp_id), None)
        if entry is None or not messagebox.askyesno("Eliminar sello guardado",
                f'¿Eliminar «{entry.name}» de la biblioteca? La imagen original y los PDF se conservan.', parent=self):
            return
        try:
            self.library.remove(entry.id)
        except OSError as exc:
            messagebox.showerror("No se pudo eliminar el sello", str(exc), parent=self)
            return
        self.selected_stamp_id = None
        self.stamp_path, self.stamp = None, None
        self.stamp_label.configure(text="PNG, JPG, WEBP, BMP o TIFF")
        self.refresh_library()
        self.draw_preview()
        self.status.set("Sello eliminado de la biblioteca. Selecciona otro para continuar.")

    def update_controls(self):
        if self.busy:
            self.progress.grid()
        else:
            self.progress.grid_remove()
        for control in self.controls:
            control.state(["disabled"] if self.busy else ["!disabled"])
        if not self.pdf or not self.stamp:
            self.save_button.state(["disabled"])
        self.library_selector.configure(state="disabled" if self.busy or not self.saved_stamps else "readonly")
        if not self.stamp:
            self.save_stamp_button.state(["disabled"])
        if not self.selected_stamp_id:
            self.delete_stamp_button.state(["disabled"])
        self.document_selector.configure(state="disabled" if self.busy or not self.pdf_files else "readonly")
        self.layer_selector.configure(state="disabled" if self.busy else "readonly")
        self.save_button.configure(text="Sellar toda la carpeta" if self.folder else "Guardar PDF sellado…")
        self.destination_label.configure(text="Copias en una nueva subcarpeta Sellados.\nLos originales se conservan."
                                         if self.folder else "Se guarda una copia. El original se conserva.")
        if self.page <= 0 or self.busy:
            self.prev_button.state(["disabled"])
        if self.page >= self.pages - 1 or self.busy:
            self.next_button.state(["disabled"])
        self.page_label.config(text=f"{self.page + 1} / {self.pages}" if self.pages else "Sin documento")
        self.preview.enabled = not self.busy and self.preview_image is not None

    def move(self, delta):
        self.page = max(0, min(self.pages - 1, self.page + delta))
        self.update_controls()
        self.schedule_preview()

    def schedule_preview(self, *_):
        if self.updating_position:
            return
        self.preview_version += 1
        self.preview_image, self.page_size, self.preview_error = None, None, None
        self.draw_preview()
        if self.preview_timer:
            self.after_cancel(self.preview_timer)
        self.preview_timer = self.after(300, self.start_preview)

    def start_preview(self):
        self.preview_timer = None
        if not self.pdf:
            return
        if self.busy or self.preview_busy:
            self.preview_timer = self.after(150, self.start_preview)
            return
        self.preview_busy = True
        version = self.preview_version
        args = (self.pdf, self.page, LAYERS[self.layer_value.get()])
        self.status.set("Actualizando vista previa…")
        self.worker = multiprocessing.Process(target=preview_worker,
            args=(self.events, version, args), daemon=True)
        self.worker.start()

    def draw_preview(self, *_):
        error = self.preview_error
        try:
            options = self.options()
        except ValueError as exc:
            options, error = None, str(exc)
        self.preview.set_content(self.preview_image, self.page_size, self.stamp, options,
                                 error=error, enabled=not self.busy)

    def options_changed(self, *_):
        if not self.updating_position:
            self.draw_preview()

    def position_changed(self, options):
        self.updating_position = True
        try:
            self.top_value.set(f"{options.top_mm:.6f}".rstrip("0").rstrip("."))
            self.right_value.set(f"{options.right_mm:.6f}".rstrip("0").rstrip("."))
        finally:
            self.updating_position = False
        self.draw_preview()
        self.status.set("Posición actualizada. Se usará en todas las páginas y los PDF de la carpeta.")

    def save(self):
        if self.busy or not self.pdf or not self.stamp_path:
            return
        if self.preview_busy:
            self.status.set("Espera a que termine la vista previa y vuelve a guardar.")
            return
        try:
            options = self.options()
        except ValueError as exc:
            messagebox.showerror("Revisa las medidas", str(exc))
            return
        target = self.folder or filedialog.asksaveasfilename(title="Guardar copia sellada", defaultextension=".pdf",
            initialdir=str(Path(self.pdf).parent), initialfile=f"{Path(self.pdf).stem}_sellado.pdf",
            filetypes=[("Documento PDF", "*.pdf")], confirmoverwrite=True)
        if not target:
            return
        self.busy = True
        self.progress["value"] = 0
        self.open_button.state(["disabled"])
        self.status.set("Aplicando sello a todas las páginas…")
        self.update_controls()
        args = (self.folder, self.stamp_path, options) if self.folder else (self.pdf, self.stamp_path, target, options)
        self.worker = multiprocessing.Process(target=batch_worker if self.folder else stamp_worker,
            args=(self.events, args), daemon=True)
        self.worker.start()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "preview":
                    self.preview_busy = False
                    if event[1] == self.preview_version:
                        self.preview_image, self.preview_error, self.pages, self.page_size = event[2:]
                        self.update_controls()
                        self.draw_preview()
                        self.status.set(event[3] or "Vista previa lista. Ajusta el sello y guarda tu copia.")
                elif event[0] == "progress":
                    self.progress["value"] = event[1] / event[2] * 100
                    self.status.set(f"Sellando página {event[1]} de {event[2]}…")
                elif event[0] == "batch_progress":
                    _, index, total, name, page, pages = event
                    fraction = page / pages if pages else 0
                    self.progress["value"] = (index - 1 + fraction) / total * 100
                    detail = f" · página {page}/{pages}" if pages else ""
                    self.status.set(f"PDF {index}/{total}: {name}{detail}")
                elif event[0] == "batch_done":
                    result = event[1]
                    self.busy = False
                    self.output = str(result.output_dir)
                    self.progress["value"] = 100
                    self.status.set(f"Finalizado: {len(result.succeeded)} PDF sellados, {len(result.failed)} con error. {self.output}")
                    self.open_button.state(["!disabled"])
                    self.update_controls()
                    self.show_batch_result(result)
                elif event[0] == "done":
                    self.busy = False
                    self.output = event[1]
                    self.progress["value"] = 100
                    self.status.set(f"Listo: {event[2]} página(s) selladas. Guardado en {event[1]}")
                    self.open_button.state(["!disabled"])
                    self.update_controls()
                elif event[0] == "error":
                    self.busy = False
                    self.progress["value"] = 0
                    self.status.set("No se pudo guardar el PDF. Revisa los archivos y las medidas.")
                    self.update_controls()
                    messagebox.showerror("No se pudo sellar el PDF", event[1])
        except queue.Empty:
            pass
        if self.worker and self.worker.exitcode is not None:
            if self.worker.exitcode != 0 and (self.busy or self.preview_busy):
                self.busy = self.preview_busy = False
                self.status.set("El proceso se interrumpió. Vuelve a seleccionar los archivos e inténtalo de nuevo.")
                self.update_controls()
            self.worker.join(timeout=0)
            self.worker = None
        self.poll_timer = self.after(80, self.poll)

    def show_batch_result(self, result):
        dialog = tk.Toplevel(self)
        dialog.title("Resultado del sellado de carpeta")
        dialog.geometry("720x430")
        dialog.transient(self)
        container = ttk.Frame(dialog, padding=18)
        container.pack(fill="both", expand=True)
        summary = f"{len(result.succeeded)} PDF sellados · {len(result.failed)} con error"
        tk.Label(container, text=summary, font=("Segoe UI Semibold", 14), bg=BG, fg=INK).pack(anchor="w")
        report = tk.Text(container, wrap="word", font=("Segoe UI", 10), relief="flat", padx=12, pady=12)
        report.pack(fill="both", expand=True, pady=12)
        report.insert("end", f"Carpeta de salida:\n{result.output_dir}\n\n")
        if result.report_error:
            report.insert("end", f"No se pudo guardar el informe CSV: {result.report_error}\n\n")
        else:
            report.insert("end", "El detalle de todos los archivos está en informe.csv.\n\n")
        for name, error in result.failed:
            report.insert("end", f"ERROR · {name}\n{error}\n\n")
        if not result.failed:
            report.insert("end", "Todos los PDF se sellaron correctamente. Los originales se conservaron.")
        report.configure(state="disabled")
        ttk.Button(container, text="Cerrar", command=dialog.destroy).pack(side="right")
        ttk.Button(container, text="Abrir carpeta de resultados", command=self.open_output).pack(side="left")

    def open_output(self):
        if self.output:
            try:
                os.startfile(self.output)
            except OSError as exc:
                messagebox.showerror("No se pudo abrir el resultado", str(exc))

    def close(self):
        if self.busy:
            messagebox.showinfo("Guardado en curso", "Espera a que termine el guardado antes de cerrar.")
        else:
            self.destroy()

    def destroy(self):
        for timer in (getattr(self, "preview_timer", None), getattr(self, "poll_timer", None)):
            if timer:
                self.after_cancel(timer)
        if getattr(self, "worker", None) is not None:
            if self.worker.is_alive():
                self.worker.terminate()
            self.worker.join(timeout=1)
        if hasattr(self, "events"):
            self.events.close()
            self.events.cancel_join_thread()
        super().destroy()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    StampApp().mainloop()
