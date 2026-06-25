"""
File validation before ingestion.

Two layers of checks:
  1. Structural — size, magic bytes (format identity), text decodability.
  2. Content    — non-empty text after parsing (handled in api/main.py).

Raises ValueError with a user-readable Spanish message on any failure.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Size limits ────────────────────────────────────────────────────────────

_MAX_FILE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
_MAX_FILE_BYTES: int = _MAX_FILE_MB * 1024 * 1024

# ── Magic byte signatures for binary formats ───────────────────────────────
# (offset, expected_bytes, human-readable format name)
_MAGIC: dict[str, tuple[int, bytes, str]] = {
    ".pdf":  (0, b"%PDF",           "PDF"),
    ".docx": (0, b"PK\x03\x04",    "DOCX (ZIP)"),
    ".xlsx": (0, b"PK\x03\x04",    "XLSX (ZIP)"),
    ".doc":  (0, b"\xd0\xcf\x11\xe0", "DOC (OLE2)"),
    ".xls":  (0, b"\xd0\xcf\x11\xe0", "XLS (OLE2)"),
}

# Formats whose content must be valid UTF-8 / plain text
_TEXT_FORMATS: frozenset[str] = frozenset({".txt", ".md", ".csv", ".html", ".htm", ".json"})


# ── Public entry point ─────────────────────────────────────────────────────

def validate_file(path: Path) -> None:
    """
    Run all structural checks on *path*.
    Raises ValueError with a clear Spanish message if any check fails.
    """
    suffix = path.suffix.lower()

    _check_exists(path)
    _check_size(path)

    if suffix in _MAGIC:
        _check_magic_bytes(path, suffix)
    elif suffix in _TEXT_FORMATS:
        _check_text_decodable(path)


# ── Individual checks ──────────────────────────────────────────────────────

def _check_exists(path: Path) -> None:
    size = path.stat().st_size
    if size == 0:
        raise ValueError(
            f"El archivo '{path.name}' está vacío (0 bytes). "
            "Por favor sube un archivo con contenido."
        )


def _check_size(path: Path) -> None:
    size = path.stat().st_size
    if size > _MAX_FILE_BYTES:
        size_mb = size / (1024 * 1024)
        raise ValueError(
            f"El archivo '{path.name}' pesa {size_mb:.1f} MB, "
            f"lo cual supera el límite de {_MAX_FILE_MB} MB."
        )


def _check_magic_bytes(path: Path, suffix: str) -> None:
    offset, expected, fmt_name = _MAGIC[suffix]
    header_size = offset + len(expected)

    with path.open("rb") as f:
        f.seek(offset)
        header = f.read(len(expected))

    if header != expected:
        raise ValueError(
            f"El archivo '{path.name}' tiene extensión '{suffix}' "
            f"pero su contenido no corresponde a un archivo {fmt_name} válido. "
            "Puede estar corrompido o ser de un formato diferente."
        )


def _check_text_decodable(path: Path) -> None:
    """
    Read the first 8 KB and verify the file is valid UTF-8 text,
    not binary data disguised with a text extension.
    """
    with path.open("rb") as f:
        sample = f.read(8192)

    # Null bytes are a strong indicator of binary content
    if b"\x00" in sample:
        raise ValueError(
            f"El archivo '{path.name}' parece ser binario "
            f"aunque tiene una extensión de texto. "
            "Verifique que el archivo no esté corrompido."
        )

    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        # Retry with latin-1 tolerance — some CSV/HTML files use legacy encodings
        try:
            sample.decode("latin-1")
        except UnicodeDecodeError:
            raise ValueError(
                f"El archivo '{path.name}' no se puede leer como texto. "
                "Asegúrese de que esté guardado en UTF-8 o Latin-1."
            )
