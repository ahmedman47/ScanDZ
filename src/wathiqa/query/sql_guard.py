"""Defence in depth for any SQL that a language model writes.

Layer 1 (this file): parse and allow-list. Layer 2 (database): a read-only role that can
only see three views, with a short statement timeout. Never rely on only one layer.
"""

from __future__ import annotations

from sqlglot import exp, parse
from sqlglot.errors import SqlglotError

ALLOWED_RELATIONS = frozenset({"v_invoices", "v_invoice_lines", "v_suppliers"})
BLOCKED_FUNCTIONS = frozenset(
    {
        "pg_sleep",
        "pg_read_file",
        "pg_read_binary_file",
        "pg_ls_dir",
        "lo_import",
        "lo_export",
        "dblink",
        "set_config",
        "current_setting",
        "pg_terminate_backend",
        "pg_cancel_backend",
        "pg_advisory_lock",
    }
)
_DANGEROUS_NODES = tuple(
    getattr(exp, name)
    for name in (
        "Insert",
        "Update",
        "Delete",
        "Merge",
        "Create",
        "Drop",
        "Alter",
        "Command",
        "Copy",
    )
    if hasattr(exp, name)
)


class UnsafeSqlError(ValueError):
    """The statement is not a plain, read-only SELECT on allowed views."""


def _function_name(node: exp.Func) -> str:
    name = node.name if isinstance(node, exp.Anonymous) else node.sql_name()
    return name.lower()


def guard_select(
    sql: str, *, allowed: frozenset[str] = ALLOWED_RELATIONS, max_rows: int = 200
) -> str:
    """Return a safe version of ``sql`` (with a LIMIT) or raise ``UnsafeSqlError``."""
    try:
        statements = [s for s in parse(sql, read="postgres") if s is not None]
    except SqlglotError as err:
        raise UnsafeSqlError(f"cannot parse SQL: {err}") from err
    if len(statements) != 1:
        raise UnsafeSqlError("exactly one statement is allowed")
    tree = statements[0]
    if not isinstance(tree, exp.Select):
        raise UnsafeSqlError("only SELECT statements are allowed")
    if tree.args.get("into") or tree.args.get("locks"):
        raise UnsafeSqlError("SELECT INTO and locking clauses are not allowed")
    if any(tree.find_all(*_DANGEROUS_NODES)):
        raise UnsafeSqlError("data-changing statements are not allowed, even inside a CTE")

    ctes = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if table.db or table.catalog:
            raise UnsafeSqlError("schema-qualified names are not allowed")
        if not name:
            raise UnsafeSqlError("table functions are not allowed")
        if name not in allowed and name not in ctes:
            raise UnsafeSqlError(f"relation {name!r} is not allowed")
    for func in tree.find_all(exp.Func):
        if _function_name(func) in BLOCKED_FUNCTIONS:
            raise UnsafeSqlError(f"function {_function_name(func)!r} is not allowed")

    limit = tree.args.get("limit")
    if limit is None:
        tree = tree.limit(max_rows)
    else:
        try:
            requested = int(limit.expression.name)
        except ValueError as err:
            raise UnsafeSqlError("LIMIT must be a number") from err
        if requested > max_rows:
            tree = tree.limit(max_rows)
    return tree.sql(dialect="postgres")
