import os
import re
import time
import json
import uuid
import secrets
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
META_FILE = os.path.join(UPLOAD_DIR, "meta.json")
os.makedirs(UPLOAD_DIR, exist_ok=True)

AUTH_TOKEN = os.getenv("AUTH_TOKEN", "123456")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
CLEANUP_INTERVAL_SEC = int(os.getenv("CLEANUP_INTERVAL_SEC", "600"))

ALLOWED_EXT = {"jpg", "jpeg", "png", "gif", "webp", "bmp"}
FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def load_meta() -> dict:
    if not os.path.exists(META_FILE):
        return {}
    try:
        with open(META_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_meta(data: dict) -> None:
    tmp = META_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, META_FILE)


def get_expire_ts(entry) -> Optional[float]:
    if isinstance(entry, (int, float)):
        return float(entry)
    if isinstance(entry, dict) and "expire" in entry:
        return float(entry["expire"])
    return None


def cleanup_expired() -> int:
    meta = load_meta()
    if not meta:
        return 0
    now = time.time()
    removed = 0
    changed = False
    for filename, entry in list(meta.items()):
        expire_at = get_expire_ts(entry)
        if expire_at is None or expire_at > now:
            continue
        path = os.path.join(UPLOAD_DIR, filename)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
        del meta[filename]
        removed += 1
        changed = True
    if changed:
        save_meta(meta)
    return removed


async def cleanup_loop():
    while True:
        try:
            cleanup_expired()
        except Exception:
            pass
        await asyncio.sleep(CLEANUP_INTERVAL_SEC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_expired()
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="PixNest", lifespan=lifespan)


class CachedStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


app.mount("/i", CachedStaticFiles(directory=UPLOAD_DIR), name="images")


def require_auth(x_auth_token: Optional[str] = Header(None)) -> str:
    if not x_auth_token or not secrets.compare_digest(x_auth_token, AUTH_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_auth_token


def public_base(request: Request) -> str:
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL + "/"
    return str(request.base_url)


def safe_filename(name: str) -> str:
    if not name or name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    base = os.path.basename(name)
    if base != name or ".." in base or "/" in base or "\\" in base:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not FILENAME_RE.match(base) or base == "meta.json":
        raise HTTPException(status_code=400, detail="Invalid filename")
    return base


def normalize_ext(filename: Optional[str], content_type: Optional[str]) -> str:
    ext = ""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXT and content_type:
        mapping = {
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
            "image/webp": "webp",
            "image/bmp": "bmp",
        }
        ext = mapping.get(content_type.lower(), ext)
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Unsupported image type")
    return ext


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pixnest"}


@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open(os.path.join(BASE_DIR, "index.html"), "r", encoding="utf-8") as f:
        return f.read()


@app.get("/verify")
async def verify_token(_: str = Depends(require_auth)):
    return {"success": True}


@app.post("/upload")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    expire_days: int = Form(0),
    _: str = Depends(require_auth),
):
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are allowed")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)}MB)",
        )

    ext = normalize_ext(file.filename, file.content_type)
    new_filename = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, new_filename)

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    if expire_days > 0:
        meta = load_meta()
        meta[new_filename] = time.time() + (expire_days * 86400)
        save_meta(meta)

    base_url = public_base(request)
    return JSONResponse(
        content={
            "success": True,
            "url": f"{base_url}i/{new_filename}",
            "filename": new_filename,
            "size": len(content),
        }
    )


@app.get("/api/history")
async def get_history(request: Request, _: str = Depends(require_auth)):
    meta = load_meta()
    files_list = []
    base_url = public_base(request)
    for filename in os.listdir(UPLOAD_DIR):
        if filename == "meta.json" or filename.endswith(".tmp") or filename == ".gitkeep":
            continue
        file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.isfile(file_path):
            continue
        stat = os.stat(file_path)
        expire_at = get_expire_ts(meta.get(filename))
        item = {
            "filename": filename,
            "url": f"{base_url}i/{filename}",
            "time": stat.st_mtime,
        }
        if expire_at is not None:
            item["expire_at"] = expire_at
        files_list.append(item)
    files_list.sort(key=lambda x: x["time"], reverse=True)
    return {"success": True, "images": files_list}


@app.delete("/api/delete/{filename}")
async def delete_image(filename: str, _: str = Depends(require_auth)):
    safe = safe_filename(filename)
    file_path = os.path.join(UPLOAD_DIR, safe)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Not found")
    os.remove(file_path)
    meta = load_meta()
    if safe in meta:
        del meta[safe]
        save_meta(meta)
    return {"success": True}
