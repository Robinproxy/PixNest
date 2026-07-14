import asyncio
import base64
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
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
META_DIR = os.getenv("META_DIR", os.path.join(BASE_DIR, "data"))
META_FILE = os.path.join(META_DIR, "meta.json")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(META_DIR, exist_ok=True)

_FAVICON_ICO = base64.b64decode("AAABAAEAICAAAAEAIACoEAAAFgAAACgAAAAgAAAAQAAAAAEAIAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAj6mbAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAj6mbIo+pm3CPqZutj6mb2o+pm/WPqZv/j6mb9Y+pm9qPqZutj6mbcI+pmyIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAj6mbO4+pm62PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm62PqZs7AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAj6mbAI+pm5OPqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZuTj6mbAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAI+pmyKPqZvIj6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZvIj6mbIgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACPqZsij6mb2o+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZvaj6mbIgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAj6mbAI+pm8iPqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZvIj6mbAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACPqZuTj6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZuTAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAj6mbO4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZs7AAAAAAAAAAAAAAAAAAAAAAAAAACPqZutj6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm60AAAAAAAAAAAAAAAAAAAAAj6mbIo+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pmyIAAAAAAAAAAAAAAACPqZtwj6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mbcAAAAAAAAAAAAAAAAI+pm62PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZutAAAAAAAAAAAAAAAAj6mb2o+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm9oAAAAAAAAAAAAAAACPqZv1j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb9QAAAAAAAAAAj6mbAI+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mbAAAAAAAAAAAAj6mb9Y+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/UAAAAAAAAAAAAAAACPqZvaj6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb2gAAAAAAAAAAAAAAAI+pm62PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZutAAAAAAAAAAAAAAAAj6mbcI+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm3AAAAAAAAAAAAAAAACPqZsij6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mbIgAAAAAAAAAAAAAAAAAAAACPqZutj6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm60AAAAAAAAAAAAAAAAAAAAAAAAAAI+pmzuPqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mbOwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAI+pm5OPqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm5MAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAj6mbAI+pm8iPqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZvIj6mbAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAj6mbIo+pm9qPqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb2o+pmyIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAj6mbIo+pm8iPqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm8iPqZsiAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAj6mbAI+pm5OPqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZuTj6mbAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAI+pmzuPqZutj6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZv/j6mb/4+pm/+PqZutj6mbOwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACPqZsij6mbcI+pm62PqZvaj6mb9Y+pm/+PqZv1j6mb2o+pm62PqZtwj6mbIgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAj6mbAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//9////gA///gAD//gAAP/wAAB/4AAAP8AAAB/AAAAfgAAAD4AAAA8AAAAHAAAABwAAAAcAAAAHAAAABgAAAAMAAAAHAAAABwAAAAcAAAAHAAAAB4AAAA+AAAAPwAAAH8AAAB/gAAA/8AAAf/gAAP/+AAP//4AP///9///////8=")

logger = logging.getLogger("pixnest")

AUTH_TOKEN = os.getenv("AUTH_TOKEN")
if not AUTH_TOKEN:
    logger.warning("AUTH_TOKEN is not set. All authenticated requests will be rejected.")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
ALLOWED_HOSTS = {h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()}
TRUSTED_PROXIES = {ip.strip() for ip in os.getenv("TRUSTED_PROXIES", "").split(",") if ip.strip()}


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

UPLOAD_RATE_LIMIT_WINDOW = 60
UPLOAD_RATE_LIMIT_MAX = 30
_upload_attempts: dict[str, list[float]] = {}

API_RATE_LIMIT_WINDOW = 60
API_RATE_LIMIT_MAX = 60
_api_attempts: dict[str, list[float]] = {}

_RATE_LIMIT_MAX_ENTRIES = 10000


def _get_client_ip(request: Request) -> str:
    client_ip = request.client.host if request.client else "unknown"
    if client_ip not in TRUSTED_PROXIES:
        return client_ip
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return client_ip


def _rate_limit(ip: str, attempts: dict, window: int, limit: int, detail: str) -> None:
    now = time.time()
    recent = [t for t in attempts.get(ip, []) if now - t < window]
    if len(recent) >= limit:
        raise HTTPException(status_code=429, detail=detail, headers={"Retry-After": str(window)})
    recent.append(now)
    attempts[ip] = recent
    if len(attempts) > _RATE_LIMIT_MAX_ENTRIES:
        for k in [k for k, v in attempts.items() if not any(now - t < window for t in v)]:
            del attempts[k]

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


def get_expire_ts(entry: int | float | dict | None) -> float | None:
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
            for attempts, window in (_login_attempts, RATE_LIMIT_WINDOW), (_upload_attempts, UPLOAD_RATE_LIMIT_WINDOW), (_api_attempts, API_RATE_LIMIT_WINDOW):
                for ip in list(attempts):
                    recent = [t for t in attempts[ip] if now - t < window]
                    if recent:
                        attempts[ip] = recent
                    else:
                        del attempts[ip]
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

_CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'none'; "
    "base-uri 'none'; "
    "object-src 'none'; "
    "upgrade-insecure-requests"
)


class CachedStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        if path in ("meta.json",) or path.endswith(".tmp"):
            raise HTTPException(status_code=404)
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


app.mount("/i", CachedStaticFiles(directory=UPLOAD_DIR), name="images")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    if ALLOWED_HOSTS:
        host = request.headers.get("host", "").split(":")[0]
        if host not in ALLOWED_HOSTS:
            return JSONResponse(status_code=400, content={"detail": "Invalid Host header"})
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if PUBLIC_BASE_URL.startswith("https://") or request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = _CSP_POLICY
    return response


_MAX_BODY_BYTES = MAX_UPLOAD_BYTES + 1024 * 1024


@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl:
        try:
            if int(cl) > _MAX_BODY_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Request too large"})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"})
    return await call_next(request)


def require_auth(request: Request, x_auth_token: str | None = Header(None)) -> str:
    if not AUTH_TOKEN or not x_auth_token or not secrets.compare_digest(x_auth_token, AUTH_TOKEN):
        logger.warning("Authentication failed from %s", _get_client_ip(request))
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_auth_token


def require_auth_upload(request: Request, x_auth_token: str | None = Header(None)) -> str:
    if not AUTH_TOKEN or not x_auth_token or not secrets.compare_digest(x_auth_token, AUTH_TOKEN):
        logger.warning("Authentication failed from %s", _get_client_ip(request))
        raise HTTPException(status_code=401, detail="Unauthorized")
    _rate_limit(_get_client_ip(request), _upload_attempts, UPLOAD_RATE_LIMIT_WINDOW, UPLOAD_RATE_LIMIT_MAX, "Too many uploads, try again later")
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
    _rate_limit(ip, _login_attempts, RATE_LIMIT_WINDOW, RATE_LIMIT_MAX, "Too many login attempts, try again later")
    token = request.headers.get("X-Auth-Token")
    if not AUTH_TOKEN or not token or not secrets.compare_digest(token, AUTH_TOKEN):
        logger.warning("Verify failed: invalid token from %s", ip)
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"success": True}


@app.get("/favicon.ico")
async def favicon():
    return HTMLResponse(content=_FAVICON_ICO, media_type="image/x-icon")


@app.post("/upload")
async def upload_image(
    request: Request,
    _: str = Depends(require_auth_upload),
    file: UploadFile = File(...),
    expire_days: int = Form(0),
):
    if expire_days < 0:
        expire_days = 0
    elif expire_days > 365:
        expire_days = 365

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
    except Exception:
        if os.path.isfile(file_path):
            os.remove(file_path)
        raise

    async with _meta_lock:
        meta = load_meta()
        now = time.time()
        entry: dict[str, int | float] = {"size": written, "mtime": now}
        if expire_days > 0:
            entry["expire"] = now + (expire_days * 86400)
        meta[new_filename] = entry
        save_meta(meta)

    base_url = public_base(request)
    logger.info("Uploaded %s (%d bytes) from %s", new_filename, written, _get_client_ip(request))
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
    ip = _get_client_ip(request)
    _rate_limit(ip, _api_attempts, API_RATE_LIMIT_WINDOW, API_RATE_LIMIT_MAX, "Too many requests, try again later")
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
        entry = meta.get(filename)
        size_from_meta = None
        mtime = None
        if isinstance(entry, dict):
            size_from_meta = entry.get("size")
            mtime = entry.get("mtime")
        if mtime is None:
            try:
                stat = os.stat(file_path)
                if size_from_meta is None:
                    size_from_meta = stat.st_size
                mtime = stat.st_mtime
            except OSError:
                continue
        item: dict[str, object] = {
            "filename": filename,
            "url": f"{base_url}i/{filename}",
            "time": mtime,
        }
        if size_from_meta is not None:
            item["size"] = size_from_meta
        expire_at = get_expire_ts(entry)
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
async def delete_image(request: Request, filename: str, _: str = Depends(require_auth)):
    ip = _get_client_ip(request)
    _rate_limit(ip, _api_attempts, API_RATE_LIMIT_WINDOW, API_RATE_LIMIT_MAX, "Too many requests, try again later")
    safe = safe_filename(filename)
    file_path = os.path.join(UPLOAD_DIR, safe)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        os.remove(file_path)
    except FileNotFoundError:
        pass
    async with _meta_lock:
        meta = load_meta()
        if safe in meta:
            del meta[safe]
            save_meta(meta)
    logger.info("Deleted %s from %s", safe, _get_client_ip(request))
    return {"success": True}
