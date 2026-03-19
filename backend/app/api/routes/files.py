"""
files.py — роут для загрузки и обработки файлов.

Эндпоинты:
  POST /api/files/extract-text — извлекает текст из PDF (и других файлов).
"""
import io
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/files", tags=["files"])


def _extract_pdf_text(file_bytes: bytes, max_chars: int = 30000) -> str:
    """Извлекает текст из PDF через pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        parts = []
        total = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            if total + len(text) > max_chars:
                parts.append(text[:max_chars - total])
                break
            parts.append(text)
            total += len(text)
        return "\n\n".join(parts)
    except ImportError:
        return "[pypdf не установлен — pip install pypdf]"
    except Exception as e:
        return f"[Ошибка PDF: {e}]"


def _extract_text_file(file_bytes: bytes, max_chars: int = 30000) -> str:
    """Пробует прочитать как текст."""
    try:
        text = file_bytes.decode("utf-8", errors="replace")
        return text[:max_chars]
    except Exception:
        return ""


@router.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    """
    Принимает файл (PDF, текст, код) и возвращает извлечённый текст.
    """
    try:
        contents = await file.read()
        filename = file.filename or ""

        if filename.lower().endswith(".pdf"):
            text = _extract_pdf_text(contents)
        else:
            text = _extract_text_file(contents)

        return {
            "ok": True,
            "filename": filename,
            "size": len(contents),
            "text": text,
            "chars": len(text),
        }
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(exc)},
        )
