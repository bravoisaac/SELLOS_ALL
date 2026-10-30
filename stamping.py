"""Sellado local de PDF. Las coordenadas se calculan sobre la página visible."""
from __future__ import annotations

import io
import csv
import math
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pymupdf
from PIL import Image, ImageOps

MM = 72 / 25.4


@dataclass
class BatchResult:
    output_dir: Path
    succeeded: list[tuple[str, int]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    report_error: str | None = None


def list_pdfs(folder: str | Path) -> list[Path]:
    """Solo archivos directamente contenidos; nunca reingresa en Sellados."""
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError("Selecciona una carpeta válida.")
    return sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"),
                  key=lambda p: p.name.casefold())


def stamp_folder(folder: str | Path, image_path: str | Path,
                 options: StampOptions | None = None,
                 progress: Callable[[int, int, str, int, int], None] | None = None) -> BatchResult:
    options = options or StampOptions()
    options.validate()
    files = list_pdfs(folder)
    if not files:
        raise ValueError("La carpeta no contiene archivos PDF. No se incluyen subcarpetas.")
    load_stamp(image_path)  # Fallar antes de crear resultados si la imagen es inválida.
    folder = Path(folder).resolve()
    number = 1
    while True:
        output = folder / ("Sellados" if number == 1 else f"Sellados ({number})")
        try:
            output.mkdir()
            break
        except FileExistsError:
            number += 1
    result = BatchResult(output)
    for index, source in enumerate(files, 1):
        if progress:
            progress(index, len(files), source.name, 0, 0)
        try:
            count = stamp_pdf(source, image_path, output / source.name, options,
                progress=(lambda page, total: progress(index, len(files), source.name, page, total))
                if progress else None)
            result.succeeded.append((source.name, count))
        except Exception as exc:
            result.failed.append((source.name, str(exc)))
        if progress:
            progress(index, len(files), source.name, 1, 1)
    try:
        with (output / "informe.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(["Archivo", "Estado", "Páginas", "Detalle"])
            # Evitar que nombres/errores se interpreten como fórmulas al abrir en Excel.
            def literal(value):
                text = str(value)
                return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
            for name, count in result.succeeded:
                writer.writerow([literal(name), "Sellado", count, ""])
            for name, error in result.failed:
                writer.writerow([literal(name), "Error", "", literal(error)])
    except OSError as exc:
        result.report_error = str(exc)
    return result


@dataclass(frozen=True)
class StampOptions:
    width_mm: float = 35
    top_mm: float = 10
    right_mm: float = 10

    def validate(self):
        values = (self.width_mm, self.top_mm, self.right_mm)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Introduce medidas numéricas válidas.")
        if self.width_mm <= 0 or self.top_mm < 0 or self.right_mm < 0:
            raise ValueError("El ancho debe ser mayor que cero y los márgenes no pueden ser negativos.")


def load_stamp(path: str | Path) -> tuple[bytes, float]:
    """Normaliza orientación y conserva la transparencia de PNG."""
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
        if image.width == 0 or image.height == 0:
            raise ValueError("La imagen está vacía.")
        ratio = image.height / image.width
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue(), ratio


def open_pdf(path: str | Path) -> pymupdf.Document:
    doc = pymupdf.open(path)
    if not doc.is_pdf or doc.needs_pass or not len(doc):
        doc.close()
        raise ValueError("Elige un PDF con páginas y sin contraseña de apertura.")
    if doc.is_encrypted or not doc.permissions & pymupdf.PDF_PERM_MODIFY:
        doc.close()
        raise ValueError("Este PDF está protegido contra modificaciones. Usa una copia con permisos de edición.")
    return doc


def stamp_rect(page, ratio: float, options: StampOptions) -> pymupdf.Rect:
    options.validate()
    width, height = options.width_mm * MM, options.width_mm * MM * ratio
    right, top = options.right_mm * MM, options.top_mm * MM
    bounds = page.rect
    if width + right > bounds.width or height + top > bounds.height:
        raise ValueError(
            f"El sello no cabe en la página {page.number + 1}. Reduce el ancho o los márgenes."
        )
    return pymupdf.Rect(bounds.width - right - width, top, bounds.width - right, top + height)


def insert_stamp(page, png: bytes, ratio: float, options: StampOptions, xref: int = 0) -> int:
    rect = stamp_rect(page, ratio, options) * page.derotation_matrix
    # insert_image gira antihorario; compensa la rotación horaria de la página.
    rotation = page.rotation
    # MuPDF debe usar la transformación completa del CropBox al insertar.
    # Con una página rotada, su matriz omite el desplazamiento del recorte.
    page.set_rotation(0)
    try:
        return page.insert_image(rect, stream=png if not xref else None, xref=xref,
                                 rotate=rotation, keep_proportion=False, overlay=False)
    finally:
        page.set_rotation(rotation)


def render_preview(pdf_path: str | Path, page_number: int, stamp: tuple[bytes, float] | None,
                   options: StampOptions, max_size=(760, 880)) -> tuple[Image.Image, int]:
    with open_pdf(pdf_path) as doc:
        page = doc[page_number]
        if stamp:
            insert_stamp(page, *stamp, options)
        scale = min(max_size[0] / page.rect.width, max_size[1] / page.rect.height, 2)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples), len(doc)


def stamp_pdf(pdf_path: str | Path, image_path: str | Path, output_path: str | Path,
              options: StampOptions = StampOptions(),
              progress: Callable[[int, int], None] | None = None) -> int:
    source, target = Path(pdf_path).resolve(), Path(output_path).resolve()
    image_path = Path(image_path).resolve()
    for original in (source, image_path):
        if target == original or (target.exists() and os.path.samefile(target, original)):
            raise ValueError("El destino debe ser diferente del PDF y de la imagen originales.")
    if target.suffix.lower() != ".pdf":
        raise ValueError("El archivo de salida debe tener extensión .pdf.")
    png, ratio = load_stamp(image_path)
    temp_path = None
    try:
        with open_pdf(source) as doc:
            # Validar todas las páginas antes de modificar el documento en memoria.
            for page in doc:
                stamp_rect(page, ratio, options)
            xref = 0
            for current, page in enumerate(doc, 1):
                xref = insert_stamp(page, png, ratio, options, xref)
                if progress:
                    progress(current, len(doc))
            count = len(doc)
            fd, temp_path = tempfile.mkstemp(prefix=".sello-", suffix=".pdf", dir=target.parent)
            os.close(fd)
            doc.save(temp_path, garbage=3, deflate=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
        with pymupdf.open(temp_path) as check:
            if len(check) != count:
                raise ValueError("No se pudo verificar el PDF generado.")
        os.replace(temp_path, target)
        return count
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
