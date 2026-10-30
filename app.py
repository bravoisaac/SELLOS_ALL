"""Interfaz de escritorio de Sello PDF."""
from __future__ import annotations

import ctypes
import os
import multiprocessing
import queue
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import ImageTk

from stamping import StampOptions, load_stamp, open_pdf, render_preview, stamp_pdf, list_pdfs, stamp_folder

BG = "#f3f5f9"
INK = "#17283d"
MUTED = "#58697e"
BLUE = "#245edb"


def preview_worker(events, version, args):
    try:
        image, count = render_preview(*args)
        events.put(("preview", version, image, None, count))
    except Exception as exc:
        events.put(("preview", version, None, str(exc), 0))


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
    def __init__(self):
        super().__init__()
        self.title("Sello PDF")
        self.geometry("1120x800")
        self.minsize(960, 740)
        self.configure(bg=BG)
        self.pdf = None
        self.folder = None
        self.pdf_files = []
        self.stamp_path = None
        self.stamp = None
        self.page = 0
        self.pages = 0
        self.output = None
        self.busy = False
        self.preview_busy = False
        self.preview_version = 0
        self.preview_timer = None
        self.events = multiprocessing.Queue()
        self.worker = None
        self.controls = []
        self.width_value = tk.StringVar(value="35")
        self.top_value = tk.StringVar(value="10")
        self.right_value = tk.StringVar(value="10")
        self.status = tk.StringVar(value="Selecciona un PDF o una carpeta y la imagen de tu sello.")
        self._style()
        self._layout()
        for value in (self.width_value, self.top_value, self.right_value):
            value.trace_add("write", self.schedule_preview)
        self.bind("<Control-o>", lambda _: self.choose_pdf() if not self.busy else None)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(80, self.poll)

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

    def button(self, parent, text, command, **kwargs):
        result = ttk.Button(parent, text=text, command=command, **kwargs)
        self.controls.append(result)
        return result

    def _layout(self):
        header = tk.Frame(self, bg=INK, padx=28, pady=20)
        header.pack(fill="x")
        tk.Label(header, text="Sello PDF", font=("Segoe UI Semibold", 24), fg="white", bg=INK).pack(anchor="w")
        tk.Label(header, text="Tu sello en cada página, en unos pasos.", font=("Segoe UI", 11),
                 fg="#c6d4e6", bg=INK).pack(anchor="w", pady=(3, 0))
        body = ttk.Frame(self, padding=20)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        left = ttk.Frame(body, style="Card.TFrame", padding=20, width=360)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        left.grid_propagate(False)
        left.columnconfigure(0, weight=1)
        ttk.Label(left, text="01   Archivos", style="Title.TLabel").grid(row=0, sticky="w")
        sources = ttk.Frame(left, style="Card.TFrame")
        sources.grid(row=1, sticky="ew", pady=(14, 5))
        self.button(sources, "Un PDF…", self.choose_pdf).pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.button(sources, "Carpeta de PDF…", self.choose_folder).pack(side="left", fill="x", expand=True)
        self.pdf_label = ttk.Label(left, text="Ningún documento seleccionado", style="Muted.TLabel", wraplength=310)
        self.pdf_label.grid(row=2, sticky="w")
        self.button(left, "Seleccionar imagen del sello…", self.choose_stamp).grid(row=3, sticky="ew", pady=(16, 5))
        self.stamp_label = ttk.Label(left, text="PNG, JPG, WEBP, BMP o TIFF", style="Muted.TLabel", wraplength=310)
        self.stamp_label.grid(row=4, sticky="w")
        ttk.Separator(left).grid(row=5, sticky="ew", pady=20)
        ttk.Label(left, text="02   Posición y tamaño", style="Title.TLabel").grid(row=6, sticky="w")
        ttk.Label(left, text="Esquina superior derecha · Todas las páginas",
                  style="Muted.TLabel", wraplength=310).grid(row=7, sticky="w", pady=(6, 14))
        options = ttk.Frame(left, style="Card.TFrame")
        options.grid(row=8, sticky="ew")
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
        ttk.Label(left, text="La imagen conserva sus proporciones.\nPara un fondo transparente, usa PNG.",
                  style="Muted.TLabel", wraplength=310).grid(row=9, sticky="w", pady=(12, 0))
        left.rowconfigure(10, weight=1)
        self.save_button = self.button(left, "Guardar PDF sellado…", self.save, style="Primary.TButton")
        self.save_button.grid(row=11, sticky="ew", pady=(20, 8))
        self.save_button.state(["disabled"])
        self.destination_label = ttk.Label(left, text="Se guarda una copia. El original se conserva.",
                                           style="Muted.TLabel", wraplength=310)
        self.destination_label.grid(row=12, sticky="w")

        right = ttk.Frame(body, style="Card.TFrame", padding=16)
        right.grid(row=0, column=1, sticky="nsew")
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
        self.canvas = tk.Canvas(right, bg="#e8edf4", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self.draw_preview)
        self.preview_image = None
        self.preview_error = None
        ttk.Label(right, text="El sello se coloca detrás del texto. Revisa su visibilidad.", style="Muted.TLabel").pack(anchor="w", pady=(10, 0))
        footer = ttk.Frame(self, padding=(20, 0, 20, 14))
        footer.pack(fill="x")
        self.progress = ttk.Progressbar(footer, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 8))
        self.open_button = ttk.Button(footer, text="Abrir resultado", command=self.open_output)
        self.open_button.pack(side="right", padx=(12, 0))
        self.open_button.state(["disabled"])
        tk.Label(footer, textvariable=self.status, bg=BG, fg=MUTED, font=("Segoe UI", 10),
                 anchor="w", wraplength=780, justify="left").pack(side="left", fill="x", expand=True)
        self.update_controls()

    def options(self):
        try:
            values = [float(v.get().strip().replace(",", ".")) for v in
                      (self.width_value, self.top_value, self.right_value)]
        except ValueError:
            raise ValueError("Introduce números en el ancho y los márgenes.") from None
        result = StampOptions(*values)
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
            self.stamp_label.config(text=Path(path).name)
            self.schedule_preview()
            self.update_controls()
        except Exception as exc:
            messagebox.showerror("No se pudo abrir la imagen", str(exc))

    def update_controls(self):
        for control in self.controls:
            control.state(["disabled"] if self.busy else ["!disabled"])
        if not self.pdf or not self.stamp:
            self.save_button.state(["disabled"])
        self.document_selector.configure(state="disabled" if self.busy or not self.pdf_files else "readonly")
        self.save_button.configure(text="Sellar toda la carpeta" if self.folder else "Guardar PDF sellado…")
        self.destination_label.configure(text="Copias en una nueva subcarpeta Sellados.\nLos originales se conservan."
                                         if self.folder else "Se guarda una copia. El original se conserva.")
        if self.page <= 0 or self.busy:
            self.prev_button.state(["disabled"])
        if self.page >= self.pages - 1 or self.busy:
            self.next_button.state(["disabled"])
        self.page_label.config(text=f"{self.page + 1} / {self.pages}" if self.pages else "Sin documento")

    def move(self, delta):
        self.page = max(0, min(self.pages - 1, self.page + delta))
        self.update_controls()
        self.schedule_preview()

    def schedule_preview(self, *_):
        self.preview_version += 1
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
        try:
            options = self.options()
        except ValueError as exc:
            self.preview_image, self.preview_error = None, str(exc)
            self.draw_preview()
            return
        self.preview_busy = True
        version = self.preview_version
        args = (self.pdf, self.page, self.stamp, options)
        self.status.set("Actualizando vista previa…")
        self.worker = multiprocessing.Process(target=preview_worker,
            args=(self.events, version, args), daemon=True)
        self.worker.start()

    def draw_preview(self, *_):
        self.canvas.delete("all")
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if self.preview_image is None:
            self.canvas.create_text(w / 2, h / 2, text=self.preview_error or
                                    "Aquí verás tu documento\ncon el sello aplicado", fill=MUTED,
                                    font=("Segoe UI", 12), width=max(100, w - 60), justify="center")
            return
        image = self.preview_image.copy()
        image.thumbnail((max(1, w - 32), max(1, h - 32)))
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.create_rectangle((w - image.width) / 2 + 3, (h - image.height) / 2 + 3,
                                     (w + image.width) / 2 + 3, (h + image.height) / 2 + 3,
                                     fill="#c5cddb", outline="")
        self.canvas.create_image(w / 2, h / 2, image=self.photo)

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
                        self.preview_image, self.preview_error, self.pages = event[2:]
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
        self.after(80, self.poll)

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


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    StampApp().mainloop()
