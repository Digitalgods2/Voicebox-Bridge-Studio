"""App pages that share a path with an API GET route still load in the browser."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import config
from backend.app import SPA_PAGES_SHADOWED_BY_API, _mount_frontend

PAGE_LOAD = {"Accept": "text/html", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}


def make_client(tmp_path, monkeypatch) -> TestClient:
    (tmp_path / "index.html").write_text("<!doctype html><title>app</title>", encoding="utf-8")
    monkeypatch.setattr(config, "get_frontend_dir", lambda: tmp_path)
    app = FastAPI()

    @app.get("/stories")
    def list_stories():
        return [{"id": "story"}]

    _mount_frontend(app)
    return TestClient(app)


def test_page_load_of_a_shadowed_path_serves_the_app(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    response = client.get("/stories", headers=PAGE_LOAD)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>app</title>" in response.text


def test_api_requests_to_the_same_path_still_get_json(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    response = client.get("/stories", headers={"Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty"})
    assert response.json() == [{"id": "story"}]
    assert client.get("/stories").json() == [{"id": "story"}]


def test_shadowed_paths_are_app_pages():
    from pathlib import Path

    router = (Path(__file__).resolve().parents[2] / "app" / "src" / "router.tsx").read_text(encoding="utf-8")
    for path in SPA_PAGES_SHADOWED_BY_API:
        assert f"path: '/{path.rsplit('/', 1)[-1]}'" in router, path
