"""POST /documents — upload files to the RAG knowledge base."""
from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile

from backend.auth import get_current_user, require_admin
from backend.models import User

log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
# parents[2] from backend/routers/documents.py  →  agentic_rag/ (project root)
# parents[3] mirrors chat.py's sys.path trick so `src.*` imports resolve via CWD
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC_PARENT   = Path(__file__).resolve().parents[3]
RAW_DIR = _PROJECT_ROOT / "data" / "raw"

if str(_SRC_PARENT) not in sys.path:
    sys.path.insert(0, str(_SRC_PARENT))

# ── Constants ─────────────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_BYTES = 50 * 1024 * 1024  # 50 MB

# ── In-memory job registry ────────────────────────────────────────────────────
# Single-process only; fine for the dev/single-worker deployment.
JOBS: dict[str, dict] = {}

router = APIRouter(prefix="/documents", tags=["documents"])


# ── Background ingestion ──────────────────────────────────────────────────────
# FastAPI runs sync BackgroundTask functions in a thread pool, so blocking I/O
# and CPU work here won't stall the event loop.

def _run_ingestion(job_id: str, file_path: Path) -> None:
    try:
        from src.pipeline.indexing_pipeline import IndexingPipeline  # lazy: avoids startup cost
        result = IndexingPipeline().run(file_path)
        chunks = result.get("chunks", 0)
        docs   = result.get("docs", 0)
        JOBS[job_id].update({
            "status":  "done",
            "message": f"Indexed {chunks} chunk(s) from {docs} doc(s).",
        })
        log.info("Ingestion job %s complete: %s", job_id, result)
    except Exception:
        log.error("Ingestion job %s failed", job_id, exc_info=True)
        JOBS[job_id].update({
            "status":  "error",
            "message": "Ingestion failed — check server logs for details.",
        })


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    _: User = Depends(require_admin),
):
    """Accept a PDF / DOCX / TXT file and kick off background ingestion."""
    # Extension check (more reliable than MIME type sent by the client)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: pdf, docx, txt.",
        )

    # Read fully before writing so we can size-check without leaving a partial file
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 50 MB limit.")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Persist to data/raw/{uuid}_{original_filename}
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    job_id    = str(uuid.uuid4())
    safe_name = f"{job_id}_{file.filename}"
    dest_path = RAW_DIR / safe_name
    dest_path.write_bytes(content)

    # Register job and schedule background work
    JOBS[job_id] = {"status": "processing", "filename": file.filename, "message": ""}
    background_tasks.add_task(_run_ingestion, job_id, dest_path)

    return {"job_id": job_id, "status": "processing", "filename": file.filename}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, _: User = Depends(require_admin)):
    """Poll the status of an ingestion job."""
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"job_id": job_id, **job}


@router.get("")
async def list_documents(_: User = Depends(require_admin)):
    """List files currently in data/raw/ (uploaded documents only, not sub-directories)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(RAW_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not f.is_file():
            continue
        stat = f.stat()
        files.append({
            "name":        f.name,
            "size":        stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return files
