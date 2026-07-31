---
name: stmsn-query
description: Read-only ad hoc SQL against the Strong Towns Madison civic geospatial lakehouse, via CLI, Python library, or DuckDB web UI.
---

# stmsn-query

Read-only SQL over the stmsn lakehouse. A DuckLake catalog
(`ducklake:gs://stmsn-meta/catalog/stmsn.ducklake`) is attached from GCS as the catalog `stmsn`; queries
hit Parquet in `gs://stmsn-lake/` directly. No data is copied locally.

## Prerequisite

`STMSN_GCS_KEY_ID` and `STMSN_GCS_SECRET` must already be in the environment. If they are not, the CLI
exits 1 and `connect()` raises `RuntimeError`. Do not work around this in code — tell the user to get GCS
HMAC reader keys from the maintainer and set both vars (see the README Credentials section).

## CLI

```
stmsn-query [duckdb-cli-args...]
```

`--skill` (this document) is the only flag the package owns. **Every other argument is forwarded verbatim
to the pinned DuckDB CLI**, so `-c`, `-json`, `-csv`, `-line`, `-ui`, dot-commands and the pager behave
exactly as DuckDB documents them. The catalog is attached and `USE stmsn` applied before your args run.

```bash
stmsn-query -c "SHOW TABLES;"                       # always the first move
stmsn-query -c "DESCRIBE <table>;"                  # columns and types
stmsn-query -c "SELECT ... ;" -json                 # machine-parseable output
stmsn-query                                         # interactive shell
stmsn-query -ui                                     # local web UI, catalog pre-attached
```

Prefer `-c "..." -json` when consuming results programmatically. Bare `stmsn-query` is interactive and
will hang a non-interactive caller.

## Python

```python
from stmsn_query import connect

con = connect()                                # reads the env vars
con = connect(key_id=..., secret=...)          # explicit wins, per-argument

con.sql("SHOW TABLES").fetchall()              # discover before querying
df = con.sql("SELECT * FROM <table> LIMIT 100").df()      # pandas
tbl = con.sql("SELECT * FROM <table>").arrow()            # arrow -> polars etc.
```

`connect()` returns a plain `duckdb.DuckDBPyConnection`, so the whole DuckDB Python API applies.

Streamlit — reconnect once per session, credentials from the platform's secret store:

```python
@st.cache_resource
def get_con():
    return connect(
        key_id=st.secrets["STMSN_GCS_KEY_ID"],
        secret=st.secrets["STMSN_GCS_SECRET"],
    )
```

## Rules

- **Do not guess table names.** Run `SHOW TABLES;`, then `DESCRIBE` what looks relevant. The catalog is
  the only authority on what exists.
- **Layers:** `silver` holds fine-grained records for flexible ad hoc querying — start there when the
  question needs slicing, filtering, or joining at the record level. `gold` holds aggregated facts — use
  it when a pre-aggregated answer already exists.
- **Read-only.** The catalog is attached `READ_ONLY`: no writes, no `CREATE TABLE` in `stmsn`. Put scratch
  tables in the `memory` catalog.
- **The web UI starts in `memory`, not `stmsn`.** In `-ui` cells, fully qualify as `stmsn.<schema>.<table>`
  or run `USE stmsn;` first. The terminal shell and `connect()` are already in `stmsn`.
- **The catalog is replaced daily** by the dbt pipeline. Long-lived sessions (Streamlit, Jupyter, an open
  UI) go stale — call `connect()` again, or restart the shell.
- **`duckdb==1.5.4` is pinned** for catalog storage-version compatibility. Do not install a separate
  `duckdb` alongside this package and do not loosen the pin.
