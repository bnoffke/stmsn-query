import os
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("STMSN_QUERY_LIVE_TEST") != "1",
    reason="Set STMSN_QUERY_LIVE_TEST=1 to run live integration tests",
)


def test_connect_and_show_tables():
    from stmsn_query import connect
    con = connect()
    result = con.sql("SHOW TABLES;").fetchall()
    assert isinstance(result, list)
    assert len(result) > 0


def test_silver_schema_accessible():
    from stmsn_query import connect
    con = connect()
    result = con.sql("SELECT table_name FROM information_schema.tables WHERE table_schema = 'silver';").fetchall()
    assert isinstance(result, list)
