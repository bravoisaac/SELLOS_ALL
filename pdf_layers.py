"""Separación vectorial de texto y gráficos para el modo intermedio."""
import io
from contextlib import contextmanager

import pymupdf
from PIL import Image, ImageChops
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, DecodedStreamObject, NameObject

TEXT_SHOW = {b"Tj", b"TJ", b"'", b'"'}
PATH_PAINT = {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}


def _resolve(value):
    return value.get_object() if hasattr(value, "get_object") else value


def _check_appearance(page, graphics, text):
    """No elevar texto oculto por máscaras/fondos ni cambiar el aspecto original."""
    scale = min(1.5, 1400 / max(page.rect.width, page.rect.height))

    def raster(target):
        pix = target.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=True,
                                colorspace=pymupdf.csRGB, annots=False)
        return Image.frombytes("RGBa", (pix.width, pix.height), pix.samples).convert("RGBA")

    before = raster(page)
    combined = Image.alpha_composite(raster(graphics[0]), raster(text[0]))
    if before.size != combined.size:
        raise ValueError("No se pudieron separar las capas de esta página. Elige Al fondo o Delante del texto.")
    difference = ImageChops.difference(before, combined)
    # Tolerar pequeños redondeos de antialiasing, no cambios de contenido.
    if any(sum(band.histogram()[21:]) > 3 for band in difference.split()):
        raise ValueError("Separar fondo y texto cambiaría el aspecto de esta página. Elige Al fondo o Delante del texto.")


def _filtered_pdf(data: bytes, text_only: bool) -> bytes:
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data), strict=True))
    forms = {}
    active = set()

    def filter_stream(stream, resources):
        operations = []
        for operands, operator in stream.operations:
            # El texto que actúa como recorte relaciona ambas capas: no separarlo.
            if operator == b"Tr" and int(operands[0]) >= 4:
                raise ValueError("Este PDF usa letras como máscara de recorte. Elige Al fondo o Delante del texto.")
            if not text_only and operator in TEXT_SHOW:
                continue
            if text_only and operator in PATH_PAINT:
                if operator in {b"s", b"b", b"b*"}:
                    operations.append(([], b"h"))
                operations.append(([], b"n"))  # Finaliza el camino y conserva los recortes W/W*.
                continue
            if text_only and operator in {b"sh", b"INLINE IMAGE"}:
                continue
            if operator == b"Do":
                xobjects = _resolve(resources.get("/XObject", {}))
                name = operands[0]
                if name not in xobjects:
                    raise ValueError("El PDF contiene una referencia gráfica inválida.")
                original = xobjects[name].get_object()
                subtype = original.get("/Subtype")
                if subtype == "/Image" and text_only:
                    continue
                if subtype == "/Form":
                    key = id(original)
                    if key in active:
                        raise ValueError("El PDF contiene formularios gráficos circulares.")
                    if key not in forms:
                        active.add(key)
                        child_resources = _resolve(original.get("/Resources", resources))
                        child = filter_stream(ContentStream(original, writer), child_resources)
                        replacement = DecodedStreamObject()
                        replacement.update({k: v for k, v in original.items()
                                            if k not in {"/Filter", "/DecodeParms", "/Length"}})
                        replacement.set_data(child.get_data())
                        # API interna estable en la versión fijada: registrar el stream como objeto indirecto.
                        forms[key] = writer._add_object(replacement)
                        # Si el recurso se reutiliza, no volver a filtrar su sustituto.
                        forms[id(replacement)] = forms[key]
                        active.remove(key)
                    xobjects[name] = forms[key]
            operations.append((operands, operator))
        filtered = ContentStream(None, writer)
        filtered.operations = operations
        return filtered

    page = writer.pages[0]
    if not text_only:
        page.pop("/Annots", None)
    content = page.get_contents()
    if content is not None:
        page.replace_contents(filter_stream(content, _resolve(page.get("/Resources", {}))))
    buffer = io.BytesIO()
    writer.write(buffer)
    writer.close()
    return buffer.getvalue()


@contextmanager
def split_page(page):
    """Dos documentos temporales: gráficos y texto; anotaciones solo en la vista de texto."""
    with pymupdf.open() as source:
        source.insert_pdf(page.parent, from_page=page.number, to_page=page.number,
                          links=False, annots=True, widgets=True)
        data = source.tobytes()
    with pymupdf.open(stream=_filtered_pdf(data, False), filetype="pdf") as graphics:
        with pymupdf.open(stream=_filtered_pdf(data, True), filetype="pdf") as text:
            _check_appearance(page, graphics, text)
            yield graphics, text
