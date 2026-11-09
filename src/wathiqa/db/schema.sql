-- Wathiqa reference schema (PostgreSQL 16+ with pgvector 0.7+).
-- Single-tenant by design: one deployment serves one organisation.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sha256      char(64) NOT NULL UNIQUE,              -- idempotent upload: same bytes, same row
    filename    text NOT NULL,
    mime_type   text NOT NULL,
    page_count  int  NOT NULL CHECK (page_count > 0),
    status      text NOT NULL DEFAULT 'uploaded'
                CHECK (status IN ('uploaded','processing','needs_review','approved','rejected','failed')),
    source      text NOT NULL DEFAULT 'upload',        -- upload | synthetic | public_dataset
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ocr_pages (
    document_id    uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no        int  NOT NULL,
    engine         text NOT NULL,                       -- e.g. tesseract, paddleocr
    engine_version text NOT NULL,
    text           text NOT NULL,
    mean_conf      real CHECK (mean_conf BETWEEN 0 AND 1),
    created_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, page_no, engine)
);

CREATE TABLE extractions (                              -- immutable log of every model attempt
    id             bigserial PRIMARY KEY,
    document_id    uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    prompt_version text NOT NULL,
    model          text NOT NULL,
    raw            jsonb NOT NULL,                      -- RawInvoice as returned by the model
    confidence     real NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    issues         jsonb NOT NULL DEFAULT '[]',
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE invoices (                                 -- the current, human-approved truth
    document_id   uuid PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    extraction_id bigint REFERENCES extractions(id),
    doc_type      text NOT NULL DEFAULT 'invoice',
    invoice_number text,
    issue_date    date,
    due_date      date,
    currency      char(3) NOT NULL DEFAULT 'DZD',
    seller_name   text,
    seller_nif    text,
    buyer_name    text,
    buyer_nif     text,
    total_ht      numeric(14,2),
    vat_rate      numeric(5,2),
    vat_amount    numeric(14,2),
    timbre        numeric(14,2),
    total_ttc     numeric(14,2),
    approved_by   text,
    approved_at   timestamptz,
    CHECK (approved_at IS NULL OR (total_ttc IS NOT NULL AND issue_date IS NOT NULL))
);
-- Business-level duplicate detection: same supplier and same number is the same invoice.
CREATE UNIQUE INDEX invoices_business_key
    ON invoices (seller_nif, invoice_number)
    WHERE seller_nif IS NOT NULL AND invoice_number IS NOT NULL AND approved_at IS NOT NULL;
CREATE INDEX invoices_date_idx ON invoices (issue_date) WHERE approved_at IS NOT NULL;

CREATE TABLE invoice_lines (
    document_id   uuid   NOT NULL REFERENCES invoices(document_id) ON DELETE CASCADE,
    line_no       int    NOT NULL,
    description   text,
    quantity      numeric(14,3),
    unit_price_ht numeric(14,2),
    vat_rate      numeric(5,2),
    total_ht      numeric(14,2),
    PRIMARY KEY (document_id, line_no)
);

CREATE TABLE review_events (                            -- audit trail and source of gold labels
    id          bigserial PRIMARY KEY,
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    actor       text NOT NULL,
    action      text NOT NULL CHECK (action IN ('edit','approve','reject','reopen')),
    field       text,
    old_value   text,
    new_value   text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id          bigserial PRIMARY KEY,
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('ocr','invoice')),
    content     text NOT NULL,
    content_norm text NOT NULL,                         -- normalize_text(content), done in Python
    embedding   halfvec(1024) NOT NULL,                 -- bge-m3 dense vector
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('simple', content_norm)) STORED,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding halfvec_cosine_ops);
CREATE INDEX chunks_tsv_gin ON chunks USING gin (tsv);

CREATE TABLE jobs (                                     -- a queue in PostgreSQL: no extra service
    id           bigserial PRIMARY KEY,
    document_id  uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    kind         text NOT NULL CHECK (kind IN ('process','embed')),
    status       text NOT NULL DEFAULT 'queued'
                 CHECK (status IN ('queued','running','done','failed')),
    attempts     int  NOT NULL DEFAULT 0,
    max_attempts int  NOT NULL DEFAULT 3,
    run_at       timestamptz NOT NULL DEFAULT now(),
    locked_at    timestamptz,
    last_error   text,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX jobs_ready_idx ON jobs (run_at) WHERE status = 'queued';

-- ---------------------------------------------------------------- read-only surface
-- The text-to-SQL path may only ever read these three views, never the base tables.
CREATE VIEW v_invoices AS
    SELECT document_id, doc_type, invoice_number, issue_date, currency,
           seller_name, buyer_name, total_ht, vat_amount, total_ttc
    FROM invoices WHERE approved_at IS NOT NULL;

CREATE VIEW v_invoice_lines AS
    SELECT l.document_id, l.line_no, l.description, l.quantity, l.unit_price_ht, l.total_ht
    FROM invoice_lines l JOIN invoices i USING (document_id) WHERE i.approved_at IS NOT NULL;

CREATE VIEW v_suppliers AS
    SELECT seller_name, seller_nif, count(*) AS invoice_count, sum(total_ttc) AS total_ttc,
           min(issue_date) AS first_invoice, max(issue_date) AS last_invoice
    FROM invoices WHERE approved_at IS NOT NULL GROUP BY seller_name, seller_nif;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'wathiqa_ro') THEN
        CREATE ROLE wathiqa_ro NOLOGIN;
    END IF;
END $$;
GRANT SELECT ON v_invoices, v_invoice_lines, v_suppliers TO wathiqa_ro;
-- wathiqa_ro is a group role. Create a LOGIN role that is a member of it (see roles.sql);
-- ALTER ROLE ... SET defaults only apply to the role you log in as, not to SET ROLE.
