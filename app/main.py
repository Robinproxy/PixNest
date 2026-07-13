import asyncio
import json
import logging
import os
import re
import secrets
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
META_FILE = os.path.join(UPLOAD_DIR, "meta.json")
os.makedirs(UPLOAD_DIR, exist_ok=True)

logger = logging.getLogger("pixnest")

AUTH_TOKEN = os.getenv("AUTH_TOKEN", "123456")
if AUTH_TOKEN == "123456":
    logger.warning("AUTH_TOKEN is using default value '123456'; set a strong token in production.")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")


def _env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        logger.warning("Invalid %s=%r, using default %d", key, val, default)
        return default


MAX_UPLOAD_BYTES = _env_int("MAX_UPLOAD_MB", 10) * 1024 * 1024
CLEANUP_INTERVAL_SEC = _env_int("CLEANUP_INTERVAL_SEC", 600)

_meta_lock = asyncio.Lock()

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 5
_login_attempts: dict[str, list[float]] = {}


def _get_client_ip(request: Request) -> str:
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    recent = [t for t in attempts if now - t < RATE_LIMIT_WINDOW]
    if len(recent) >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts, try again later",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )
    recent.append(now)
    _login_attempts[ip] = recent

ALLOWED_EXT = {"jpg", "jpeg", "png", "gif", "webp", "bmp"}
FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_image_magic(data: bytes, ext: str) -> None:
    if not data:
        raise HTTPException(status_code=400, detail="Empty file content")
    if ext == "webp":
        if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
            raise HTTPException(status_code=400, detail="File content does not match WEBP format")
        return
    magics = {
        "jpg": (b"\xff\xd8\xff",),
        "jpeg": (b"\xff\xd8\xff",),
        "png": (b"\x89PNG\r\n\x1a\n",),
        "gif": (b"GIF87a", b"GIF89a"),
        "bmp": (b"BM",),
    }
    expected = magics.get(ext)
    if expected is None:
        return
    if not any(data.startswith(m) for m in expected):
        raise HTTPException(status_code=400, detail=f"File content does not match {ext.upper()} format")


def load_meta() -> dict:
    if not os.path.exists(META_FILE):
        return {}
    try:
        with open(META_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_meta(data: dict) -> None:
    tmp = META_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, META_FILE)


def get_expire_ts(entry) -> float | None:
    if isinstance(entry, (int, float)):
        return float(entry)
    if isinstance(entry, dict) and "expire" in entry:
        return float(entry["expire"])
    return None


async def cleanup_expired() -> int:
    async with _meta_lock:
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
                    logger.warning("Failed to remove expired file: %s", filename)
            del meta[filename]
            removed += 1
            changed = True
        if changed:
            save_meta(meta)
    return removed


async def cleanup_loop():
    while True:
        try:
            await cleanup_expired()
            now = time.time()
            for ip in list(_login_attempts):
                recent = [t for t in _login_attempts[ip] if now - t < RATE_LIMIT_WINDOW]
                if recent:
                    _login_attempts[ip] = recent
                else:
                    del _login_attempts[ip]
        except Exception:
            logger.exception("cleanup loop error")
        await asyncio.sleep(CLEANUP_INTERVAL_SEC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await cleanup_expired()
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="PixNest", lifespan=lifespan)

_INDEX_HTML: str = ""
_index_path = os.path.join(BASE_DIR, "index.html")
if os.path.exists(_index_path):
    with open(_index_path, encoding="utf-8") as f:
        _INDEX_HTML = f.read()


class CachedStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


app.mount("/i", CachedStaticFiles(directory=UPLOAD_DIR), name="images")


def require_auth(x_auth_token: str | None = Header(None)) -> str:
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


def normalize_ext(filename: str | None, content_type: str | None) -> str:
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
    return _INDEX_HTML


@app.get("/verify")
async def verify_token(request: Request):
    ip = _get_client_ip(request)
    _check_rate_limit(ip)
    token = request.headers.get("X-Auth-Token")
    if not token or not secrets.compare_digest(token, AUTH_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")
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

    ext = normalize_ext(file.filename, file.content_type)
    new_filename = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, new_filename)

    written = 0
    try:
        with open(file_path, "wb") as buffer:
            first = True
            while chunk := await file.read(1024 * 1024):
                if first:
                    validate_image_magic(chunk, ext)
                    first = False
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)}MB)",
                    )
                buffer.write(chunk)
        if written == 0:
            raise HTTPException(status_code=400, detail="Empty file")
    except HTTPException:
        if os.path.isfile(file_path):
            os.remove(file_path)
        raise
    except Exception:
        if os.path.isfile(file_path):
            os.remove(file_path)
        raise

    if expire_days > 0:
        async with _meta_lock:
            meta = load_meta()
            meta[new_filename] = time.time() + (expire_days * 86400)
            save_meta(meta)

    base_url = public_base(request)
    return JSONResponse(
        content={
            "success": True,
            "url": f"{base_url}i/{new_filename}",
            "filename": new_filename,
            "size": written,
        }
    )


@app.get("/api/history")
async def get_history(
    request: Request,
    page: int = 1,
    size: int = 30,
    _: str = Depends(require_auth),
):
    if page < 1:
        page = 1
    if size < 1 or size > 100:
        size = 30
    meta = load_meta()
    base_url = public_base(request)
    all_files = [
        f for f in os.listdir(UPLOAD_DIR)
        if f != "meta.json" and not f.endswith(".tmp") and f != ".gitkeep"
    ]
    all_files.sort(reverse=True)
    total = len(all_files)
    start = (page - 1) * size
    page_files = all_files[start:start + size]
    images = []
    for filename in page_files:
        file_path = os.path.join(UPLOAD_DIR, filename)
        try:
            stat = os.stat(file_path)
        except OSError:
            continue
        item = {
            "filename": filename,
            "url": f"{base_url}i/{filename}",
            "time": stat.st_mtime,
        }
        expire_at = get_expire_ts(meta.get(filename))
        if expire_at is not None:
            item["expire_at"] = expire_at
        images.append(item)
    return {
        "success": True,
        "images": images,
        "page": page,
        "size": size,
        "total": total,
    }


@app.delete("/api/delete/{filename}")
async def delete_image(filename: str, _: str = Depends(require_auth)):
    safe = safe_filename(filename)
    file_path = os.path.join(UPLOAD_DIR, safe)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Not found")
    os.remove(file_path)
    async with _meta_lock:
        meta = load_meta()
        if safe in meta:
            del meta[safe]
            save_meta(meta)
    return {"success": True}
