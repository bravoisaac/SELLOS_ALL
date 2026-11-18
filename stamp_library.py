"""Biblioteca local: cada sello es un PNG con sus ajustes, guardado atómicamente."""
from __future__ import annotations

import io
import json
import os
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, PngImagePlugin

from stamping import StampOptions

METADATA_KEY = "SelloPDF"


def default_library_dir() -> Path:
    base = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else Path.home() / ".local" / "share"
    return base / "SelloPDF" / "sellos"


def valid_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("Escribe un nombre para el sello.")
    name = name.strip()
    if not name or len(name) > 80 or any(ord(char) < 32 for char in name):
        raise ValueError("El nombre debe tener entre 1 y 80 caracteres, sin saltos de línea.")
    return name


@dataclass(frozen=True)
class SavedStamp:
    id: str
    name: str
    path: Path
    options: StampOptions


class StampLibrary:
    def __init__(self, directory: Path | None = None):
        self.directory = Path(directory) if directory is not None else default_library_dir()
        self.unreadable_count = 0

    def _path(self, stamp_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", stamp_id):
            raise ValueError("El identificador del sello no es válido.")
        return self.directory / f"{stamp_id}.png"

    def list(self) -> list[SavedStamp]:
        self.unreadable_count = 0
        if not self.directory.exists():
            return []
        saved = []
        for path in self.directory.glob("*.png"):
            try:
                if path.is_symlink() or self._path(path.stem) != path:
                    raise ValueError("Ruta no válida")
                with Image.open(path) as image:
                    if image.format != "PNG":
                        raise ValueError("Formato no válido")
                    data = json.loads(image.info[METADATA_KEY])
                if data["version"] != 1:
                    raise ValueError("Versión no compatible")
                options = StampOptions(**data["options"])
                options.validate()
                saved.append(SavedStamp(path.stem, valid_name(data["name"]), path, options))
            except (OSError, ValueError, KeyError, TypeError):
                self.unreadable_count += 1
        return sorted(saved, key=lambda entry: (entry.name.casefold(), entry.id))

    def save(self, name: str, png: bytes, options: StampOptions,
             replace_id: str | None = None) -> SavedStamp:
        name = valid_name(name)
        options.validate()
        existing = self.list()
        if any(item.name.casefold() == name.casefold() and item.id != replace_id for item in existing):
            raise ValueError("Ya existe un sello con ese nombre. Elige otro nombre o reemplázalo.")
        if replace_id is not None and not any(item.id == replace_id for item in existing):
            raise ValueError("El sello ya no está en la biblioteca. Vuelve a guardarlo como uno nuevo.")
        stamp_id = replace_id or uuid.uuid4().hex
        target = self._path(stamp_id)
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text(METADATA_KEY, json.dumps({
            "version": 1, "name": name, "options": asdict(options),
        }, ensure_ascii=False))
        # Una copia normalizada evita depender de la ubicación o metadatos de la imagen original.
        with Image.open(io.BytesIO(png)) as source:
            image = source.convert("RGBA")
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.directory, suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                image.save(stream, format="PNG", pnginfo=metadata)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            image.close()
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return SavedStamp(stamp_id, name, target, options)

    def remove(self, stamp_id: str) -> None:
        # Solo se elimina la copia administrada, nunca la imagen original del usuario.
        self._path(stamp_id).unlink()
