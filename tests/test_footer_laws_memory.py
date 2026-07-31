"""Footer IA, Relevant laws, and Memory log (separate calendar)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from constitution_memorizer.progress.memory import (
    MEMORY_INTERVAL_LADDER,
    advance_memory_interval,
)
from constitution_memorizer.web.app import create_app
from constitution_memorizer.web.laws_data import load_laws

MINI_UNITS = Path(__file__).parent / "fixtures" / "learning" / "mini_units.json"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "progress.db"


@pytest.fixture
def client(db_path: Path) -> TestClient:
    return TestClient(create_app(units_path=MINI_UNITS, db_path=db_path))


def test_advance_memory_ladder_stops_at_thirty():
    assert advance_memory_interval(0) == 1
    assert advance_memory_interval(1) == 3
    assert advance_memory_interval(14) == 30
    assert advance_memory_interval(30) is None
    assert MEMORY_INTERVAL_LADDER == (1, 3, 7, 14, 30)


def test_nav_slim_and_footer_has_tools(client: TestClient):
    html = client.get("/").text
    assert 'aria-label="Primary"' in html
    # Top nav: core loop only
    assert ">Tables</a>" not in html.split("aria-label=\"Primary\"")[1].split("</nav>")[0]
    assert ">Settings</a>" not in html.split("aria-label=\"Primary\"")[1].split("</nav>")[0]
    assert "theme-toggle" not in html.split("aria-label=\"Primary\"")[1].split("</nav>")[0]
    # Footer tools
    assert 'aria-label="Tools"' in html
    footer = html.split('aria-label="Tools"')[1].split("</nav>")[0]
    assert "/tables" in footer
    assert "/laws" in footer
    assert "/memory" in footer
    assert "/settings" in footer
    assert 'id="theme-toggle"' in html
    assert "Reference &amp; tools" in html
    assert 'href="/memory"' in html
    assert "styles.css?v=browse1c" in html


def test_constitution_calendar_has_no_memory_chips(client: TestClient):
    html = client.get("/calendar").text
    assert "/memory/" not in html
    assert "Memory log" not in html.split("<main")[1].split("</main>")[0]


def test_laws_list_and_detail(client: TestClient):
    acts = load_laws()
    assert len(acts) >= 7
    listing = client.get("/laws")
    assert listing.status_code == 200
    assert "Relevant laws" in listing.text
    assert "Right to Information Act" in listing.text
    detail = client.get("/laws/rti-2005")
    assert detail.status_code == 200
    assert "s. 3" in detail.text
    assert "Practice all" in detail.text or "not wired" in detail.text.lower()
    assert client.get("/laws/no-such-act").status_code == 404


def test_memory_create_done_notes_photo(client: TestClient, db_path: Path):
    create = client.post(
        "/memory",
        data={"title": "UNESCO sites year-wise", "acronym": "ABCD"},
        follow_redirects=False,
    )
    assert create.status_code == 303
    loc = create.headers["location"]
    assert loc.startswith("/memory/mem-")
    entry_id = loc.rsplit("/", 1)[-1]

    page = client.get(loc)
    assert page.status_code == 200
    assert "UNESCO sites year-wise" in page.text
    assert "ABCD" in page.text
    assert "Add notes" in page.text
    assert "Photo notes" in page.text

    notes = client.post(
        f"/memory/{entry_id}/notes",
        data={"notes": "Palace: first locus is the gate."},
        follow_redirects=False,
    )
    assert notes.status_code == 303
    assert "Palace: first locus" in client.get(loc).text

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND"
        b"\xaeB`\x82"
    )
    upload = client.post(
        f"/memory/{entry_id}/photo",
        files={"photo": ("note.png", BytesIO(png), "image/png")},
        follow_redirects=False,
    )
    assert upload.status_code == 303
    media = client.get(f"/memory/media/{entry_id}")
    assert media.status_code == 200
    assert media.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert media.headers["content-type"].startswith("image/")

    detail = client.get(loc)
    assert detail.status_code == 200
    assert f'/memory/media/{entry_id}' in detail.text
    assert 'alt="Revision notes photo"' in detail.text
    assert "Replace photo" in detail.text

    media_dir = db_path.parent / "memory_media"
    assert media_dir.is_dir()
    assert any(media_dir.glob(f"{entry_id}.*"))

    done = client.post(f"/memory/{entry_id}/done", follow_redirects=False)
    assert done.status_code == 303

    from constitution_memorizer.progress.db import open_progress_db
    from constitution_memorizer.progress.memory import MemoryRepository

    repo = MemoryRepository(open_progress_db(db_path))
    entry = repo.get(entry_id)
    assert entry is not None
    assert entry.interval_days == 3
    assert entry.times_completed == 1
    assert entry.notes.startswith("Palace:")


def test_memory_photo_survives_cwd_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: relative media_dir broke image GETs after process cwd changed."""
    db_path = tmp_path / "progress.db"
    client = TestClient(create_app(units_path=MINI_UNITS, db_path=db_path))
    create = client.post(
        "/memory",
        data={"title": "cwd-safe photo", "acronym": ""},
        follow_redirects=False,
    )
    entry_id = create.headers["location"].rsplit("/", 1)[-1]
    jpeg = b"\xff\xd8\xff\xe0" + b"fake-jpeg"
    assert (
        client.post(
            f"/memory/{entry_id}/photo",
            files={"photo": ("notes.jpg", BytesIO(jpeg), "image/jpeg")},
            follow_redirects=False,
        ).status_code
        == 303
    )

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    media = client.get(f"/memory/media/{entry_id}")
    assert media.status_code == 200
    assert media.content == jpeg
    assert media.headers["content-type"].startswith("image/")

    detail = client.get(f"/memory/{entry_id}")
    assert detail.status_code == 200
    assert f"/memory/media/{entry_id}" in detail.text
    assert "Replace photo" in detail.text


def test_memory_month_page_separate_route(client: TestClient):
    client.post("/memory", data={"title": "Fundamental Duties acronym", "acronym": "FD"})
    page = client.get("/memory")
    assert page.status_code == 200
    assert "Memory log" in page.text
    assert "Revision sheet" in page.text
    assert "Fundamental Duties" in page.text
    assert "/calendar" not in page.text.split("calendar-grid")[0] or True
    # Calendar chips link to /memory/ not /learn/
    assert 'href="/memory/mem-' in page.text
