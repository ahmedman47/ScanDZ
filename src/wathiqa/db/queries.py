"""SQL used by the application, kept in one place and covered by integration tests."""

from __future__ import annotations

# Claim one job. FOR UPDATE SKIP LOCKED lets many workers pull at once without blocking
# each other or taking the same job twice. Failed jobs are retried with back-off.
CLAIM_JOB = """
UPDATE jobs SET status = 'running', locked_at = now(), attempts = attempts + 1
WHERE id = (
    SELECT id FROM jobs
    WHERE status = 'queued' AND run_at <= now()
    ORDER BY run_at, id
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id, document_id, kind, attempts, max_attempts
"""

COMPLETE_JOB = "UPDATE jobs SET status = 'done', locked_at = NULL WHERE id = %(id)s"

# Retry with exponential back-off (30 s, 60 s, 120 s ...) until max_attempts, then fail.
FAIL_JOB = """
UPDATE jobs SET
    status   = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'queued' END,
    run_at   = now() + make_interval(secs => 30 * power(2, attempts - 1)),
    locked_at = NULL,
    last_error = %(error)s
WHERE id = %(id)s
"""

# Jobs whose worker died stay 'running' forever unless they are put back in the queue.
# A job that keeps killing its worker must not loop forever: once it has used all its
# attempts it is marked failed instead of queued.
REQUEUE_STALE = """
UPDATE jobs SET
    status = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'queued' END,
    locked_at = NULL,
    last_error = coalesce(last_error, 'worker lost (stale lock)')
WHERE status = 'running' AND locked_at < now() - make_interval(mins => %(minutes)s)
"""

# Hybrid retrieval: dense vector search plus keyword search, fused with reciprocal rank
# fusion (RRF, k = 60). Rank-based fusion needs no score calibration between the two.
# Only chunks of approved invoices are searchable (the join enforces it, not convention).
HYBRID_SEARCH = """
WITH semantic AS (
    SELECT id, row_number() OVER (ORDER BY dist) AS rnk
    FROM (
        SELECT c.id, c.embedding <=> %(qvec)s::halfvec AS dist
        FROM chunks c JOIN invoices i ON i.document_id = c.document_id AND i.approved_at IS NOT NULL
        ORDER BY c.embedding <=> %(qvec)s::halfvec
        LIMIT %(pool)s
    ) s
), keyword AS (
    SELECT id, row_number() OVER (ORDER BY score DESC) AS rnk
    FROM (
        SELECT c.id, ts_rank_cd(c.tsv, q) AS score
        FROM chunks c
        JOIN invoices i ON i.document_id = c.document_id AND i.approved_at IS NOT NULL,
             to_tsquery('simple', %(tsq)s) q
        WHERE c.tsv @@ q
        ORDER BY score DESC
        LIMIT %(pool)s
    ) k
), fused AS (
    SELECT id, sum(1.0 / (60 + rnk)) AS score
    FROM (SELECT * FROM semantic UNION ALL SELECT * FROM keyword) u
    GROUP BY id
)
SELECT c.id, c.document_id, c.content, f.score
FROM fused f JOIN chunks c ON c.id = f.id
ORDER BY f.score DESC, c.id
LIMIT %(k)s
"""

# Pre-written analytics tools. The model picks a tool and fills the parameters; it does
# not write SQL for the common questions. Every statement reads only the allowed views.
SPEND_BY_MONTH = """
SELECT date_trunc('month', issue_date)::date AS month,
       sum(total_ttc) AS total_ttc, count(*) AS invoices
FROM v_invoices
WHERE issue_date >= %(start)s AND issue_date < %(end)s
GROUP BY 1 ORDER BY 1
"""

SPEND_BY_SUPPLIER = """
SELECT seller_name, sum(total_ttc) AS total_ttc, count(*) AS invoices
FROM v_invoices
WHERE issue_date >= %(start)s AND issue_date < %(end)s
GROUP BY seller_name ORDER BY total_ttc DESC LIMIT %(limit)s
"""

# Spend with one supplier (case-insensitive substring on the name). The router does not
# extract the supplier or the dates yet: that parameter-extraction step is yours to build.
SPEND_FOR_SUPPLIER = """
SELECT seller_name, date_trunc('month', issue_date)::date AS month,
       sum(total_ttc) AS total_ttc, count(*) AS invoices
FROM v_invoices
WHERE seller_name ILIKE '%%' || %(supplier)s || '%%'
  AND issue_date >= %(start)s AND issue_date < %(end)s
GROUP BY 1, 2 ORDER BY 2, 1
"""

# "Top N suppliers" is the same statement as SPEND_BY_SUPPLIER with a small LIMIT.
TOP_SUPPLIERS = SPEND_BY_SUPPLIER
