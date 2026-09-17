from apix.db.session import database_backend, database_url


def test_default_backend_is_sqlite(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Force re-read without mutating global engine in other tests too hard
    assert database_url().startswith("sqlite:///")
    assert database_backend() == "sqlite"


def test_neon_style_url_normalized(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@ep-x.neon.tech/neondb")
    assert database_url().startswith("postgresql+psycopg://")
    assert "ep-x.neon.tech" in database_url()
    assert database_backend() == "postgres"
