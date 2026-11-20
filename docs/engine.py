"""Motor web puro de Python: sin red, procesos nativos ni acceso a archivos del PC."""
import io
import json
import math

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ContentStream, DecodedStreamObject, DictionaryObject, NameObject,
    NumberObject, RectangleObject,
)

MM = 72 / 25.4
TEXT_SHOW = {b"Tj", b"TJ", b"'", b'"'}
PATH_PAINT = {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}


def serialized(writer):
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def filter_writer(writer, text_only):
    """Adaptación de pdf_layers.py, conservando recursos y texto vectorial."""
    forms, active = {}, set()

    def resolve(value):
        return value.get_object() if hasattr(value, "get_object") else value

    def filtered(stream, resources):
        operations = []
        for operands, operator in stream.operations:
            if operator == b"Tr" and int(operands[0]) >= 4:
                raise ValueError("Este PDF usa texto como máscara. Elige Al fondo o Delante del texto.")
            if not text_only and operator in TEXT_SHOW:
                continue
            if text_only and operator in PATH_PAINT:
                if operator in {b"s", b"b", b"b*"}:
                    operations.append(([], b"h"))
                operations.append(([], b"n"))
                continue
            if text_only and operator in {b"sh", b"INLINE IMAGE"}:
                continue
            if operator == b"Do":
                xobjects = resolve(resources.get("/XObject", {}))
                if operands[0] not in xobjects:
                    raise ValueError("El PDF contiene un recurso gráfico inválido.")
                original = resolve(xobjects[operands[0]])
                if original.get("/Subtype") == "/Image" and text_only:
                    continue
                if original.get("/Subtype") == "/Form":
                    key = id(original)
                    if key in active:
                        raise ValueError("El PDF contiene recursos gráficos circulares.")
                    if key not in forms:
                        active.add(key)
                        child = filtered(ContentStream(original, writer), resolve(original.get("/Resources", resources)))
                        replacement = DecodedStreamObject()
                        replacement.update({k: v for k, v in original.items() if k not in {"/Filter", "/DecodeParms", "/Length"}})
                        replacement.set_data(child.get_data())
                        forms[key] = writer._add_object(replacement)
                        forms[id(replacement)] = forms[key]
                        active.remove(key)
                    xobjects[operands[0]] = forms[key]
            operations.append((operands, operator))
        result = ContentStream(None, writer)
        result.operations = operations
        return result

    for page in writer.pages:
        if text_only:
            page.pop("/Annots", None)
        content = page.get_contents()
        if content is not None:
            page.replace_contents(filtered(content, resolve(page.get("/Resources", {}))))


def image_object(writer, rgba, width, height):
    if not 0 < width <= 4096 or not 0 < height <= 4096 or width * height > 8_000_000:
        raise ValueError("La imagen del sello es demasiado grande.")
    if len(rgba) != width * height * 4:
        raise ValueError("Datos de imagen incompletos.")
    rgb = bytearray(width * height * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = rgba[0::4], rgba[1::4], rgba[2::4]

    def stream(data, color):
        result = DecodedStreamObject()
        result.set_data(data)
        result.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
                       NameObject('/Width'): NumberObject(width), NameObject('/Height'): NumberObject(height),
                       NameObject('/ColorSpace'): NameObject(color), NameObject('/BitsPerComponent'): NumberObject(8)})
        return result.flate_encode()

    image = stream(bytes(rgb), '/DeviceRGB')
    alpha = bytes(rgba[3::4])
    if any(value != 255 for value in alpha):
        image[NameObject('/SMask')] = writer._add_object(stream(alpha, '/DeviceGray'))
    return writer._add_object(image)


def stamp_matrix(page, ratio, options):
    unit = float(page.get('/UserUnit', 1))
    if not math.isfinite(unit) or unit <= 0:
        raise ValueError('La escala de esta página no es válida.')
    box, media = page.cropbox, page.mediabox
    cx, cy = max(float(box.left), float(media.left)), max(float(box.bottom), float(media.bottom))
    w = min(float(box.right), float(media.right)) - cx
    h = min(float(box.top), float(media.top)) - cy
    rotation = page.rotation % 360
    if rotation not in {0, 90, 180, 270}:
        raise ValueError('La rotación de esta página no es compatible.')
    visible_w, visible_h = (w, h) if rotation in {0, 180} else (h, w)
    sw = options['width'] * MM / unit
    sh = sw * ratio
    x = visible_w - options['right'] * MM / unit - sw
    y = visible_h - options['top'] * MM / unit - sh
    if x < -0.001 or y < -0.001:
        raise ValueError('El sello no cabe en esta página. Reduce el ancho o los márgenes.')
    return {
        0: (sw, 0, 0, sh, cx + x, cy + y),
        90: (0, sw, -sh, 0, cx + w - y, cy + x),
        180: (-sw, 0, 0, -sh, cx + w - x, cy + h - y),
        270: (0, -sw, sh, 0, cx + y, cy + h - x),
    }[rotation]


def process(pdf_data, rgba_data, width, height, options_json, page_index=-1):
    options = json.loads(options_json)
    for key in ('width', 'top', 'right'):
        value = options.get(key)
        if not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
            raise ValueError('Introduce medidas numéricas válidas.')
    if options['width'] <= 0 or options.get('layer') not in {'foreground', 'background', 'middle'}:
        raise ValueError('Revisa el ancho y la capa del sello.')
    reader = PdfReader(io.BytesIO(bytes(pdf_data)), strict=False)
    if reader.is_encrypted:
        raise ValueError('Este PDF está protegido. Usa una copia autorizada sin contraseña ni restricciones.')
    if not reader.pages:
        raise ValueError('El PDF no contiene páginas.')
    if page_index >= 0:
        writer = PdfWriter()
        writer.add_page(reader.pages[page_index])
    else:
        writer = PdfWriter(clone_from=reader)
    count = len(writer.pages)
    # Validar todas las páginas antes de modificar el documento.
    matrices = []
    for index, page in enumerate(writer.pages):
        try:
            matrices.append(stamp_matrix(page, height / width, options))
        except ValueError as error:
            raise ValueError(f'Página {index + 1}: {error}') from error
    source = serialized(writer) if options['layer'] == 'middle' else b''
    text_writer = None
    check_pdf = b''
    if options['layer'] == 'middle':
        text_writer = PdfWriter(clone_from=PdfReader(io.BytesIO(source)))
        filter_writer(writer, False)
        filter_writer(text_writer, True)
        check = PdfWriter(clone_from=PdfReader(io.BytesIO(serialized(writer))))
        for index, page in enumerate(check.pages):
            page.merge_page(text_writer.pages[index], over=True)
        check_pdf = serialized(check)
        check.close()
    image_writer = PdfWriter()
    image_ref = image_object(image_writer, bytes(rgba_data), width, height)
    for index, page in enumerate(writer.pages):
        stamp = image_writer.add_blank_page(width=float(page.mediabox.width), height=float(page.mediabox.height))
        stamp.mediabox = RectangleObject(page.mediabox)
        stamp.cropbox = RectangleObject(page.cropbox)
        stamp[NameObject('/Resources')] = DictionaryObject({NameObject('/XObject'): DictionaryObject({NameObject('/Sello'): image_ref})})
        content = DecodedStreamObject()
        content.set_data(('q\n' + ' '.join(f'{v:.8f}' for v in matrices[index]) + ' cm\n/Sello Do\nQ\n').encode('ascii'))
        stamp[NameObject('/Contents')] = image_writer._add_object(content)
        page.merge_page(stamp, over=options['layer'] != 'background')
        if text_writer:
            page.merge_page(text_writer.pages[index], over=True)
    result = {'pdf': serialized(writer), 'check': check_pdf, 'source': source, 'pages': count}
    writer.close()
    image_writer.close()
    if text_writer:
        text_writer.close()
    return result
