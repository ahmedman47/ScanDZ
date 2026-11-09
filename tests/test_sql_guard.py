import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from wathiqa.query.sql_guard import UnsafeSqlError, guard_select

SAFE = [
    "SELECT seller_name, sum(total_ttc) FROM v_invoices GROUP BY 1",
    "select * from v_suppliers order by total_ttc desc",
    "SELECT date_trunc('month', issue_date) m, count(*) FROM v_invoices GROUP BY m ORDER BY m",
    "WITH t AS (SELECT * FROM v_invoices) SELECT count(*) FROM t",
    "SELECT i.invoice_number, l.description FROM v_invoices i JOIN v_invoice_lines l USING (document_id)",
    "SELECT * FROM v_invoices WHERE seller_name ILIKE '%drop table%'",
    "SELECT * FROM v_invoices -- ; DROP TABLE invoices",
    "SELECT 1;",
]

UNSAFE = [
    "DROP TABLE invoices",
    "DELETE FROM invoices",
    "UPDATE invoices SET total_ttc = 0",
    "INSERT INTO invoices DEFAULT VALUES",
    "SELECT * FROM invoices",  # base table, not an allowed view
    "SELECT * FROM documents",
    "SELECT * FROM v_invoices; DROP TABLE invoices",
    "SELECT * FROM public.v_invoices",
    "SELECT * FROM pg_catalog.pg_user",
    "SELECT * FROM information_schema.tables",
    "SELECT pg_sleep(10)",
    "SELECT pg_read_file('/etc/passwd')",
    "SELECT set_config('app.x', '1', false)",
    "SELECT current_setting('server_version')",
    "WITH x AS (DELETE FROM invoices RETURNING *) SELECT * FROM x",
    "SELECT * INTO newtable FROM v_invoices",
    "SELECT * FROM v_invoices FOR UPDATE",
    "SELECT * FROM generate_series(1, 10)",
    "COPY invoices TO '/tmp/x'",
    "CREATE TABLE x (a int)",
    "SELECT * FROM v_invoices UNION SELECT * FROM v_invoices",  # v1 is deliberately strict
    "",
    "not sql at all",
]


@pytest.mark.parametrize("sql", SAFE)
def test_safe_statements_pass_and_get_a_limit(sql: str) -> None:
    out = guard_select(sql)
    assert "LIMIT 200" in out.upper()


@pytest.mark.parametrize("sql", UNSAFE)
def test_unsafe_statements_are_refused(sql: str) -> None:
    with pytest.raises(UnsafeSqlError):
        guard_select(sql)


def test_limit_is_capped_not_raised() -> None:
    assert "LIMIT 200" in guard_select("SELECT * FROM v_invoices LIMIT 100000").upper()
    assert "LIMIT 5" in guard_select("SELECT * FROM v_invoices LIMIT 5").upper()
    assert "LIMIT 50" in guard_select("SELECT * FROM v_invoices", max_rows=50).upper()


@settings(max_examples=300, deadline=None)
@given(st.text(max_size=120))
def test_guard_only_ever_raises_unsafe_sql_error(sql: str) -> None:
    try:
        out = guard_select(sql)
    except UnsafeSqlError:
        return
    assert out.upper().startswith("SELECT")
