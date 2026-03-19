from __future__ import annotations

from tag_fastmcp.core.database_urls import normalize_database_url


def test_normalize_database_url_strips_jdbc_mysql_query_flags() -> None:
    url = (
        "mysql+aiomysql://user:pass@db.example.com:3306/fits"
        "?allowPublicKeyRetrieval=true&useSSL=false&charset=utf8mb4"
    )

    normalized = normalize_database_url(url)

    assert "allowPublicKeyRetrieval" not in normalized
    assert "useSSL" not in normalized
    assert "charset=utf8mb4" in normalized


def test_normalize_database_url_leaves_other_drivers_unchanged() -> None:
    url = "sqlite+aiosqlite:///data/tag_fastmcp.sqlite3"
    assert normalize_database_url(url) == url
