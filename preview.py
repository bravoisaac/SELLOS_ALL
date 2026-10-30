"""Vista previa con capas, zoom y arrastre en coordenadas del PDF visible."""
import io
import math
from dataclasses import replace
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from stamping import MM, StampOptions


def moved_options(page_size, ratio, options, left, top):
    """Convierte el arrastre en márgenes; limita el sello al interior de la página."""
    options.validate()
    width = options.width_mm * MM
    height = width * ratio
    room_x, room_y = page_size[0] - width, page_size[1] - height
    if room_x < 0 or room_y < 0:
        raise ValueError("El sello no cabe en esta página. Reduce el ancho.")
    if not math.isfinite(left) or not math.isfinite(top):
        raise ValueError("La posición no es válida.")
    left = min(room_x, max(0, left))
    top = min(room_y, max(0, top))
    # Redondear hacia dentro evita superar el borde por precisión decimal.
    top_mm = math.floor(top / MM * 1_000_000) / 1_000_000
    right_mm = math.floor((room_x - left) / MM * 1_000_000) / 1_000_000
    return replace(options, top_mm=top_mm, right_mm=right_mm)


class PreviewPane(ttk.Frame):
    def __init__(self, parent, on_move):
        super().__init__(parent, style="Card.TFrame")
        self.on_move = on_move
        self.source = None
        self.page_size = None
        self.stamp = None
        self.options = None
        self.zoom = None  # None = ajustar a ventana; 1 = 100 %, 96 ppp.
        self.scale = 1
        self.origin = (0, 0)
        self.region = (1, 1)
        self.drag = None
        self.bounds = None
        self.enabled = True
        self.error = None
        self._base_cache = None
        self._stamp_cache = None
        self._resize_timer = None
        toolbar = ttk.Frame(self, style="Card.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="−", width=3, command=lambda: self.change_zoom(.8)).pack(side="left")
        self.zoom_label = ttk.Label(toolbar, text="Ajustar", width=10, anchor="center")
        self.zoom_label.pack(side="left")
        ttk.Button(toolbar, text="+", width=3, command=lambda: self.change_zoom(1.25)).pack(side="left")
        ttk.Button(toolbar, text="Ajustar", command=self.fit).pack(side="left", padx=(8, 0))
        viewport = ttk.Frame(self, style="Card.TFrame")
        viewport.pack(fill="both", expand=True)
        viewport.rowconfigure(0, weight=1)
        viewport.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(viewport, bg="#e8edf4", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(viewport, orient="vertical", command=self.canvas.yview)
        horizontal = ttk.Scrollbar(viewport, orient="horizontal", command=self.canvas.xview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.bind("<Configure>", self.resize)
        self.canvas.bind("<ButtonPress-1>", self.begin_drag)
        self.canvas.bind("<B1-Motion>", self.drag_to)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<Motion>", self.hover)
        self.canvas.bind("<MouseWheel>", self.wheel)
        self.canvas.bind("<Control-MouseWheel>", self.wheel_zoom)
        self.canvas.bind("<Shift-MouseWheel>", self.wheel_horizontal)
        self.canvas.bind("<Escape>", self.cancel_drag)
        ttk.Label(self, text="Arrastra el sello · Ctrl + rueda: zoom · Rueda: desplazar",
                  style="Muted.TLabel").pack(anchor="w", pady=(7, 0))

    def set_content(self, source, page_size, stamp, options, error=None, enabled=True):
        self.cancel_drag()
        if source is not self.source:
            self._base_cache = None
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)
        if stamp is not self.stamp:
            self._stamp_cache = None
        self.source, self.page_size, self.stamp, self.options = source, page_size, stamp, options
        self.error, self.enabled = error, enabled
        self.redraw()

    def resize(self, *_):
        if self._resize_timer:
            self.after_cancel(self._resize_timer)
        self._resize_timer = self.after(80, self.redraw)

    def redraw(self):
        self._resize_timer = None
        self.cancel_drag()
        c = self.canvas
        c.delete("all")
        self.bounds = None
        vw, vh = max(1, c.winfo_width()), max(1, c.winfo_height())
        if self.source is None or not self.page_size:
            c.configure(scrollregion=(0, 0, vw, vh))
            c.create_text(vw / 2, vh / 2, text=self.error or "Aquí verás tu documento\ncon el sello aplicado",
                          fill="#58697e", font=("Segoe UI", 12), width=max(100, vw - 40), justify="center")
            return
        pw, ph = self.page_size
        self.scale = max(.001, min((vw - 32) / pw, (vh - 32) / ph)) if self.zoom is None else self.zoom * 96 / 72
        # Limitar imágenes temporales incluso con páginas de tamaño excepcional.
        self.scale = min(self.scale, 8192 / max(pw, ph), math.sqrt(16_000_000 / (pw * ph)))
        iw, ih = max(1, round(pw * self.scale)), max(1, round(ph * self.scale))
        rw, rh = max(vw, iw + 32), max(vh, ih + 32)
        self.region = rw, rh
        self.origin = ox, oy = (rw - iw) / 2, (rh - ih) / 2
        c.configure(scrollregion=(0, 0, rw, rh))
        self.zoom_label.configure(text=f"{self.scale * 72 / 96 * 100:.0f}%" + (" · auto" if self.zoom is None else ""))
        c.create_rectangle(ox + 3, oy + 3, ox + iw + 3, oy + ih + 3, fill="#c5cddb", outline="")
        c.create_rectangle(ox, oy, ox + iw, oy + ih, fill="white", outline="")
        base = self.source[0] if isinstance(self.source, tuple) else self.source
        top = self.source[1] if isinstance(self.source, tuple) else None
        if self._base_cache != (iw, ih):
            self.base_photo = ImageTk.PhotoImage(base.resize((iw, ih), Image.Resampling.LANCZOS))
            self.top_photo = ImageTk.PhotoImage(top.resize((iw, ih), Image.Resampling.LANCZOS)) if top is not None else None
            self._base_cache = iw, ih
        layer = self.options.layer if self.options else "background"
        if layer in {"middle", "foreground"}:
            c.create_image(ox, oy, image=self.base_photo, anchor="nw", tags="base")
        # Orden configurable: fondo/sello/texto, documento/sello, o sello/documento.
        if self.stamp and self.options:
            try:
                self.options.validate()
                width = self.options.width_mm * MM
                height = width * self.stamp[1]
                x, y = pw - self.options.right_mm * MM - width, self.options.top_mm * MM
                if x < -1e-6 or y + height > ph + 1e-6:
                    raise ValueError("El sello no cabe. Reduce el ancho o los márgenes.")
                sw, sh = max(1, round(width * self.scale)), max(1, round(height * self.scale))
                if self._stamp_cache != (sw, sh):
                    with Image.open(io.BytesIO(self.stamp[0])) as image:
                        self.stamp_photo = ImageTk.PhotoImage(image.resize((sw, sh), Image.Resampling.LANCZOS))
                    self._stamp_cache = sw, sh
                sx, sy = ox + x * self.scale, oy + y * self.scale
                self.bounds = (sx, sy, sx + width * self.scale, sy + height * self.scale)
                c.create_image(sx, sy, image=self.stamp_photo, anchor="nw", tags="stamp")
            except ValueError as exc:
                self.error = str(exc)
        if layer == "background":
            c.create_image(ox, oy, image=self.base_photo, anchor="nw", tags="base")
        elif layer == "middle" and self.top_photo is not None:
            c.create_image(ox, oy, image=self.top_photo, anchor="nw", tags="text")
        if self.bounds:
            c.create_rectangle(*self.bounds, outline="#245edb", width=2, dash=(5, 3), tags="selection")
        if self.error:
            c.create_text(c.canvasx(vw / 2), c.canvasy(20), text=self.error, fill="#a52424",
                          font=("Segoe UI", 11), width=max(100, vw - 40), anchor="n")

    def fit(self):
        self.zoom = None
        self.redraw()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def change_zoom(self, factor, anchor=None):
        if self.source is None or self.drag:
            return
        c = self.canvas
        ax, ay = anchor or (c.winfo_width() / 2, c.winfo_height() / 2)
        px, py = self.canvas_point(ax, ay)
        self.zoom = min(3, max(.25, self.scale * 72 / 96 * factor))
        self.redraw()
        c.xview_moveto(max(0, self.origin[0] + px * self.scale - ax) / self.region[0])
        c.yview_moveto(max(0, self.origin[1] + py * self.scale - ay) / self.region[1])

    def canvas_point(self, x, y):
        return ((self.canvas.canvasx(x) - self.origin[0]) / self.scale,
                (self.canvas.canvasy(y) - self.origin[1]) / self.scale)

    def hit(self, event):
        if not self.enabled or not self.bounds:
            return False
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        x0, y0, x1, y1 = self.bounds
        return x0 <= x <= x1 and y0 <= y <= y1

    def hover(self, event):
        self.canvas.configure(cursor="fleur" if self.hit(event) else "")

    def begin_drag(self, event):
        if not self.hit(event):
            return
        px, py = self.canvas_point(event.x, event.y)
        x = self.page_size[0] - (self.options.right_mm + self.options.width_mm) * MM
        self.drag = (px - x, py - self.options.top_mm * MM, self.options)
        self.canvas.focus_set()
        self.canvas.grab_set()

    def drag_to(self, event):
        if not self.drag:
            return
        px, py = self.canvas_point(event.x, event.y)
        options = moved_options(self.page_size, self.stamp[1], self.drag[2], px - self.drag[0], py - self.drag[1])
        width, height = options.width_mm * MM, options.width_mm * MM * self.stamp[1]
        x = self.origin[0] + (self.page_size[0] - (options.right_mm + options.width_mm) * MM) * self.scale
        y = self.origin[1] + options.top_mm * MM * self.scale
        self.bounds = x, y, x + width * self.scale, y + height * self.scale
        self.canvas.coords("stamp", x, y)
        self.canvas.coords("selection", *self.bounds)
        self.options = options

    def end_drag(self, event):
        if not self.drag:
            return
        self.drag_to(event)
        self.drag = None
        self.canvas.grab_release()
        self.on_move(self.options)

    def cancel_drag(self, *_):
        if self.drag:
            self.options = self.drag[2]
            self.drag = None
            self.canvas.grab_release()
            # Restaurar la posición antes de cualquier redibujado o cambio de documento.
            if self.bounds:
                width = self.options.width_mm * MM
                x = self.origin[0] + (self.page_size[0] - self.options.right_mm * MM - width) * self.scale
                y = self.origin[1] + self.options.top_mm * MM * self.scale
                self.bounds = x, y, x + width * self.scale, y + width * self.stamp[1] * self.scale
                self.canvas.coords("stamp", x, y)
                self.canvas.coords("selection", *self.bounds)

    def wheel(self, event):
        if not self.drag:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def wheel_horizontal(self, event):
        if not self.drag:
            self.canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def wheel_zoom(self, event):
        self.change_zoom(1.25 if event.delta > 0 else .8, (event.x, event.y))
        return "break"
