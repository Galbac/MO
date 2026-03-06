from pathlib import Path


def test_public_and_admin_templates_exist() -> None:
    templates_dir = Path("source/web/templates")

    assert (templates_dir / "public" / "index.html").exists()
    assert (templates_dir / "public" / "match-detail.html").exists()
    assert (templates_dir / "admin" / "dashboard.html").exists()
    assert (templates_dir / "admin" / "match-detail.html").exists()
