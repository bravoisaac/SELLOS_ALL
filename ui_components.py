"""Controles adaptables de la interfaz Tk, sin dependencias adicionales."""
import tkinter as tk
from tkinter import ttk


class ScrollableSettings(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="Card.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, background="white", highlightthickness=0, width=340, height=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.content = ttk.Frame(self.canvas, style="Card.TFrame", padding=16)
        self.window = self.canvas.create_window(0, 0, window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._content_changed)
        self.canvas.bind("<Configure>", self._resized)
        root = self.winfo_toplevel()
        root.bind("<MouseWheel>", self._wheel, add="+")
        root.bind("<FocusIn>", self._focus, add="+")

    def _inside(self, widget):
        while widget is not None:
            if widget is self:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _content_changed(self, *_):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resized(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)

    def _wheel(self, event):
        if (self._inside(event.widget) and event.widget.winfo_class() not in {"TCombobox", "TSpinbox"}
                and self.content.winfo_height() > self.canvas.winfo_height()):
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"

    def _focus(self, event):
        if self._inside(event.widget) and event.widget is not self.canvas:
            self.reveal(event.widget)

    def reveal(self, widget):
        top = widget.winfo_rooty() - self.content.winfo_rooty()
        bottom = top + widget.winfo_height()
        visible_top = self.canvas.canvasy(0)
        visible_bottom = visible_top + self.canvas.winfo_height()
        total = max(1, self.content.winfo_height())
        if top < visible_top:
            self.canvas.yview_moveto(max(0, top - 8) / total)
        elif bottom > visible_bottom:
            self.canvas.yview_moveto(max(0, bottom + 8 - self.canvas.winfo_height()) / total)
