# tests/test_static_serving.py — the single-service catch-all must serve files
# from the frontend build and NOTHING outside it. Regression test for a path
# traversal (SECURITY-AUDIT-2026-07-15): a request like /..%2f..%2fserver/.env
# reaches the handler as "../../server/.env" and, without a containment check,
# FileResponse would happily read it.

from pathlib import Path

from main import _resolve_static_file


def _make_dist(tmp_path: Path) -> Path:
    """A fake build dir with one real asset, plus a secret file OUTSIDE it."""
    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>")
    (tmp_path / "secret.env").write_text("JWT_SECRET=leaked")  # sibling, off-limits
    return dist


def test_serves_a_real_file_inside_dist(tmp_path):
    dist = _make_dist(tmp_path)
    result = _resolve_static_file(dist, "index.html")
    assert result == (dist / "index.html").resolve()


def test_returns_none_for_a_missing_file(tmp_path):
    # Not a real file -> fall back to index.html (handler's job), so None here.
    dist = _make_dist(tmp_path)
    assert _resolve_static_file(dist, "does-not-exist.js") is None


def test_rejects_traversal_escaping_dist(tmp_path):
    # The vulnerability: "../secret.env" resolves to a real file one level up.
    # It must be refused (None), never returned for serving.
    dist = _make_dist(tmp_path)
    assert _resolve_static_file(dist, "../secret.env") is None


def test_rejects_deep_traversal(tmp_path):
    dist = _make_dist(tmp_path)
    assert _resolve_static_file(dist, "../../secret.env") is None
