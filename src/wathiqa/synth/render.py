"""Render an invoice to HTML, then to PDF and PNG with headless Chromium."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from wathiqa.domain.contract import Invoice
from wathiqa.synth.formatting import format_amount, format_date, format_quantity
from wathiqa.synth.generate import CATALOGUE, Style

TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "j2"], default_for_string=True),
    undefined=StrictUndefined,
)
_AR_BY_FR = {fr: ar for fr, ar, _ in CATALOGUE}


def render_html(invoice: Invoice, style: Style) -> str:
    unit = "دج" if style.template == "bilingual" else "DA"
    context = {
        "inv": invoice,
        "css": (TEMPLATE_DIR / "base.css").read_text(encoding="utf-8"),
        "unit": unit,
        "amt": lambda v: format_amount(v, style.numbers),
        "qty": lambda v: format_quantity(v, style.numbers),
        "dt": lambda v: format_date(v, style.dates),
        "pct": lambda v: f"{int(v)} %",
        "ar_desc": [_AR_BY_FR.get(line.description or "", "") for line in invoice.lines],
    }
    return _env.get_template(f"invoice_{style.template}.html.j2").render(**context)


def write_ground_truth(path: Path, invoice: Invoice, meta: dict[str, object]) -> None:
    payload = {"invoice": invoice.model_dump(mode="json"), "meta": meta}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def html_to_files(htmls: dict[str, str], out_dir: Path, *, scale: float = 2.0) -> None:
    """Write ``<name>.pdf`` and ``<name>.png`` for every ``name -> html`` (one browser)."""
    from playwright.sync_api import sync_playwright  # imported late: optional dependency

    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 794, "height": 1123}, device_scale_factor=scale)
        for name, html in htmls.items():
            page.set_content(html, wait_until="load")
            page.evaluate("document.fonts.ready")
            page.pdf(path=str(out_dir / f"{name}.pdf"), format="A4", print_background=True)
            page.screenshot(path=str(out_dir / f"{name}.png"), full_page=True)
        browser.close()
