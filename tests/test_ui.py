"""Unit and integration tests for the RouteFlow Control Center Frontend UI serving.

Verifies:
- Root redirect / -> /ui/
- Serving of index.html at /ui/
- Serving of stylesheet at /ui/styles/styles.css
- Serving of JS modular scripts (app.js, api.js, components.js)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_redirects_to_ui(client: AsyncClient) -> None:
    """Requesting the root URL / should return a RedirectResponse to /ui/."""
    # follow_redirects=False to verify the redirect header itself
    response = await client.get("/")
    assert response.status_code == 307
    assert response.headers["location"] == "/ui/"


@pytest.mark.asyncio
async def test_ui_index_html_loads(client: AsyncClient) -> None:
    """Requesting /ui/ should successfully serve the index.html page."""
    response = await client.get("/ui/")
    assert response.status_code == 200
    assert "RouteFlow Server" in response.text
    assert "app.js" in response.text


@pytest.mark.asyncio
async def test_ui_styles_loads(client: AsyncClient) -> None:
    """Requesting /ui/styles/styles.css should serve the stylesheet with correct CSS content."""
    response = await client.get("/ui/styles/styles.css")
    assert response.status_code == 200
    assert "accent-orange" in response.text


@pytest.mark.asyncio
async def test_ui_javascript_modules_load(client: AsyncClient) -> None:
    """Requesting the JS ES module files should return 200 OK."""
    js_files = ["app.js", "api.js", "components.js"]
    for file_name in js_files:
        response = await client.get(f"/ui/js/{file_name}")
        assert response.status_code == 200
        assert "export" in response.text or "import" in response.text or "DOM" in response.text
