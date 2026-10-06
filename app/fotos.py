"""Fotos que sube el alumnado para usarlas como base (img2img)."""

from __future__ import annotations

import base64
import binascii
import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps

MAX_BYTES = 10 * 1024 * 1024
PIXELES = 1024 * 1024  # Z-Image Turbo trabaja bien alrededor de 1 megapíxel
MULTIPLO = 16


class FotoNoValida(Exception):
    pass


def medidas(ancho: int, alto: int) -> tuple[int, int]:
    """Escala a ~1 MP manteniendo la proporción, con lados múltiplos de 16."""
    escala = (PIXELES / (ancho * alto)) ** 0.5
    return (max(MULTIPLO, round(ancho * escala / MULTIPLO) * MULTIPLO),
            max(MULTIPLO, round(alto * escala / MULTIPLO) * MULTIPLO))


def guardar(datos_url: str, carpeta: Path) -> tuple[str, int, int]:
    """Valida una foto en data URL (o base64), la ajusta y la guarda como JPEG. Devuelve (id, ancho, alto)."""
    base64_ = datos_url.split(",", 1)[1] if datos_url.startswith("data:") else datos_url
    try:
        crudo = base64.b64decode(base64_, validate=True)
    except (binascii.Error, ValueError) as e:
        raise FotoNoValida("La foto no ha llegado bien. Prueba otra vez.") from e
    if len(crudo) > MAX_BYTES:
        raise FotoNoValida("La foto es demasiado grande.")
    try:
        with Image.open(io.BytesIO(crudo)) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
    except (OSError, Image.DecompressionBombError) as e:
        raise FotoNoValida("No puedo leer esa imagen. Prueba con otra foto.") from e
    ancho, alto = medidas(*im.size)
    if max(ancho, alto) / min(ancho, alto) > 3:
        raise FotoNoValida("La foto es demasiado alargada. Prueba con otra.")
    im = im.resize((ancho, alto), Image.LANCZOS)
    carpeta.mkdir(parents=True, exist_ok=True)
    id_ = uuid.uuid4().hex
    im.save(carpeta / f"{id_}.jpg", "JPEG", quality=92)
    return id_, ancho, alto
