"""Create schema on the configured database (SQLite local or Neon via DATABASE_URL)."""

from __future__ import annotations

from apix.db.session import database_backend, database_url, ensure_schema, reset_engine


def main() -> None:
    reset_engine()
    ensure_schema()
    url = database_url()
    safe = url.split("@")[-1] if "@" in url else url
    print(f"schema ready backend={database_backend()} target={safe}")


if __name__ == "__main__":
    main()
