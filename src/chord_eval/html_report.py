"""Offline viewer export with JSON-safe embedding and no network dependencies."""

import json
from importlib.resources import files

from .models import AnnotationError


def render_html(report: dict) -> str:
    if report.get("kind") not in ("pair", "collection") or report.get("schema_version") != "1.1":
        raise AnnotationError("HTML export requires a toolkit schema 1.1 report")
    payload = json.dumps(report, ensure_ascii=True, allow_nan=False)
    # An input filename/description must not close the data script element.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = files("chord_eval").joinpath("viewer.html").read_text(encoding="utf-8")
    return template.replace("__REPORT_DATA__", payload)
