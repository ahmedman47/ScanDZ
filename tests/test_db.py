"""Integration tests against a real PostgreSQL (embedded, with pgvector)."""

from __future__ import annotations

import pathlib
import shutil
import tempfile
import uuid
from collections.abc import Iterator
from datetime import date

import numpy as np
import psycopg
import pytest
from psycopg import errors

from wathiqa.db import queries
from wathiqa.domain.normalize import build_or_tsquery, normalize_text

pgserver = pytest.importorskip("pixeltable_pgserver")
SCHEMA = (pathlib.Path(__file__).parents[1] / "src/wathiqa/db/schema.sql").read_text()
ROLES = (pathlib.Path(__file__).parents[1] / "src/wathiqa/db/roles.sql").read_text()
DIM = 1024


def vec(seed: int) -> list[float]:
    v = np.random.default_rng(seed).normal(size=DIM)
    return (v / np.linalg.norm(v)).tolist()


@pytest.fixture(scope="module")
def uri() -> Iterator[str]:
    root = pathlib.Path(tempfile.mkdtemp(prefix="wathiqa-pg-"))
    server = pgserver.get_server(root / "data", cleanup_mode="delete")
    yield server.get_uri()
    server.cleanup()
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(scope="module")
def conn(uri: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(uri, autocommit=True) as c:
        c.execute(SCHEMA)
        c.execute(ROLES.replace("CHANGE_ME", "test-only"))
        yield c


def new_doc(conn: psycopg.Connection, name: str = "f.pdf") -> uuid.UUID:
    row = conn.execute(
        "INSERT INTO documents (sha256, filename, mime_type, page_count) VALUES (%s, %s, 'application/pdf', 1) RETURNING id",
        (uuid.uuid4().hex + uuid.uuid4().hex, name),
    ).fetchone()
    assert row is not None
    return row[0]  # type: ignore[no-any-return]


def add_invoice(
    conn: psycopg.Connection, nif: str | None, number: str, ttc: float, approved: bool = True
) -> uuid.UUID:
    doc = new_doc(conn)
    conn.execute(
        """INSERT INTO invoices (document_id, invoice_number, issue_date, seller_name, seller_nif, total_ttc, approved_at)
           VALUES (%s, %s, %s, 'Sonelgaz', %s, %s, CASE WHEN %s THEN now() END)""",
        (doc, number, date(2026, 3, 5), nif, ttc, approved),
    )
    return doc


def test_schema_applies_and_has_the_extension(conn: psycopg.Connection) -> None:
    tables = {
        r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    }
    assert {
        "documents",
        "ocr_pages",
        "extractions",
        "invoices",
        "invoice_lines",
        "review_events",
        "chunks",
        "jobs",
    } <= tables
    assert (
        conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
        is not None
    )


def test_same_file_cannot_be_uploaded_twice(conn: psycopg.Connection) -> None:
    sha = "a" * 64
    conn.execute(
        "INSERT INTO documents (sha256, filename, mime_type, page_count) VALUES (%s, 'a', 'x', 1)",
        (sha,),
    )
    with pytest.raises(errors.UniqueViolation):
        conn.execute(
            "INSERT INTO documents (sha256, filename, mime_type, page_count) VALUES (%s, 'b', 'x', 1)",
            (sha,),
        )


def test_business_key_blocks_duplicate_approved_invoices_only(conn: psycopg.Connection) -> None:
    add_invoice(conn, "002016001234567", "DUP-1", 100)
    with pytest.raises(errors.UniqueViolation):
        add_invoice(conn, "002016001234567", "DUP-1", 100)
    add_invoice(conn, "002016001234567", "DUP-1", 100, approved=False)  # drafts may repeat
    add_invoice(conn, None, "DUP-1", 100)  # unknown NIF is not a business key


def test_cannot_approve_an_invoice_without_total_and_date(conn: psycopg.Connection) -> None:
    doc = new_doc(conn)
    with pytest.raises(errors.CheckViolation):
        conn.execute("INSERT INTO invoices (document_id, approved_at) VALUES (%s, now())", (doc,))


def test_job_queue_skip_locked_gives_each_worker_a_different_job(
    uri: str, conn: psycopg.Connection
) -> None:
    conn.execute("DELETE FROM jobs")
    doc = new_doc(conn)
    for _ in range(3):
        conn.execute("INSERT INTO jobs (document_id, kind) VALUES (%s, 'process')", (doc,))
    with psycopg.connect(uri) as w1, psycopg.connect(uri) as w2:
        a = w1.execute(queries.CLAIM_JOB).fetchone()  # transaction stays open: row stays locked
        b = w2.execute(queries.CLAIM_JOB).fetchone()
        assert a is not None and b is not None and a[0] != b[0]
        w1.commit()
        w2.commit()
    assert conn.execute("SELECT count(*) FROM jobs WHERE status = 'running'").fetchone() == (2,)


def test_failed_job_backs_off_then_fails_for_good(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM jobs")
    doc = new_doc(conn)
    conn.execute(
        "INSERT INTO jobs (document_id, kind, max_attempts) VALUES (%s, 'process', 2)", (doc,)
    )
    job = conn.execute(queries.CLAIM_JOB).fetchone()
    assert job is not None
    conn.execute(queries.FAIL_JOB, {"id": job[0], "error": "boom"})
    status, delay = conn.execute(
        "SELECT status, extract(epoch FROM run_at - now()) FROM jobs"
    ).fetchone()  # type: ignore[misc]
    assert status == "queued" and 20 < delay <= 30
    assert conn.execute(queries.CLAIM_JOB).fetchone() is None  # not due yet
    conn.execute("UPDATE jobs SET run_at = now()")
    job = conn.execute(queries.CLAIM_JOB).fetchone()
    assert job is not None and job[3] == 2
    conn.execute(queries.FAIL_JOB, {"id": job[0], "error": "boom again"})
    assert conn.execute("SELECT status, last_error FROM jobs").fetchone() == (
        "failed",
        "boom again",
    )


def test_stale_running_jobs_are_requeued(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM jobs")
    doc = new_doc(conn)
    conn.execute(
        "INSERT INTO jobs (document_id, kind, status, locked_at) VALUES (%s, 'process', 'running', now() - interval '20 minutes')",
        (doc,),
    )
    conn.execute(queries.REQUEUE_STALE, {"minutes": 10})
    assert conn.execute("SELECT status FROM jobs").fetchone() == ("queued",)


def test_a_job_that_keeps_killing_its_worker_ends_as_failed(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM jobs")
    doc = new_doc(conn)
    conn.execute(
        "INSERT INTO jobs (document_id, kind, status, attempts, max_attempts, locked_at) "
        "VALUES (%s, 'process', 'running', 3, 3, now() - interval '20 minutes')",
        (doc,),
    )
    conn.execute(queries.REQUEUE_STALE, {"minutes": 10})
    status, error = conn.execute("SELECT status, last_error FROM jobs").fetchone()  # type: ignore[misc]
    assert status == "failed" and "stale" in error
    assert conn.execute(queries.CLAIM_JOB).fetchone() is None


def approve(conn: psycopg.Connection, doc: uuid.UUID) -> None:
    conn.execute(
        "INSERT INTO invoices (document_id, issue_date, total_ttc, approved_at) "
        "VALUES (%s, '2026-03-05', 1, now())",
        (doc,),
    )


def add_chunk(conn: psycopg.Connection, doc: uuid.UUID, text: str, embedding: list[float]) -> int:
    row = conn.execute(
        "INSERT INTO chunks (document_id, kind, content, content_norm, embedding) VALUES (%s, 'ocr', %s, %s, %s::halfvec) RETURNING id",
        (doc, text, normalize_text(text), str(embedding)),
    ).fetchone()
    assert row is not None
    return row[0]  # type: ignore[no-any-return]


def test_hybrid_search_fuses_semantic_and_keyword_rankings(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM chunks")
    doc = new_doc(conn)
    approve(conn, doc)
    q = np.array(vec(1))
    close = (q + 0.05 * np.array(vec(2))).tolist()  # near the query vector, no keyword
    both = (q + 0.30 * np.array(vec(3))).tolist()  # somewhat near, and has the keyword
    only_kw = vec(4)  # far in vector space, has the keyword
    noise = [add_chunk(conn, doc, f"bruit {i}", vec(100 + i)) for i in range(20)]
    c_close = add_chunk(conn, doc, "facture papier", close)
    c_both = add_chunk(conn, doc, "Facture Sonelgaz mars électricité", both)
    c_kw = add_chunk(conn, doc, "Sonelgaz", only_kw)

    params = {
        "qvec": str(q.tolist()),
        "tsq": build_or_tsquery("Sonelgaz électricité"),
        "pool": 10,
        "k": 5,
    }
    rows = conn.execute(queries.HYBRID_SEARCH, params).fetchall()
    ids = [r[0] for r in rows]
    assert ids[0] == c_both, "a chunk found by both rankings must beat chunks found by one"
    assert {c_close, c_kw} <= set(ids[:3])
    assert not set(ids) & set(noise[:5]) or len(ids) == 5
    scores = [float(r[3]) for r in rows]
    assert scores == sorted(scores, reverse=True)


def test_arabic_keyword_search_works_after_python_normalisation(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM chunks")
    doc = new_doc(conn)
    approve(conn, doc)
    add_chunk(conn, doc, "فاتورة مورد: مؤسسة النور للتجارة", vec(7))
    add_chunk(conn, doc, "autre document sans rapport", vec(8))
    params = {"qvec": str(vec(9)), "tsq": build_or_tsquery("مؤسسه النور"), "pool": 5, "k": 3}
    top = conn.execute(queries.HYBRID_SEARCH, params).fetchall()[0]
    assert "النور" in top[2]


def test_read_only_role_sees_only_the_views(conn: psycopg.Connection) -> None:
    add_invoice(conn, "002016001234999", "RO-1", 500)
    conn.execute("SET ROLE wathiqa_ro")
    try:
        assert conn.execute("SELECT count(*) FROM v_invoices").fetchone() is not None
        for sql in ("SELECT * FROM invoices", "SELECT * FROM documents", "SELECT * FROM chunks"):
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute(sql)
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute("DELETE FROM v_invoices")
    finally:
        conn.execute("RESET ROLE")


def test_views_hide_unapproved_invoices(conn: psycopg.Connection) -> None:
    add_invoice(conn, "002016001234888", "DRAFT-1", 9999, approved=False)
    assert conn.execute(
        "SELECT count(*) FROM v_invoices WHERE invoice_number = 'DRAFT-1'"
    ).fetchone() == (0,)


def test_role_defaults_apply_to_the_login_role_not_to_set_role(
    uri: str, conn: psycopg.Connection
) -> None:
    conn.execute("SET ROLE wathiqa_ro")
    via_set_role = conn.execute("SHOW statement_timeout").fetchone()
    conn.execute("RESET ROLE")
    assert via_set_role == ("0",)  # no timeout: ALTER ROLE defaults were NOT applied
    with psycopg.connect(uri, user="wathiqa_app_ro") as ro:
        assert ro.execute("SHOW statement_timeout").fetchone() == ("3s",)
        assert ro.execute("SHOW default_transaction_read_only").fetchone() == ("on",)
        with pytest.raises(errors.QueryCanceled):
            ro.execute("SELECT pg_sleep(5)")


def test_analytics_tools_run_against_the_views(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM invoice_lines")
    conn.execute("DELETE FROM invoices")
    add_invoice(conn, "002016001230001", "A-1", 1000)
    add_invoice(conn, "002016001230001", "A-2", 500)
    rows = conn.execute(
        queries.SPEND_BY_MONTH, {"start": date(2026, 1, 1), "end": date(2027, 1, 1)}
    ).fetchall()
    assert rows == [(date(2026, 3, 1), 1500, 2)]
    by_supplier = conn.execute(
        queries.SPEND_BY_SUPPLIER, {"start": date(2026, 1, 1), "end": date(2027, 1, 1), "limit": 5}
    ).fetchall()
    assert by_supplier == [("Sonelgaz", 1500, 2)]


def test_chunks_of_unapproved_documents_are_not_searchable(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM chunks")
    draft = new_doc(conn)  # never approved
    add_chunk(conn, draft, "secret draft Sonelgaz", vec(21))
    good = new_doc(conn)
    approve(conn, good)
    kept = add_chunk(conn, good, "Sonelgaz approved", vec(22))
    params = {"qvec": str(vec(21)), "tsq": build_or_tsquery("Sonelgaz"), "pool": 10, "k": 5}
    assert [r[0] for r in conn.execute(queries.HYBRID_SEARCH, params).fetchall()] == [kept]


def test_supplier_filter_and_top_suppliers(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM invoice_lines")
    conn.execute("DELETE FROM invoices")
    add_invoice(conn, "002016001230001", "S-1", 1000)
    add_invoice(conn, "002016001230001", "S-2", 500)
    rng = {"start": date(2026, 1, 1), "end": date(2027, 1, 1)}
    rows = conn.execute(queries.SPEND_FOR_SUPPLIER, {"supplier": "sonel", **rng}).fetchall()
    assert rows == [("Sonelgaz", date(2026, 3, 1), 1500, 2)]
    assert conn.execute(queries.SPEND_FOR_SUPPLIER, {"supplier": "nobody", **rng}).fetchall() == []
    assert conn.execute(queries.TOP_SUPPLIERS, {**rng, "limit": 3}).fetchall() == [
        ("Sonelgaz", 1500, 2)
    ]
