import os
import duckdb

CATALOG_URI = "ducklake:gs://stmsn-meta/catalog/stmsn.ducklake"
KEY_ID_VAR = "STMSN_GCS_KEY_ID"
SECRET_VAR = "STMSN_GCS_SECRET"
DEFAULT_ALIAS = "stmsn"


def _sq(s: str) -> str:
    return s.replace("'", "''")


def _read_creds(
    key_id: str | None = None, secret: str | None = None
) -> tuple[str, str]:
    key_id = key_id or os.environ.get(KEY_ID_VAR)
    secret = secret or os.environ.get(SECRET_VAR)
    if not key_id and not secret:
        raise RuntimeError(
            f"{KEY_ID_VAR} and {SECRET_VAR} are not set and no credentials "
            "were passed to connect(). "
            "See the Credentials section of the README."
        )
    if not key_id:
        raise RuntimeError(
            f"{KEY_ID_VAR} is not set and no key_id was passed to connect(). "
            "See the Credentials section of the README."
        )
    if not secret:
        raise RuntimeError(
            f"{SECRET_VAR} is not set and no secret was passed to connect(). "
            "See the Credentials section of the README."
        )
    return key_id, secret


def build_secret_sql(key_id: str, secret: str) -> str:
    return (
        f"CREATE SECRET (TYPE gcs, KEY_ID '{_sq(key_id)}', SECRET '{_sq(secret)}');"
    )


def connect(
    key_id: str | None = None,
    secret: str | None = None,
    *,
    alias: str = DEFAULT_ALIAS,
) -> duckdb.DuckDBPyConnection:
    key_id, secret = _read_creds(key_id, secret)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("INSTALL ducklake; LOAD ducklake;")
    con.execute(build_secret_sql(key_id, secret))
    con.execute(f"ATTACH '{CATALOG_URI}' AS {alias} (READ_ONLY);")
    con.execute(f"USE {alias};")
    return con
