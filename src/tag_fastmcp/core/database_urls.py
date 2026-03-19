from __future__ import annotations

from sqlalchemy.engine import URL, make_url


UNSUPPORTED_AIO_MYSQL_QUERY_KEYS = {
    "allowPublicKeyRetrieval",
    "useSSL",
}


def normalize_database_url(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername != "mysql+aiomysql":
        return database_url

    query = {key: value for key, value in url.query.items() if key not in UNSUPPORTED_AIO_MYSQL_QUERY_KEYS}
    normalized: URL = url.set(query=query)
    return normalized.render_as_string(hide_password=False)
