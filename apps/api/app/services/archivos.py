"""Guardado de comprobantes en disco, deduplicados por SHA-256."""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Archivo  # noqa: F401  (re-export para routers)

TIPOS_PERMITIDOS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "application/pdf": ".pdf",
}


def guardar(db: Session, upload: UploadFile) -> Archivo:
    mime = (upload.content_type or "").lower()
    if mime not in TIPOS_PERMITIDOS:
        raise HTTPException(415, f"Tipo de archivo no admitido: {mime or 'desconocido'}. Usá foto o PDF.")

    limite = settings.max_upload_mb * 1024 * 1024
    contenido = upload.file.read(limite + 1)
    if len(contenido) > limite:
        raise HTTPException(413, f"El archivo supera {settings.max_upload_mb} MB.")
    if not contenido:
        raise HTTPException(400, "El archivo está vacío.")

    sha = hashlib.sha256(contenido).hexdigest()
    existente = db.scalar(select(Archivo).where(Archivo.sha256 == sha))
    if existente:
        return existente

    ahora = datetime.now(timezone.utc)
    relativa = Path(f"{ahora:%Y}/{ahora:%m}/{sha}{TIPOS_PERMITIDOS[mime]}")
    esquema = (db.get_bind().get_execution_options().get("schema_translate_map") or {}).get(None, "public")
    if esquema != "public":
        relativa = Path(esquema) / relativa
    destino = Path(settings.upload_dir) / relativa
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)

    archivo = Archivo(
        nombre_original=(upload.filename or f"comprobante{TIPOS_PERMITIDOS[mime]}")[:255],
        ruta=str(relativa),
        mime=mime,
        tamano=len(contenido),
        sha256=sha,
    )
    db.add(archivo)
    db.flush()
    return archivo


def ruta_absoluta(archivo: Archivo) -> Path:
    return Path(settings.upload_dir) / archivo.ruta
