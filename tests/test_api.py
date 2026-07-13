import json
import time

import pytest
from fastapi.testclient import TestClient

TEST_TOKEN = "test-token"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _png_bytes(size: int = 200) -> bytes:
    return PNG_MAGIC + b"\x00" * size


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr("app.main.UPLOAD_DIR", str(upload_dir))
    monkeypatch.setattr("app.main.META_FILE", str(upload_dir / "meta.json"))
    monkeypatch.setattr("app.main.AUTH_TOKEN", TEST_TOKEN)
    monkeypatch.setattr("app.main.MAX_UPLOAD_BYTES", 1024 * 1024)
    from app.main import _login_attempts
    _login_attempts.clear()


@pytest.fixture
def client(setup):
    from app.main import app
    with TestClient(app) as c:
        yield c


def auth():
    return {"X-Auth-Token": TEST_TOKEN}


class TestHealth:
    def test_health(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


class TestVerify:
    def test_no_token(self, client):
        res = client.get("/verify")
        assert res.status_code == 401

    def test_wrong_token(self, client):
        res = client.get("/verify", headers={"X-Auth-Token": "wrong"})
        assert res.status_code == 401

    def test_ok(self, client):
        res = client.get("/verify", headers=auth())
        assert res.status_code == 200

    def test_rate_limit(self, client):
        for _ in range(5):
            res = client.get("/verify", headers={"X-Auth-Token": "wrong"})
            assert res.status_code == 401
        res = client.get("/verify", headers=auth())
        assert res.status_code == 429


class TestUpload:
    def test_valid_png(self, client):
        res = client.post(
            "/upload",
            files={"file": ("test.png", _png_bytes(), "image/png")},
            headers=auth(),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["filename"].endswith(".png")
        assert data["size"] > 0
        assert "/i/" in data["url"]

    def test_empty(self, client):
        res = client.post(
            "/upload",
            files={"file": ("test.png", b"", "image/png")},
            headers=auth(),
        )
        assert res.status_code == 400
        assert "Empty" in res.json()["detail"]

    def test_wrong_magic(self, client):
        res = client.post(
            "/upload",
            files={"file": ("fake.jpg", b"<html>notanimage</html>", "image/jpeg")},
            headers=auth(),
        )
        assert res.status_code == 400

    def test_too_large(self, client):
        data = _png_bytes(2 * 1024 * 1024)
        res = client.post(
            "/upload",
            files={"file": ("large.png", data, "image/png")},
            headers=auth(),
        )
        assert res.status_code == 413

    def test_no_auth(self, client):
        res = client.post(
            "/upload",
            files={"file": ("test.png", _png_bytes(), "image/png")},
        )
        assert res.status_code == 401


class TestHistory:
    def test_empty(self, client):
        res = client.get("/api/history", headers=auth())
        assert res.status_code == 200
        assert res.json()["images"] == []

    def test_after_upload(self, client):
        client.post(
            "/upload",
            files={"file": ("test.png", _png_bytes(), "image/png")},
            headers=auth(),
        )
        res = client.get("/api/history", headers=auth())
        assert res.status_code == 200
        data = res.json()
        assert len(data["images"]) == 1
        img = data["images"][0]
        assert img["filename"].endswith(".png")
        assert "time" in img
        assert img["size"] == 208

    def test_pagination(self, client):
        for i in range(5):
            client.post(
                "/upload",
                files={"file": (f"test{i}.png", _png_bytes(), "image/png")},
                headers=auth(),
            )
        res = client.get("/api/history?page=1&size=2", headers=auth())
        assert len(res.json()["images"]) == 2
        assert res.json()["total"] == 5

    def test_old_file_fallback(self, client, tmp_path):
        upload_dir = tmp_path / "uploads"
        old_file = upload_dir / "old_image.png"
        old_file.write_bytes(_png_bytes())
        res = client.get("/api/history", headers=auth())
        assert res.status_code == 200
        data = res.json()
        assert len(data["images"]) == 1
        assert data["images"][0]["filename"] == "old_image.png"
        assert data["images"][0]["size"] == 208


class TestDelete:
    def test_not_found(self, client):
        res = client.delete("/api/delete/nonexistent.png", headers=auth())
        assert res.status_code == 404

    def test_ok(self, client):
        up = client.post(
            "/upload",
            files={"file": ("test.png", _png_bytes(), "image/png")},
            headers=auth(),
        )
        filename = up.json()["filename"]
        res = client.delete(f"/api/delete/{filename}", headers=auth())
        assert res.status_code == 200
        res = client.get("/api/history", headers=auth())
        assert res.json()["images"] == []

    def test_no_auth(self, client):
        res = client.delete("/api/delete/any.png")
        assert res.status_code == 401


class TestCleanup:
    def test_cleanup_expired(self, client, tmp_path):
        up = client.post(
            "/upload",
            files={"file": ("test.png", _png_bytes(), "image/png")},
            data={"expire_days": "1"},
            headers=auth(),
        )
        assert up.status_code == 200
        filename = up.json()["filename"]
        meta_file = tmp_path / "uploads" / "meta.json"
        meta = json.loads(meta_file.read_text())
        meta[filename]["expire"] = time.time() - 3600
        meta_file.write_text(json.dumps(meta))
        import asyncio

        from app.main import cleanup_expired
        removed = asyncio.run(cleanup_expired())
        assert removed == 1
        res = client.get("/api/history", headers=auth())
        assert not any(f["filename"] == filename for f in res.json()["images"])
