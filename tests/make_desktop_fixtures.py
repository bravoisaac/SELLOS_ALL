from pathlib import Path
import pymupdf
from PIL import Image, ImageDraw

root = Path(__file__).parents[1] / 'tmp' / 'desktop-qa'
root.mkdir(parents=True, exist_ok=True)
image = Image.new('RGBA', (200, 100), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rectangle((0, 0, 99, 99), fill=(255, 0, 0, 255))
draw.rectangle((100, 0, 199, 99), fill=(0, 0, 255, 255))
image.save(root / 'sello.png')
with pymupdf.open() as doc:
    for rotation in (0, 90, 180, 270):
        page = doc.new_page(width=600, height=800)
        page.insert_text((60, 300), f'Documento de prueba {rotation}')
        page.set_rotation(rotation)
    doc.save(root / 'documento.pdf')
(root / 'invalido.pdf').write_text('Documento de prueba inválido', encoding='utf-8')
